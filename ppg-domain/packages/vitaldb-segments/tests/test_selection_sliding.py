"""Synthetic sliding-driver integration; numeric and raw readers are mocked."""
import json

import numpy as np
import pandas as pd
import pytest

from vitaldb_segments import selection as driver


@pytest.mark.parametrize("durations", [(3600, 4800, 3590), (3590, 1200, 0)])
def test_sliding_keeps_explicit_eligible_cohort_and_reports_empty_pool(tmp_path, monkeypatch, durations):
    ids = [11, 21, 31]
    split = tmp_path / "splits.csv"
    pd.DataFrame(dict(caseid=ids, split="train", source_dir="vital_dev")).to_csv(split, index=False)
    cases = tmp_path / "ids.txt"
    cases.write_text("11,21,31")
    config = tmp_path / "config.json"
    config.write_text(json.dumps(dict(scan_dir=str(tmp_path), raw_dir=str(tmp_path / "vital_dev"), gain_step_factor=1.5,
        event_policy=driver.EVENT_POLICY, selection_mode="sliding",
        n_cases=1, windows_per_case=0)))
    calls, opened = [], []
    def numeric(cid, **kwargs):
        assert tuple(kwargs["authorization"].allow_splits) == ("train",)
        assert tuple(kwargs["authorization"].explicit_caseids) == tuple(ids)
        calls.append(("numeric", cid))
        return dict(dur_s=6000, recorded_pump_rates={}, events=[], flush=[])
    def scan(cid, **kwargs):
        assert ("numeric", cid) in calls
        calls.append(("scan", cid))
        times = np.arange(0., durations[ids.index(cid)], 10.)
        d = pd.DataFrame(dict(t_s=times, quality_ok=True, ple_amp=10.,
                              map=80., hr=60., ibi_cv=.01))
        d.attrs.update(first80_bins=480, event_excluded_bins=0)
        return d
    def verify(cid, a, b, **kwargs):
        assert kwargs["fs_hz"] == 500
        assert kwargs["raw_access_callback"] is callback
        assert set(kwargs["authorization"].recorded_events) == set(ids)
        assert b - a == 30 and a % 120 == 0
        opened.append((cid, a, b))
    callback = object()
    monkeypatch.setattr(driver, "read_recorded_events", numeric)
    monkeypatch.setattr(driver, "case_scan_bins", scan)
    monkeypatch.setattr(driver, "load_window", verify)
    monkeypatch.setattr(driver, "choose_windows", lambda *a, **kw: pytest.fail("Round2 sampling"))
    monkeypatch.setattr(driver, "stratified_cases", lambda *a, **kw: pytest.fail("cohort subsampling"))
    out = tmp_path / "out"
    out.mkdir()
    result = driver.run_select(split, cases, out, config_path=config, raw_access_callback=callback)
    meta = json.loads((out / "selection.json").read_text())
    selected_cases = pd.read_csv(out / "cases.csv")
    windows = pd.read_csv(out / "windows.csv")
    expected_ids = [cid for cid, duration in zip(ids, durations) if duration >= 3600]
    assert selected_cases.caseid.tolist() == expected_ids
    assert result["selected_cases"] == len(expected_ids)
    assert result["selected_windows"] == len(opened) == len(windows)
    assert result["input_paths"] == [str(split), str(cases), str(config)]
    assert len(result["consulted_scan_paths"]) == 6
    assert meta["requested_caseids"] == ids
    assert meta["windows_per_case"] is None
    assert meta["n_cases"] == len(expected_ids)
    assert meta["selection_mode"] == "sliding"
    assert meta["stride_s"] == 120
    assert meta["min_qualifying_time_s"] == 3600
    assert meta["qualifying_time_resolution_s"] == 10
    assert meta["qualifying_time_s"] == {str(cid): float(t) for cid, t in zip(ids, durations)}
    assert meta["pump_track_counts"] == {str(cid): 0 for cid in ids}
    for entry, duration in zip(meta["availability"], durations):
        assert entry["qualifying_time_s"] == duration
        assert entry["eligible"] == (duration >= 3600)
        assert entry["reason"] == ("selected" if duration >= 3600 else "qualifying_time_below_minimum")
    if expected_ids:
        assert len(windows) == 70  # 30 + 40; n_cases=1 never clips the cohort.
        assert not selected_cases.map_pair_ge15.any()
    else:
        assert windows.empty and selected_cases.empty and not opened
        assert {"caseid", "start_s", "end_s"} <= set(windows.columns)
