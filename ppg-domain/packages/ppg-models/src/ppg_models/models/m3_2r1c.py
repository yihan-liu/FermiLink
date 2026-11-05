"""M3: import-only existing local 2R1C negative control.

Rin/Rout are fixed to the package engineering-example ratio (1000/1500).
With external gain and offset, only tau=C*(Rin||Rout) is identifiable from
this linear branch; fitting C, Rin and Rout separately would be redundant.
Initial local pressure is the equilibrium at the first inlet pressure.
"""
import numpy as np
from . import _input, _priors

PARAM_BOUNDS = {"tau_s": (0.02, 2.0)}
PARAM_NAMES = tuple(PARAM_BOUNDS)
PARAM_PRIORS = _priors(PARAM_BOUNDS)
DEFAULT_PARAMS = {"fs_hz": 50.0, "tau_s": 0.6}


def predict(art, params):
    from peripheral_ppg.model import local_model
    x, p, fs = _input(art, params, DEFAULT_PARAMS)
    tau = float(p["tau_s"])
    if tau <= 0:
        raise ValueError("2R1C time constant must be positive")
    rin, rout, pv = 1000.0, 1500.0, 5.0
    c = tau / (rin*rout/(rin+rout))
    initial = (rout*x[0] + rin*pv)/(rin+rout)
    # Reference and initial volume coincide; a sufficiently large reference
    # ensures positive package volume without altering the dynamic equation.
    cfg = {"R_in_mmHg_s_per_mL": rin, "R_out_mmHg_s_per_mL": rout,
           "C_mL_per_mmHg": c, "P_venous_mmHg": pv,
           "P_ref_mmHg": initial, "P_initial_mmHg": initial,
           "V_ref_mL": 1.0 + c*np.ptp(x)}
    rows = local_model(np.arange(len(x))/fs, x, cfg)
    volume = np.array([row["V_local_mL"] for row in rows])
    return volume - volume[0]
