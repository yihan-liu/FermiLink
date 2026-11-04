"""Public CLI smoke checks using synthetic, in-memory signals only."""
import json
import numpy as np

from ppg_forward.cli import main
from ppg_forward.manifests import dump, validate_run


def test_doctor_fresh_directory(tmp_path):
    out = tmp_path / "doctor"
    assert main(["doctor", "--out", str(out)]) in (0, 1)
    manifest = json.loads((out / "manifest.json").read_text())
    report = json.loads((out / "doctor.json").read_text())
    assert manifest["status"] == report["status"]
    assert not report["solver_executed"]
    assert "M3" in report["capabilities"] and "mcx_cli" in report
    before = (out / "manifest.json").read_bytes()
    assert main(["doctor", "--out", str(out)]) == 1
    assert (out / "manifest.json").read_bytes() == before
    if manifest["status"] == "complete":
        assert validate_run(out)["valid"]


def test_synthetic_select_fit_evaluate_validate(tmp_path, monkeypatch):
    # Only the selection/raw-loading boundaries are replaced. Actual fitting,
    # saved-parameter reevaluation, manifest writing and CLI routing execute.
    from ppg_forward import selection_driver, round2_driver
    from ppg_forward.segments import WindowData
    op = {"lo_hz": .2, "hi_hz": 10., "order": 2, "phase": "causal",
          "sign": 1, "device_delay_s": .4}
    split, cases, config = [tmp_path / name for name in ("split.csv", "cases.txt", "config.json")]
    split.write_text("caseid,split,source_dir\n11,train,vital_dev\n")
    cases.write_text("11\n")
    dump(config, {})
    def selected(split_path, cases_path, out, **kwargs):
        dump(out / "selection.json", {"split_path": str(split_path),
             "cases_path": str(cases_path), "requested_caseids": [11]})
        (out / "windows.csv").write_text("caseid,start_s,end_s\n11,0,30\n11,900,930\n11,1800,1830\n")
        return {"input_paths": [str(split_path), str(cases_path), str(config)]}
    monkeypatch.setattr(selection_driver, "run_select", selected)
    def windows(*args, **kwargs):
        fs = 500
        t = np.arange(30 * fs) / fs
        return iter([WindowData(t + j*900, mean + 20*np.cos(2*np.pi*1.2*t),
                 100 + 20*np.cos(2*np.pi*1.2*(t-.5)), fs, 11, j*900., j*900.+30)
                 for j, mean in enumerate((75., 95., 82.))])
    monkeypatch.setattr(round2_driver, "load_selected_windows", windows)
    selection, fits, evaluated = [tmp_path / name for name in ("selection", "fits", "evaluated")]
    assert main(["select-segments", "--split", str(split), "--cases", str(cases),
                 "--config", str(config), "--out", str(selection)]) == 0
    operator = tmp_path / "operator.json"
    dump(operator, op)
    assert main(["fit", "--segments", str(selection), "--models", "M0",
                 "--operator", "frozen:" + str(operator), "--max-nfev", "2",
                 "--out", str(fits)]) == 0
    prereg = tmp_path / "PREREG.md"
    prereg.write_text("Synthetic CLI check only.\n")
    assert main(["evaluate", "--fits", str(fits), "--prereg", str(prereg),
                 "--out", str(evaluated)]) == 0
    for directory in (selection, fits, evaluated):
        assert validate_run(directory)["valid"]
        assert main(["validate-run", str(directory), "--out",
                     str(tmp_path / ("audit-" + directory.name))]) == 0
    (evaluated / "work" / "summary.json").write_text("{}")
    assert main(["validate-run", str(evaluated), "--out", str(tmp_path / "tamper-audit")]) == 1
