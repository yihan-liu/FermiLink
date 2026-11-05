"""Normalized ensemble-beat waveform comparison between observed and predicted signals.

NMSE is computed on foot-aligned physical-time ensemble means; the odd/even
noise ceiling and morphology features use the same ensembles.
"""
import numpy as np
from scipy.signal import find_peaks

from ppg_transfer.beats import FOOT_METHOD, ensemble


def noise_ceiling(e):
    """Full-mean noise floor from disjoint odd/even means, unequal halves allowed."""
    if not e["defined"]:
        return {"defined": False, "reason": e["reason"], "n_beats": e["n_beats"]}
    b = e["beats"]
    odd, even = b[::2].mean(axis=0), b[1::2].mean(axis=0)
    n1, n2 = len(b[::2]), len(b[1::2])
    denom = np.sum((e["mean"]-e["mean"].mean())**2)
    if n2 == 0 or denom <= 0:
        return {"defined": False, "reason": "undefined split-half denominator"}
    difference = float(np.sum((odd-even)**2))
    floor = n1*n2/(n1+n2)**2*difference/denom
    odd_denom = np.sum((odd-odd.mean())**2)
    raw_r2 = 1-difference/odd_denom if odd_denom > 0 else None
    correlation = (float(np.corrcoef(odd, even)[0, 1])
                   if np.std(odd) > 0 and np.std(even) > 0 else None)
    return {"defined": True, "n_odd": n1, "n_even": n2,
            "odd_even_squared_difference": difference,
            "odd_even_r2": None if raw_r2 is None else float(raw_r2),
            "odd_even_correlation": correlation, "noise_floor": float(floor),
            "ceiling_r2": float(1-floor)}


def features(e):
    """Physical timing, post-peak notch and half-height systolic width.

    A notch is a local minimum after the systolic peak and before 85% of
    shared support, followed by a local maximum, with >=2% prominence.
    No qualifying notch is recorded as absent, with undefined time/depth.
    """
    if not e["defined"]:
        return {"defined": False, "reason": e["reason"]}
    y, t = e["mean"], e["time_s"]
    peak = int(np.argmax(y))
    prominence = .02*np.ptp(y)
    minima, _ = find_peaks(-y, prominence=prominence)
    maxima, _ = find_peaks(y, prominence=prominence)
    candidates = [k for k in minima if peak < k < .85*len(y)
                  and np.any(maxima > k)]
    notch = int(candidates[0]) if candidates else None
    level = (y[peak]+y[0])/2
    rising = np.flatnonzero(y[:peak] < level)
    falling = np.flatnonzero(y[peak+1:] <= level)
    width = None
    if len(rising) and len(falling):
        a = int(rising[-1])
        b = peak+1+int(falling[0])
        rise = np.interp(level, y[a:a+2], t[a:a+2])
        fall = np.interp(level, y[b-1:b+1][::-1], t[b-1:b+1][::-1])
        width = float(fall-rise)
    return {"defined": True, "upstroke_s": float(t[peak]),
            "notch_present": notch is not None,
            "notch_time_s": None if notch is None else float(t[notch]),
            "notch_depth": None if notch is None else float(y[peak]-y[notch]),
            "systolic_width_s": width}


def window_metrics(observed, predicted, fs_hz):
    """Primary normalized ensemble NMSE, noise ceiling and retained timing."""
    a = ensemble(observed, fs_hz)
    result = {"defined": False, "foot_method": FOOT_METHOD,
              "fs_hz": fs_hz, "observed_beats": a["n_beats"],
              "observed_coverage": a.get("coverage"),
              "observed_eligibility_loss": a.get("eligibility_loss"),
              "noise_ceiling": noise_ceiling(a)}
    if not a["defined"]:
        return dict(result, reason=a["reason"])
    b = ensemble(predicted, fs_hz, a["duration_s"])
    result["predicted_beats"] = b["n_beats"]
    result["predicted_coverage"] = b.get("coverage")
    result["predicted_eligibility_loss"] = b.get("eligibility_loss")
    if not b["defined"]:
        return dict(result, reason=b["reason"])
    denom = np.sum((a["mean"]-a["mean"].mean())**2)
    nmse = float(np.sum((a["mean"]-b["mean"])**2)/denom)
    # Match nearest feet only within half a reference cycle to retain timing.
    differences = []
    for foot in a["feet_s"]:
        delta = b["feet_s"]-foot
        nearest = delta[np.argmin(np.abs(delta))]
        if abs(nearest) < .5*a["duration_s"]:
            differences.append(float(nearest))
    fa, fb = features(a), features(b)
    errors = {}
    for key in ("upstroke_s", "notch_time_s", "notch_depth", "systolic_width_s"):
        errors[key] = (None if fa.get(key) is None or fb.get(key) is None
                       else float(fb[key]-fa[key]))
    return dict(result, defined=True, nmse=nmse, r2=1-nmse,
                support_s=a["duration_s"], observed_features=fa,
                predicted_features=fb, feature_errors=errors,
                delay_residual_s=(float(np.median(differences)) if differences else None),
                delay_matched_feet=len(differences))


def aggregate_cases(rows):
    """Average windows within cases, then summarize equally weighted cases."""
    groups = {}
    for row in rows:
        if row.get("defined"):
            groups.setdefault(int(row["caseid"]), []).append(float(row["nmse"]))
    per_case = {str(k): float(np.mean(v)) for k, v in groups.items()}
    values = list(per_case.values())
    return {"per_case_nmse": per_case, "n_cases": len(values),
            "mean_nmse": float(np.mean(values)) if values else None,
            "median_nmse": float(np.median(values)) if values else None}
