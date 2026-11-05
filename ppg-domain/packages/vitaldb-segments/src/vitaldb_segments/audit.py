"""Raw-open records, metadata hashing guard and raw-scope validation for VitalDB runs."""
import csv
import json
import math
from pathlib import Path, PurePosixPath
import re

from ppg_runkit.runs import Run, validate_run

from .rules import ALLOWED_SPLITS, EVENT_TRACKS, FORBIDDEN_PATH_PARTS, RECORD_FRACTION, SOURCE_DIR, TRACKS


def metadata_path(path):
    """Refuse to hash or copy raw recordings; derived metadata only."""
    path = Path(path).resolve()
    if path.suffix.lower() == ".vital" or any(part in ("VitalDB_raw",) + FORBIDDEN_PATH_PARTS for part in path.parts):
        raise PermissionError("Raw VitalDB files must be audited, never hashed or copied")
    return path


def raw_record(path=None, **scope):
    if isinstance(path, dict):
        scope = {**path, **scope}
        path = scope.pop("path", scope.pop("raw_path", None))
    if path is None:
        path = scope.pop("raw_path", None)
    value = PurePosixPath(str(path))
    if (value.parent.name != SOURCE_DIR or any(part in FORBIDDEN_PATH_PARTS for part in value.parts)
            or not re.fullmatch(r"[0-9]{4}\.vital", value.name)):
        raise PermissionError("Raw audit path must be an explicit vital_dev/NNNN.vital file")
    caseid = int(value.stem)
    if "caseid" in scope and int(scope["caseid"]) != caseid:
        raise PermissionError("Raw audit caseid does not match its filename")
    return {"path": str(value), "caseid": caseid, **scope}


def audited_run(out, command, inputs=(), parameters=None, *, code=None):
    """A ppg-runkit Run that refuses raw hashing and records audited raw opens."""
    import vitaldb_segments
    return Run(out, command, inputs, parameters, input_guard=metadata_path,
               raw_record=raw_record, code=code or vitaldb_segments)


def metadata_inputs(path):
    """Enumerate a derived metadata directory, never a raw-data directory."""
    path = metadata_path(path)
    if path.is_file():
        return [path]
    result = []
    for item in sorted(path.rglob("*")):
        if item.is_file():
            metadata_path(item)
            result.append(item)
    for item in list(result):
        if item.name == "selection.json":
            selection = json.loads(item.read_text())
            for key in ("split_path", "cases_path"):
                if selection.get(key):
                    result.append(metadata_path(selection[key]))
    return list(dict.fromkeys(result))


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
    if not allow or set(allow) - set(ALLOWED_SPLITS):
        raise PermissionError("Only Train and explicitly selected Validation are allowed")
    with metadata_path(meta["split_path"]).open(newline="") as stream:
        eligible = {int(row["caseid"]) for row in csv.DictReader(stream)
                    if row["split"].lower() in allow and row["source_dir"] == SOURCE_DIR}
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


def validate_raw_scopes(root, manifest):
    records = manifest.get("raw_files_opened", [])
    if not records:
        return []
    errors = []
    try:
        meta, requested, windows = _audit_authorization(root, manifest)
        raw_dir = PurePosixPath(str(meta["raw_dir"]))
        hashed = set(manifest.get("inputs", {}))
        hashed.update(str((root / name).resolve()) for name in manifest.get("outputs", {}))
        if str(Path(meta["split_path"]).resolve()) not in hashed:
            raise PermissionError("Split authorization is not a hashed input")
        if str(Path(meta["cases_path"]).resolve()) not in hashed:
            raise PermissionError("Explicit case list is not a hashed input")
        for record in records:
            item = raw_record(record)
            if PurePosixPath(item["path"]).parent != raw_dir:
                raise PermissionError("Raw path is outside the selection raw directory")
            cid = int(item["caseid"])
            if cid not in requested:
                raise PermissionError("Raw case is outside the explicit authorized case list")
            event_path = Path(meta["scan_dir"]) / "events" / f"{cid}.json"
            if str(event_path.resolve()) not in hashed:
                raise PermissionError("Record duration metadata is not a hashed input")
            event = json.loads(metadata_path(event_path).read_text())
            readable_end = RECORD_FRACTION * float(event["dur_s"])
            start, end = float(item["start_s"]), float(item["end_s"])
            duration = float(item["duration_s"])
            if not all(math.isfinite(v) for v in (readable_end, start, end, duration)):
                raise PermissionError("Nonfinite raw access interval")
            if not 0 <= start < end <= readable_end + 1e-8 or abs(duration - (end-start)) > 1e-8:
                raise PermissionError("Raw access is outside the readable record fraction or has inconsistent duration")
            if item.get("access_kind") == "numeric-events":
                if start != 0 or abs(end-readable_end) > 1e-8:
                    raise PermissionError("Numeric events must use the explicit readable-fraction scope")
                if set(item["tracks"]) != set(EVENT_TRACKS):
                    raise PermissionError("Numeric-event access contains unapproved tracks")
            else:
                if item.get("access_kind", "waveform") != "waveform":
                    raise PermissionError("Unknown raw access kind")
                if not any(cid == c and abs(start-a) < 1e-8 and abs(end-b) < 1e-8
                           for c, a, b in windows):
                    raise PermissionError("Raw waveform interval is absent from approved windows")
                if not item["tracks"] or set(item["tracks"]) - set(TRACKS):
                    raise PermissionError("Waveform access contains unapproved tracks")
    except (OSError, KeyError, ValueError, TypeError, PermissionError) as exc:
        errors.append("Illegal raw audit: " + str(exc))
    return errors


def validate(directory):
    """Validate a run that may contain audited VitalDB raw opens."""
    return validate_run(directory, raw_check=validate_raw_scopes, input_guard=metadata_path)
