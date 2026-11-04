"""Physical-time ensemble metrics for normalized Round-2 PLETH shape.

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
    ceiling = result["noise_ceiling"].get("ceiling_r2")
    return dict(result, defined=True, nmse=nmse, r2=1-nmse,
                p2_90pct_ceiling=(None if ceiling is None or ceiling <= 0
                                  else bool(1-nmse >= .9*ceiling)),
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
