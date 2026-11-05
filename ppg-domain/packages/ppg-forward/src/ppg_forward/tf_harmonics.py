"""Native-500-Hz common-foot beat-phase harmonic transfer descriptors.

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

from . import metrics


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
    seconds from sample zero; otherwise metrics.feet detects ART feet only.
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
    ft = (metrics.feet(art, fs_hz) if foot_times is None
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
                foot_method=(metrics.FOOT_METHOD if foot_times is None else "supplied ART feet"),
                beat_feet_s=np.column_stack((starts, ends)), beat_rr_s=rr,
                mean_rr_s=mean_rr, hr_bpm=60 / mean_rr,
                harmonics=_HARMONICS.copy(), frequencies_hz=_HARMONICS / mean_rr,
                art_coefficients=x, pleth_coefficients=y,
                art_beat_dc=dc[0], pleth_beat_dc=dc[1],
                phase_grid=phase_grid, art_phase_mean=phase_means[0],
                pleth_phase_mean=phase_means[1],
                odd=_estimate(x[::2], y[::2], float(ac_scales[0][::2].mean()), mean_rr),
                even=_estimate(x[1::2], y[1::2], float(ac_scales[0][1::2].mean()), mean_rr))
