#!/usr/bin/env python3
"""Quick integration checks or actual solver-backed acceptance for ppg-domain."""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
FERMILINK_ROOT = Path(os.environ.get("FERMILINK_ROOT", str(ROOT.parent)))
FERMILINK_CLI = FERMILINK_ROOT / ".venv/bin/fermilink"
CODEX_BIN = ROOT / ".runtime" / "codex-cli"
REGISTRY = ROOT / ".runtime" / "fermilink-registry"
PULSE = ROOT / ".runtime" / "pulse" / "bin" / "pulse" if (ROOT / ".runtime" / "pulse" / "bin" / "pulse").is_file() else ROOT / ".runtime" / "pulse" / "bin" / "pulse-physiology"
MCX = ROOT / ".runtime" / "mcx" / "venv" / "bin" / "mcx" if (ROOT / ".runtime" / "mcx" / "venv" / "bin" / "mcx").is_file() else ROOT / ".runtime" / "mcx" / "venv" / "bin" / "mcx-optics"
PPG = ROOT / ".runtime" / "ppg-venv" / "bin" / "peripheral-ppg"
PKGS = {
    "pulse": ("pulse_physiology", "pulse_knowledge", "pulse_examples"),
    "mcx": ("mcx_optics", "mcx_knowledge", "mcx_examples"),
    "peripheral-ppg": ("peripheral_ppg", "ppg_knowledge", "ppg_examples"),
}

def command(args: list[str], *, env: dict[str, str], timeout: int = 3600, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, timeout=timeout)

def process_environment() -> dict[str, str]:
    env = os.environ.copy()
    env["FERMILINK_SCIPKG_ROOT"] = str(REGISTRY)
    solver_bins = [str(PULSE.parent), str(MCX.parent), str(PPG.parent)]
    env["PATH"] = os.pathsep.join([str(CODEX_BIN), *solver_bins, env.get("PATH", "")])
    return env

def record(items: list[dict], name: str, status: str, detail: str, **extra) -> None:
    items.append({"name": name, "status": status, "detail": detail, **extra})

def check_structure(items: list[dict]) -> bool:
    ready = True
    for package_id, (namespace, knowledge, examples) in PKGS.items():
        path = ROOT / "packages" / package_id
        required = [path / "pyproject.toml", path / "README.md", path / "skills", path / "src" / namespace, path / knowledge, path / examples]
        missing = [str(x.relative_to(ROOT)) for x in required if not x.exists()]
        if missing:
            ready = False
            record(items, f"package:{package_id}", "blocked", "missing required package content", missing=missing)
        else:
            record(items, f"package:{package_id}", "passed", "required package structure exists")
    return ready

def check_registration(items: list[dict], env: dict[str, str]) -> bool:
    path = REGISTRY / "registry.json"
    if not path.is_file():
        record(items, "fermilink:registry", "blocked", "isolated registry has not been created")
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        packages = data.get("packages", {})
        missing = sorted(set(PKGS) - set(packages))
        if missing:
            record(items, "fermilink:registry", "blocked", "packages are not all registered", missing=missing)
            return False
        for package_id in PKGS:
            installed = REGISTRY / "packages" / package_id
            if not installed.is_dir():
                record(items, f"fermilink:installed:{package_id}", "failed", "registry entry has no installed package directory")
                return False
        pmeta = packages["peripheral-ppg"]
        dependencies = pmeta.get("dependency_package_ids", pmeta.get("dependencies", []))
        if set(dependencies) != {"pulse", "mcx"}:
            record(items, "fermilink:dependencies", "failed", "peripheral-ppg dependency registration is incomplete", actual=dependencies)
            return False
        record(items, "fermilink:registry", "passed", "all packages registered in isolated registry")
        return True
    except Exception as error:
        record(items, "fermilink:registry", "failed", str(error))
        return False

def check_workspace(items: list[dict]) -> bool:
    workspace = ROOT / "workspaces" / "fermilink-validation"
    manifest_path = workspace / ".package_manifest.json"
    if not workspace.is_dir() or not manifest_path.is_file():
        record(items, "fermilink:workspace", "blocked", "dedicated package-linked workspace or manifest is missing")
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = {
            "skills/ppg-model/SKILL.md": workspace / "skills/ppg-model/SKILL.md",
            "ppg_knowledge/index.md": workspace / "ppg_knowledge/index.md",
            "ppg_examples/engineering_example.json": workspace / "ppg_examples/engineering_example.json",
            "external_packages/pulse/pulse_knowledge/index.md": workspace / "external_packages/pulse/pulse_knowledge/index.md",
            "external_packages/pulse/skills/pulse-circulation/SKILL.md": workspace / "external_packages/pulse/skills/pulse-circulation/SKILL.md",
            "external_packages/pulse/pulse_source": workspace / "external_packages/pulse/pulse_source",
            "external_packages/mcx/mcx_knowledge/index.md": workspace / "external_packages/mcx/mcx_knowledge/index.md",
            "external_packages/mcx/skills/mcx/SKILL.md": workspace / "external_packages/mcx/skills/mcx/SKILL.md",
            "external_packages/mcx/mcx_source": workspace / "external_packages/mcx/mcx_source",
        }
        missing = [name for name, path in expected.items() if not path.exists()]
        dependencies = set(manifest.get("configured_dependency_package_ids", []))
        linked = {item.get("package_id") for item in manifest.get("linked_dependency_packages", [])}
        collisions = manifest.get("collisions", []) + manifest.get("dependency_collisions", [])
        invalid = []
        if dependencies != {"pulse", "mcx"}:
            invalid.append(f"configured dependencies={sorted(dependencies)}")
        if linked != dependencies:
            invalid.append(f"linked dependencies={sorted(linked)}")
        if collisions:
            invalid.append(f"collisions={collisions}")
        for name, path in expected.items():
            if path.exists() and path.is_file():
                try:
                    path.read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    invalid.append(f"unreadable navigation file={name}")
        if missing or invalid:
            record(items, "fermilink:workspace", "failed", "workspace navigation or dependency links are incomplete", missing=missing, invalid=invalid)
            return False
        record(items, "fermilink:workspace", "passed", "PPG entry, both dependency skills/knowledge/source links are readable and collision-free", checked=list(expected))
        return True
    except Exception as error:
        record(items, "fermilink:workspace", "failed", f"cannot validate workspace manifest: {error}")
        return False

def doctor(items: list[dict], name: str, executable: Path, env: dict[str, str]) -> bool:
    if not executable.is_file():
        record(items, f"doctor:{name}", "blocked", f"CLI not found: {executable}")
        return False
    try:
        result = command([str(executable), "doctor", "--json"], env=env, timeout=180)
        try:
            payload = json.loads(result.stdout)
            if not isinstance(payload, dict):
                raise ValueError("doctor JSON must be an object")
        except (json.JSONDecodeError, ValueError) as error:
            record(items, f"doctor:{name}", "failed", f"doctor did not return a JSON object: {error}", stdout=result.stdout[-1500:], stderr=result.stderr[-1500:])
            return False
        if "available" in payload:
            ready = payload["available"] is True
            reason = payload.get("reason", payload.get("error", "doctor reported unavailable"))
        elif "ready" in payload:
            ready = payload["ready"] is True
            reason = payload.get("reason", payload.get("error", "doctor reported not ready"))
        elif isinstance(payload.get("solvers"), dict):
            states = [item.get("returncode") == 0 and item.get("report", {}).get("available") is True for item in payload["solvers"].values()]
            ready = bool(states) and all(states)
            reason = "one or more solver doctor reports are unavailable"
        else:
            ready = False
            reason = "doctor JSON lacks an explicit availability field"
        if result.returncode == 0 and ready:
            record(items, f"doctor:{name}", "passed", "doctor returned explicit available=true", result=payload)
            return True
        status = "blocked" if not ready and (result.returncode != 0 or "available" in payload or "ready" in payload) else "failed"
        record(items, f"doctor:{name}", status, str(reason), result=payload, returncode=result.returncode)
        return False
    except Exception as error:
        record(items, f"doctor:{name}", "failed", str(error))
        return False

def run_solver_acceptance(items: list[dict], run_root: Path, env: dict[str, str]) -> None:
    run_root.mkdir(parents=True, exist_ok=False)
    # Pulse baseline first; control and intervention configurations can restore its state.
    pulse_examples = ROOT / "packages" / "pulse" / "pulse_examples"
    for key in ("baseline", "control", "intervention"):
        config = pulse_examples / f"{key}.json"
        output = run_root / "pulse" / key
        if not config.is_file():
            record(items, f"pulse:{key}", "blocked", f"example config missing: {config}")
            continue
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            payload = json.loads(config.read_text(encoding="utf-8"))
            # Ensure branch examples use the state emitted by this acceptance run.
            if key != "baseline":
                payload["state_file"] = str(run_root / "pulse" / "baseline" / "state.json")
                config_run = run_root / "pulse" / f"{key}.json"
                config_run.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            else:
                config_run = config
            result = command([str(PULSE), "run", "--config", str(config_run), "--output", str(output)], env=env)
            if result.returncode == 0:
                record(items, f"pulse:{key}", "passed", "real Pulse CLI run completed", output=str(output), stdout=result.stdout[-1500:])
            else:
                record(items, f"pulse:{key}", "failed", result.stderr[-3000:] or result.stdout[-3000:], output=str(output))
        except Exception as error:
            record(items, f"pulse:{key}", "failed", str(error))

    mcx_examples = ROOT / "packages" / "mcx" / "mcx_examples"
    baselines: dict[int, Path] = {}
    for wavelength in (660, 940):
        config = mcx_examples / f"skin_vessel_{wavelength}.json"
        output = run_root / "mcx" / f"baseline_{wavelength}nm"
        if not config.is_file():
            record(items, f"mcx:simulate:{wavelength}nm", "blocked", f"example config missing: {config}")
            continue
        output.parent.mkdir(parents=True, exist_ok=True)
        result = command([str(MCX), "simulate", "--config", str(config), "--output", str(output)], env=env)
        if result.returncode == 0 and (output / "reading.json").is_file():
            reading = json.loads((output / "reading.json").read_text(encoding="utf-8"))
            baselines[wavelength] = output
            record(items, f"mcx:simulate:{wavelength}nm", "passed", "real PMCX simulation produced finite-area detector reading", output=str(output), reading=reading)
        else:
            record(items, f"mcx:simulate:{wavelength}nm", "failed", result.stderr[-3000:] or result.stdout[-3000:], output=str(output))
    if 660 in baselines:
        reweight_cfg = run_root / "mcx" / "reweight.json"
        source_config = json.loads((mcx_examples / "skin_vessel_660.json").read_text(encoding="utf-8"))
        media = source_config["optical_properties"][1:]
        target = [float(row[0]) for row in media]
        if len(target):
            target[0] *= 1.1
        reweight_cfg.write_text(json.dumps({"baseline": str(baselines[660]), "cases": [{"name": "absorption_plus_10_percent", "mua_per_mm": target}]}, indent=2) + "\n", encoding="utf-8")
        output = run_root / "mcx" / "reweight_660nm"
        result = command([str(MCX), "reweight", "--config", str(reweight_cfg), "--output", str(output)], env=env)
        record(items, "mcx:reweight", "passed" if result.returncode == 0 else "failed", "absorption-only photon path reweight", output=str(output), detail_output=(result.stdout or result.stderr)[-1500:])
        if result.returncode == 0:
            direct_cfg = run_root / "mcx" / "direct_config.json"
            direct_output = run_root / "mcx" / "direct_660nm"
            direct_payload = json.loads(json.dumps(source_config))
            direct_payload["optical_properties"][1][0] = target[0]
            direct_payload["seed"] = int(source_config.get("seed", 1)) + 1
            direct_cfg.write_text(json.dumps(direct_payload, indent=2) + "\n", encoding="utf-8")
            direct_result = command([str(MCX), "simulate", "--config", str(direct_cfg), "--output", str(direct_output)], env=env)
            if direct_result.returncode == 0:
                rw = json.loads((output / "readings.json").read_text(encoding="utf-8"))[0]
                direct = json.loads((direct_output / "reading.json").read_text(encoding="utf-8"))
                combined_se = (float(rw["standard_error"]) ** 2 + float(direct["standard_error"]) ** 2) ** 0.5
                z_score = (float(direct["collected_fraction"]) - float(rw["collected_fraction"])) / combined_se if combined_se else None
                comparison = {"reweighted": rw, "direct": direct, "difference": float(direct["collected_fraction"]) - float(rw["collected_fraction"]), "combined_standard_error": combined_se, "difference_in_standard_errors": z_score, "criterion": "absolute difference <= 4 combined standard errors"}
                comparison_path = run_root / "mcx" / "reweight_direct_comparison.json"
                comparison_path.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
                comparison_status = "passed" if z_score is not None and abs(z_score) <= 4 else "failed"
                record(items, "mcx:reweight-direct-comparison", comparison_status, f"direct vs reweighted difference is {z_score:.3g} combined SE" if z_score is not None else "combined standard error is zero", output=str(comparison_path), comparison=comparison)
            else:
                record(items, "mcx:reweight-direct-comparison", "failed", direct_result.stderr[-2000:] or direct_result.stdout[-2000:])
        else:
            record(items, "mcx:reweight-direct-comparison", "blocked", "reweight did not complete")
        replay_cfg = run_root / "mcx" / "replay.json"
        replay_cfg.write_text(json.dumps({"baseline": str(baselines[660])}, indent=2) + "\n", encoding="utf-8")
        output = run_root / "mcx" / "replay_660nm"
        result = command([str(MCX), "sensitivity", "--config", str(replay_cfg), "--output", str(output)], env=env)
        record(items, "mcx:replay", "passed" if result.returncode == 0 else "failed", "real MCX photon replay Jacobian", output=str(output), detail_output=(result.stdout or result.stderr)[-1500:])
    else:
        record(items, "mcx:reweight", "blocked", "requires a successful 660 nm baseline")
        record(items, "mcx:replay", "blocked", "requires a successful 660 nm baseline")

    coupled = ROOT / "packages" / "peripheral-ppg" / "ppg_examples" / "engineering_example.json"
    if not coupled.is_file():
        record(items, "peripheral-ppg:end-to-end", "blocked", f"coupled example missing: {coupled}")
    elif not PPG.is_file():
        record(items, "peripheral-ppg:end-to-end", "blocked", f"CLI not found: {PPG}")
    else:
        output = run_root / "coupled-ppg"
        result = command([str(PPG), "simulate", "--config", str(coupled), "--output", str(output)], env=env)
        if result.returncode == 0:
            validation = command([str(PPG), "validate-run", str(output)], env=env)
            status = "passed" if validation.returncode == 0 else "failed"
            record(items, "peripheral-ppg:end-to-end", status, "Pulse → 2R1C → MCX coupled run and validation", output=str(output), validation=(validation.stdout or validation.stderr)[-1500:])
        else:
            record(items, "peripheral-ppg:end-to-end", "failed", result.stderr[-3000:] or result.stdout[-3000:], output=str(output))

def run_scientific_checks(items: list[dict], run_root: Path, env: dict[str, str]) -> None:
    ppg_env = env.copy()
    ppg_env["PYTHONPATH"] = str(ROOT / "packages" / "peripheral-ppg" / "src")
    ppg_python = PPG.parent / "python"
    tests = command([str(ppg_python), "-m", "unittest", "discover", "-s", str(ROOT / "packages" / "peripheral-ppg" / "tests"), "-v"], env=ppg_env, timeout=180)
    tests_output = (tests.stdout + tests.stderr)[-4000:]
    test_status = "passed" if tests.returncode == 0 and "OK" in tests_output else "failed"
    record(items, "peripheral-ppg:unit-tests", test_status, "PPG analytical, conservation, timestep-refinement, alignment, volume and invalid-record-reference tests", output=tests_output)

    mcx_python = MCX.parent / "python"
    detector_run = run_root / "mcx" / "baseline_660nm"
    detector = command([str(mcx_python), str(ROOT / "packages" / "mcx" / "tests" / "check_detector.py"), str(detector_run)], env=env, timeout=180)
    detector_output = (detector.stdout + detector.stderr)[-3000:]
    detector_status = "passed" if detector.returncode == 0 else "failed"
    record(items, "mcx:detector-normalization-units", detector_status, "Independent raw photon check of voxel path conversion, unit collected fraction, detector area in mm2 and reflectance in mm-2", output=detector_output)

    try:
        baseline_manifest = json.loads((run_root / "pulse" / "baseline" / "manifest.json").read_text(encoding="utf-8"))
        coupled_manifest = json.loads((run_root / "coupled-ppg" / "manifest.json").read_text(encoding="utf-8"))
        pulse_units = baseline_manifest["units"]
        coupled_units = coupled_manifest["units"]
        step = float(baseline_manifest["engine_timestep_s"])
        interval = float(baseline_manifest["output_interval_s"])
        coupled_interval = float(coupled_manifest["output_interval_s"])
        valid = (
            step > 0 and interval == step and coupled_interval == interval
            and pulse_units.get("time") == "s" and pulse_units.get("pressure") == "mmHg"
            and pulse_units.get("cardiac_output") == "mL/min"
            and coupled_units == {"pressure": "mmHg", "volume": "mL", "time": "s", "absorption": "1/mm"}
        )
        if not valid:
            raise ValueError(f"inconsistent timestep or units: engine={step}, output={interval}, coupled={coupled_interval}, pulse={pulse_units}, ppg={coupled_units}")
        record(items, "ppg:pulse-step-units", "passed", "Real manifests agree on engine/output timestep and explicit time, pressure, cardiac-output, volume and absorption units", engine_timestep_s=step, output_interval_s=interval, pulse_units=pulse_units, coupled_units=coupled_units)
    except Exception as error:
        record(items, "ppg:pulse-step-units", "failed", str(error))

    catalog = ROOT / "reports" / "sources.json"
    try:
        entries = json.loads(catalog.read_text(encoding="utf-8"))
        missing = [row["local_path"] for row in entries if not (ROOT / row["local_path"]).exists()]
        if missing:
            record(items, "sources:local-citations", "failed", "Source catalog contains unresolved local paths", missing=missing)
        else:
            record(items, "sources:local-citations", "passed", "All cataloged local source and knowledge paths resolve", entries=len(entries))
    except Exception as error:
        record(items, "sources:local-citations", "failed", f"Cannot validate source catalog: {error}")

def check_agent_task(items: list[dict], env: dict[str, str]) -> None:
    agent = command([str(FERMILINK_CLI), "agent", "--json"], env=env, timeout=30)
    try:
        configuration = json.loads(agent.stdout)
        provider = configuration.get("provider") if isinstance(configuration, dict) else None
    except json.JSONDecodeError:
        provider = None
    executable = {"codex": "codex", "claude": "claude", "gemini": "gemini", "opencode": "opencode"}.get(provider)
    if agent.returncode or not executable:
        record(items, "fermilink:agent-task", "blocked", "agent task not run: provider configuration could not be resolved")
        return
    cli_path = shutil.which(executable, path=env.get("PATH"))
    if not cli_path:
        record(items, "fermilink:agent-task", "blocked", f"agent task not run: configured provider {provider!r} executable {executable!r} is unavailable in this process PATH")
        return
    version = command([executable, "--version"], env=env, timeout=30)
    if provider != "codex":
        record(items, "fermilink:agent-task", "blocked", f"agent task not run: provider {provider!r} login check is not configured", cli_executable=cli_path)
        return
    login = command([executable, "login", "status"], env=env, timeout=30)
    auth_evidence = {
        "provider": provider,
        "cli_executable": cli_path,
        "cli_version": (version.stdout or version.stderr).strip(),
        "login_status": (login.stdout or login.stderr).strip(),
        "login_returncode": login.returncode,
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "path_scope": "child_process_only",
    }
    if login.returncode:
        detail = (
            f"agent task not run: project-local Codex CLI {auth_evidence['cli_version']} is installed but not authenticated "
            f"(login status: {auth_evidence['login_status']}; exit code {auth_evidence['login_returncode']}; "
            f"checked {auth_evidence['checked_at_utc']}; PATH is child-process only)"
        )
        record(items, "fermilink:agent-task", "blocked", detail, **auth_evidence)
        return
    workspace = ROOT / "workspaces" / "fermilink-validation"
    task_output = ROOT / "runs" / "acceptance-agent-task" / (
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    )
    if task_output.exists():
        record(items, "fermilink:agent-task", "failed", "agent task output path already exists; refusing to overwrite", **auth_evidence, output=str(task_output))
        return
    task_output.parent.mkdir(parents=True, exist_ok=True)
    prompt = (
        "Use the workspace tools to perform this task, not just describe it. "
        "First read skills/ppg-model/SKILL.md and ppg_knowledge/index.md from the current workspace. "
        "Then use the terminal tool from this workspace to run the documented engineering example with a fresh output directory: "
        f"{PPG} simulate --config ppg_examples/engineering_example.json --output {task_output}. "
        f"Then run {PPG} validate-run {task_output}. "
        "Report the exact skill path read, the command used, and the manifest run_id. "
        "Do not claim completion unless the command produced a complete manifest and validate-run returned valid=true."
    )
    result = command(
        [str(FERMILINK_CLI), "exec", "--package", "peripheral-ppg", prompt],
        env=env, timeout=3600, cwd=workspace,
    )
    output_text = (result.stdout or result.stderr)[-6000:]
    if result.returncode:
        record(items, "fermilink:agent-task", "failed", "FermiLink agent task returned a nonzero exit status", **auth_evidence, returncode=result.returncode, task_output=str(task_output), output=output_text)
        return
    manifest_path = task_output / "manifest.json"
    if not manifest_path.is_file():
        record(items, "fermilink:agent-task", "failed", "agent task returned success without creating manifest.json", **auth_evidence, returncode=result.returncode, task_output=str(task_output), output=output_text)
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        record(items, "fermilink:agent-task", "failed", f"agent task created an unreadable manifest: {error}", **auth_evidence, returncode=result.returncode, task_output=str(task_output), output=output_text)
        return
    validation = command([str(PPG), "validate-run", str(task_output)], env=env, timeout=180)
    try:
        validation_report = json.loads(validation.stdout)
        valid_run = isinstance(validation_report, dict) and validation_report.get("valid") is True
    except json.JSONDecodeError:
        validation_report = {"stdout": validation.stdout[-2000:], "stderr": validation.stderr[-2000:]}
        valid_run = False
    manifest_ok = manifest.get("status") == "complete" and manifest.get("run_type") == "coupled_ppg"
    response_ok = all(token in output_text for token in (
        "skills/ppg-model/SKILL.md", "ppg_examples/engineering_example.json", "validate-run"
    ))
    passed = validation.returncode == 0 and valid_run and manifest_ok and response_ok
    record(
        items, "fermilink:agent-task",
        "passed" if passed else "failed",
        "agent read the PPG skill and ran the engineering example; manifest and independent validate-run passed" if passed else "agent task did not satisfy skill, example, manifest and validate-run checks",
        **auth_evidence, returncode=result.returncode, task_output=str(task_output),
        manifest_run_id=manifest.get("run_id"), manifest_status=manifest.get("status"),
        validation_returncode=validation.returncode, validation=validation_report,
        output=output_text,
    )

def write_reports(payload: dict) -> None:
    reports = ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "acceptance.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# " + "\u9a8c\u6536", "", f"\u8fd0\u884c: {payload['run_id']}  ", f"\u6a21\u5f0f: {payload['mode']}  ", f"\u603b\u4f53: **{payload['status']}**  ", f"\u786e\u5b9a\u6027\u68c0\u67e5: **{payload.get('deterministic_status', payload['status'])}**", "", "| \u68c0\u67e5 | \u72b6\u6001 | \u7ed3\u679c |", "| --- | --- | --- |"]
    for item in payload["checks"]:
        lines.append(f"| `{item['name']}` | **{item['status']}** | {item['detail'].replace('|', '/').replace(chr(10), ' ')} |")
    lines.extend(["", "\u88ab\u963b\u65ad\u9879\u8868\u793a\u9a8c\u6536\u672a\u5b8c\u6210\uff0c\u4e0d\u8ba1\u4e3a\u901a\u8fc7\u3002", ""])
    (reports / "acceptance.md").write_text("\n".join(lines), encoding="utf-8")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="read-only structure, registry and doctor checks; skip simulations")
    args = parser.parse_args()
    items: list[dict] = []
    env = process_environment()
    all_ready = check_structure(items)
    if args.quick:
        registered = check_registration(items, env)
        if registered:
            check_workspace(items)
        for name, executable in (("pulse", PULSE), ("mcx", MCX), ("peripheral-ppg", PPG)):
            doctor(items, name, executable, env)
    else:
        solver_results = [
            doctor(items, name, executable, env)
            for name, executable in (("pulse", PULSE), ("mcx", MCX))
        ]
        solver_prerequisites = all(solver_results)
        if not all_ready:
            record(items, "fermilink:setup", "blocked", "package structure is incomplete; no registration changes made")
            record(items, "solver-runs", "blocked", "package structure must be ready first")
        elif not solver_prerequisites:
            record(items, "fermilink:setup", "blocked", "real Pulse and MCX doctor checks must pass before installation")
            record(items, "solver-runs", "blocked", "one or more real solver doctors are unavailable")
        else:
            install_cmd = [sys.executable, str(ROOT / "scripts" / "integrate_fermilink.py"), "--install", "--workspace"]
            setup = command(install_cmd, env=env, timeout=900)
            if setup.returncode:
                record(items, "fermilink:setup", "blocked", (setup.stdout + setup.stderr)[-3000:])
                registered = False
            else:
                record(items, "fermilink:setup", "passed", setup.stdout[-1000:])
                registered = check_registration(items, env)
            workspace_ready = check_workspace(items) if registered else False
            ppg_ready = doctor(items, "peripheral-ppg", PPG, env) if registered else False
            if registered and workspace_ready and ppg_ready:
                run_root = ROOT / "runs" / "acceptance" / (dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
                try:
                    run_solver_acceptance(items, run_root, env)
                    run_scientific_checks(items, run_root, env)
                except Exception as error:
                    record(items, "solver-runs", "failed", f"{type(error).__name__}: {error}")
            else:
                record(items, "solver-runs", "blocked", "package registration and PPG CLI doctor must pass before solver examples")
    if not args.quick:
        check_agent_task(items, env)

    statuses = [x["status"] for x in items]
    overall = "failed" if "failed" in statuses else ("blocked" if "blocked" in statuses else "passed")
    deterministic_statuses = [x["status"] for x in items if x["name"] != "fermilink:agent-task"]
    deterministic_status = "failed" if "failed" in deterministic_statuses else ("blocked" if "blocked" in deterministic_statuses else "passed")
    payload = {"deterministic_status": deterministic_status, "run_id": str(uuid.uuid4()), "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "mode": "quick" if args.quick else "full", "status": overall, "registry": str(REGISTRY), "checks": items}
    write_reports(payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if overall == "passed" else 1

if __name__ == "__main__":
    raise SystemExit(main())
