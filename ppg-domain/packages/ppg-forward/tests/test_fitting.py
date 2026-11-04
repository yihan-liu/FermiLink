"""One synthetic development check; no patient input or solver execution."""
import json
from types import SimpleNamespace

import numpy as np

from ppg_forward.fit import (fit_case, evaluate_case, model_module, prepare_art,
    cross_window, parameter_stability, default_operator_candidates,
    profile_amplitude, _mask)
from ppg_forward.metrics import noise_ceiling, aggregate_cases
from ppg_forward.operator import apply


def test_synthetic_fit_metrics_and_serialized_driver(tmp_path, monkeypatch):
    op = {"lo_hz": .2, "hi_hz": 10., "order": 2, "phase": "causal",
          "sign": 1, "device_delay_s": .4}
    truth = {"frequency_hz": 4., "zeta": .8}

    def make(fs):
        t = np.arange(30*fs)/fs
        result = []
        for j, mean in enumerate((75., 95., 82.)):
            phase = 2*np.pi*1.2*t
            art = mean+22*np.cos(phase)+7*np.sin(2*phase)+3*np.cos(3*phase)
            area = model_module("M1").predict(
                prepare_art(art, fs, "uncorrected")["art"], dict(truth, fs_hz=fs))
            pleth = apply(area, dict(op, fs_hz=fs, ptt_s=.12, gain=j+1., offset=100.))
            pleth[~np.isfinite(pleth)] = 100.
            result.append(SimpleNamespace(time_s=t+j*900, art=art, pleth=pleth,
                fs_hz=fs, caseid=11, start_s=float(j*900), end_s=float(j*900+30)))
        return result

    low, high = make(50), make(500)
    fit = fit_case(low, "M1", op, max_nfev=100)
    assert fit["success"] and fit["waveform_nmse"] < 1e-8
    assert abs(fit["ptt_s"]-.12) < .002
    assert all(w["defined"] and w["nmse"] < 1e-7 for w in fit["windows"])
    restored = json.loads(json.dumps(fit, allow_nan=False))
    native = evaluate_case(high, restored)
    assert all(w["defined"] and w["fs_hz"] == 500 for w in native)
    assert all(abs(w["feature_errors"]["upstroke_s"]) <= .004 for w in native)
    assert all(w["observed_coverage"] > .8 for w in native)
    unavailable = fit_case(low, "M1", op, branch="corrected")
    assert not unavailable["available"] and "windows" not in unavailable
    identity = prepare_art(low[0].art, 50, "corrected",
        {"fn_hz": 1e9, "zeta": .7, "frequency_kind": "natural"})["art"]
    assert np.max(abs(identity-prepare_art(low[0].art, 50, "uncorrected")["art"])) < 1e-5
    b = np.array([[0., 1., .3], [0., .8, .4], [0., 1.2, .2],
                  [0., .9, .3], [0., 1.1, .4]])
    nc = noise_ceiling({"defined": True, "beats": b, "mean": b.mean(0)})
    expected = 6/25*np.sum((b[::2].mean(0)-b[1::2].mean(0))**2)/np.sum((b.mean(0)-b.mean())**2)
    assert abs(nc["noise_floor"]-expected) < 1e-14
    transfer = cross_window(low, "M1", op, max_nfev=100)
    assert transfer["defined"] and transfer["absolute_delta_map_mmHg"] >= 15
    assert transfer["transfer_b"]["fixed_physiology"]
    assert abs(transfer["degradation_nmse"]) < 1e-7
    diagnostics = [fit_case([w], "M1", op, max_nfev=100) for w in low]
    stability = parameter_stability(diagnostics)
    assert stability["n_windows"] == 3 and "map_pearson_r" in stability["parameters"]["zeta"]
    assert len(default_operator_candidates()) == 16
    assert np.isclose(aggregate_cases([dict(caseid=11, defined=True, nmse=.1),
                            dict(caseid=11, defined=True, nmse=.3),
                            dict(caseid=12, defined=True, nmse=.4)])["mean_nmse"], .3)

    # Exercise saved-config reevaluation through the public package driver.
    # Synthetic loader replacement supplies in-memory waves and never opens raw files.
    from dataclasses import make_dataclass
    from ppg_forward import round2_driver as driver
    W = make_dataclass("SyntheticWindow", [(k, object) for k in vars(high[0])])
    high = [W(**vars(w)) for w in high]
    monkeypatch.setattr(driver, "load_selected_windows", lambda *a, **k: iter(high))
    segment_dir = tmp_path/"segments"
    segment_dir.mkdir()
    (segment_dir/"selection.json").write_text("{}")
    (segment_dir/"windows.csv").write_text(
        "caseid,start_s,end_s\n11,0,30\n11,900,930\n11,1800,1830\n")
    out = tmp_path/"fit"
    result = driver.run_fit(segment_dir, ["M1"], op, out, max_nfev=80)
    assert result["raw_files_opened"] == []
    context = json.loads((out/"fit_context.json").read_text())
    assert context["operator"] == op and context["segments_dir"] == str(segment_dir)
    corners = json.loads((out/"corner-diagnostics.json").read_text())
    assert len(corners["per_case"][0]["starts"]) == 2
    assert corners["corners"]["lo_hz"]["valid_n"] == int(corners["per_case"][0]["valid"])
    assert corners["p6_conclusion"] is None
    assert all(np.isfinite(s["loss"]) for s in corners["per_case"][0]["starts"])
    evaluated = driver.run_evaluate(segment_dir, out, tmp_path/"evaluate")
    assert evaluated["summary"]["corrected_M1"]["unavailable_cases"] == 1
    assert evaluated["summary"]["uncorrected_M1"]["n_cases"] == 1


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
