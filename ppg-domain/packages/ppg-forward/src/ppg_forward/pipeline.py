"""Small public orchestration layer; numerical work stays in package drivers."""
import importlib
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from . import __version__
from .manifests import dump, metadata_path, validate_run


def doctor(out):
    modules = {}
    for name in ("numpy", "scipy", "pandas", "pyarrow", "vitaldb", "peripheral_ppg", "mcx", "statsmodels"):
        try:
            importlib.import_module(name)
            modules[name] = {"available": True}
        except Exception as exc:
            modules[name] = {"available": False, "error": str(exc)}
    checks = {}
    for name, module, symbol in (
        ("selection", "ppg_forward.selection_driver", "run_select"),
        ("harmonics", "ppg_forward.tf_harmonics", "compute_tf_harmonics"),
        ("harmonic_delay", "ppg_forward.tf_delay", "fit_delay"),
        ("mixed_decomposition", "ppg_forward.tf_statistics", "decompose_feature"),
        ("fitting", "ppg_forward.round2_driver", "run_fit"),
        ("evaluation", "ppg_forward.round2_driver", "run_evaluate"),
        ("cross_window", "ppg_forward.round2_driver", "run_cross_window"),
        ("mcx_linear", "ppg_forward.mcx_driver", "run_from_config"),
    ):
        try:
            checks[name] = {"available": callable(getattr(importlib.import_module(module), symbol))}
        except Exception as exc:
            checks[name] = {"available": False, "error": str(exc)}
    try:
        from .fit import model_module
        model_module("M3")
        from peripheral_ppg.model import local_model
        if not callable(local_model):
            raise ImportError("M3 peripheral local_model is not callable")
        checks["M3"] = {"available": True}
    except Exception as exc:
        checks["M3"] = {"available": False, "error": str(exc)}
    executable = shutil.which("mcx")
    local_mcx = Path("/data/liuyihan/FermiLink/ppg-domain/.runtime/mcx/venv/bin/mcx")
    if executable is None and local_mcx.is_file():
        executable = str(local_mcx)
    mcx_cli = {"path": executable, "available": False}
    if executable:
        try:
            completed = subprocess.run([executable, "--help"], capture_output=True,
                                       text=True, timeout=20, check=False)
            mcx_cli.update(available=completed.returncode == 0,
                           returncode=completed.returncode,
                           output=(completed.stdout + completed.stderr).strip())
        except (OSError, subprocess.TimeoutExpired) as exc:
            mcx_cli["error"] = str(exc)
    ready = (all(check["available"] for check in checks.values()) and mcx_cli["available"]
             and all(modules[name]["available"] for name in
                     ("numpy", "scipy", "pandas", "pyarrow", "vitaldb", "peripheral_ppg", "statsmodels")))
    result = {"package_version": __version__, "python": sys.executable,
              "python_version": platform.python_version(), "modules": modules,
              "capabilities": checks, "mcx_cli": mcx_cli,
              "status": "complete" if ready else "blocked", "solver_executed": False}
    dump(Path(out) / "doctor.json", result)
    return result


def segment_root(path):
    path = Path(path).absolute()
    return path / "work" if (path / "work" / "selection.json").is_file() else path


def fits_root(path):
    path = Path(path).absolute()
    return path / "work" if (path / "work" / "fit_context.json").is_file() else path


def metadata_inputs(path):
    """Enumerate a derived metadata directory, never a raw-data directory."""
    path = metadata_path(path)
    if path.is_file():
        return [path]
    result = []
    for item in sorted(path.rglob("*")):
        if item.is_file():
            metadata_path(item)
            result.append(item)
    for item in list(result):
        if item.name == "selection.json":
            selection = json.loads(item.read_text())
            for key in ("split_path", "cases_path"):
                if selection.get(key):
                    result.append(metadata_path(selection[key]))
    return list(dict.fromkeys(result))


def record_result(run, result):
    result = result or {}
    # Drivers can add explicit metadata references, not raw files or full scans.
    paths = result.get("input_files", result.get("input_paths", []))
    run.add_inputs(list(paths) + list(result.get("consulted_scan_paths", [])))
    # Raw readers already report each physical open through the callback.
    run.result = result
    return result


def select_segments(args, run):
    from .selection_driver import run_select
    (run.out / "work").mkdir()
    return record_result(run, run_select(args.split, args.cases, run.out / "work",
        allow_splits=tuple(args.allow_splits.split(",")), config_path=args.config,
        event_policy=args.event_policy, raw_access_callback=run.raw_open))


def fit(args, run):
    from .round2_driver import run_fit
    operator = None
    if args.operator != "fit-global":
        if not args.operator.startswith("frozen:") or not args.operator[7:]:
            raise ValueError("--operator must be fit-global or frozen:FILE")
        operator = Path(args.operator[7:]).absolute()
        run.add_inputs([operator])
    return record_result(run, run_fit(segment_root(args.segments),
        args.models.split(","), operator, run.out / "work",
        raw_access_callback=run.raw_open, max_nfev=args.max_nfev,
        candidates=args.operator_candidates))


def fit_context(fits):
    root = fits_root(fits)
    context = json.loads((root / "fit_context.json").read_text(encoding="utf-8"))
    return root, Path(context["segments_dir"])


def evaluate(args, run):
    from .round2_driver import run_evaluate
    fits, segments = fit_context(args.fits)
    run.add_inputs(metadata_inputs(segments))
    return record_result(run, run_evaluate(segments, fits, run.out / "work",
        raw_access_callback=run.raw_open, prereg_path=args.prereg))


def cross_window(args, run):
    from .round2_driver import run_cross_window
    fits, segments = fit_context(args.fits)
    run.add_inputs(metadata_inputs(segments))
    return record_result(run, run_cross_window(segments, fits, run.out / "work",
        raw_access_callback=run.raw_open))


def mcx_linear(args, run):
    from .mcx_driver import run_from_config
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    result = run_from_config(config, run.out / "work")
    result = record_result(run, result)
    if result.get("study_status") in ("prepared", "blocked"):
        result["status"] = result["study_status"]
    return result


def validate(args, run):
    report = validate_run(args.directory)
    dump(run.out / "validation.json", report)
    if not report["valid"]:
        raise ValueError("Run validation failed: " + "; ".join(report["errors"]))
    return report
