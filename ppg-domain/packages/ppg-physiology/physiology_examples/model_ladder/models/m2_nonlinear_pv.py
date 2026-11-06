"""M2: M1 transmission followed by a fixed Langewouters-type arctan P-V.

V/Vscale = 1/2 + atan((Ptm-Pmid)/width)/pi. Ptm=P-Pexternal.
Scale is unidentifiable under window gain and is fixed. Pmid and external
pressure cannot both be free; external pressure is fixed at 0 mmHg.
The input pressure DC is retained through the P-V operation.
"""
import numpy as np
from . import _input, _priors, _transmit
from .m1_transmission import PARAM_BOUNDS as M1_BOUNDS

PARAM_BOUNDS = {**M1_BOUNDS, "p_mid_mmHg": (-20.0, 120.0),
                "width_mmHg": (5.0, 120.0)}
PARAM_NAMES = tuple(PARAM_BOUNDS)
PARAM_PRIORS = _priors(PARAM_BOUNDS)
DEFAULT_PARAMS = {"fs_hz": 50.0, "frequency_hz": 6.0, "zeta": 0.7,
                  "p_mid_mmHg": 40.0, "width_mmHg": 40.0}
EXTERNAL_PRESSURE_MMHG = 0.0


def predict(art, params):
    x, p, fs = _input(art, params, DEFAULT_PARAMS)
    pressure = _transmit(x, fs, p["frequency_hz"], p["zeta"])
    width = float(p["width_mmHg"])
    if width <= 0:
        raise ValueError("P-V width must be positive")
    volume = 0.5 + np.arctan(
        (pressure-EXTERNAL_PRESSURE_MMHG-p["p_mid_mmHg"])/width)/np.pi
    return volume - volume[0]
