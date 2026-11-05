"""PWDB public-data geometry and common-root timing (all solver quantities SI)."""
import json
from pathlib import Path
import numpy as np

MMHG_PA = 133.322387415
SITES = {"root": (1, "AorticRoot"), "radial": (22, "Radial"), "digital": (112, "Digital")}


def load_baseline(path):
    data = json.loads(Path(path).read_text())
    if data["wave_units"] != {"P": "mmHg", "U": "m/s", "A": "m^2"}:
        raise ValueError("PWDB baseline must use the documented P/U/A source units")
    return data


def periodic_interpolate(time, samples, period, at):
    """Interpolate native samples periodically, including the fractional last gap."""
    time = np.asarray(time, float)
    samples = np.asarray(samples, float)
    return np.interp(np.mod(at, period), np.mod(time, period), samples, period=period)


def reference(data, site, at):
    """Restore local-foot exports to common aortic-root time, without extra shifts."""
    _, prefix = SITES[site]
    values = {}
    for quantity in ("P", "U", "A"):
        key = prefix + "_" + quantity
        raw = np.asarray(data["waveforms"][key], float)
        native = float(data["onset_times"][key]) + np.arange(len(raw)) / data["fs_hz"]
        values[quantity] = periodic_interpolate(native, raw, data["period_s"], at)
    values["P"] *= MMHG_PA
    values["Q"] = values["U"] * values["A"]
    return values


def network(data):
    """Published PDDL geometry: lengths/radii m; R Pa s/m3; C m3/Pa."""
    return [{key: int(row[key]) if key in ("seg_no", "inlet_node", "outlet_node") else float(row[key])
             for key in row} for row in data["geometry"]]


def radius(segment, x):
    """Exact published linear taper; x is physical distance from proximal end."""
    return segment["inlet_radius"] + (segment["outlet_radius"] - segment["inlet_radius"]) * np.asarray(x) / segment["length"]


def wall_parameters(data, r):
    """Return Ad and square-root coefficient B, Pe=Pd+B*(sqrt(A/Ad)-1)."""
    cfg = data["model_config"]
    k1, k2, k3 = (float(cfg[k]) for k in ("k1 [g/s^2/cm]", "k2 [/cm]", "k3 [g/s^2/cm]"))
    eh = .1 * (k1 * np.exp(k2 * 100 * np.asarray(r)) + k3) * r
    return np.pi * np.asarray(r)**2, (4 / 3) * eh / r


def nektar_gamma(data, r):
    """Nektar input Gamma, not yet a momentum diffusion coefficient."""
    cfg = data["model_config"]
    b0, b1 = float(cfg["b0 [g/s]"]), float(cfg["b1 [g cm/s]"])
    return (4 / np.pi) * (b1 / (2 * 100 * np.asarray(r)) + b0) / 1000 / (2 * np.asarray(r))**2
