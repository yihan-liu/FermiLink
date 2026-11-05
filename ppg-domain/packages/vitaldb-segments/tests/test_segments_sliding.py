"""Synthetic scan/event checks for Round 3; no patient raw access."""
import numpy as np
import pandas as pd

from vitaldb_segments import segments as s


def _bins(end):
    return pd.DataFrame(dict(t_s=np.arange(0., end, 10.), quality_ok=True,
                             ple_amp=10., map=80., hr=60., ibi_cv=.01))


def _event(duration=6000):
    return dict(dur_s=duration, recorded_pump_rates={}, events=[], flush=[])


def _select(bins, event=None, **kwargs):
    return s.case_sliding_windows(11, scan_dir="unused", ibi_cv_cutoff=.04,
        gain_step_factor=1.5, event_policy=s.EVENT_POLICY,
        recorded_events=_event() if event is None else event, scan_bins=bins, **kwargs)


def test_union_time_gate_precedes_sparse_sampling(monkeypatch):
    # Overlapping duplicate scan intervals cannot manufacture qualifying time.
    bins = _bins(3600)
    bins = pd.concat([bins, bins], ignore_index=True).sort_values("t_s")
    rejected = _select(bins.iloc[:-2])
    assert rejected.empty and not rejected.attrs["eligible"]
    assert rejected.attrs["qualifying_time_s"] == 3590.
    # The sparse output totals only 900 s, but the case has 3600 qualifying s.
    accepted = _select(_bins(3600))
    assert accepted.attrs["eligible"]
    assert accepted.attrs["qualifying_time_s"] == 3600.
    assert len(accepted) == 30
    assert (accepted.end_s - accepted.start_s).sum() == 900.
    # No candidate construction, and hence no window verification, for a reject.
    monkeypatch.setattr(s, "case_candidates",
                        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("candidate access")))
    assert _select(_bins(3590)).empty


def test_first80_grid_and_recorded_exclusions():
    event = _event(duration=6000)  # first80 ends at 4800
    event["recorded_pump_rates"] = {"pump": [(0., 0.), (1200., 1.), (1500., 0.)]}
    event["events"] = [dict(kind="nibp", t_s=3000.)]
    windows = _select(_bins(6000), event)
    assert windows.attrs["qualifying_time_s"] == 3180.
    assert windows.empty  # 4800 - union([600,2100], [2940,3060]) < 3600
    windows = _select(_bins(6000), event, min_qualifying_time_s=3000)
    assert (windows.start_s % 120 == 0).all()
    assert (windows.start_s.diff().dropna() >= 120).all()
    assert (windows.end_s <= 4800).all()
    for a, b in s.event_exclusions(event, policy=s.EVENT_POLICY):
        assert not ((windows.start_s < b) & (windows.end_s > a)).any()
    assert windows.start_s.min() == 0.
    assert 2160. in windows.start_s.to_list()


def test_quality_gain_step_gaps_and_round2_behavior_unchanged():
    bins = _bins(4800)
    bins.loc[bins.t_s == 120., "quality_ok"] = False
    bins.loc[bins.t_s >= 250., "ple_amp"] = 30.
    result = _select(bins)
    assert result.attrs["qualifying_time_s"] == 4770.
    assert 120. not in result.start_s.to_list()
    assert 240. not in result.start_s.to_list()
    assert 360. in result.start_s.to_list()
    spaced_candidates = s.case_candidates(11, scan_dir="unused", ibi_cv_cutoff=.04,
        gain_step_factor=1.5, event_policy=s.EVENT_POLICY,
        recorded_events=_event(), scan_bins=bins)
    chosen = s.choose_windows(spaced_candidates)
    assert len(chosen) == 3
    assert (chosen.start_s.diff().dropna() >= 600).all()
    assert 10. in spaced_candidates.start_s.to_list()
    assert 10. not in result.start_s.to_list()
