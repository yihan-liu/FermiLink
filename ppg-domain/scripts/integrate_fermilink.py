#!/usr/bin/env python3
"""Register the ppg-domain packages and create a dedicated FermiLink workspace."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
FERMILINK_ROOT = Path(os.environ.get("FERMILINK_ROOT", str(ROOT.parent)))
SCIPKG_ROOT = ROOT / ".runtime" / "fermilink-registry"
STAGING_ROOT = ROOT / ".runtime" / "install-staging"
CLI = FERMILINK_ROOT / ".venv/bin/fermilink"
FERMILINK_PYTHON = FERMILINK_ROOT / ".venv/bin/python"
PPG_VENV = ROOT / ".runtime" / "ppg-venv"
PACKAGE_SPECS = (
    ("pulse", "pulse_physiology", "pulse_knowledge", "pulse_examples"),
    ("mcx", "mcx_optics", "mcx_knowledge", "mcx_examples"),
    ("peripheral-ppg", "peripheral_ppg", "ppg_knowledge", "ppg_examples"),
    ("vitaldb-segments", "vitaldb_segments", "vitaldb_knowledge", "vitaldb_examples"),
    ("ppg-transfer", "ppg_transfer", "transfer_knowledge", "transfer_examples"),
    ("ppg-models", "ppg_models", "models_knowledge", "models_examples"),
    ("pwdb", "pwdb", "pwdb_knowledge", "pwdb_examples"),
    ("openbf-walls", "openbf_walls", "openbf_knowledge", "openbf_examples"),
)
# Libraries on the launcher path that are not registered as FermiLink packages.
LIBRARY_SOURCES = ("ppg-runkit",)
RETIRED_PACKAGES = ("ppg-forward", "arterial-1d")
EXCLUDED_DIRS = {".checks", ".runtime", ".cache", "__pycache__", ".pytest_cache", "build", "dist"}
SOURCE_LINK_TARGETS = {"pulse": {"pulse_source": "pulse"}, "mcx": {"mcx_source": "mcx"}}

def run(args: list[str]) -> str:
    env = os.environ.copy()
    env["FERMILINK_SCIPKG_ROOT"] = str(SCIPKG_ROOT)
    result = subprocess.run(args, cwd=ROOT, env=env, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}{result.stderr}")
    return result.stdout.strip()

def registry() -> dict:
    path = SCIPKG_ROOT / "registry.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"packages": {}}

def check_package(package_id: str, namespace: str, knowledge: str, examples: str) -> Path:
    path = ROOT / "packages" / package_id
    required = [path / "pyproject.toml", path / "README.md", path / "skills", path / "src" / namespace, path / knowledge, path / examples]
    missing = [str(item.relative_to(ROOT)) for item in required if not item.exists()]
    if missing:
        raise RuntimeError(f"{package_id} is not ready; missing: {', '.join(missing)}")
    project = tomllib.loads((path / "pyproject.toml").read_text(encoding="utf-8")).get("project", {})
    if project.get("name") != package_id:
        raise RuntimeError(f"{path}/pyproject.toml project.name must be {package_id!r}")
    return path

def excluded(relative: Path) -> bool:
    return any(part in EXCLUDED_DIRS or part.endswith(".egg-info") or part.endswith(".pyc") for part in relative.parts)

def package_digest(source: Path, *, include_symlinks: bool = True) -> str:
    digest = hashlib.sha256()
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if excluded(relative):
            continue
        if path.is_symlink():
            if include_symlinks:
                digest.update(b"L\0" + relative.as_posix().encode() + b"\0" + str(path.resolve()).encode() + b"\n")
        elif path.is_file():
            digest.update(b"F\0" + relative.as_posix().encode() + b"\0" + path.read_bytes() + b"\n")
    return digest.hexdigest()

def stage_package(package_id: str, source: Path) -> Path:
    """Create a stable sanitized export; upstream/source symlinks are restored post-install."""
    digest = package_digest(source)
    stage = STAGING_ROOT / f"{package_id}-{digest[:12]}"
    if stage.exists():
        if package_digest(stage, include_symlinks=False) != package_digest(source, include_symlinks=False):
            raise RuntimeError(f"Sanitized stage content mismatch; preserving it: {stage}")
        return stage
    STAGING_ROOT.mkdir(parents=True, exist_ok=True)
    def ignore_generated(directory: str, names: list[str]) -> set[str]:
        parent = Path(directory)
        ignored = set()
        for name in names:
            relative = (parent / name).relative_to(source)
            if excluded(relative) or (parent / name).is_symlink():
                ignored.add(name)
        return ignored
    shutil.copytree(source, stage, ignore=ignore_generated)
    if package_digest(stage, include_symlinks=False) != package_digest(source, include_symlinks=False):
        raise RuntimeError(f"Sanitized stage failed content check: {stage}")
    return stage

def installed_tree_matches(stage: Path, installed: Path) -> bool:
    if not installed.is_dir():
        return False
    return package_digest(stage, include_symlinks=False) == package_digest(installed, include_symlinks=False)

def install_packages() -> None:
    if not CLI.is_file() or not FERMILINK_PYTHON.is_file():
        raise RuntimeError(f"FermiLink executable environment not found under {FERMILINK_ROOT}")
    SCIPKG_ROOT.mkdir(parents=True, exist_ok=True)
    existing = registry().get("packages", {})
    for package_id, namespace, knowledge, examples in PACKAGE_SPECS:
        source = check_package(package_id, namespace, knowledge, examples)
        stage = stage_package(package_id, source)
        installed = SCIPKG_ROOT / "packages" / package_id
        package_meta = existing.get(package_id)
        force = False
        if package_meta:
            expected_path = installed.resolve()
            managed_root = (SCIPKG_ROOT / "packages").resolve()
            registered_path = Path(package_meta.get("installed_path", "")).resolve()
            registered_source = package_meta.get("source", "")
            if registered_path != expected_path or managed_root not in registered_path.parents:
                raise RuntimeError(f"Refusing to refresh package outside this isolated registry: {package_id}")
            if not registered_source.startswith("local-path:"):
                raise RuntimeError(f"Refusing to replace package with non-local source metadata: {package_id}")
            prior_source = Path(registered_source.removeprefix("local-path:")).resolve()
            if STAGING_ROOT.resolve() not in prior_source.parents:
                raise RuntimeError(f"Refusing to refresh package from an unowned source path: {package_id}")
            force = not (Path(registered_source.removeprefix("local-path:")).resolve() == stage.resolve() and installed_tree_matches(stage, installed))
            if force:
                print(f"refreshing managed snapshot: {package_id}")
            else:
                print(f"registered: {package_id} (snapshot matches current source)")
        elif installed.exists():
            raise RuntimeError(f"Unregistered target already exists; preserving it: {installed}")
        if not package_meta or force:
            args = [str(CLI), "install", package_id, "--local-path", str(stage), "--title", package_id, "--workflow-type", "simulation"]
            if force:
                args.append("--force")
            run(args)
        for link in source.rglob("*"):
            relative = link.relative_to(source)
            if excluded(relative) or not link.is_symlink():
                continue
            target = installed / relative
            source_name = SOURCE_LINK_TARGETS.get(package_id, {}).get(relative.as_posix())
            resolved = (ROOT / "upstream" / source_name).resolve() if source_name else link.resolve()
            if not resolved.exists():
                raise RuntimeError(f"Source link target is unavailable: {link} -> {resolved}")
            if target.is_symlink() and target.resolve() == resolved:
                continue
            if target.exists() or target.is_symlink():
                raise RuntimeError(f"Unexpected installed path collision: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(resolved, target_is_directory=resolved.is_dir())
    entries = {
        "pulse": "skills,pulse_knowledge",
        "mcx": "skills,mcx_knowledge",
        "peripheral-ppg": "skills,ppg_knowledge,ppg_examples",
        "vitaldb-segments": "skills,vitaldb_knowledge,vitaldb_examples",
        "ppg-transfer": "skills,transfer_knowledge,transfer_examples",
        "ppg-models": "skills,models_knowledge,models_examples",
        "pwdb": "skills,pwdb_knowledge,pwdb_examples",
        "openbf-walls": "skills,openbf_knowledge,openbf_examples",
    }
    for package_id, selected in entries.items():
        run([str(CLI), "overlay", package_id, "--entries", selected])
        print(f"overlay: {package_id}: {selected}")
    run([str(CLI), "dependencies", "peripheral-ppg", "--package", "pulse", "--package", "mcx"])
    print("dependencies: peripheral-ppg -> pulse, mcx")
    run([str(CLI), "dependencies", "ppg-models", "--package", "ppg-transfer", "--package", "peripheral-ppg"])
    print("dependencies: ppg-models -> ppg-transfer, peripheral-ppg")
    run([str(CLI), "dependencies", "openbf-walls", "--package", "pwdb"])
    print("dependencies: openbf-walls -> pwdb")
    for package_id in RETIRED_PACKAGES:
        if package_id in registry().get("packages", {}):
            run([str(CLI), "delete", package_id])
            print(f"removed retired registration: {package_id}")
    ensure_ppg_cli()

def ensure_ppg_cli() -> None:
    """Create a project-local CLI shim without writing into package source or solver venvs."""
    python = PPG_VENV / "bin" / "python"
    if not python.exists():
        subprocess.run([str(FERMILINK_PYTHON), "-m", "venv", str(PPG_VENV)], check=True)
    executable = PPG_VENV / "bin" / "peripheral-ppg"
    package_src = ROOT / "packages" / "peripheral-ppg" / "src"
    executable.write_text(
        f"#!{python}\nimport runpy, sys\nsys.path.insert(0, {str(package_src)!r})\nrunpy.run_module('peripheral_ppg.cli', run_name='__main__')\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    print(f"PPG CLI shim: {executable}")
    forward_python = Path(os.environ.get("PPG_FORWARD_PYTHON", str(python))).absolute()
    if not forward_python.is_file():
        raise RuntimeError(f"PPG_FORWARD_PYTHON is unavailable: {forward_python}")
    names = LIBRARY_SOURCES + tuple(spec[0] for spec in PACKAGE_SPECS if spec[0] != "pulse")
    sources = [ROOT / ".runtime" / "analysis-python"] + [ROOT / "packages" / name / "src" for name in names]
    prelude = (f"#!{forward_python}\nimport os, runpy, sys\nos.environ['PYTHONDONTWRITEBYTECODE']='1'\n"
               f"sys.dont_write_bytecode=True\nsys.path[:0]={list(map(str,sources))!r}\n")
    for command, module in (("vitaldb-segments", "vitaldb_segments.cli"), ("openbf-walls", "openbf_walls.cli")):
        shim = PPG_VENV / "bin" / command
        shim.write_text(prelude + f"runpy.run_module({module!r}, run_name='__main__')\n", encoding="utf-8")
        shim.chmod(0o755)
        print(f"CLI shim: {shim} (interpreter {forward_python})")
    launcher = PPG_VENV / "bin" / "ppg-python"
    launcher.write_text(prelude + "script = sys.argv.pop(1)\nsys.path.insert(0, os.path.dirname(os.path.abspath(script)))\n"
                        "runpy.run_path(script, run_name='__main__')\n", encoding="utf-8")
    launcher.chmod(0o755)
    print(f"Stage-code launcher: {launcher} (interpreter {forward_python})")
    for retired in RETIRED_PACKAGES:
        old = PPG_VENV / "bin" / retired
        if old.exists():
            old.unlink()
            print(f"removed retired CLI shim: {old}")


def create_workspace() -> None:
    workspace = ROOT / "workspaces" / "fermilink-validation"
    workspace.parent.mkdir(parents=True, exist_ok=True)
    action = "refreshing" if workspace.exists() else "initializing"
    print(f"{action} package-linked workspace: {workspace}")
    run([str(CLI), "init", "peripheral-ppg", str(workspace)])
    readme = workspace / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Peripheral PPG FermiLink workspace\n\n"
            "Primary navigation: `skills/ppg-model/SKILL.md`, `ppg_knowledge/index.md`, and `ppg_examples/engineering_example.json`.\n\n"
            "Pulse and MCX skills, knowledge indexes, and source trees are linked under `external_packages/pulse/` and `external_packages/mcx/`.\n\n"
            f"Run the coupled example with `{ROOT}/.runtime/ppg-venv/bin/peripheral-ppg simulate --config {workspace}/ppg_examples/engineering_example.json --output {ROOT}/runs/workspace-coupled-demo`, then validate the new run with the same CLI's `validate-run` command.\n",
            encoding="utf-8",
        )
    print(f"workspace ready: {workspace}")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true", help="register/refresh managed packages, configure overlays/dependencies, and prepare the PPG CLI")
    parser.add_argument("--workspace", action="store_true", help="initialize the dedicated workspace after registration")
    args = parser.parse_args()
    try:
        for spec in PACKAGE_SPECS:
            check_package(*spec)
        if args.install:
            install_packages()
        if args.workspace:
            if not args.install and "peripheral-ppg" not in registry().get("packages", {}):
                raise RuntimeError("Install/register packages first with --install")
            create_workspace()
    except Exception as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"status": "ready", "registry": str(SCIPKG_ROOT), "packages": [spec[0] for spec in PACKAGE_SPECS]}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
