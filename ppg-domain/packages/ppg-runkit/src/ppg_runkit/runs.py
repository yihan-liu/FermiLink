"""Fresh run directories, metadata hashes and run validation.

Data-specific packages supply two hooks: an input guard that refuses files
which must never be hashed (for example raw recordings) and a raw-open
recorder/validator for audited data access.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import uuid
from . import __version__


def now():
    return datetime.now(timezone.utc).isoformat()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False, default=str) + "\n", encoding="utf-8")


def digest(path, guard=None):
    path = Path(path).resolve()
    if guard is not None:
        guard(path)
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def code_version(module=None):
    """Package version and git commit of the module's source tree."""
    if module is None:
        import ppg_runkit as module
    source = Path(module.__file__).parent
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source,
                    text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    return {"package": getattr(module, "__version__", __version__), "git_commit": commit}


def unique_output(command, parent=None):
    parent = Path(parent) if parent else Path(".runtime")
    return parent / (command + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8])


class Run:
    """Hash metadata only; readers report raw opens separately.

    input_guard(path) raises for files that must not be hashed.
    raw_record(path, **scope) normalizes and checks one raw-open record.
    code is the module whose version and git commit are recorded.
    """
    def __init__(self, out, command, inputs=(), parameters=None, *,
                 input_guard=None, raw_record=None, code=None):
        self.input_guard = input_guard
        self.raw_record = raw_record
        self.out = Path(out).absolute()
        self.out.mkdir(parents=True, exist_ok=False)
        self.manifest = {"run_id": self.out.name, "command": command,
            "status": "running", "started_at": now(), "finished_at": None,
            "inputs": {}, "outputs": {}, "code_version": code_version(code),
            "raw_files_opened": [], "parameters": parameters or {}}
        self.result = None
        self._save()
        try:
            self.add_inputs(inputs)
        except Exception as exc:
            self.manifest.update(status="failed", finished_at=now(), error=str(exc))
            self._save()
            raise

    def _save(self):
        dump(self.out / "manifest.json", self.manifest)

    def digest(self, path):
        return digest(path, self.input_guard)

    def add_inputs(self, paths):
        for value in paths:
            path = Path(value).resolve()
            self.manifest["inputs"][str(path)] = self.digest(path)
        self._save()

    def raw_open(self, path=None, **scope):
        if self.raw_record is None:
            raise PermissionError("This run has no audited raw-data reader")
        item = self.raw_record(path, **scope)
        self.manifest["raw_files_opened"].append(item)
        self._save()

    def __enter__(self):
        return self

    def __exit__(self, kind, exc, traceback):
        try:
            outputs = {}
            for path in sorted(self.out.rglob("*")):
                if path == self.out / "manifest.json" or not path.is_file():
                    continue
                if path.is_symlink() or self.out.resolve() not in path.resolve().parents:
                    raise PermissionError("Run outputs must stay inside the fresh run directory")
                outputs[str(path.relative_to(self.out))] = self.digest(path)
            self.manifest["outputs"] = outputs
            if exc:
                self.manifest.update(status="failed", error=str(exc))
            else:
                status = self.result.get("status", "complete") if isinstance(self.result, dict) else "complete"
                if status not in ("complete", "prepared", "blocked"):
                    raise ValueError("Invalid final run status: " + str(status))
                self.manifest["status"] = status
                if self.result is not None:
                    self.manifest["result"] = self.result
        except Exception as audit_error:
            self.manifest.update(status="failed", error=str(audit_error))
            if exc is None:
                raise
        finally:
            self.manifest["finished_at"] = now()
            self._save()
        return False


def validate_run(directory, *, raw_check=None, input_guard=None):
    """Inspect saved evidence without rewriting the inspected run.

    raw_check(root, manifest) returns a list of errors for recorded raw opens.
    A run with raw opens and no raw_check is invalid.
    """
    root = Path(directory).absolute()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    errors = []
    for key in ("run_id", "status", "started_at", "finished_at", "inputs",
                "outputs", "code_version", "raw_files_opened"):
        if key not in manifest:
            errors.append("Missing manifest field: " + key)
    if manifest.get("status") != "complete":
        errors.append("Run status is not complete")
    if not manifest.get("finished_at"):
        errors.append("Run has no finish time")
    if manifest.get("raw_files_opened"):
        if raw_check is None:
            errors.append("Run records raw opens but no raw-access validator was supplied")
        else:
            errors.extend(raw_check(root, manifest))
    for label in ("inputs", "outputs"):
        for name, expected in manifest.get(label, {}).items():
            try:
                if label == "outputs":
                    relative = Path(name)
                    if relative.is_absolute() or ".." in relative.parts:
                        raise PermissionError("Output path escapes run directory")
                    path = root / relative
                    if path.is_symlink() or root.resolve() not in path.resolve().parents:
                        raise PermissionError("Output path escapes run directory")
                else:
                    path = Path(name)
                if digest(path, input_guard) != expected:
                    errors.append(label + " SHA256 mismatch: " + name)
            except (OSError, ValueError, PermissionError) as exc:
                errors.append(label + ": " + name + ": " + str(exc))
    return {"valid": not errors, "run": str(root), "run_id": manifest.get("run_id"),
            "errors": errors, "raw_files_opened": manifest.get("raw_files_opened", [])}
