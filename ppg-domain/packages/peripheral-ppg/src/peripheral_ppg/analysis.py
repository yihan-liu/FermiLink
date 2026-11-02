"""Explicitly defined signal summaries and finite differences."""
import math


def ac_dc(values):
    if not values:
        raise ValueError("empty waveform")
    dc = sum(values)/len(values)
    ac = max(values)-min(values)
    return {"dc_mean": dc, "ac_peak_to_peak": ac, "ac_over_dc": ac/dc if dc else None}


def align(time_a, values_a, time_b, values_b):
    """Interpolate B on A's time grid over their common time range."""
    if len(time_a) != len(values_a) or len(time_b) != len(values_b) or len(time_b) < 2:
        raise ValueError("misaligned or insufficient time series")
    if any(y <= x for series in (time_a, time_b) for x, y in zip(series, series[1:])):
        raise ValueError("time axes must increase")
    out = []
    j = 0
    for t, a in zip(time_a, values_a):
        if not time_b[0] <= t <= time_b[-1]:
            continue
        while j+1 < len(time_b)-1 and time_b[j+1] < t:
            j += 1
        f = (t-time_b[j])/(time_b[j+1]-time_b[j])
        out.append((t, a, values_b[j]+f*(values_b[j+1]-values_b[j])))
    return out


def central_difference(evaluate, params, name, step):
    if step <= 0 or name not in params:
        raise ValueError("finite-difference step must be positive and parameter present")
    lo, hi = dict(params), dict(params)
    lo[name] -= step
    hi[name] += step
    return (evaluate(hi)-evaluate(lo))/(2*step)


def compare_same_origin(time_a, values_a, time_b, values_b):
    """Compare on the original time axes; no correlation-based phase shift."""
    return [{"time_s": t, "control": a, "condition": b, "difference": b-a}
            for t, a, b in align(time_a, values_a, time_b, values_b)]
