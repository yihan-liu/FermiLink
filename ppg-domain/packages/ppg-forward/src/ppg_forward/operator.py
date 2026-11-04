"""Explicit monitor observation operator for signed optical/area changes.

PLETH(t) = gain * BP[sign*dA(t-device_delay-PTT)] + offset.
Device delay and PTT are identifiable only through their sum. A fixed global
device delay is a convention, not a separately measured delay estimate.
Positive gain prevents its sign from cancelling the declared global sign.
"""
import numpy as np
from scipy import signal

# Candidate pilot search space, not verified monitor/physiological priors.
# Freeze selected global settings only after pilot and scientific review.
GLOBAL_OPTIONS = {
    "lo_hz_bounds": (0.05, 1.0),
    "hi_hz_bounds": (5.0, 15.0),
    "order_options": (1, 2, 3, 4),
    "sign_options": (-1, 1),
    "phase_options": ("causal", "zero_phase"),
    "device_delay_s": 0.4,
}
CASE_PTT_S_BOUNDS = (-0.4, 0.5)


def delay(x, delay_s, fs_hz=50):
    """Physical fractional delay; unsupported samples are NaN, never wrapped."""
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or x.size < 2 or fs_hz <= 0 or not np.isfinite(delay_s):
        raise ValueError("Require a 1-D signal, finite delay and positive fs_hz.")
    sample = np.arange(x.size, dtype=float)
    return np.interp(sample - delay_s * fs_hz, sample, x,
                     left=np.nan, right=np.nan)


def apply(dA, params):
    """Apply explicit global BP/sign, case PTT and window gain/offset.

    Required params: lo_hz, hi_hz, order, phase ('causal'/'zero_phase'), sign.
    Others: fs_hz=50, device_delay_s=0.4, ptt_s=0, gain=1, offset=0.
    BP uses Butterworth SOS. order is the prototype order, yielding
    2*order poles for band-pass. Causal mode initializes at constant first
    sample; zero_phase uses scipy's odd extension and forward/backward pass
    (squared magnitude response). These are distinct candidate operators.

    Filter the signed input before delaying; the LTI operations commute in
    the interior, with these explicit finite-record boundary conventions.
    Delayed samples outside input support are NaN and must be excluded from
    fitting. Filtering endpoint transients require an analysis edge mask;
    no physical timing interpretation may use those endpoint transients.
    """
    x = np.asarray(dA, dtype=float)
    if x.ndim != 1 or x.size < 2 or not np.all(np.isfinite(x)):
        raise ValueError("dA must be a finite one-dimensional waveform.")
    fs = float(params.get("fs_hz", 50))
    lo, hi = float(params["lo_hz"]), float(params["hi_hz"])
    order = params["order"]
    sign = params["sign"]
    phase = params["phase"]
    gain = float(params.get("gain", 1))
    offset = float(params.get("offset", 0))
    if not 0 < lo < hi < fs / 2:
        raise ValueError("Require 0 < lo_hz < hi_hz < Nyquist.")
    if order not in GLOBAL_OPTIONS["order_options"] or sign not in (-1, 1):
        raise ValueError("Require order in 1..4 and sign in {-1, 1}.")
    if not np.isfinite(gain) or gain <= 0 or not np.isfinite(offset):
        raise ValueError("Require finite positive gain and finite offset.")
    sos = signal.butter(order, [lo, hi], btype="bandpass", fs=fs, output="sos")
    signed = sign * x
    if phase == "causal":
        filtered, _ = signal.sosfilt(sos, signed, zi=signal.sosfilt_zi(sos) * signed[0])
    elif phase == "zero_phase":
        filtered = signal.sosfiltfilt(sos, signed, padtype="odd")
    else:
        raise ValueError("Choose phase='causal' or 'zero_phase' explicitly.")
    total_delay = float(params.get("device_delay_s", 0.4)) + float(params.get("ptt_s", 0))
    return gain * delay(filtered, total_delay, fs) + offset
