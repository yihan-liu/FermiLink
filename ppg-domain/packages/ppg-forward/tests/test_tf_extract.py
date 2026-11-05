"""Synthetic extraction I/O smoke; native waveforms never leave the test."""
import inspect
import json

import numpy as np
import pandas as pd
import pytest

from ppg_forward import tf_extract
from ppg_forward.fit import fit_case
from ppg_forward.models.m0_empirical import DEFAULT_PARAMS
from ppg_forward.segments import WindowData
from ppg_forward.tf_delay import fit_delay


def test_synthetic_extract_freeze_replay_fallback_and_empty(tmp_path, monkeypatch):
    source = tmp_path / "selection"
    source.mkdir()
    (source / "selection.json").write_text(json.dumps({"selection_mode": "sliding"}))
    operator = dict(lo_hz=.2, hi_hz=10., order=2, phase="causal",
                    sign=1, device_delay_s=.4)
    operator_file = tmp_path / "operator.json"
    operator_file.write_text(json.dumps(operator))
    t = np.arange(6000) / 500
    k = np.arange(1, 6)
    a = np.array([15., 2., .8, .3, .15])
    art = 85 - np.sum(a * np.cos(2 * np.pi * t[:, None] * k), axis=1)
    windows = []
    for cid, count in ((1, 3), (2, 2)):
        for j in range(count):
            alternating = np.where((np.floor(t).astype(int) % 2) == 0, 1., -1.)
            phase = (-2 * np.pi * k * (.43 + j * .004)
                     + alternating[:, None] * np.array([.01, .025, .04, .03, .02]))
            pleth = 300 - np.sum(a * np.cos(2 * np.pi * t[:, None] * k + phase), axis=1)
            windows.append(WindowData(t, art.copy(), pleth, 500, cid, j * 120., j * 120. + 12.))
    loaded = list(windows)
    def load(directory, *, fs_hz, raw_access_callback):
        assert directory == source and fs_hz == 500
        return iter(loaded)
    monkeypatch.setattr(tf_extract, "load_selected_windows", load)
    calls = []
    signature = inspect.signature(fit_case)
    def fit(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        w = bound.arguments["windows"][0]
        assert w.art.shape == (6000,) and w.fs_hz == 500
        assert bound.arguments["fit_fs_hz"] == 500
        assert bound.arguments["evaluate"] is False
        calls.append((w, bound.arguments["analysis_masks"]))
        return dict(available=True, success=True, physiology=dict(DEFAULT_PARAMS),
                    ptt_s=.07, fit_fs_hz=500)
    monkeypatch.setattr(tf_extract, "fit_case", fit)
    learned = tmp_path / "learned"
    result = tf_extract.run_extract(source, operator_file, learned)
    assert result["n_windows"] == 5 and result["n_cases"] == 2
    assert result["weights_defined"]
    frozen = json.loads((learned / "feature_config.json").read_text())
    assert frozen["operator"] == dict(operator, fs_hz=500)
    assert np.isfinite(frozen["weights"]).all()
    assert len(calls) == 15
    tf = tf_extract.compute_tf_harmonics(windows[0].art, windows[0].pleth)
    assert calls[0][1] is None
    masks = []
    for parity in (0, 1):
        expected = np.zeros(len(t), bool)
        for start, end in tf["beat_feet_s"][parity::2]:
            expected |= (t >= start) & (t < end)
        actual = calls[parity + 1][1][0]
        np.testing.assert_array_equal(actual, expected)
        assert actual.dtype == np.bool_ and actual.any()
        masks.append(actual)
    assert not np.any(masks[0] & masks[1])
    table = pd.read_csv(learned / "features.csv")
    for name in ("group_delay_residual_s", "h1_phase_delay_residual_s"):
        for cid, rows in table.groupby("caseid"):
            raw = {prefix: [] for prefix in ("", "odd_", "even_")}
            for w in [w for w in windows if w.caseid == cid]:
                descriptor = tf_extract.compute_tf_harmonics(w.art, w.pleth)
                for prefix, estimate in (("", descriptor), ("odd_", descriptor["odd"]),
                                         ("even_", descriptor["even"])):
                    delay = fit_delay(estimate["H"], descriptor["frequencies_hz"],
                                      frozen["operator"], frozen["weights"])
                    raw[prefix].append(delay["tau_s"] if name.startswith("group")
                                       else delay["h1_phase_delay_s"])
            common = np.mean(raw[""])
            np.testing.assert_allclose(rows[name + "_case_common_s"], common)
            for prefix in raw:
                np.testing.assert_allclose(rows[prefix + name], np.array(raw[prefix]) - common,
                                           atol=1e-12)
    replay = tmp_path / "replay"
    tf_extract.run_extract(source, operator_file, replay,
                           feature_config=learned / "feature_config.json")
    pd.testing.assert_frame_equal(table, pd.read_csv(replay / "features.csv"))
    wrong_operator = tmp_path / "wrong_operator.json"
    wrong_operator.write_text(json.dumps(dict(operator, hi_hz=11.)))
    with pytest.raises(ValueError, match="Frozen feature/operator"):
        tf_extract.run_extract(source, wrong_operator, tmp_path / "mismatch",
                               feature_config=learned / "feature_config.json")
    # Empty selection preserves explicit unestimable weights and readable coverage.
    loaded.clear()
    empty = tmp_path / "empty"
    result = tf_extract.run_extract(source, operator_file, empty)
    assert result["n_windows"] == 0 and not result["weights_defined"]
    assert pd.read_csv(empty / "features.csv").empty
    assert pd.read_csv(empty / "reliability.csv")["n_paired_windows"].eq(0).all()
    # A saved undefined primary configuration still permits the H1 fallback.
    loaded.extend(windows[:1])
    fallback = tmp_path / "fallback"
    result = tf_extract.run_extract(source, operator_file, fallback,
                                   feature_config=empty / "feature_config.json")
    assert not result["weights_defined"]
    fallback_table = pd.read_csv(fallback / "features.csv")
    assert fallback_table["group_delay_residual_s"].isna().all()
    assert fallback_table["h1_phase_delay_residual_s"].notna().all()
    for directory in (learned, replay, empty, fallback):
        for path in directory.glob("*.json"):
            json.loads(path.read_text(), parse_constant=lambda value: pytest.fail(value))
