"""Synthetic fitting check; no patient input or solver execution."""
import json
from types import SimpleNamespace

import numpy as np

from ppg_models.fit import fit_case, model_module, prepare_art, profile_amplitude, _mask
from ppg_models.operator import apply


def test_ptt_initialization_escapes_nonpositive_gain_plateau():
    fs = 50
    t = np.arange(30*fs)/fs
    op = {"lo_hz": .2, "hi_hz": 10., "order": 2, "phase": "causal",
          "sign": 1, "device_delay_s": .4}
    physiology = dict(model_module("M1").DEFAULT_PARAMS)
    phase = 2*np.pi*1.2*t
    art = 80.+22*np.cos(phase)+7*np.sin(2*phase)+3*np.cos(3*phase)
    area = model_module("M1").predict(
        prepare_art(art, fs, "uncorrected")["art"], physiology)
    windows = []
    initial_losses = []
    for j, gain in enumerate((1., 3.)):
        pleth = apply(area, dict(op, fs_hz=fs, ptt_s=-.3, gain=gain, offset=100.))
        pleth[~np.isfinite(pleth)] = 100.
        w = SimpleNamespace(time_s=t+j*900, art=art, pleth=pleth,
            fs_hz=fs, caseid=11, start_s=float(j*900), end_s=float(j*900+30))
        windows.append(w)
        mask = _mask(w, op)
        initial_prediction = apply(area, dict(op, fs_hz=fs, ptt_s=.15))
        x, y = initial_prediction[mask], pleth[mask]
        assert np.dot(x-x.mean(), y-y.mean()) < 0
        initial_gain, offset = profile_amplitude(initial_prediction, pleth, mask)
        assert initial_gain == np.finfo(float).eps
        initial_losses.append(np.sum((initial_gain*x+offset-y)**2)
                              /np.sum((y-y.mean())**2))
    assert np.allclose(initial_losses, 1.)

    fit = fit_case(windows, "M1", op, fixed_physiology=physiology, max_nfev=100)
    assert fit["success"] and np.isfinite(fit["waveform_nmse"])
    assert fit["waveform_nmse"] < 1e-8
    assert abs(fit["ptt_s"]-.15) > .1
    assert abs(fit["ptt_s"]+.3) < .002
    assert fit["physiology"] == physiology
    assert all(np.isfinite(w["gain"]) and w["gain"] > .1 for w in fit["windows"])
