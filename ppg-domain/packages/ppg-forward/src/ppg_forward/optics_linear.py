"""Shared detected-photon absorption responses; paths mm and mua 1/mm."""
from __future__ import annotations
import numpy as np


def logsumexp(values):
    values = np.asarray(values, dtype=float)
    top = float(np.max(values))
    if not np.isfinite(top):
        raise ValueError("positive finite detected photon weight required")
    return top + float(np.log(np.exp(values-top).sum()))


def photon_log_weights(paths_mm, w0, mua_per_mm):
    paths = np.asarray(paths_mm, dtype=float)
    initial = np.asarray(w0, dtype=float).reshape(-1)
    mua = np.asarray(mua_per_mm, dtype=float)
    if paths.ndim != 2 or initial.shape != (len(paths),) or mua.shape != (paths.shape[1],):
        raise ValueError("path, weight and absorption dimensions disagree")
    if (not np.all(np.isfinite(paths)) or not np.all(np.isfinite(initial))
            or not np.all(np.isfinite(mua)) or np.any(paths < 0)
            or np.any(initial < 0) or np.any(mua < 0)):
        raise ValueError("paths, weights and absorption must be finite and nonnegative")
    with np.errstate(divide="ignore"):
        return np.log(initial) - paths @ mua


def photon_weights(paths_mm, w0, mua_per_mm):
    return np.exp(photon_log_weights(paths_mm, w0, mua_per_mm))


def normalized_weights(log_weights):
    return np.exp(np.asarray(log_weights)-logsumexp(log_weights))


def weight_coverage(log_weights):
    w = normalized_weights(log_weights)
    return {"detected_count": len(w), "detected_weight_ess": float(1/(w@w)),
            "maximum_normalized_weight": float(w.max())}


def absorption_jacobian(paths_mm, weights, launched_count):
    """Gradient of intensity and Hessian of ln intensity at fixed scattering."""
    paths = np.asarray(paths_mm, dtype=float)
    weights = np.asarray(weights, dtype=float)
    total = float(weights.sum())
    if launched_count <= 0 or total <= 0:
        raise ValueError("positive launched count and detected weight are required")
    mean = weights @ paths / total
    second = (paths.T * weights) @ paths / total
    intensity = total / launched_count
    return {"intensity": intensity, "mean_path_mm": mean,
        "intensity_gradient_mm": -intensity * mean,
        "intensity_hessian_mm2": intensity * second,
        "log_intensity_hessian_mm2": second - np.outer(mean, mean)}


def log_absorption_response(paths_mm, log_weights, delta_mua_per_mm):
    """ln E_w exp(-X), with same-photon linear and quadratic cumulants.

    The exact remainder supplements the quadratic/linear criterion. Zero
    perturbations have undefined ratios rather than an invented zero bound.
    """
    x = np.asarray(paths_mm, dtype=float) @ np.asarray(delta_mua_per_mm, dtype=float)
    lw = np.asarray(log_weights, dtype=float)
    w = normalized_weights(lw)
    mean = float(w @ x)
    variance = float(w @ np.square(x-mean))
    # Centering preserves small log changes and avoids overflow in exp(-X).
    centered = -(x-mean)
    if np.max(np.abs(centered)) < .5:
        exact = -mean + float(np.log1p(w @ np.expm1(centered)))
    else:
        exact = logsumexp(lw-x)-logsumexp(lw)
    return {"log_intensity_change": exact,
        "log_intensity_linear_change": -mean,
        "log_intensity_second_order_term": .5*variance,
        "log_intensity_second_to_linear": .5*variance/abs(mean) if mean else None,
        "log_intensity_remainder_to_linear": abs(exact+mean)/abs(mean) if mean else None}


def absorption_response(paths_mm, weights, launched_count, delta_mua_per_mm):
    weights = np.asarray(weights, dtype=float)
    with np.errstate(divide="ignore"):
        log_weights = np.log(weights)
    response = log_absorption_response(paths_mm, log_weights, delta_mua_per_mm)
    x = np.asarray(paths_mm, dtype=float) @ np.asarray(delta_mua_per_mm, dtype=float)
    baseline = float(weights.sum()/launched_count)
    linear = -float(weights @ x)/launched_count
    second = .5*float(weights @ np.square(x))/launched_count
    change = baseline*float(np.expm1(response["log_intensity_change"]))
    return {**response, "intensity": baseline+change, "intensity_change": change,
        "intensity_linear_change": linear, "intensity_second_order_term": second,
        "intensity_second_to_linear": abs(second/linear) if linear else None,
        "intensity_remainder_to_linear": abs((change-linear)/linear) if linear else None,
        "optical_density_change": -response["log_intensity_change"],
        "optical_density_linear_change": -response["log_intensity_linear_change"],
        "optical_density_second_order_term": -response["log_intensity_second_order_term"],
        "optical_density_second_to_linear": response["log_intensity_second_to_linear"]}


def volume_scattering(fraction, mus_matrix, g_matrix, mus_blood, g_blood):
    """Engineering sensitivity: volume mixing of mus and g separately."""
    return (fraction*mus_blood+(1-fraction)*mus_matrix,
            fraction*g_blood+(1-fraction)*g_matrix)


def _log_i0(z):
    # NumPy I0 overflows for large z. Its large-positive-argument expansion
    # through six terms is accurate to floating precision above 500.
    z = np.asarray(z, dtype=float)
    result = np.empty_like(z)
    small = z <= 500
    result[small] = np.log(np.i0(z[small]))
    large = z[~small]
    term = np.ones_like(large)
    series = term.copy()
    for k in range(1, 7):
        term *= (2*k-1)**2/(8*k*large)
        series += term
    result[~small] = large-.5*np.log(2*np.pi*large)+np.log(series)
    return result


def sine_ac_dc(projected_paths, weights, amplitude):
    """Exact continuous sine detector intensity peak-to-peak / cycle mean.

    q=L_mix*(mua_blood-mua_matrix)>=0 and f(t)=f0+a*sin(theta).
    The numerator is 2 E_w sinh(a*q), denominator E_w I0(a*q).
    """
    q = np.asarray(projected_paths, dtype=float)
    w = np.asarray(weights, dtype=float)
    if (q.shape != w.shape or np.any(q < 0) or amplitude < 0
            or not np.all(np.isfinite(q)) or np.any(w < 0) or w.sum() <= 0):
        raise ValueError("nonnegative aligned paths, weights and amplitude required")
    z = amplitude*q
    if not np.any(z):
        return 0.
    with np.errstate(divide="ignore"):
        lw = np.log(w)
        # log(2*sinh(z)) = z + log(1-exp(-2*z)).
        numerator = logsumexp(lw+z+np.log(-np.expm1(-2*z)))
    return float(np.exp(numerator-logsumexp(lw+_log_i0(z))))


def select_sine_excursion(projected_paths, weights, baseline_fraction, target_ac_dc):
    """Infer absolute f excursion from a target exact detector AC/DC.

    The physical excursion limit is min(f0,1-f0). Unattainable targets are
    recorded as uncovered. No raw PLETH AC/DC is inferred from SNUADC.
    """
    if not 0 < baseline_fraction < 1 or target_ac_dc <= 0:
        raise ValueError("interior baseline fraction and positive AC/DC required")
    maximum = min(baseline_fraction, 1-baseline_fraction)
    max_ac_dc = sine_ac_dc(projected_paths, weights, maximum)
    attainable = max_ac_dc >= target_ac_dc
    lower, upper = 0., maximum
    if attainable:
        for _ in range(40):
            middle = .5*(lower+upper)
            if sine_ac_dc(projected_paths, weights, middle) < target_ac_dc:
                lower = middle
            else:
                upper = middle
        amplitude = .5*(lower+upper)
    else:
        amplitude = maximum
    return {"target_ac_dc": float(target_ac_dc),
        "achieved_ac_dc": sine_ac_dc(projected_paths, weights, amplitude),
        "fraction_excursion_amplitude": float(amplitude),
        "fraction_min": float(baseline_fraction-amplitude),
        "fraction_max": float(baseline_fraction+amplitude),
        "target_attainable": bool(attainable), "physical_maximum_ac_dc": max_ac_dc}
