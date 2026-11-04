"""Command-line entry point for audited PPG forward-model runs."""
import argparse
import json
from pathlib import Path
import sys

from . import pipeline
from .manifests import Run, unique_output


def parser():
    ap = argparse.ArgumentParser(prog="ppg-forward")
    commands = ap.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Inspect the analysis environment without running solvers")
    doctor.add_argument("--out", type=Path)
    select = commands.add_parser("select-segments", help="Select and quality-check explicit authorized cases")
    select.add_argument("--split", type=Path, required=True)
    select.add_argument("--cases", type=Path, required=True)
    select.add_argument("--allow-splits", default="train")
    select.add_argument("--config", type=Path, help="Explicit selection settings and metadata locations")
    select.add_argument("--event-policy", help="Explicit event policy; no scientific policy is assumed")
    select.add_argument("--out", type=Path, required=True)
    fit = commands.add_parser("fit")
    fit.add_argument("--segments", type=Path, required=True)
    fit.add_argument("--models", required=True, help="Comma-separated model names, e.g. M0,M1")
    fit.add_argument("--operator", required=True, help="fit-global or frozen:FILE")
    fit.add_argument("--max-nfev", type=int, default=200)
    fit.add_argument("--operator-candidates", type=Path)
    fit.add_argument("--out", type=Path, required=True)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--fits", type=Path, required=True)
    evaluate.add_argument("--prereg", type=Path, required=True)
    evaluate.add_argument("--out", type=Path, required=True)
    cross = commands.add_parser("cross-window")
    cross.add_argument("--fits", type=Path, required=True)
    cross.add_argument("--out", type=Path, required=True)
    mcx = commands.add_parser("mcx-linear")
    mcx.add_argument("--config", type=Path, required=True)
    mcx.add_argument("--out", type=Path, required=True)
    validate = commands.add_parser("validate-run")
    validate.add_argument("directory", type=Path)
    validate.add_argument("--out", type=Path, help="Fresh audit directory; defaults to a unique sibling")
    return ap


def command_inputs(args):
    paths = []
    for name in ("split", "cases", "config", "prereg", "operator_candidates"):
        value = getattr(args, name, None)
        if value is not None:
            paths.append(value)
    for name in ("segments", "fits"):
        value = getattr(args, name, None)
        if value is not None:
            paths.extend(pipeline.metadata_inputs(value))
    if args.command == "validate-run":
        paths.append(args.directory / "manifest.json")
    return paths


def main(argv=None):
    args = parser().parse_args(argv)
    out = args.out
    if out is None:
        parent = args.directory.absolute().parent if args.command == "validate-run" else None
        out = unique_output(args.command, parent)
    # Allocate first so failures in metadata lookup also leave a failed manifest.
    try:
        with Run(out, args.command, parameters={k: str(v) if isinstance(v, Path) else v
                                               for k, v in vars(args).items() if k != "out"}) as run:
            run.add_inputs(command_inputs(args))
            if args.command == "doctor":
                run.result = pipeline.doctor(run.out)
            else:
                function = {"select-segments": pipeline.select_segments, "fit": pipeline.fit,
                    "evaluate": pipeline.evaluate, "cross-window": pipeline.cross_window,
                    "mcx-linear": pipeline.mcx_linear, "validate-run": pipeline.validate}[args.command]
                run.result = function(args, run)
        print(json.dumps({"status": run.manifest["status"], "out": str(run.out)}))
        return 0 if run.manifest["status"] in ("complete", "prepared") else 1
    except Exception as exc:
        print(json.dumps({"status": "failed", "out": str(out), "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
