import argparse, csv, datetime, hashlib, json, math, os, sys, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "upstream/pulse"
INSTALL = ROOT / ".runtime/pulse-build/install/bin"

def bootstrap():
    for p in (INSTALL.parent / "python", INSTALL):
        sys.path.insert(0, str(p))

def doctor():
    try:
        bootstrap()
        from pulse.engine.PulseEngine import version, git_hash
        if not (INSTALL / "substances/Oxygen.json").is_file():
            raise RuntimeError("Pulse runtime data not generated: substances/Oxygen.json is missing")
        return {"available": True, "backend": "Pulse Python/PyPulse", "version": version(), "commit": git_hash(), "data_root": str(INSTALL)}
    except Exception as exc:
        return {"available": False, "backend": "Pulse Python/PyPulse", "reason": str(exc), "data_root": str(INSTALL)}

def run(config_path, output):
    cfg_path = Path(config_path).resolve()
    raw = cfg_path.read_bytes()
    cfg = json.loads(raw)
    allowed = {"duration_s", "sample_interval_s", "state_file", "initialize_patient", "heart_rate_multiplier", "incremental", "save_state", "parent_run_id"}
    if set(cfg) - allowed:
        raise ValueError("unsupported configuration keys: " + str(sorted(set(cfg) - allowed)))
    duration = float(cfg["duration_s"]); sample = float(cfg.get("sample_interval_s", 0.02))
    if not math.isfinite(duration) or not math.isfinite(sample) or duration <= 0 or sample <= 0:
        raise ValueError("duration_s and sample_interval_s must be finite and positive")
    if "state_file" in cfg and cfg.get("initialize_patient"):
        raise ValueError("choose state_file or initialize_patient")
    output = Path(output).resolve()
    if not (INSTALL / "substances/Oxygen.json").is_file():
        raise RuntimeError("Pulse runtime data not generated: substances/Oxygen.json is missing")
    output.mkdir(parents=True, exist_ok=False)
    (output / "config.json").write_bytes(raw)
    bootstrap()
    from pulse.engine.PulseEngine import PulseEngine, version, git_hash
    from pulse.cdm.engine import SEDataRequest, SEDataRequestManager
    from pulse.cdm.patient import SEPatientConfiguration, eSex
    from pulse.cdm.patient_actions import SECardiovascularMechanicsModification
    from pulse.cdm.scalars import FrequencyUnit, PressureUnit, VolumePerTimeUnit
    req = [SEDataRequest.create_physiology_request("ArterialPressure", unit=PressureUnit.mmHg),
           SEDataRequest.create_physiology_request("HeartRate", unit=FrequencyUnit.Per_min),
           SEDataRequest.create_physiology_request("SystolicArterialPressure", unit=PressureUnit.mmHg),
           SEDataRequest.create_physiology_request("DiastolicArterialPressure", unit=PressureUnit.mmHg),
           SEDataRequest.create_physiology_request("MeanArterialPressure", unit=PressureUnit.mmHg),
           SEDataRequest.create_physiology_request("CardiacOutput", unit=VolumePerTimeUnit.mL_Per_min),
           SEDataRequest.create_liquid_compartment_request("Aorta", "Pressure", unit=PressureUnit.mmHg)]
    pulse = PulseEngine(data_root_dir=str(INSTALL))
    pulse.set_log_filename(str(output / "pulse.log"))
    manager = SEDataRequestManager(req)
    state = cfg.get("state_file")
    input_info = {}
    parent_id = cfg.get("parent_run_id")
    if state:
        state_path = Path(state); state_path = state_path if state_path.is_absolute() else cfg_path.parent / state_path
        state_path = state_path.resolve()
        input_info = {"state_file": str(state_path), "sha256": hashlib.sha256(state_path.read_bytes()).hexdigest()}
        parent_manifest = state_path.parent / "manifest.json"
        if parent_id is None and parent_manifest.exists():
            parent_id = json.loads(parent_manifest.read_text())["run_id"]
        ok = pulse.serialize_from_file(str(state_path), manager)
    else:
        pc = SEPatientConfiguration(); pc.get_patient().set_sex(eSex.Male)
        pc.set_data_root_dir(str(INSTALL))
        ok = pulse.initialize_engine(pc, manager)
    if not ok: raise RuntimeError("Pulse initialization/state loading failed; see pulse.log")
    dt = pulse._dt_s  # Version-specific binding exposes no public time-step accessor.
    n = round(sample / dt); count = round(duration / sample)
    if n < 1 or abs(n * dt - sample) > 1e-8 or abs(count * sample - duration) > 1e-8:
        raise ValueError("sample interval must be an integer multiple of engine timestep and duration of sample interval")
    if "heart_rate_multiplier" in cfg:
        value = float(cfg["heart_rate_multiplier"])
        if not math.isfinite(value) or value <= 0: raise ValueError("heart_rate_multiplier must be positive")
        action = SECardiovascularMechanicsModification()
        action.get_modifiers().get_heart_rate_multiplier().set_value(value)
        action.set_incremental(bool(cfg.get("incremental", True)))
        pulse.process_action(action)  # This binding does not return action success.
    names = ["time_s", "arterial_pressure_mmHg", "heart_rate_per_min", "systolic_arterial_pressure_mmHg", "diastolic_arterial_pressure_mmHg", "mean_arterial_pressure_mmHg", "cardiac_output_mL_per_min", "aorta_pressure_mmHg"]
    with (output / "data.csv").open("w", newline="") as f:
        writer = csv.writer(f); writer.writerow(names); writer.writerow(pulse.pull_data())
        for _ in range(count):
            for __ in range(n):
                if not pulse.advance_time(): raise RuntimeError("Pulse advance failed")
            writer.writerow(pulse.pull_data())
    if cfg.get("save_state", True) and not pulse.serialize_to_file(str(output / "state.json")):
        raise RuntimeError("Pulse state save failed")
    pulse.clear()
    files = [p for p in (output / "data.csv", output / "state.json", output / "pulse.log") if p.exists()]
    manifest = {"run_id": str(uuid.uuid4()), "parent_run_id": parent_id, "run_type": "pulse", "status": "completed", "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "package_version": "0.1.0", "solver_version": version(), "solver_commit": git_hash(), "model": "human adult whole body", "backend": "Pulse Python/PyPulse", "device": "CPU", "random_seed": None, "engine_timestep_s": dt, "output_interval_s": sample, "interpolation": False, "units": {"time": "s", "pressure": "mmHg", "heart_rate": "1/min", "cardiac_output": "mL/min"}, "spatial_scope": "systemic arterial pressure; Aorta compartment pressure", "config_sha256": hashlib.sha256(raw).hexdigest(), "inputs": input_info, "outputs": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}, "evidence_status": "real solver; model outputs, not patient measurements", "assumptions": ["Pulse adult lumped circulation", "no modeled finger propagation"]}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("doctor"); d.add_argument("--json", action="store_true")
    r = sub.add_parser("run"); r.add_argument("--config", required=True); r.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "doctor":
        result = doctor(); print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if result["available"] else 1
    existed = Path(args.output).exists()
    try: run(args.config, args.output)
    except Exception as exc:
        out = Path(args.output).resolve()
        if not existed and out.is_dir() and (out / "config.json").exists() and not (out / "manifest.json").exists():
            failure = {"run_id": str(uuid.uuid4()), "run_type": "pulse", "status": "failed", "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "error": str(exc)}
            (out / "manifest.json").write_text(json.dumps(failure, indent=2), encoding="utf-8")
        print(f"Pulse run failed: {exc}", file=sys.stderr); return 1
    return 0

if __name__ == "__main__": sys.exit(main())
