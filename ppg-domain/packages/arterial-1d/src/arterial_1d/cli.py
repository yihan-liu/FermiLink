"""Fresh-directory CLI for actual public PWDB network simulations."""
import argparse
import json
from pathlib import Path
from ppg_forward.manifests import dump
from .manifests import Run, unique_output, validate_run
from .solver import julia, simulate
from .acceptance import compare


def doctor():
    checked=julia("smoke.jl")
    return {"available":checked.returncode==0,"upstream":"openBF 2.8.0 / Julia 1.11.2",
            "adapter":"package-owned explicit three-law PWDB adaptation of openBF",
            "synthetic_smoke_stdout":checked.stdout.strip(),"synthetic_smoke_stderr":checked.stderr.strip(),
            "baseline_acceptance":"not executed by doctor",
            "status":"complete" if checked.returncode==0 else "blocked"}


def main(argv=None):
    parser=argparse.ArgumentParser(prog="arterial-1d")
    sub=parser.add_subparsers(dest="command",required=True)
    doc=sub.add_parser("doctor"); doc.add_argument("--out")
    for name in ("simulate","sweep"):
        cmd=sub.add_parser(name); cmd.add_argument("--config",required=True); cmd.add_argument("--out",required=True)
    acc=sub.add_parser("acceptance"); acc.add_argument("--config",required=True); acc.add_argument("--simulation",required=True); acc.add_argument("--refinement",required=True); acc.add_argument("--out",required=True)
    val=sub.add_parser("validate-run"); val.add_argument("run"); val.add_argument("--out")
    args=parser.parse_args(argv)
    out=args.out or unique_output("arterial-1d-"+args.command)
    inputs=[args.config] if hasattr(args,"config") else []
    with Run(out,"arterial-1d "+args.command,inputs=inputs) as run:
        if args.command=="doctor":
            result=doctor()
        elif args.command=="validate-run":
            run.add_inputs([Path(args.run)/"manifest.json"])
            result=validate_run(args.run)
        else:
            config=json.loads(Path(args.config).read_text())
            run.add_inputs([config["baseline"]])
            if args.command=="simulate":
                result=simulate(config,run)
            elif args.command=="acceptance":
                for directory in (args.simulation,args.refinement):
                    run.add_inputs([Path(directory)/name for name in ("manifest.json","result.json","transfer.json","waveforms.csv","solver_input.json")])
                result=compare(args.simulation,config["baseline"],run.out,config["tolerances"],refinement=args.refinement)
                result["status"]="complete" if result["pass"] else "blocked"
            else:
                result={"status":"blocked","reason":"Target-MAP intervention awaits the owner's decision"}
        dump(run.out/"result.json",result); run.result=result
    print(json.dumps({"out":str(run.out),**result}))
    return 2 if result.get("status")=="blocked" or result.get("valid") is False else 0


if __name__=="__main__":
    raise SystemExit(main())
