#!/usr/bin/env python3
"""Read-only inventory of the FermiLink and solver environment for ppg-domain."""
from __future__ import annotations
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FERMILINK = Path(os.environ.get("FERMILINK_ROOT", "/data/liuyihan/FermiLink"))
PACKAGES = {
    "pulse": ("pulse_physiology", "pulse_knowledge", "pulse_examples", "pulse_source"),
    "mcx": ("mcx_optics", "mcx_knowledge", "mcx_examples", "mcx_source"),
    "peripheral-ppg": ("peripheral_ppg", "ppg_knowledge", "ppg_examples", None),
}

def command_output(args: list[str]) -> str | None:
    try:
        result = subprocess.run(args, check=True, text=True, capture_output=True)
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None

def main() -> int:
    venv_python = FERMILINK / ".venv/bin/python"
    venv_cli = FERMILINK / ".venv/bin/fermilink"
    mcx_env_python = ROOT / ".runtime/mcx/venv/bin/python"
    result: dict = {
        "ppg_domain_root": str(ROOT),
        "fermilink_root": str(FERMILINK),
        "python": sys.version.split()[0],
        "fermilink_git_commit": command_output(["git", "-C", str(FERMILINK), "rev-parse", "--short", "HEAD"]),
        "fermilink_python": command_output([str(venv_python), "-c", "import importlib.metadata as m; print(m.version('fermilink'))"]) if venv_python.exists() else None,
        "fermilink_cli": str(venv_cli) if venv_cli.exists() else None,
        "gpu": command_output(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"]),
        "solver_clis": {
            "pulse": str(ROOT / ".runtime/pulse/bin/pulse") if (ROOT / ".runtime/pulse/bin/pulse").is_file() else str(ROOT / ".runtime/pulse/bin/pulse-physiology") if (ROOT / ".runtime/pulse/bin/pulse-physiology").is_file() else None,
            "mcx": str(ROOT / ".runtime/mcx/venv/bin/mcx") if (ROOT / ".runtime/mcx/venv/bin/mcx").is_file() else str(ROOT / ".runtime/mcx/venv/bin/mcx-optics") if (ROOT / ".runtime/mcx/venv/bin/mcx-optics").is_file() else None,
            "peripheral-ppg": str(ROOT / ".runtime/ppg-venv/bin/peripheral-ppg") if (ROOT / ".runtime/ppg-venv/bin/peripheral-ppg").is_file() else None,
        },
        "mcx_python_packages": {},
        "upstream_commits": {name: command_output(["git", "-C", str(ROOT / "upstream" / name), "rev-parse", "--short", "HEAD"]) for name in ("pulse", "mcx")},
        "packages": {},
        "registry_env": os.environ.get("FERMILINK_SCIPKG_ROOT"),
    }
    if mcx_env_python.is_file():
        for name in ("pmcx", "numpy", "mcx"):
            result["mcx_python_packages"][name] = command_output([str(mcx_env_python), "-c", f"import importlib.metadata as m; print(m.version({name!r}))"])
    for package_id, (namespace, knowledge, examples, source) in PACKAGES.items():
        path = ROOT / "packages" / package_id
        result["packages"][package_id] = {
            "path_exists": path.is_dir(),
            "pyproject": (path / "pyproject.toml").is_file(),
            "readme": (path / "README.md").is_file(),
            "skills": (path / "skills").is_dir(),
            "source_namespace": (path / "src" / namespace).is_dir(),
            "knowledge": (path / knowledge).is_dir(),
            "examples": (path / examples).is_dir(),
            "upstream_source_entry": str((path / source).resolve()) if source and (path / source).exists() else None,
        }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
