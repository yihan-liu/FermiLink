"""Command-line entry point for audited VitalDB window selection."""
import argparse
import importlib
import json
from pathlib import Path
import platform
import sys

from ppg_runkit.runs import dump, unique_output

from . import __version__
from .audit import audited_run, validate


def parser():
    ap = argparse.ArgumentParser(prog="vitaldb-segments")
    commands = ap.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Inspect reader dependencies without opening data")
    doctor.add_argument("--out", type=Path)
    select = commands.add_parser("select-segments", help="Select and verify windows for explicit authorized cases")
    select.add_argument("--split", type=Path, required=True)
    select.add_argument("--cases", type=Path, required=True)
    select.add_argument("--allow-splits", default="train")
    select.add_argument("--config", type=Path, required=True, help="Selection settings, scan_dir and raw_dir")
    select.add_argument("--event-policy", help="Explicit event policy name")
    select.add_argument("--out", type=Path, required=True)
    check = commands.add_parser("validate-run")
    check.add_argument("directory", type=Path)
    check.add_argument("--out", type=Path, help="Fresh audit directory; defaults to a unique sibling")
    return ap


def doctor(out):
    modules = {}
    for name in ("numpy", "scipy", "pandas", "pyarrow"):
        try:
            importlib.import_module(name)
            modules[name] = {"available": True}
        except Exception as exc:
            modules[name] = {"available": False, "error": str(exc)}
    ready = all(item["available"] for item in modules.values())
    result = {"package_version": __version__, "python": sys.executable,
              "python_version": platform.python_version(), "modules": modules,
              "status": "complete" if ready else "blocked", "data_opened": False}
    dump(Path(out) / "doctor.json", result)
    return result


def select_segments(args, run):
    from .selection import run_select
    (run.out / "work").mkdir()
    result = run_select(args.split, args.cases, run.out / "work",
        allow_splits=tuple(args.allow_splits.split(",")), config_path=args.config,
        event_policy=args.event_policy, raw_access_callback=run.raw_open)
    run.add_inputs(list(result.get("input_paths", [])) + list(result.get("consulted_scan_paths", [])))
    return result


def validate_command(args, run):
    report = validate(args.directory)
    dump(run.out / "validation.json", report)
    if not report["valid"]:
        raise ValueError("Run validation failed: " + "; ".join(report["errors"]))
    return report


def main(argv=None):
    args = parser().parse_args(argv)
    out = args.out
    if out is None:
        parent = args.directory.absolute().parent if args.command == "validate-run" else None
        out = unique_output(args.command, parent)
    try:
        with audited_run(out, args.command, parameters={k: str(v) if isinstance(v, Path) else v
                                                     for k, v in vars(args).items() if k != "out"}) as run:
            if args.command == "doctor":
                run.result = doctor(run.out)
            elif args.command == "select-segments":
                run.add_inputs([args.split, args.cases, args.config])
                run.result = select_segments(args, run)
            else:
                run.add_inputs([args.directory / "manifest.json"])
                run.result = validate_command(args, run)
        print(json.dumps({"status": run.manifest["status"], "out": str(run.out)}))
        return 0 if run.manifest["status"] in ("complete", "prepared") else 1
    except Exception as exc:
        print(json.dumps({"status": "failed", "out": str(out), "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
