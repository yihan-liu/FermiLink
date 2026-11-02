import math
import json
import tempfile
import unittest
from pathlib import Path
from peripheral_ppg.model import local_model, blood_fraction
from peripheral_ppg.analysis import ac_dc, align
from peripheral_ppg.records import save_record
from peripheral_ppg.cli import validate_run, digest


class ModelTest(unittest.TestCase):
    def test_flow_conservation_and_timestep_refinement(self):
        c = {"R_in_mmHg_s_per_mL": 1000, "R_out_mmHg_s_per_mL": 1500,
             "C_mL_per_mmHg": 0.001, "P_initial_mmHg": 62, "P_venous_mmHg": 5,
             "P_ref_mmHg": 62, "V_ref_mL": 0.1}
        # Compare the numerical volume derivative at an interior point to net flow.
        h = 1e-4
        near = local_model([0, 0.2-h, 0.2, 0.2+h], [90, 90+100*(0.2-h), 110, 90+100*(0.2+h)], c)
        dv_dt = (near[3]["V_local_mL"] - near[1]["V_local_mL"])/(2*h)
        self.assertAlmostEqual(dv_dt, near[2]["Q_in_mL_per_s"]-near[2]["Q_out_mL_per_s"], places=8)
        # Refine the same piecewise-linear input, without changing its waveform.
        coarse = local_model([0, .2, .4, .6], [90, 110, 95, 90], c)
        fine = local_model([0, .1, .2, .3, .4, .5, .6], [90, 100, 110, 102.5, 95, 92.5, 90], c)
        for a, b in zip(coarse, fine[::2]):
            for name in ("P_local_mmHg", "V_local_mL", "Q_in_mL_per_s", "Q_out_mL_per_s"):
                self.assertAlmostEqual(a[name], b[name], places=11)

    def test_align_preserves_time_and_interpolates(self):
        result = align([0, .5, 1, 1.5, 2], [10, 11, 12, 13, 14], [0, 1, 2], [0, 2, 4])
        self.assertEqual(result, [(0, 10, 0), (.5, 11, 1), (1, 12, 2), (1.5, 13, 3), (2, 14, 4)])

    def test_constant_input_and_volume(self):
        c = {"R_in_mmHg_s_per_mL": 2, "R_out_mmHg_s_per_mL": 3,
             "C_mL_per_mmHg": 0.5, "P_initial_mmHg": 10, "P_venous_mmHg": 5,
             "P_ref_mmHg": 10, "V_ref_mL": 2}
        rows = local_model([0, 1], [100, 100], c)
        target, tau = 62, 0.6
        self.assertAlmostEqual(rows[-1]["P_local_mmHg"], target + (10-target)*math.exp(-1/tau))
        self.assertAlmostEqual(rows[-1]["V_local_mL"], 2 + 0.5*(rows[-1]["P_local_mmHg"]-10))

    def test_fraction_rejects_invalid(self):
        with self.assertRaises(ValueError):
            blood_fraction([{"time_s": 0, "V_local_mL": 3}], {"f_b_ref": .1, "V_ref_mL": 1, "V_sampling_mL": 1})
        self.assertEqual(ac_dc([1, 2, 3])["ac_over_dc"], 1)

    def test_negative_local_volume_rejected(self):
        c = {"R_in_mmHg_s_per_mL": 2, "R_out_mmHg_s_per_mL": 3,
             "C_mL_per_mmHg": 0.5, "P_initial_mmHg": 0, "P_venous_mmHg": 5,
             "P_ref_mmHg": 10, "V_ref_mL": 2}
        with self.assertRaises(ValueError):
            local_model([0, 1], [100, 100], c)

    def test_nonfinite_direct_comparison_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("config.json", "input_config.json"):
                (root/name).write_text("{}")
            (root/"comparison.json").write_text('{"difference_in_standard_errors": NaN}')
            manifest = {"status": "complete", "run_id": "one", "config": "config.json",
                        "config_sha256": digest(root/"config.json"), "input_config_sha256": digest(root/"input_config.json"),
                        "outputs": {"comparison.json": digest(root/"comparison.json")}}
            (root/"manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                validate_run(root)

    def test_record_requires_completed_run_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            (root/"data.csv").write_text("data")
            manifest.write_text(json.dumps({"run_id": "one", "status": "complete", "outputs": {"data.csv": digest(root/"data.csv")}}))
            record = {"question": "q", "hypothesis": "h", "parameters_and_sources": {},
                      "run_id": "one", "evidence": ["manifest.json"], "conditional_conclusion": "c",
                      "ambiguities": [], "next_question": "next"}
            save_record(root/"record.json", record)
            record["run_id"] = "missing"
            with self.assertRaises(ValueError):
                save_record(root/"other.json", record)
            record["run_id"] = "one"
            (root/"data.csv").unlink()
            with self.assertRaises(ValueError):
                save_record(root/"missing.json", record)


if __name__ == "__main__":
    unittest.main()
