"""Fresh-directory CLI for PWDB-network simulations with the adapted openBF solver."""
import argparse
import json
from pathlib import Path

from ppg_runkit.runs import dump

from .runs import Run, unique_output, validate
from .solver import julia, simulate


def doctor():
    checked=julia("smoke.jl")
    return {"available":checked.returncode==0,"upstream":"openBF 2.8.0 / Julia 1.11.2",
            "adapter":"package-owned explicit three-law PWDB adaptation of openBF",
            "synthetic_smoke_stdout":checked.stdout.strip(),"synthetic_smoke_stderr":checked.stderr.strip(),
            "baseline_acceptance":"not executed by doctor",
            "status":"complete" if checked.returncode==0 else "blocked"}


def main(argv=None):
    parser=argparse.ArgumentParser(prog="openbf-walls")
    sub=parser.add_subparsers(dest="command",required=True)
    doc=sub.add_parser("doctor"); doc.add_argument("--out")
    cmd=sub.add_parser("simulate"); cmd.add_argument("--config",required=True); cmd.add_argument("--out",required=True)
    val=sub.add_parser("validate-run"); val.add_argument("run"); val.add_argument("--out")
    args=parser.parse_args(argv)
    out=args.out or unique_output("openbf-walls-"+args.command)
    inputs=[args.config] if hasattr(args,"config") else []
    with Run(out,"openbf-walls "+args.command,inputs=inputs) as run:
        if args.command=="doctor":
            result=doctor()
        elif args.command=="validate-run":
            run.add_inputs([Path(args.run)/"manifest.json"])
            result=validate(args.run)
        else:
            config=json.loads(Path(args.config).read_text())
            run.add_inputs([config["baseline"]])
            result=simulate(config,run)
        dump(run.out/"result.json",result); run.result=result
    print(json.dumps({"out":str(run.out),**result}))
    return 2 if result.get("status")=="blocked" or result.get("valid") is False else 0


if __name__=="__main__":
    raise SystemExit(main())
