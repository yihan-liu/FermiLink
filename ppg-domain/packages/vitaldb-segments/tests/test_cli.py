"""CLI smoke checks with synthetic metadata only."""
import json

from ppg_runkit.runs import dump
from vitaldb_segments.cli import main
from vitaldb_segments.audit import validate


def test_doctor_fresh_directory(tmp_path):
    out = tmp_path / "doctor"
    assert main(["doctor", "--out", str(out)]) in (0, 1)
    manifest = json.loads((out / "manifest.json").read_text())
    report = json.loads((out / "doctor.json").read_text())
    assert manifest["status"] == report["status"] and report["data_opened"] is False
    before = (out / "manifest.json").read_bytes()
    assert main(["doctor", "--out", str(out)]) == 1
    assert (out / "manifest.json").read_bytes() == before


def test_select_and_validate_with_replaced_selector(tmp_path, monkeypatch):
    from vitaldb_segments import selection
    split, cases, config = [tmp_path / name for name in ("split.csv", "cases.txt", "config.json")]
    split.write_text("caseid,split,source_dir\n11,train,vital_dev\n")
    cases.write_text("11\n")
    dump(config, {})
    def selected(split_path, cases_path, out, **kwargs):
        dump(out / "selection.json", {"split_path": str(split_path),
             "cases_path": str(cases_path), "requested_caseids": [11]})
        (out / "windows.csv").write_text("caseid,start_s,end_s\n11,0,30\n")
        return {"input_paths": [str(split_path), str(cases_path), str(config)]}
    monkeypatch.setattr(selection, "run_select", selected)
    out = tmp_path / "selection"
    assert main(["select-segments", "--split", str(split), "--cases", str(cases),
                 "--config", str(config), "--out", str(out)]) == 0
    assert validate(out)["valid"]
    assert main(["validate-run", str(out), "--out", str(tmp_path / "audit")]) == 0
    (out / "work" / "windows.csv").write_text("tampered")
    assert main(["validate-run", str(out), "--out", str(tmp_path / "tamper-audit")]) == 1
