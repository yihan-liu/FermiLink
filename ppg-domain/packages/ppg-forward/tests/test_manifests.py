"""Synthetic metadata and raw-open audit checks; no native data is opened."""
import json
import pytest

from ppg_forward.manifests import Run, RAW_ROOT, digest, dump, validate_run


def audited_run(tmp_path, split="train", source="vital_dev", allow=("train",)):
    split_path = tmp_path / "split.csv"
    split_path.write_text(f"caseid,split,source_dir\n11,{split},{source}\n")
    cases = tmp_path / "cases.txt"
    cases.write_text("11\n")
    events = tmp_path / "scan" / "events"
    events.mkdir(parents=True)
    dump(events / "11.json", {"dur_s": 1000})
    with Run(tmp_path / "run", "select-segments", inputs=[split_path, cases, events / "11.json"]) as run:
        dump(run.out / "selection.json", {
            "split_path": str(split_path), "cases_path": str(cases),
            "scan_dir": str(events.parent), "allow_splits": list(allow),
            "requested_caseids": [11]})
        (run.out / "windows.csv").write_text("caseid,start_s,end_s\n11,10,40\n")
        run.raw_open(str(RAW_ROOT / "0011.vital"), caseid=11, start_s=10.,
                     end_s=40., duration_s=30., tracks=["SNUADC/ART", "SNUADC/PLETH"])
        run.raw_open(str(RAW_ROOT / "0011.vital"), caseid=11, start_s=0.,
                     end_s=800., duration_s=800., access_kind="numeric-events",
                     tracks=["Orchestra/*_RATE", "drugpump*/*_RATE", "*/drugpump*_RATE"])
    return run.out


def test_hashes_and_authorized_scopes(tmp_path):
    out = audited_run(tmp_path)
    assert validate_run(out)["valid"]
    manifest = json.loads((out / "manifest.json").read_text())
    assert len(manifest["raw_files_opened"]) == 2
    assert not any(".vital" in path for path in manifest["inputs"])
    (out / "windows.csv").write_text("tampered")
    assert not validate_run(out)["valid"]


@pytest.mark.parametrize("split,source,allow", [
    ("test", "vital_dev", ("train",)), ("dev_reserve", "vital_dev", ("train",)),
    ("train", "vital", ("train",)), ("validation", "vital_dev", ("train",)),
])
def test_disallowed_raw_audit(tmp_path, split, source, allow):
    assert not validate_run(audited_run(tmp_path, split, source, allow))["valid"]


def test_validation_opt_in_and_illegal_scope(tmp_path):
    out = audited_run(tmp_path, "validation", allow=("validation",))
    assert validate_run(out)["valid"]
    path = out / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["raw_files_opened"][0]["end_s"] = 810.
    manifest["raw_files_opened"][0]["duration_s"] = 800.
    dump(path, manifest)
    assert not validate_run(out)["valid"]


def test_refuse_raw_hash_and_raw_source(tmp_path):
    with pytest.raises(PermissionError):
        digest(RAW_ROOT / "0011.vital")
    with Run(tmp_path / "run", "test") as run:
        with pytest.raises(PermissionError):
            run.raw_open("/data/liuyihan/database/VitalDB_raw/vital/0011.vital")


@pytest.mark.parametrize("field,value", [
    ("caseid", 12), ("tracks", ["SNUADC/PLETH"]),
    ("end_s", 900.), ("access_kind", "entire-record"),
])
def test_numeric_audit_rejects_modified_scope(tmp_path, field, value):
    out = audited_run(tmp_path)
    path = out / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["raw_files_opened"][1][field] = value
    dump(path, manifest)
    assert not validate_run(out)["valid"]


def test_input_hash_and_stable_recorded_code_version(tmp_path):
    out = audited_run(tmp_path)
    (tmp_path / "cases.txt").write_text("12")
    assert not validate_run(out)["valid"]
    (tmp_path / "cases.txt").write_text("11\n")
    path = out / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["code_version"]["git_commit"] = "historical-code-version"
    dump(path, manifest)
    assert validate_run(out)["valid"]


def test_raw_open_callback_preserves_repeated_opens(tmp_path):
    with Run(tmp_path / "repeat", "test") as run:
        for _ in range(2):
            run.raw_open(str(RAW_ROOT / "0011.vital"), caseid=11, start_s=10.,
                         end_s=40., duration_s=30., tracks=["SNUADC/ART"])
    assert len(run.manifest["raw_files_opened"]) == 2
