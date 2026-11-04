"""Select explicit cases from derived scans and verify exact raw windows."""
import json
from pathlib import Path
import re

import pandas as pd

from ppg_forward.segments import (
    RAW, EVENT_POLICY, WindowAuthorization, read_recorded_events, _raw_path, allowed_cases, case_candidates,
    choose_windows, load_window, stratified_cases, case_scan_bins, calibrate_gain_step, gain_step_flags,
)


def read_case_ids(path):
    """Read an explicit CSV caseid column or a whitespace/comma-separated list."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        values = pd.read_csv(path)["caseid"].tolist()
    else:
        values = re.split(r"[\s,]+", path.read_text().strip())
    ids = list(dict.fromkeys(int(v) for v in values if str(v).strip()))
    if not ids:
        raise ValueError("An explicit nonempty case list is required")
    return ids


def run_select(split_path, cases_path, out_dir, *, allow_splits=("train",),
               config_path=None, event_policy=None, raw_access_callback=None):
    """Write metadata only; callers own fresh run creation and the manifest.

    Config requires scan_dir and gain_step_factor. Event policy has no default:
    owner-20261104-drugpump-rate-nibp is the active recorded-event rule.
    """
    if config_path is None:
        raise ValueError("Selection requires an explicit config JSON")
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text())
    event_policy = event_policy or config.get("event_policy")
    if event_policy != EVENT_POLICY:
        raise ValueError("An explicit approved event policy is required")
    scan_dir = Path(config["scan_dir"]).resolve()
    raw_dir = Path(config.get("raw_dir", RAW)).absolute()
    factor_input = config["gain_step_factor"]
    factor = None if factor_input == "train-p995" else float(factor_input)
    cutoff = float(config.get("ibi_cv_cutoff", .037145875))
    count = int(config.get("windows_per_case", 3))
    if (factor is not None and not factor > 1) or not 0 < cutoff <= .3 or count not in (3, 4, 5):
        raise ValueError("Require gain factor >1, CV cutoff in (0,.3], and 3-5 windows")
    split_path, cases_path = Path(split_path).resolve(), Path(cases_path).resolve()
    ids = read_case_ids(cases_path)
    for cid in ids:
        _raw_path(cid, raw_dir)
    allowed = set(allowed_cases(split_path, allow_splits))
    if set(ids) - allowed:
        raise PermissionError("Explicit cases include a disallowed split or source")
    out_dir = Path(out_dir)
    if not out_dir.is_dir():
        raise ValueError("Caller must allocate a fresh run directory")
    if any((out_dir / name).exists() for name in ("windows.csv", "cases.csv", "availability.csv", "selection.json")):
        raise FileExistsError("Selection outputs already exist")
    windows, cases, availability, consulted = [], [], [], []
    recorded_events, bins = {}, {}
    if factor is None and tuple(str(v).lower() for v in allow_splits) != ("train",):
        raise PermissionError("Gain calibration requires Train only")
    scalar_auth = WindowAuthorization(pd.DataFrame(), split_path, scan_dir, raw_dir,
                                      tuple(allow_splits), event_policy, explicit_caseids=tuple(ids))
    for cid in ids:
        consulted += [str(scan_dir / "events" / f"{cid}.json"),
                      str(scan_dir / "windows" / f"{cid}.parquet")]
        recorded_events[cid] = read_recorded_events(cid, authorization=scalar_auth,
                                                    raw_access_callback=raw_access_callback)
        bins[cid] = case_scan_bins(cid, scan_dir=scan_dir, ibi_cv_cutoff=cutoff,
                                  event_policy=event_policy, recorded_events=recorded_events[cid])
    calibration = calibrate_gain_step(bins.values()) if factor is None else dict(
        mode="explicit", factor=factor, interpretation="extreme amplitude-step screening; not proven AGC")
    factor = calibration["factor"]
    calibration["first80_bins"] = sum(d.attrs["first80_bins"] for d in bins.values())
    calibration["event_excluded_bins"] = sum(d.attrs["event_excluded_bins"] for d in bins.values())
    calibration["quality_rejected_bins"] = sum(int((~d.quality_ok).sum()) for d in bins.values() if not d.empty)
    calibration["quality_bins"] = sum(int(d.quality_ok.sum()) for d in bins.values() if not d.empty)
    calibration["gain_flagged_bins"] = sum(int(gain_step_flags(d, factor).sum()) for d in bins.values() if not d.empty)
    for cid in ids:
        candidates = case_candidates(cid, scan_dir=scan_dir, ibi_cv_cutoff=cutoff,
                                     gain_step_factor=factor, event_policy=event_policy,
                                     recorded_events=recorded_events[cid], scan_bins=bins[cid])
        selected = choose_windows(candidates, count=count)
        availability.append(dict(caseid=cid, candidates=len(candidates), selected=len(selected),
            first80_bins=bins[cid].attrs["first80_bins"],
            event_excluded_bins=bins[cid].attrs["event_excluded_bins"],
            quality_bins=int(bins[cid].quality_ok.sum()) if not bins[cid].empty else 0))
        if len(selected) < count:
            continue
        windows.append(selected)
        cases.append(dict(caseid=cid, MAP=float(candidates.MAP.median()),
                          HR=float(candidates.HR.median()), zeta=float(candidates.zeta.iloc[0]),
                          fn_hz=float(candidates.fn_hz.iloc[0]),
                          frequency_kind="ring_peak",
                          catheter_status=candidates.catheter_status.iloc[0],
                          map_pair_ge15=bool(selected.map_pair_ge15.iloc[0])))
    if not cases:
        raise ValueError("No explicit cases have the requested eligible windows")
    requested_count = int(config.get("n_cases", len(cases)))
    if requested_count < 1:
        raise ValueError("n_cases must be positive")
    case_table = stratified_cases(pd.DataFrame(cases), requested_count)
    table = pd.concat(windows, ignore_index=True)
    table = table.loc[table.caseid.isin(case_table.caseid)].sort_values(["caseid", "start_s"])
    auth = WindowAuthorization(table, split_path, scan_dir, raw_dir,
                               tuple(allow_splits), event_policy, recorded_events)
    # Verify only final exact windows. No waveform arrays are saved.
    for row in table.itertuples(index=False):
        load_window(row.caseid, row.start_s, row.end_s, authorization=auth,
                    fs_hz=500, raw_access_callback=raw_access_callback)
    case_table.to_csv(out_dir / "cases.csv", index=False)
    table.to_csv(out_dir / "windows.csv", index=False)
    metadata = dict(split_path=str(split_path), cases_path=str(cases_path),
                    scan_dir=str(scan_dir), raw_dir=str(raw_dir),
                    allow_splits=list(allow_splits), event_policy=event_policy,
                    ibi_cv_cutoff=cutoff, gain_step_factor=factor,
                    windows_per_case=count, requested_caseids=ids,
                    event_scope="recorded data only; absent rates do not establish drug absence",
                    nibp_rule="Round1 Solar8000/NIBP_SBP value change or >120s consecutive-sample gap; +/-60s",
                    pump_rule="all recorded Orchestra/*_RATE or drugpump*_RATE; rate>0 and every change +/-600s",
                    pump_track_counts={str(cid): len(ev["recorded_pump_rates"]) for cid, ev in recorded_events.items()},
                    availability=availability, gain_step_calibration=calibration, n_cases=requested_count)
    (out_dir / "selection.json").write_text(json.dumps(metadata, indent=2))
    return dict(outputs=[str(out_dir / n) for n in
                         ("windows.csv", "cases.csv", "selection.json")],
                input_paths=[str(split_path), str(cases_path), str(config_path)],
                consulted_scan_paths=consulted,
                selected_cases=len(case_table), selected_windows=len(table),
                selection_shortfall=max(0, requested_count-len(case_table)),
                candidate_pool_shortfall=len(ids)-len(cases),
                gain_step_calibration=calibration)
