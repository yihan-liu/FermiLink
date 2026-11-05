"""ART-to-area shape models M0-M4; device filtering and residual PTT are external.

All outputs are area-change proxies with an arbitrary constant scale, as the
window-level observation gain removes scale. Pressure inputs remain in mmHg.
Parameter bounds/priors are engineering search ranges, not measured ranges.
"""
import numpy as np
from scipy import signal


def _input(art, params, defaults):
    p = dict(defaults)
    p.update(params)
    x = np.asarray(art, dtype=float)
    if x.ndim != 1 or len(x) < 2 or not np.all(np.isfinite(x)):
        raise ValueError("ART must contain at least two finite samples")
    fs = float(p["fs_hz"])
    if fs not in (50.0, 500.0):
        raise ValueError("fs_hz must be 50 or 500")
    return x, p, fs


def _priors(bounds):
    return {k: {"distribution": "uniform", "low": lo, "high": hi}
            for k, (lo, hi) in bounds.items()}


def _transmit(x, fs, frequency_hz, zeta):
    """Stable causal analog lowpass, bilinear discretization, equilibrium start.

    The bilinear warp is intentional and common to M0/M1/M2. No zero-phase
    filtering is used for physiological dynamics. Constant prehistory at x[0]
    prevents an artificial zero-state pressure transient at the left boundary.
    """
    w = 2 * np.pi * float(frequency_hz)
    z = float(zeta)
    if not 0 < frequency_hz < fs / 2 or z <= 0:
        raise ValueError("positive sub-Nyquist frequency and damping required")
    b, a = signal.bilinear([w * w], [1, 2 * z * w, w * w], fs=fs)
    sos = signal.tf2sos(b, a)
    return signal.sosfilt(sos, x, zi=signal.sosfilt_zi(sos) * x[0])[0]
