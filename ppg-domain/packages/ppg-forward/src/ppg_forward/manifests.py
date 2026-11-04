"""Fresh run directories, metadata hashes, and authorized raw-open audits."""
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess
import uuid
from . import __version__

RAW_ROOT = PurePosixPath("/data/liuyihan/database/VitalDB_raw/vital_dev")

def now():
    return datetime.now(timezone.utc).isoformat()

def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False, default=str) + "\n", encoding="utf-8")

def metadata_path(path):
    path = Path(path).resolve()
    if path.suffix.lower() == ".vital" or any(part in ("VitalDB_raw", "vital", "dev_reserve") for part in path.parts):
        raise PermissionError("Raw VitalDB files must be audited, never hashed or copied")
    return path

def digest(path):
    h = hashlib.sha256()
    with metadata_path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def raw_record(path=None, **scope):
    if isinstance(path, dict):
        scope = {**path, **scope}
        path = scope.pop("path", scope.pop("raw_path", None))
    if path is None:
        path = scope.pop("raw_path", None)
    value = PurePosixPath(str(path))
    if value.parent != RAW_ROOT or not re.fullmatch(r"[0-9]{4}\.vital", value.name):
        raise PermissionError("Raw audit path must be an explicit vital_dev/NNNN.vital file")
    caseid = int(value.stem)
    if "caseid" in scope and int(scope["caseid"]) != caseid:
        raise PermissionError("Raw audit caseid does not match its filename")
    return {"path": str(value), "caseid": caseid, **scope}

def code_version():
    source = Path(__file__).parent
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source,
                    text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    return {"package": __version__, "git_commit": commit}

def unique_output(command, parent=None):
    parent = Path(parent) if parent else Path(".runtime")
    return parent / (command + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8])

class Run:
    """Hash metadata only; readers report raw opens separately."""
    def __init__(self, out, command, inputs=(), parameters=None):
        self.out = Path(out).absolute()
        self.out.mkdir(parents=True, exist_ok=False)
        self.manifest = {"run_id": self.out.name, "command": command,
            "status": "running", "started_at": now(), "finished_at": None,
            "inputs": {}, "outputs": {}, "code_version": code_version(),
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

    def add_inputs(self, paths):
        for value in paths:
            path = metadata_path(value).absolute()
            self.manifest["inputs"][str(path)] = digest(path)
        self._save()

    def raw_open(self, path=None, **scope):
        item = raw_record(path, **scope)
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
                outputs[str(path.relative_to(self.out))] = digest(path)
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


def _audit_authorization(root, manifest):
    """Read hashed selection metadata, without opening any native recording."""
    paths = [root / name for name in manifest.get("outputs", {})]
    paths += [Path(name) for name in manifest.get("inputs", {})]
    selections = [path for path in paths if path.name == "selection.json"]
    if len(set(selections)) != 1:
        raise PermissionError("Raw opens require one explicit selection.json")
    selection_path = metadata_path(selections[0])
    meta = json.loads(selection_path.read_text())
    allow = [str(v).lower() for v in meta["allow_splits"]]
    if not allow or set(allow) - {"train", "validation"}:
        raise PermissionError("Only Train and explicitly selected Validation are allowed")
    with metadata_path(meta["split_path"]).open(newline="") as stream:
        eligible = {int(row["caseid"]) for row in csv.DictReader(stream)
                    if row["split"].lower() in allow and row["source_dir"] == "vital_dev"}
    requested = set(map(int, meta["requested_caseids"]))
    cases_path = metadata_path(meta["cases_path"])
    if cases_path.suffix.lower() == ".csv":
        with cases_path.open(newline="") as stream:
            explicit = {int(row["caseid"]) for row in csv.DictReader(stream)}
    else:
        explicit = {int(v) for v in re.split(r"[\s,]+", cases_path.read_text().strip()) if v}
    if requested != explicit:
        raise PermissionError("Selection cases differ from the explicit case-list file")
    if not requested or requested - eligible:
        raise PermissionError("Selection includes a disallowed case, source or split")
    windows_path = Path(meta.get("windows_path", selection_path.parent / "windows.csv"))
    if not windows_path.is_absolute():
        windows_path = selection_path.parent / windows_path
    with metadata_path(windows_path).open(newline="") as stream:
        windows = {(int(row["caseid"]), float(row["start_s"]), float(row["end_s"]))
                   for row in csv.DictReader(stream)}
    if any(cid not in requested for cid, _, _ in windows):
        raise PermissionError("Approved windows include cases outside the explicit case list")
    return meta, requested, windows


def _validate_raw_scopes(root, manifest):
    records = manifest.get("raw_files_opened", [])
    if not records:
        return []
    errors = []
    try:
        meta, requested, windows = _audit_authorization(root, manifest)
        hashed = set(manifest.get("inputs", {}))
        hashed.update(str((root / name).resolve()) for name in manifest.get("outputs", {}))
        if str(Path(meta["split_path"]).resolve()) not in hashed:
            raise PermissionError("Split authorization is not a hashed input")
        if str(Path(meta["cases_path"]).resolve()) not in hashed:
            raise PermissionError("Explicit case list is not a hashed input")
        for record in records:
            item = raw_record(record)
            cid = int(item["caseid"])
            if cid not in requested:
                raise PermissionError("Raw case is outside the explicit authorized case list")
            event_path = Path(meta["scan_dir"]) / "events" / f"{cid}.json"
            if str(event_path.resolve()) not in hashed:
                raise PermissionError("Record duration metadata is not a hashed input")
            event = json.loads(metadata_path(event_path).read_text())
            first80 = .8 * float(event["dur_s"])
            start, end = float(item["start_s"]), float(item["end_s"])
            duration = float(item["duration_s"])
            if not all(math.isfinite(v) for v in (first80, start, end, duration)):
                raise PermissionError("Nonfinite raw access interval")
            if not 0 <= start < end <= first80 + 1e-8 or abs(duration - (end-start)) > 1e-8:
                raise PermissionError("Raw access is outside the first 80% or has inconsistent duration")
            if item.get("access_kind") == "numeric-events":
                if start != 0 or abs(end-first80) > 1e-8:
                    raise PermissionError("Numeric events must use the explicit first-80% scope")
                if set(item["tracks"]) != {"Orchestra/*_RATE", "drugpump*/*_RATE", "*/drugpump*_RATE"}:
                    raise PermissionError("Numeric-event access contains unapproved tracks")
            else:
                if item.get("access_kind", "waveform") != "waveform":
                    raise PermissionError("Unknown raw access kind")
                if not any(cid == c and abs(start-a) < 1e-8 and abs(end-b) < 1e-8
                           for c, a, b in windows):
                    raise PermissionError("Raw waveform interval is absent from approved windows")
                if not item["tracks"] or set(item["tracks"]) - {"SNUADC/ART", "SNUADC/PLETH"}:
                    raise PermissionError("Waveform access contains unapproved tracks")
    except (OSError, KeyError, ValueError, TypeError, PermissionError) as exc:
        errors.append("Illegal raw audit: " + str(exc))
    return errors

def validate_run(directory):
    """Inspect saved evidence without rewriting the inspected run."""
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
    errors.extend(_validate_raw_scopes(root, manifest))
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
                if digest(path) != expected:
                    errors.append(label + " SHA256 mismatch: " + name)
            except (OSError, ValueError, PermissionError) as exc:
                errors.append(label + ": " + name + ": " + str(exc))
    return {"valid": not errors, "run": str(root), "run_id": manifest.get("run_id"),
            "errors": errors, "raw_files_opened": manifest.get("raw_files_opened", [])}
