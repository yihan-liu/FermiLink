"""M0: empirical stable 4-pole/2-zero linear ART filter.

Two real lead/lag sections extend the exact M1 second-order lowpass; setting
each pole equal to its zero gives M1 sample-for-sample. This is a causal
rational filter, not a fitted waveform template. Residual delay is external.
"""
import numpy as np
from scipy import signal
from . import _input, _priors, _transmit
from .m1_transmission import PARAM_BOUNDS as M1_BOUNDS

PARAM_BOUNDS = {**M1_BOUNDS,
                "pole1_hz": (0.3, 20.0), "zero1_hz": (0.3, 20.0),
                "pole2_hz": (0.3, 20.0), "zero2_hz": (0.3, 20.0)}
PARAM_NAMES = tuple(PARAM_BOUNDS)
PARAM_PRIORS = _priors(PARAM_BOUNDS)
DEFAULT_PARAMS = {"fs_hz": 50.0, "frequency_hz": 6.0, "zeta": 0.7,
                  "pole1_hz": 6.0, "zero1_hz": 6.0,
                  "pole2_hz": 12.0, "zero2_hz": 12.0}


def predict(art, params):
    x, p, fs = _input(art, params, DEFAULT_PARAMS)
    y = _transmit(x, fs, p["frequency_hz"], p["zeta"])
    for i in (1, 2):
        pole, zero = float(p[f"pole{i}_hz"]), float(p[f"zero{i}_hz"])
        if not 0 < min(pole, zero) <= max(pole, zero) < fs / 2:
            raise ValueError("positive sub-Nyquist poles/zeros required")
        # H(s)=(1+s/wz)/(1+s/wp), with unit DC gain.
        if pole != zero:
            b, a = signal.bilinear([1 / (2*np.pi*zero), 1],
                                   [1 / (2*np.pi*pole), 1], fs=fs)
            y = signal.lfilter(b, a, y, zi=signal.lfilter_zi(b, a)*y[0])[0]
    return y - y[0]
