"""Command-line orchestration of actual Pulse and MCX executables."""
import argparse
import csv
import datetime
import hashlib
import importlib.metadata
import json
import math
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from . import __version__
from .analysis import ac_dc
from .model import local_model, blood_fraction, absorption


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_command(args, log):
    with open(log, "w", encoding="utf-8") as f:
        subprocess.run([str(x) for x in args], check=True, stdout=f, stderr=subprocess.STDOUT)


def simulate(config_path, output):
    config_path, out = Path(config_path).resolve(), Path(output).resolve()
    raw_config = config_path.read_bytes()
    cfg = json.loads(raw_config)
    for key in ("pulse_executable", "mcx_executable"):
        binary = Path(cfg[key])
        if not binary.is_absolute():
            cfg[key] = str((config_path.parent/binary).resolve())
    if "state_file" in cfg["pulse_config"]:
        state = Path(cfg["pulse_config"]["state_file"])
        if not state.is_absolute():
            cfg["pulse_config"]["state_file"] = str((config_path.parent/state).resolve())
    if len(cfg["wavelengths"]) < 2:
        raise ValueError("at least two wavelength configurations are required")
    if len({int(w["wavelength_nm"]) for w in cfg["wavelengths"]}) != len(cfg["wavelengths"]):
        raise ValueError("wavelengths must be unique")
    out.mkdir(parents=True, exist_ok=False)
    manifest = {"run_id": str(uuid.uuid4()), "run_type": "coupled_ppg", "status": "running",
                "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "parent_run_id": cfg.get("parent_run_id"), "peripheral_ppg_version": __version__,
                "execution": "real solvers requested", "data_origin": "simulated", "parameter_source": cfg.get("parameter_source", "see configuration"),
                "input_config_sha256": digest(config_path), "config": "config.json", "units": {"pressure": "mmHg", "volume": "mL", "time": "s", "absorption": "1/mm"},
                "assumptions": ["Pulse pressure is an assumed inlet boundary", "one-way 2R1C; no arterial propagation", "fixed geometry and scattering; absorption mixing only"]}
    (out/"input_config.json").write_bytes(raw_config)
    dump(out/"config.json", cfg)
    manifest["config_sha256"] = digest(out/"config.json")
    dump(out/"manifest.json", manifest)
    try:
        pulse_cfg = out/"pulse_config.json"
        dump(pulse_cfg, cfg["pulse_config"])
        run_command([cfg["pulse_executable"], "run", "--config", pulse_cfg, "--output", out/"pulse"], out/"pulse.log")
        with (out/"pulse"/"data.csv").open(newline="", encoding="utf-8") as f:
            pulse = list(csv.DictReader(f))
        rows = local_model([float(x["time_s"]) for x in pulse], [float(x["arterial_pressure_mmHg"]) for x in pulse], cfg["local"])
        blood_fraction(rows, {**cfg["mixture"], "V_ref_mL": cfg["local"]["V_ref_mL"]})
        for wave in cfg["wavelengths"]:
            run_wave(out, cfg, wave, rows)
        data = out/"coupled.csv"
        with data.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        selected = [r for r in rows if r["time_s"] >= rows[0]["time_s"] + cfg["analysis_start_s"]]
        if len(selected) < 2:
            raise ValueError("analysis_start_s leaves fewer than two samples")
        summaries = {str(w["wavelength_nm"]): ac_dc([r[f"detected_fraction_{w['wavelength_nm']}nm"] for r in selected]) for w in cfg["wavelengths"]}
        dump(out/"analysis.json", summaries)
        products = [data, out/"analysis.json", out/"pulse"/"data.csv", out/"pulse"/"manifest.json"]
        for w in cfg["wavelengths"]:
            base = out/f"mcx_{int(w['wavelength_nm'])}nm"
            products.extend([base/"comparison.json", base/"baseline"/"manifest.json", base/"baseline"/"detected.npz", base/"direct"/"manifest.json", base/"reweighted"/"readings.json"])
        pulse_manifest = json.loads((out/"pulse"/"manifest.json").read_text(encoding="utf-8"))
        mcx_manifests = [json.loads((out/f"mcx_{int(w['wavelength_nm'])}nm"/"baseline"/"manifest.json").read_text(encoding="utf-8")) for w in cfg["wavelengths"]]
        manifest.update(status="complete", execution="real Pulse and MCX", output_interval_s=cfg["pulse_config"]["sample_interval_s"],
                        solvers={"pulse": pulse_manifest, "mcx": mcx_manifests},
                        outputs={str(p.relative_to(out)): digest(p) for p in products},
                        completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        dump(out/"manifest.json", manifest)
    except Exception as exc:
        manifest.update(status="failed", error=str(exc))
        dump(out/"manifest.json", manifest)
        raise


def run_wave(out, cfg, wave, rows):
    """Run a wavelength-specific MCX baseline, reweight, then direct-check."""
    wavelength = int(wave["wavelength_nm"])
    root = out / f"mcx_{wavelength}nm"
    root.mkdir()
    optical = json.loads(json.dumps(wave["mcx_config"]))
    props = optical["optical_properties"]
    label = int(wave["mixture_label"])
    if label < 1 or label >= len(props):
        raise ValueError("mixture_label must identify a non-background medium")
    blood, matrix = float(wave["mua_blood_per_mm"]), float(wave["mua_matrix_per_mm"])
    props[label][0] = absorption(float(cfg["mixture"]["f_b_ref"]), blood, matrix)
    dump(root/"baseline_config.json", optical)
    executable = cfg["mcx_executable"]
    run_command([executable, "simulate", "--config", root/"baseline_config.json", "--output", root/"baseline"], root/"baseline.log")
    cases = []
    for i, row in enumerate(rows):
        mua = absorption(row["f_b"], blood, matrix)
        row[f"mua_mix_{wavelength}nm_per_mm"] = mua
        target = [float(p[0]) for p in props[1:]]
        target[label-1] = mua
        cases.append({"name": f"t{i}", "mua_per_mm": target})
    dump(root/"reweight_config.json", {"baseline": str(root/"baseline"), "cases": cases})
    run_command([executable, "reweight", "--config", root/"reweight_config.json", "--output", root/"reweighted"], root/"reweight.log")
    readings = json.loads((root/"reweighted"/"readings.json").read_text(encoding="utf-8"))
    by_name = {x["name"]: x for x in readings}
    for i, row in enumerate(rows):
        reading = by_name[f"t{i}"]
        row[f"detected_fraction_{wavelength}nm"] = reading["collected_fraction"]
        row[f"detected_se_{wavelength}nm"] = reading["standard_error"]
    index = max(range(len(rows)), key=lambda i: abs(rows[i]["f_b"] - cfg["mixture"]["f_b_ref"]))
    direct = json.loads(json.dumps(optical))
    direct["optical_properties"][label][0] = cases[index]["mua_per_mm"][label-1]
    direct["seed"] = int(optical.get("seed", 1)) + 1
    dump(root/"direct_config.json", direct)
    run_command([executable, "simulate", "--config", root/"direct_config.json", "--output", root/"direct"], root/"direct.log")
    direct_read = json.loads((root/"direct"/"reading.json").read_text(encoding="utf-8"))
    rw = by_name[f"t{index}"]
    error = math.hypot(float(direct_read["standard_error"]), float(rw["standard_error"]))
    difference = float(direct_read["collected_fraction"]) - float(rw["collected_fraction"])
    dump(root/"comparison.json", {"time_s": rows[index]["time_s"], "direct": direct_read,
         "reweighted": rw, "difference": difference, "combined_standard_error": error,
         "difference_in_standard_errors": difference/error if error else None})


def validate_run(path):
    root = Path(path).resolve()
    m = json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    if m["status"] != "complete":
        raise ValueError("run did not complete")
    if digest(root/m["config"]) != m["config_sha256"]:
        raise ValueError("effective configuration checksum mismatch")
    if digest(root/"input_config.json") != m["input_config_sha256"]:
        raise ValueError("input configuration checksum mismatch")
    for name, expected in m["outputs"].items():
        if digest(root/name) != expected:
            raise ValueError(f"output checksum mismatch: {name}")
    comparisons = []
    for name in m["outputs"]:
        if name.endswith("comparison.json"):
            check = json.loads((root/name).read_text(encoding="utf-8"))
            z = check["difference_in_standard_errors"]
            comparisons.append({"path": name, "difference_in_standard_errors": z})
            if z is None or not math.isfinite(z) or abs(z) > 4:
                raise ValueError(f"direct/reweighted agreement is unresolved at {name} (difference/SE={z})")
    return {"valid": True, "run_id": m["run_id"], "direct_comparisons": comparisons}


def doctor():
    domain = Path(__file__).resolve().parents[4]
    result = {"package": "peripheral-ppg", "version": __version__, "solvers": {}}
    for name, fallback in (("pulse-physiology", domain/".runtime/pulse/bin/pulse-physiology"),
                           ("mcx-optics", domain/".runtime/mcx/venv/bin/mcx-optics")):
        binary = shutil.which(name) or str(fallback)
        try:
            p = subprocess.run([binary, "doctor", "--json"], capture_output=True, text=True, check=False)
            result["solvers"][name] = {"executable": binary, "returncode": p.returncode, "report": json.loads(p.stdout)}
        except (OSError, ValueError) as e:
            result["solvers"][name] = {"executable": binary, "returncode": None, "error": str(e)}
    return result


def main():
    parser = argparse.ArgumentParser(prog="peripheral-ppg")
    sub = parser.add_subparsers(dest="command", required=True)
    doc = sub.add_parser("doctor"); doc.add_argument("--json", action="store_true")
    sim = sub.add_parser("simulate"); sim.add_argument("--config", required=True); sim.add_argument("--output", required=True)
    val = sub.add_parser("validate-run"); val.add_argument("run_directory")
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            report = doctor()
            print(json.dumps(report, indent=2))
            if any(x.get("returncode") != 0 for x in report["solvers"].values()):
                sys.exit(1)
        elif args.command == "simulate":
            simulate(args.config, args.output)
        else:
            print(json.dumps(validate_run(args.run_directory), indent=2))
    except (KeyError, ValueError, OSError, subprocess.CalledProcessError, NotImplementedError) as e:
        print(f"peripheral-ppg: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
