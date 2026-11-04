"""M1: second-order transmission, linear compliance and linear optics.

Unit compliance and optical gain fix an unidentifiable scale. The second-order
positive-damping lowpass includes real-pole and resonant transmission regimes.
No device delay or residual PTT is applied here.
"""
from . import _input, _priors, _transmit

PARAM_BOUNDS = {"frequency_hz": (0.3, 20.0), "zeta": (0.15, 3.0)}
PARAM_NAMES = tuple(PARAM_BOUNDS)
PARAM_PRIORS = _priors(PARAM_BOUNDS)
DEFAULT_PARAMS = {"fs_hz": 50.0, "frequency_hz": 6.0, "zeta": 0.7}


def predict(art, params):
    x, p, fs = _input(art, params, DEFAULT_PARAMS)
    pressure = _transmit(x, fs, p["frequency_hz"], p["zeta"])
    return pressure - pressure[0]
