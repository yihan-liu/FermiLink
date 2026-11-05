"""Native-rate continuous-filter fit checks on synthetic ART/PLETH only."""
from types import SimpleNamespace

import numpy as np
import pytest

from ppg_models import fit as fitting
from ppg_models.operator import apply


OPERATOR = dict(lo_hz=.2, hi_hz=10., order=2, phase="causal",
                sign=1, device_delay_s=.4)


def _window(fs, delay):
    t = np.arange(30 * fs) / fs
    phase = 2 * np.pi * 1.25 * t
    art = 80. + 22 * np.cos(phase) + 7 * np.sin(2 * phase) + 3 * np.cos(3 * phase)
    physiology = dict(fitting.model_module("M0").DEFAULT_PARAMS, fs_hz=fs)
    area = fitting.model_module("M0").predict(
        fitting.prepare_art(art, fs, "uncorrected")["art"], physiology)
    pleth = apply(area, dict(OPERATOR, fs_hz=fs, ptt_s=delay, gain=2.7, offset=93.))
    pleth[~np.isfinite(pleth)] = 93.
    return SimpleNamespace(time_s=t, art=art, pleth=pleth, fs_hz=fs,
        caseid=11, start_s=0., end_s=30.), physiology


def test_native500_odd_even_masks_preserve_continuous_filter_and_recover_5ms_change(monkeypatch):
    monkeypatch.setattr(fitting, "evaluate_case",
                        lambda *a, **kw: pytest.fail("Round2 metric evaluation"))
    original = fitting._predict
    def predict(window, art, *args):
        assert len(art) == len(window.art) == 15000
        return original(window, art, *args)
    monkeypatch.setattr(fitting, "_predict", predict)
    recovered = []
    for parity, delay in enumerate((.1233, .1283)):
        window, physiology = _window(500, delay)
        # ART has one beat every .8 s; retain complete alternating ART beats.
        mask = (np.floor(window.time_s / .8).astype(int) % 2) == parity
        window.pleth[~mask] = 1.e6  # excluded targets must not affect gain or loss
        result = fitting.fit_case([window], "M0", OPERATOR,
            fixed_physiology=physiology, fit_fs_hz=500,
            analysis_masks=[mask], evaluate=False, max_nfev=50)
        assert result["success"] and result["fit_fs_hz"] == 500
        assert result["waveform_nmse"] < 1e-10
        assert abs(result["ptt_s"] - delay) < .0005
        assert "windows" not in result
        assert result["operator"] == OPERATOR
        recovered.append(result["ptt_s"])
    assert abs((recovered[1] - recovered[0]) - .005) < .0005


def test_default50_and_native_sampling_mask_guards():
    low, physiology = _window(50, .12)
    result = fitting.fit_case([low], "M0", OPERATOR,
        fixed_physiology=physiology, evaluate=False, max_nfev=50)
    assert result["success"] and result["fit_fs_hz"] == 50
    assert abs(result["ptt_s"] - .12) < .002
    high, _ = _window(500, .12)
    with pytest.raises(ValueError, match="fit_fs_hz"):
        fitting.fit_case([high], "M0", OPERATOR, evaluate=False)
    with pytest.raises(ValueError, match="fit_fs_hz"):
        fitting.fit_case([low], "M0", OPERATOR, fit_fs_hz=100, evaluate=False)
    with pytest.raises(ValueError, match="boolean"):
        fitting.fit_case([low], "M0", OPERATOR,
            analysis_masks=[np.ones(len(low.art))], evaluate=False)
    with pytest.raises(ValueError, match="support"):
        fitting.fit_case([low], "M0", OPERATOR,
            analysis_masks=[np.zeros(len(low.art), dtype=bool)], evaluate=False)
