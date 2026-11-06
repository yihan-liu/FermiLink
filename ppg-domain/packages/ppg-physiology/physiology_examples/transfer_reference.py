"""Beat feet and physical-time beat ensembles.

Feet are local waveform minima before a prominent systolic upstroke, not
maximum-derivative timestamps. Detection uses the same fixed rule for
observations and predictions.
No beat is stretched or resampled to a normalized cardiac phase.
"""
import numpy as np
from scipy.signal import find_peaks, butter, sosfiltfilt

FOOT_METHOD = "10 Hz zero-phase smoothed local minimum within 250 ms before maximum systolic upstroke"


def feet(x, fs_hz):
    """Return sub-sample local-minimum times in seconds relative to record start.

    Prominent peaks are separated by >=0.35 s, with prominence >=15% of the
    window's 5th-to-95th percentile range. A zero-phase second-order 10 Hz
    Butterworth smooths detection only. For each peak, find maximum upstroke
    since the previous peak (at most 0.8 s), then the last local minimum in
    the preceding 250 ms, after the previous accepted foot. Reject absent
    local minima. A three-point parabolic minimum supplies sub-sample timing.
    """
    x = np.asarray(x, float)
    finite = np.flatnonzero(np.isfinite(x))
    if len(finite) < 5:
        return np.array([])
    lo, hi = finite[0], finite[-1] + 1
    v = x[lo:hi]
    if not np.isfinite(v).all():
        raise ValueError("Interior waveform gaps invalidate foot detection")
    v = sosfiltfilt(butter(2, 10., fs=fs_hz, output="sos"), v)
    scale = np.percentile(v, 95) - np.percentile(v, 5)
    if scale <= 0:
        return np.array([])
    peaks, _ = find_peaks(v, distance=max(1, int(.35 * fs_hz)),
                         prominence=.15 * scale)
    minima, _ = find_peaks(-v)
    out = []
    for j, peak in enumerate(peaks):
        left = max(peaks[j-1] if j else 0, peak-int(.8*fs_hz))
        if peak-left < 3:
            continue
        up = left + int(np.argmax(np.diff(v[left:peak+1])))
        foot_left = max(left, up-int(.25*fs_hz))
        if out:
            foot_left = max(foot_left, int(np.floor(out[-1]*fs_hz-lo))+1)
        candidates = minima[(minima >= foot_left) & (minima <= up)]
        if not len(candidates):
            continue
        k = int(candidates[-1])
        denom = v[k-1] - 2*v[k] + v[k+1]
        delta = .5*(v[k-1]-v[k+1])/denom if denom > 0 else 0.
        out.append((lo+k+np.clip(delta, -.5, .5))/fs_hz)
    return np.unique(out)


def ensemble(x, fs_hz, duration_s=None, foot_times=None):
    """Extract complete foot-to-next-foot beats on one physical-time grid.

    Shared support is the shortest complete reference RR interval. Longer
    beats are truncated on that grid; no duration warping is performed.
    The same reference support is used for prediction and both split halves.
    """
    x = np.asarray(x, float)
    ft = feet(x, fs_hz) if foot_times is None else np.asarray(foot_times)
    if len(ft) < 3:
        return {"defined": False, "reason": "fewer than two complete beats",
                "n_beats": 0, "feet_s": ft}
    rr = np.diff(ft)
    if duration_s is None:
        duration_s = float(np.min(rr))
    grid = np.arange(int(np.floor(duration_s*fs_hz))) / fs_hz
    if len(grid) < 5:
        return {"defined": False, "reason": "insufficient physical-time support",
                "n_beats": 0, "feet_s": ft}
    t = np.arange(len(x))/fs_hz
    rows = []
    for f, end, interval in zip(ft[:-1], ft[1:], rr):
        if interval+1e-8 < duration_s or f+grid[-1] > t[-1]:
            continue
        raw = np.interp(f+grid, t, x)
        # Normalize each entire raw beat once; reuse that transform in full,
        # odd and even ensembles. Half means are never renormalized.
        full_t = np.arange(f, end, 1/fs_hz)
        amplitude = np.max(np.interp(full_t, t, x))-raw[0]
        if amplitude <= 0:
            continue
        rows.append((raw-raw[0])/amplitude)
    if len(rows) < 2:
        return {"defined": False, "reason": "fewer than two supported beats",
                "n_beats": len(rows), "feet_s": ft}
    beats = np.asarray(rows)
    return {"defined": True, "time_s": grid, "beats": beats,
            "mean": beats.mean(axis=0), "feet_s": ft,
            "duration_s": duration_s, "n_beats": len(rows),
            "complete_beats": len(rr),
            "eligibility_loss": len(rr)-len(rows),
            "coverage": len(rows)/len(rr),
            "normalization": "per-beat raw foot baseline and full-beat peak-minus-foot amplitude"}

# ---- delay ----
"""Harmonic phase branches and frozen-weight group delays.

An integer-cycle phase branch is unavoidable: the residual H/O phase starts
on its principal H1 branch and adjacent selected residual increments are
assumed to lie strictly between -pi and pi. A known observation operator O
guides only this branch; the weighted slope is fitted to the restored raw H
phase. Without an operator (model transfers), O = 1.
"""
import numpy as np
from scipy import signal


def operator_phase(frequencies_hz, operator):
    """Continuous native-500-Hz causal Butterworth/sign/device phase in radians."""
    fs = float(operator.get("fs_hz", 500))
    if fs != 500 or operator["phase"] != "causal":
        raise ValueError("Delay branch requires the native 500 Hz causal operator")
    frequencies = np.asarray(frequencies_hz, dtype=float)
    if not np.isfinite(frequencies).all() or np.any(frequencies <= 0) or np.any(frequencies >= fs/2):
        raise ValueError("Frequencies must be finite, positive and sub-Nyquist")
    order = int(operator["order"])
    sign = operator["sign"]
    if sign not in (-1, 1):
        raise ValueError("Operator sign must be -1 or 1")
    sos = signal.butter(order, [operator["lo_hz"], operator["hi_hz"]],
                        btype="bandpass", fs=fs, output="sos")
    # Fixed MAP-blind grid. Anchor the filter's low-frequency asymptote before
    # adding the analytically known pure device delay, avoiding delay aliasing.
    grid = np.linspace(1.e-6, fs/2-1.e-6, 65537)
    _, response = signal.sosfreqz(sos, worN=grid, fs=fs)
    phase = np.unwrap(np.angle(response))
    phase += 2*np.pi*np.round((order*np.pi/2-phase[0])/(2*np.pi))
    continuous = np.interp(frequencies, grid, phase)
    return continuous + (np.pi if sign == -1 else 0.) - (
        2*np.pi*frequencies*float(operator.get("device_delay_s", .4)))


def fit_delay(H, frequencies_hz, operator, weights, harmonics=(1, 2, 3)):
    """WLS raw-H phase = intercept - omega*tau on one frozen harmonic set.

    operator=None uses no observation-operator phase guide.
    """
    harmonic_ids = np.asarray(harmonics, dtype=int)
    if len(harmonic_ids) < 2 or np.any(harmonic_ids < 1) or np.any(np.diff(harmonic_ids) <= 0):
        raise ValueError("Require at least two increasing positive harmonic indices")
    h = np.asarray(H, dtype=complex)
    frequencies = np.asarray(frequencies_hz, dtype=float)
    if h.ndim != 1 or frequencies.shape != h.shape or harmonic_ids[-1] > len(h):
        raise ValueError("H and frequency arrays must align and include requested harmonics")
    result = dict(defined=False, harmonics=harmonic_ids.tolist(), tau_s=None,
        h1_phase_delay_s=None, phase_rad=None, intercept_rad=None, branch_margin_rad=None)
    weights = np.asarray(weights, dtype=float)
    if weights.shape != harmonic_ids.shape or not np.isfinite(weights).all() or np.any(weights <= 0):
        result["reason"] = "positive_frozen_harmonic_weights_required"
        return result
    indices = harmonic_ids-1
    h, f = h[indices], frequencies[indices]
    if not np.isfinite(h).all() or np.any(np.abs(h) == 0):
        result["reason"] = "requested_harmonic_undefined"
        return result
    if not np.isfinite(f).all() or np.any(f <= 0) or np.any(np.diff(f) <= 0):
        result["reason"] = "requested_frequencies_must_increase"
        return result
    guide = np.zeros(len(f)) if operator is None else operator_phase(f, operator)
    residual_wrapped = np.angle(h*np.exp(-1j*guide))
    residual_phase = np.unwrap(residual_wrapped)
    phase = guide+residual_phase
    increments = np.angle(np.exp(1j*np.diff(residual_wrapped)))
    omega = 2*np.pi*f
    design = np.column_stack((np.ones(len(f)), omega))
    # Normalize weights by a common scale solely for numerical conditioning.
    root_weight = np.sqrt(weights/weights.max())
    intercept, slope = np.linalg.lstsq(design*root_weight[:, None],
                                       phase*root_weight, rcond=None)[0]
    h1 = np.flatnonzero(harmonic_ids == 1)
    margin = np.pi-np.abs(increments)
    result.update(defined=True, tau_s=float(-slope), intercept_rad=float(intercept),
        phase_rad=phase.tolist(), frequencies_hz=f.tolist(), weights=weights.tolist(),
        h1_phase_delay_s=float(-phase[h1[0]]/omega[h1[0]]) if len(h1) else None,
        branch_margin_rad=float(margin.min()),
        residual_phase_rad=residual_phase.tolist(),
        residual_adjacent_phase_increments_rad=increments.tolist(),
        adjacent_branch_margins_rad=margin.tolist(),
        phase_branch_cycles=np.rint((phase-np.angle(h))/(2*np.pi)).astype(int).tolist())
    return result


def fit_equal_weight_delay(H, frequencies_hz, operator, harmonics=(1, 2, 3)):
    """Equal-weight estimate, independent of any estimated harmonic weights."""
    return fit_delay(H, frequencies_hz, operator, np.ones(len(harmonics)), harmonics)


def half_branch_diagnostics(full, odd, even):
    """Expose whole-cycle disagreements; make no threshold or cohort decision."""
    if not all(item.get("defined") for item in (full, odd, even)):
        return dict(defined=False, reason="full_or_half_delay_undefined")
    if not (full["harmonics"] == odd["harmonics"] == even["harmonics"]):
        raise ValueError("Full and half estimates must use identical harmonics")
    differences = {}
    for name, first, second in (("odd_full", odd, full), ("even_full", even, full),
                                ("odd_even", odd, even)):
        delta = np.asarray(first["phase_rad"])-np.asarray(second["phase_rad"])
        cycles = np.rint((delta-np.angle(np.exp(1j*delta)))/(2*np.pi)).astype(int)
        differences[name] = dict(cycle_disagreements=cycles.tolist(),
                                 disagreement_count=int(np.count_nonzero(cycles)))
    return dict(defined=True, **differences)


def freeze_harmonic_weights(records, harmonics=(1, 2, 3)):
    """Equal-case/equal-window split-noise estimates, v=.25 E[(odd-even)^2].

    Records contain caseid, odd_phase_rad and even_phase_rad on the identical
    supplied harmonic set, already restored to the consistent raw-H branch.
    Harmonic weights are constants 1/v; zero or missing variance is undefined
    and requires a reviewed configuration rather than an invented floor.
    """
    by_case = {}
    for record in records:
        odd = np.asarray(record["odd_phase_rad"], dtype=float)
        even = np.asarray(record["even_phase_rad"], dtype=float)
        if odd.shape != (len(harmonics),) or even.shape != odd.shape:
            raise ValueError("Split phase arrays must match the frozen harmonic set")
        by_case.setdefault(record["caseid"], []).append(odd-even)
    variance, bias, case_counts, window_counts = [], [], [], []
    for harmonic in range(len(harmonics)):
        case_square, case_bias = [], []
        windows = 0
        for differences in by_case.values():
            values = np.asarray(differences)[:, harmonic]
            values = values[np.isfinite(values)]
            if len(values):
                case_square.append(float(np.mean(values**2)))
                case_bias.append(float(values.mean()))
                windows += len(values)
        variance.append(float(.25*np.mean(case_square)) if case_square else None)
        bias.append(float(np.mean(case_bias)) if case_bias else None)
        case_counts.append(len(case_square))
        window_counts.append(windows)
    weights = [1./value if value is not None and np.isfinite(value) and value > 0 else None
               for value in variance]
    defined = all(weight is not None and np.isfinite(weight) for weight in weights)
    result = dict(defined=defined, harmonics=list(harmonics), variance=variance, weights=weights,
        odd_even_phase_bias_rad=bias,
        coverage=dict(input_records=len(records), input_cases=len(by_case),
                      case_counts=case_counts, window_counts=window_counts))
    if not defined:
        result["reason"] = "zero_or_unestimable_split_variance_requires_reviewed_weights"
    return result

# ---- harmonics ----
"""Harmonic transfer descriptors from beat-segmented records or periodic waveforms.

Coefficients use native-sample trapezoidal quadrature after per-beat DC
removal. ART feet define both channels' complete cycles. Common phase-grid
means are audit/display outputs; coefficient estimation uses native samples.

For variable RR, H is an ensemble beat-phase descriptor. Frequencies k/mean(RR)
summarize its harmonics and do not define a single-frequency stationary LTI
experiment. Adjacent residual group delays use principal increments of delay-removed
phase in [-pi, pi],
so delays are aliased modulo mean(RR); no data-selected unwrap is applied.
"""
import numpy as np



_HARMONICS = np.arange(1, 6)


def _estimate(art_coefficients, pleth_coefficients, art_scale, mean_rr_s):
    x = art_coefficients.mean(axis=0)
    y = pleth_coefficients.mean(axis=0)
    # Resolve numerical zeros relative to the AC waveform, independently of DC.
    present = np.abs(x) > 64 * np.finfo(float).eps * art_scale
    h = np.full(5, complex(np.nan, np.nan))
    np.divide(y, x, out=h, where=present)
    magnitude = np.abs(h)
    phase = np.full(5, np.nan)
    valid = np.isfinite(h) & (magnitude > 0)
    phase[valid] = np.angle(h[valid])
    residual = np.full(5, np.nan)
    if valid[0]:
        residual[valid] = np.angle(
            h[valid] / magnitude[valid]
            * (np.conj(h[0]) / magnitude[0]) ** _HARMONICS[valid])
        residual[0] = 0.
    increments = np.full(4, np.nan)
    for j in range(4):
        if np.isfinite(residual[j:j + 2]).all():
            increments[j] = np.angle(np.exp(1j * (residual[j + 1] - residual[j])))
    unwrapped = residual.copy()
    for j in range(1, 5):
        if np.isfinite(increments[j - 1]):
            unwrapped[j] = unwrapped[j - 1] + increments[j - 1]
    features = {}
    for j in range(1, 5):
        features[f"gainratio_k{j + 1}"] = (
            float(magnitude[j] / magnitude[0])
            if valid[0] and np.isfinite(h[j]) else np.nan)
        features[f"phase_k{j + 1}"] = float(residual[j])
    for j, delta in enumerate(increments):
        features[f"groupdelay_k{j + 1}_k{j + 2}_s"] = (
            float(-delta * mean_rr_s / (2 * np.pi)))
    return {"n_beats": len(art_coefficients), "art_mean_coefficients": x,
            "pleth_mean_coefficients": y, "H": h,
            "art_harmonic_present": present, "phase_wrapped_rad": phase,
            "residual_phase_rad": residual, "residual_phase_unwrapped_rad": unwrapped, "features": features}


def compute_tf_harmonics(art, pleth, fs_hz=500, foot_times=None):
    """Compute five ensemble harmonic ratios on shared ART foot-to-foot beats.

    Inputs are finite, aligned 1D native 500 Hz records. Supplied foot_times are
    seconds from sample zero; otherwise beats.feet detects ART feet only.
    At least two complete shared beats are required. Incomplete edge beats are
    omitted. Each native beat includes linearly interpolated endpoints and its
    full RR support. Beat amplitudes retain their original scale.

    Arrays art_coefficients/pleth_coefficients have shape (n_beats, 5), with
    integral (signal - beat_DC) * exp(-2j*pi*k*u) du over u in [0, 1].
    H is mean(pleth_coefficients)/mean(art_coefficients). Odd/even estimates use
    alternating retained beats and the same full-window mean RR frequency grid.
    Undefined harmonic ratios/features are NaN. phase_grid means are DC-removed
    waveforms in original amplitude units, sampled solely for display/audit.
    """
    if fs_hz != 500:
        raise ValueError("TF harmonics require native 500 Hz inputs")
    art, pleth = np.asarray(art, float), np.asarray(pleth, float)
    if art.ndim != 1 or pleth.ndim != 1 or art.shape != pleth.shape:
        raise ValueError("ART and PLETH must be aligned one-dimensional arrays")
    if not np.isfinite(art).all() or not np.isfinite(pleth).all():
        raise ValueError("ART and PLETH must be finite aligned data")
    if len(art) < 2:
        return {"defined": False, "reason": "fewer than two complete shared beats",
                "n_beats": 0}
    ft = (feet(art, fs_hz) if foot_times is None
          else np.asarray(foot_times, float))
    if ft.ndim != 1 or not np.isfinite(ft).all() or np.any(np.diff(ft) <= 0):
        raise ValueError("foot_times must be finite strictly increasing seconds")
    time = np.arange(len(art)) / fs_hz
    complete = (ft[:-1] >= 0) & (ft[1:] <= time[-1])
    starts, ends = ft[:-1][complete], ft[1:][complete]
    if len(starts) < 2:
        return {"defined": False, "reason": "fewer than two complete shared beats",
                "n_beats": len(starts), "feet_s": ft}
    rr = ends - starts
    phase_grid = np.linspace(0., 1., 501)
    coefficients, dc, phase_means, ac_scales = [], [], [], []
    for signal in (art, pleth):
        channel_coefficients, channel_dc, display_beats, scales = [], [], [], []
        for start, end, interval in zip(starts, ends, rr):
            left = np.searchsorted(time, start, side="right")
            right = np.searchsorted(time, end, side="left")
            beat_time = np.r_[start, time[left:right], end]
            u = (beat_time - start) / interval
            values = np.r_[np.interp(start, time, signal), signal[left:right],
                           np.interp(end, time, signal)]
            # Center first to retain offset invariance and exact constant zeros.
            shifted = values - values[0]
            dc_shift = np.trapezoid(shifted, u)
            centered = shifted - dc_shift
            channel_coefficients.append(np.trapezoid(
                centered[:, None] * np.exp(-2j * np.pi * u[:, None]
                                           * _HARMONICS), u, axis=0))
            channel_dc.append(values[0] + dc_shift)
            display_beats.append(np.interp(phase_grid, u, centered))
            scales.append(np.max(np.abs(centered)))
        coefficients.append(np.asarray(channel_coefficients))
        dc.append(np.asarray(channel_dc))
        phase_means.append(np.mean(display_beats, axis=0))
        ac_scales.append(np.asarray(scales))
    x, y = coefficients
    mean_rr = float(rr.mean())
    estimate = _estimate(x, y, float(ac_scales[0].mean()), mean_rr)
    return dict(estimate, defined=True, fs_hz=fs_hz, feet_s=ft,
                foot_method=(FOOT_METHOD if foot_times is None else "supplied ART feet"),
                beat_feet_s=np.column_stack((starts, ends)), beat_rr_s=rr,
                mean_rr_s=mean_rr, hr_bpm=60 / mean_rr,
                harmonics=_HARMONICS.copy(), frequencies_hz=_HARMONICS / mean_rr,
                art_coefficients=x, pleth_coefficients=y,
                art_beat_dc=dc[0], pleth_beat_dc=dc[1],
                phase_grid=phase_grid, art_phase_mean=phase_means[0],
                pleth_phase_mean=phase_means[1],
                odd=_estimate(x[::2], y[::2], float(ac_scales[0][::2].mean()), mean_rr),
                even=_estimate(x[1::2], y[1::2], float(ac_scales[0][1::2].mean()), mean_rr))


def periodic_phasors(t, y, period):
    """Least-squares constant plus k=1..5 sine/cosine phasors on a common period."""
    t = np.asarray(t)
    cols = [np.ones(len(t))]
    for k in range(1, 6):
        cols.extend((np.cos(2*np.pi*k*t/period), np.sin(2*np.pi*k*t/period)))
    x = np.column_stack(cols)
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    return beta[1::2]-1j*beta[2::2]


def periodic_transfer(t, input_signal, output_signal, period, phase_weights=(1., 1., 1.),
                      input_name="input", output_name="output"):
    """Output/input H_k of one periodic cycle with the shared k=1..3 delay estimator.

    The group delay is the same intercept-bearing weighted phase slope as for
    beat-segmented records (delay.fit_delay), here without an observation operator.
    """
    h = periodic_phasors(t, output_signal, period)/periodic_phasors(t, input_signal, period)
    weights = np.asarray(phase_weights, float)
    if weights.shape != (3,) or np.any(weights <= 0):
        raise ValueError("Three positive predeclared phase WLS weights are required")
    frequencies = np.arange(1, 6)/period
    fitted = fit_delay(h, frequencies, None, weights, harmonics=(1, 2, 3))
    if not fitted["defined"]:
        raise ValueError("Periodic transfer delay undefined: " + fitted["reason"])
    return {"input": input_name, "output": output_name, "period_s": period,
            "harmonics": [{"k": k, "real": float(z.real), "imag": float(z.imag), "phase_rad": float(np.angle(z)),
                           "gain_over_h1": float(abs(z)/abs(h[0]))} for k, z in enumerate(h, 1)],
            "h1_phase_delay_s": float(-np.angle(h[0])*period/(2*np.pi)),
            "h2_over_h1": float(abs(h[1])/abs(h[0])),
            "group_delay_k1_3_s": fitted["tau_s"], "phase_wls_intercept_rad": fitted["intercept_rad"],
            "phase_wls_weights": weights.tolist()}
