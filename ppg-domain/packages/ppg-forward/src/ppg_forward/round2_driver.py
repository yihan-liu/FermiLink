"""Package APIs for authorized Round-2 fitting and later reevaluation.

These functions perform no segment selection and never enumerate raw sources.
The package CLI owns run allocation, manifests and input/output file hashes.
"""
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import resample_poly

from ppg_forward.fit import (MODEL_MODULES, fit_case, evaluate_case,
    window_diagnostics, parameter_stability, cross_window, calibrate_operator,
    corner_diagnostics)
from ppg_forward.metrics import aggregate_cases
from ppg_forward.segments import load_selected_windows


def _read(value):
    return json.loads(Path(value).read_text()) if isinstance(value, (str, Path)) else value


def _write(path, value):
    def convert(v):
        if isinstance(v, np.generic):
            return v.item()
        if isinstance(v, np.ndarray):
            return v.tolist()
        raise TypeError(type(v).__name__)
    Path(path).write_text(json.dumps(value, indent=2, default=convert, allow_nan=False)+"\n")


def _load(segments_dir, raw_access_callback):
    root = Path(segments_dir).resolve()
    selection_path = root/"selection.json"
    selection = _read(selection_path)
    raw = []
    def opened(path, **scope):
        record = dict(scope, path=str(path))
        raw.append(record)
        if raw_access_callback is not None:
            raw_access_callback(path, **scope)
    windows = list(load_selected_windows(root, fs_hz=500, raw_access_callback=opened))
    grouped = {}
    for window in windows:
        grouped.setdefault(int(window.caseid), []).append(window)
    table_path = Path(selection.get("windows_path", root/"windows.csv"))
    if not table_path.is_absolute():
        table_path = root/table_path
    table = pd.read_csv(table_path)
    catheter = {}
    for caseid, rows in table.groupby("caseid"):
        if not {"fn_hz", "zeta"} <= set(rows):
            continue
        values = rows[["fn_hz", "zeta"]].dropna().drop_duplicates()
        if values.empty:
            continue
        if len(values) != 1:
            raise ValueError("Conflicting per-case catheter estimates in selected windows")
        kind = rows["frequency_kind"].dropna().unique() if "frequency_kind" in rows else []
        if len(kind) != 1 or kind[0] not in ("ring_peak", "damped", "natural"):
            raise ValueError("A supplied catheter estimate requires explicit frequency meaning")
        status = rows["catheter_status"].iloc[0] if "catheter_status" in rows else "unknown"
        catheter[str(int(caseid))] = {
            "fn_hz": float(values.iloc[0].fn_hz), "zeta": float(values.iloc[0].zeta),
            "frequency_kind": "damped" if kind[0] == "ring_peak" else str(kind[0]),
            "source_frequency_kind": str(kind[0]), "source_status": str(status),
            "conversion": "natural fn=fd/sqrt(1-zeta^2)" if kind[0] in ("ring_peak", "damped") else "none"}
    inputs = [str(selection_path), str(table_path.resolve())]
    if "split_path" in selection:
        inputs.append(str(Path(selection["split_path"]).resolve()))
    if "scan_dir" in selection:
        inputs.extend(str(Path(selection["scan_dir"])/"events"/f"{caseid}.json") for caseid in grouped)
    return grouped, catheter, raw, inputs


def _low(windows):
    result = []
    for w in windows:
        art, pleth = resample_poly(w.art, 1, 10), resample_poly(w.pleth, 1, 10)
        result.append(replace(w, art=art, pleth=pleth, fs_hz=50,
                              time_s=w.start_s+np.arange(len(art))/50))
    return result


def _summary(results):
    summary = {}
    for branch in ("uncorrected", "corrected"):
        for model in sorted({r["model"] for r in results}):
            subset = [r for r in results if r["model"] == model and r["branch"] == branch]
            rows = [w for r in subset if r.get("available") for w in r.get("native_500hz_windows", [])]
            summary[branch+"_"+model] = dict(aggregate_cases(rows),
                available_cases=sum(r.get("available", False) for r in subset),
                unavailable_cases=sum(not r.get("available", False) for r in subset),
                converged_cases=sum(r.get("available", False) and r.get("success", False) for r in subset),
                nonconverged_cases=sum(r.get("available", False) and not r.get("success", False) for r in subset),
                defined_windows=sum(w.get("defined", False) for w in rows),
                total_windows=len(rows))
    return summary


def run_fit(segments_dir, models, operator, out_dir, raw_access_callback=None, *,
            max_nfev=200, candidates=None):
    """Fit all requested models/branches; operator=None calibrates on pilot M0.

    out_dir is an already allocated fresh CLI work directory. No manifest or
    shared project state is written here. No raw waveform is saved in outputs.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    models = list(models)
    if not models or not set(models) <= set(MODEL_MODULES):
        raise ValueError("models must be a nonempty list drawn from M0-M4")
    high, catheter, raw, inputs = _load(segments_dir, raw_access_callback)
    low = {caseid: _low(windows) for caseid, windows in high.items()}
    candidates_path = str(Path(candidates).resolve()) if isinstance(candidates, (str, Path)) else None
    candidates = _read(candidates)
    if candidates_path:
        inputs.append(candidates_path)
    if operator is None or (isinstance(operator, str) and operator == "fit-global"):
        calibration = calibrate_operator(list(low.values()), candidates, max_nfev=max_nfev)
        op = calibration["operator"]
        _write(out/"operator-calibration.json", calibration)
    else:
        if isinstance(operator, (str, Path)):
            path = str(operator)
            path = path[len("frozen:"):] if path.startswith("frozen:") else path
            inputs.append(str(Path(path).resolve()))
            op = _read(path)
        else:
            op = dict(operator)
    _write(out/"operator.json", op)
    results = []
    names = []
    for caseid, windows in low.items():
        case_results = []
        for branch in ("uncorrected", "corrected"):
            for model in models:
                fit = fit_case(windows, model, op, branch=branch,
                               catheter_params=catheter.get(str(caseid)), max_nfev=max_nfev)
                if fit["available"]:
                    fit["native_500hz_windows"] = evaluate_case(high[caseid], fit)
                    diagnostics = window_diagnostics(windows, model, op, branch=branch,
                        catheter_params=catheter.get(str(caseid)), max_nfev=max_nfev)
                    fit["diagnostic_window_fits"] = diagnostics
                    fit["parameter_stability"] = parameter_stability(diagnostics)
                case_results.append(fit)
        name = f"case-{caseid}.json"
        _write(out/name, case_results)
        names.append(name)
        results.extend(case_results)
    _write(out/"summary.json", _summary(results))
    corners = corner_diagnostics(list(low.values()), op, max_nfev=max_nfev)
    _write(out/"corner-diagnostics.json", corners)
    context = {"segments_dir": str(Path(segments_dir).resolve()), "models": models,
               "operator": op, "max_nfev": max_nfev, "case_results": names,
               "operator_selection": "pilot M0" if operator is None or (isinstance(operator, str) and operator == "fit-global") else "frozen",
               "catheter_params": catheter}
    _write(out/"fit_context.json", context)
    return {"outputs": [str(p.resolve()) for p in out.iterdir() if p.is_file()],
            "fit_context": str((out/"fit_context.json").resolve()),
            "input_files": inputs, "raw_files_opened": raw,
            "summary": _summary(results)}


def _saved(fits_path):
    root = Path(fits_path)
    if not (root/"fit_context.json").exists() and (root/"work"/"fit_context.json").exists():
        root = root/"work"
    context = _read(root/"fit_context.json")
    fits = [f for name in context["case_results"] for f in _read(root/name)]
    return root, context, fits


def run_evaluate(segments_dir, fits_path, out_dir, raw_access_callback=None, *, prereg_path=None):
    """Reload saved parameters, evaluate 500 Hz without global/physiology/PTT fit."""
    root, context, fits = _saved(fits_path)
    if segments_dir is None:
        segments_dir = context["segments_dir"]
    high, _, raw, inputs = _load(segments_dir, raw_access_callback)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for fit in fits:
        if fit["available"]:
            windows = high[int(fit["caseid"])]
            refs = {(r["caseid"], r["start_s"], r["end_s"]) for r in fit["window_refs"]}
            if {(w.caseid, w.start_s, w.end_s) for w in windows} != refs:
                raise ValueError("Evaluation windows differ from saved fit references")
            fit["native_500hz_windows"] = evaluate_case(windows, fit)
        results.append(fit)
    _write(out/"evaluated.json", results)
    summary = _summary(results)
    _write(out/"summary.json", summary)
    inputs += [str(root/"fit_context.json")]+[str(root/n) for n in context["case_results"]]
    if prereg_path is not None:
        inputs.append(str(Path(prereg_path).resolve()))
    return {"outputs": [str((out/n).resolve()) for n in ("evaluated.json", "summary.json")],
            "summary": summary, "input_files": inputs, "raw_files_opened": raw}


def run_cross_window(segments_dir, fits_path, out_dir, raw_access_callback=None, *, max_nfev=200):
    """Cross-window physiological transfer, retaining the saved global operator."""
    root, context, fits = _saved(fits_path)
    if segments_dir is None:
        segments_dir = context["segments_dir"]
    high, _, raw, inputs = _load(segments_dir, raw_access_callback)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for fit in fits:
        if not fit["available"]:
            results.append(fit)
            continue
        caseid = int(fit["caseid"])
        result = cross_window(_low(high[caseid]), fit["model"], fit["operator"],
            branch=fit["branch"], catheter_params=fit.get("catheter_params"), max_nfev=max_nfev)
        if result.get("available"):
            by_start = {w.start_s: w for w in high[caseid]}
            result["fit_grid_degradation_nmse"] = result["degradation_nmse"]
            for label, start in (("a_fit", result["a_start_s"]),
                                 ("transfer_b", result["b_start_s"]),
                                 ("independent_b", result["b_start_s"])):
                result[label]["native_500hz_windows"] = evaluate_case(
                    [by_start[start]], result[label])
            tm = result["transfer_b"]["native_500hz_windows"][0]
            bm = result["independent_b"]["native_500hz_windows"][0]
            result["defined"] = tm["defined"] and bm["defined"]
            result["degradation_nmse"] = float(tm["nmse"]-bm["nmse"]) if result["defined"] else None
        result.update(caseid=caseid, model=fit["model"], branch=fit["branch"])
        results.append(result)
    summary = {}
    for branch in ("uncorrected", "corrected"):
        for model in context["models"]:
            # One selected pair per case, then equal weighting across cases.
            values = [r["degradation_nmse"] for r in results if r["model"] == model
                      and r["branch"] == branch and r.get("defined")]
            summary[branch+"_"+model] = {"n_cases": len(values),
                "mean_degradation_nmse": float(np.mean(values)) if values else None,
                "median_degradation_nmse": float(np.median(values)) if values else None}
    _write(out/"cross-window.json", results)
    _write(out/"summary.json", summary)
    inputs += [str(root/"fit_context.json")]+[str(root/n) for n in context["case_results"]]
    return {"outputs": [str((out/n).resolve()) for n in ("cross-window.json", "summary.json")],
            "summary": summary, "input_files": inputs, "raw_files_opened": raw}
