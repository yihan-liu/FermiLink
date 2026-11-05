"""MAP-blind harmonic phase branches and frozen-weight group delays.

An integer-cycle phase branch is unavoidable: the residual H/O phase starts
on its principal H1 branch and adjacent selected residual increments are
assumed to lie strictly between -pi and pi. The frozen operator guides only
this branch; the weighted slope is fitted to the restored raw H phase.
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
    """WLS raw-H phase = intercept - omega*tau on one frozen harmonic set."""
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
    guide = operator_phase(f, operator)
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
    """Equal-weight synthetic/A1 acceptance estimate, independent of pilot weights."""
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
    """Pilot equal-case/equal-window split-noise estimates, v=.25 E[(odd-even)^2].

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
