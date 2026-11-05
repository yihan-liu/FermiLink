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
