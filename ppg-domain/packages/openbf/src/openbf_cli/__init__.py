"""Thin CLI around upstream openBF: run a YAML configuration and record what ran."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

__version__ = "0.1.0"
RUNTIME = Path(os.environ.get("OPENBF_JULIA_RUNTIME", Path(__file__).resolve().parents[4] / ".runtime" / "julia"))
JULIA = RUNTIME / "runtime/julia-1.11.2/bin/julia"
RUN = 'using openBF; openBF.run_simulation(ARGS[1]; verbose=false, save_stats=true, savedir=ARGS[2])'
VERSION = 'using Pkg, openBF; println(pkgversion(openBF))'


def julia(code, *args):
    return subprocess.run([str(JULIA), "--project=" + str(RUNTIME / "project"), "-e", code, *map(str, args)],
                          env=dict(os.environ, JULIA_DEPOT_PATH=str(RUNTIME / "depot")),
                          capture_output=True, text=True)


def doctor():
    checked = julia(VERSION)
    return {"julia": str(JULIA), "available": checked.returncode == 0,
            "openbf_version": checked.stdout.strip() or None, "stderr": checked.stderr.strip()[-2000:]}


def run(config, out):
    config, out = Path(config).resolve(), Path(out)
    out.mkdir(parents=True, exist_ok=False)
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    shutil.copy(config, out / config.name)
    checked = julia(RUN, config, out)
    (out / "openbf.log").write_text(checked.stdout + checked.stderr)
    record = {"command": "openbf run", "config": str(config),
              "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
              "started_at": started, "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "returncode": checked.returncode, "openbf": doctor().get("openbf_version"),
              "status": "complete" if checked.returncode == 0 else "failed"}
    (out / "run.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def main(argv=None):
    ap = argparse.ArgumentParser(prog="openbf")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    r = sub.add_parser("run")
    r.add_argument("--config", required=True)
    r.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    result = doctor() if args.command == "doctor" else run(args.config, args.out)
    print(json.dumps(result))
    ok = result.get("available") if args.command == "doctor" else result["status"] == "complete"
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
