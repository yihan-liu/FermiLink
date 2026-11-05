"""Synthetic packet and metadata checks; never open patient files."""
import gzip
import json
import struct
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from vitaldb_segments import segments as s
from vitaldb_segments.selection import run_select


def _string(value):
    value = value.encode()
    return struct.pack("<I", len(value)) + value


def _packet(kind, payload):
    return struct.pack("<BI", kind, len(payload)) + payload


def _track(tid, name, kind=2, did=1):
    return _packet(0, struct.pack("<HBB", tid, kind, 1) + _string(name) + _string("")
                   + struct.pack("<ffIfddBI", 0., 100., 0, 500. if kind == 1 else 0., 1., 0., 0, did))


def _scalar(tid, time, value):
    return _packet(1, struct.pack("<HdHf", 10, 1000. + time, tid, value))


def test_numeric_pass_skips_waveforms_and_records_all_pumps_first80(tmp_path, monkeypatch):
    path = tmp_path / "synthetic.vital"
    header = bytes(10) + struct.pack("<d", 1000.) + bytes(8)
    device = _packet(9, struct.pack("<I", 1) + _string("Orchestra") + _string("Orchestra"))
    # An intentionally invalid waveform sample payload cannot be decoded.
    waveform = _packet(1, struct.pack("<HdH", 10, 1000., 3) + b"opaque-not-samples")
    data = b"VITA" + bytes(4) + struct.pack("<H", len(header)) + header + device
    data += _track(1, "PPF20_RATE") + _track(2, "drugpump17_RATE") + _track(3, "PLETH", 1)
    data += waveform + _scalar(1, 0., 1.) + _scalar(1, 100., 1.01)
    data += _scalar(2, 0., 0.) + _scalar(2, 200., 2.) + _scalar(1, 4000., 999.)
    with gzip.open(path, "wb") as stream:
        stream.write(data)
    monkeypatch.setattr(np, "frombuffer", lambda *a, **kw: pytest.fail("waveform decoded"))
    opens = []
    rates = s._read_numeric_rates(path, 3200., caseid=11,
                                  raw_access_callback=lambda p, **kw: opens.append((p, kw)))
    assert rates == {"Orchestra/PPF20_RATE": [(0., 1.), (100., pytest.approx(1.01))],
                     "Orchestra/drugpump17_RATE": [(0., 0.), (200., 2.)]}
    assert len(opens) == 1 and opens[0][1]["access_kind"] == "numeric-events"
    assert opens[0][1]["duration_s"] == 3200.
    assert s._is_pump_rate("drugpump2/OTHER_RATE")
    assert s._is_pump_rate("Other/drugpump3_RATE")
    assert not s._is_pump_rate("Other/RESP_RATE")


def _event(rates=None):
    return dict(dur_s=10000., events=[], flush=[], recorded_pump_rates={} if rates is None else rates)


def _blocked(intervals, time):
    return any(a <= time < b for a, b in intervals)


def test_all_rate_changes_initial_status_and_nibp_flush_masks():
    event = _event({"Orchestra/PPF20_RATE": [(0., 1.), (1500., 1.01), (2000., 0.), (5000., 0.)]})
    event["events"] = [dict(kind="nibp", t_s=4000.)]
    event["flush"] = [dict(t_s=6000., dur_s=2.)]
    blocked = s.event_exclusions(event, policy=s.EVENT_POLICY)
    assert _blocked(blocked, 0.) and _blocked(blocked, 2599.)
    assert (900., 2100.) in blocked  # a 1% change is retained
    assert not _blocked(blocked, 2600.)
    assert _blocked(blocked, 3940.) and _blocked(blocked, 4059.)
    assert not _blocked(blocked, 4060.)
    assert _blocked(blocked, 5990.) and _blocked(blocked, 6011.)
    assert not _blocked(blocked, 6012.)
    assert s.event_exclusions(_event({"pump": []}), policy=s.EVENT_POLICY) == [(0., 8000.)]
    unknown = s.event_exclusions(_event({"pump": [(100., 0.)]}), policy=s.EVENT_POLICY)
    assert unknown == [(0., 100.)]
    # No recorded tracks is unknown coverage, not a claim of drug absence.
    assert s.event_exclusions(_event(), policy=s.EVENT_POLICY) == []
    with pytest.raises(ValueError):
        s.event_exclusions(dict(dur_s=100., events=[], flush=[]), policy=s.EVENT_POLICY)
    with pytest.raises(ValueError):
        s.event_exclusions(event, policy="conservative-no-tci")


def _authorization(tmp_path, monkeypatch):
    raw = tmp_path / "vital_dev"
    raw.mkdir()
    split = tmp_path / "split.csv"
    pd.DataFrame(dict(caseid=[11, 12, 13, 14], split=["train", "test", "validation", "train"],
                      source_dir=["vital_dev", "vital_dev", "vital_dev", "dev_reserve"])).to_csv(split, index=False)
    return s.WindowAuthorization(pd.DataFrame(dict(caseid=[11], start_s=[0.], end_s=[30.])),
                                  split, tmp_path, raw, ("train",), s.EVENT_POLICY)


def test_split_source_raw_path_and_explicit_case_refused_before_open(tmp_path, monkeypatch):
    auth = _authorization(tmp_path, monkeypatch)
    monkeypatch.setattr(s.gzip, "open", lambda *a, **k: pytest.fail("unauthorized open"))
    for caseid in (12, 13, 14):
        with pytest.raises(PermissionError):
            s.read_recorded_events(caseid, authorization=auth, event=_event())
    for directory in (tmp_path / "vital", tmp_path / "dev_reserve" / "vital_dev"):
        auth.raw_dir = directory
        with pytest.raises(PermissionError):
            s.read_recorded_events(11, authorization=auth, event=_event())
    auth.raw_dir = tmp_path / "vital_dev"
    auth.windows = pd.DataFrame()
    with pytest.raises(PermissionError):
        s.read_recorded_events(11, authorization=auth, event=_event())
    with pytest.raises(PermissionError):
        s.allowed_cases(auth.split_path, ("test",))


def test_first80_and_exact_interval_refused_before_open(tmp_path, monkeypatch):
    auth = _authorization(tmp_path, monkeypatch)
    (tmp_path / "events").mkdir()
    (tmp_path / "events" / "11.json").write_text(json.dumps(_event()))
    monkeypatch.setattr(s.gzip, "open", lambda *a, **k: pytest.fail("unauthorized open"))
    auth.windows = pd.DataFrame(dict(caseid=[11], start_s=[7990.], end_s=[8020.]))
    with pytest.raises(PermissionError):
        s.load_window(11, 7990., 8020., authorization=auth)
    with pytest.raises(PermissionError):
        s.load_window(11, 0., 30., authorization=auth)


def test_event_mask_precedes_pleth_scan_columns(tmp_path, monkeypatch):
    times = np.arange(0., 2000., 10.)
    data = pd.DataFrame(dict(t_s=times, art_nan=0., dbp=60., sbp=100., art_max=110., hr=60.,
        ibi_cv=.02, map=80., ple_nan=0., ple_floor=0., ple_clip=0., ple_amp=10., ple_p95=100., hr_ple=60.))
    monkeypatch.setattr(s.pq, "read_schema", lambda p: SimpleNamespace(names=list(data.columns)))
    calls = []
    def read(path, columns, filters):
        calls.append((columns, filters))
        if "ple_amp" in columns:
            allowed = filters[0][2]
            assert min(allowed) == 1160.  # active 0-500, change pad to1100, NIBP 1100 +/-60
            return data.loc[data.t_s.isin(allowed), columns]
        return data.loc[:, columns]
    monkeypatch.setattr(s.pd, "read_parquet", read)
    event = _event({"pump": [(0., 1.), (500., 0.)]})
    event["events"] = [dict(kind="nibp", t_s=1100.)]
    bins = s.case_scan_bins(11, scan_dir=tmp_path, ibi_cv_cutoff=.04,
                            event_policy=s.EVENT_POLICY, recorded_events=event)
    assert len(calls) == 2 and "ple_amp" not in calls[0][0] and bins.t_s.min() == 1160.


def test_calibration_no_join_across_removed_bins_and_step_adjacent_flags():
    d = pd.DataFrame(dict(t_s=[0., 10., 30., 40., 50.], ple_amp=[10., 11., 110., 111., 1000.],
                          quality_ok=[True, True, True, True, False]))
    result = s.calibrate_gain_step([d])
    assert result["valid_pairs"] == 2 and result["factor"] == 1.5
    assert s.gain_step_flags(d, 2.).tolist() == [False, False, False, True, True]
    with pytest.raises(ValueError):
        s.calibrate_gain_step([d.iloc[:1]])


def test_window_spacing_map_pair_and_gap_rejection(tmp_path):
    d = pd.DataFrame(dict(start_s=[0., 600., 1200., 1800.], MAP=[80., 82., 100., 90.], ibi_cv=.01))
    chosen = s.choose_windows(d)
    assert len(chosen) == 3 and chosen.start_s.diff().dropna().min() >= 600.
    assert chosen.map_pair_ge15.all()
    bins = pd.DataFrame(dict(t_s=[0., 10., 30., 40.], quality_ok=True,
        ple_amp=10., map=80., hr=60., ibi_cv=.01))
    assert s.case_candidates(11, scan_dir=tmp_path, ibi_cv_cutoff=.04,
        gain_step_factor=1.5, event_policy=s.EVENT_POLICY, recorded_events=_event(), scan_bins=bins).empty


def test_selector_calibrates_pool_caps_before_raw_verify_and_writes_metadata(tmp_path, monkeypatch):
    from vitaldb_segments import selection as driver
    auth = _authorization(tmp_path, monkeypatch)
    # Replace the synthetic split with three explicitly authorized Train cases.
    pd.DataFrame(dict(caseid=[11, 21, 31], split="train", source_dir="vital_dev")).to_csv(auth.split_path, index=False)
    cases = tmp_path / "ids.txt"
    cases.write_text("11,21,31")
    config = tmp_path / "config.json"
    config.write_text(json.dumps(dict(scan_dir=str(tmp_path), raw_dir=str(tmp_path / "vital_dev"),
        gain_step_factor="train-p995", event_policy=s.EVENT_POLICY, n_cases=2)))
    opened, consulted = [], []
    def numeric(caseid, **kwargs):
        consulted.append(caseid)
        assert set(kwargs["authorization"].explicit_caseids) == {11, 21, 31}
        return _event()
    def bins(caseid, **kwargs):
        t = np.r_[np.arange(0., 40., 10.), np.arange(700., 740., 10.), np.arange(1400., 1440., 10.)]
        d = pd.DataFrame(dict(t_s=t, quality_ok=True, ple_amp=10., map=60.+caseid+t/50., hr=60., ibi_cv=.01))
        d.attrs.update(first80_bins=len(d), event_excluded_bins=0)
        return d
    monkeypatch.setattr(driver, "read_recorded_events", numeric)
    monkeypatch.setattr(driver, "case_scan_bins", bins)
    monkeypatch.setattr(driver, "load_window", lambda cid, a, b, **kw: opened.append((cid, a, b)))
    out = tmp_path / "out"
    out.mkdir()
    result = driver.run_select(auth.split_path, cases, out, config_path=config)
    meta = json.loads((out / "selection.json").read_text())
    assert consulted == [11, 21, 31] and len(opened) == 6
    assert result["selected_cases"] == 2 and result["selected_windows"] == 6
    assert meta["gain_step_calibration"]["valid_pairs"] == 27
    assert meta["gain_step_factor"] == 1.5 and len(meta["availability"]) == 3
    assert {p.name for p in out.iterdir()} == {"selection.json", "cases.csv", "windows.csv"}
    assert len(result["consulted_scan_paths"]) == 6


@pytest.mark.parametrize("phase_s", [.0015, .0004, -.0004])
def test_native_window_fractional_packet_phase_stays_inside_bounds(tmp_path, monkeypatch, phase_s):
    """Ceil source slices and their destination share one native sample index."""
    path = tmp_path / "synthetic-native.vital"
    origin, start, end, rate = 1700000000., 2120., 2150., 500.
    epoch = origin + start - 10. + phase_s
    relative = epoch - origin
    source = np.arange(30000, dtype="<f4")
    first = int(np.ceil((start - relative) * rate))
    last = int(np.ceil((end - relative) * rate))
    assert last - first == 15000
    header = bytes(10) + struct.pack("<d", origin) + bytes(8)
    device = _packet(9, struct.pack("<I", 1) + _string("SNUADC") + _string("SNUADC"))
    record = _packet(1, struct.pack("<HdHI", 10, epoch, 1, len(source)) + source.tobytes())
    data = b"VITA" + bytes(4) + struct.pack("<H", len(header)) + header
    data += device + _track(1, "ART", 1) + record
    with gzip.open(path, "wb") as stream:
        stream.write(data)
    decode = np.frombuffer
    decoded = []
    def inside_only(raw, **kwargs):
        values = decode(raw, **kwargs)
        sample_times = relative + values.astype(float) / rate
        assert np.all(sample_times >= start) and np.all(sample_times < end)
        decoded.append(len(values))
        return values
    monkeypatch.setattr(np, "frombuffer", inside_only)
    result = s._read_window(path, start, end, tracks_wanted=("SNUADC/ART",), caseid=11)
    assert decoded == [15000]
    np.testing.assert_array_equal(result["SNUADC/ART"], source[first:last])
