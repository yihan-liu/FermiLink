"""Build a portable example configuration from the installed MCX examples."""
import json
from pathlib import Path

here = Path(__file__).resolve().parent
packages = here.parent.parent
waves = []
for nm, blood, matrix in [(660, 0.2, 0.02), (940, 0.12, 0.015)]:
    source = packages / "mcx-optics" / "mcx_examples" / f"skin_vessel_{nm}.json"
    optical = json.loads(source.read_text(encoding="utf-8"))
    waves.append({"wavelength_nm": nm, "mua_blood_per_mm": blood, "mua_matrix_per_mm": matrix,
                  "mixture_label": 2, "mcx_config": optical})
config = {
    "pulse_executable": "../../../.runtime/pulse/bin/pulse-physiology",
    "mcx_executable": "../../../.runtime/mcx/venv/bin/mcx-optics",
    "pulse_config": {"duration_s": 10, "sample_interval_s": 0.02},
    "local": {"R_in_mmHg_s_per_mL": 1000, "R_out_mmHg_s_per_mL": 1500,
              "C_mL_per_mmHg": 0.001, "P_venous_mmHg": 5, "P_ref_mmHg": 62,
              "V_ref_mL": 0.1, "P_initial_mmHg": 62},
    "mixture": {"f_b_ref": 0.1, "V_sampling_mL": 1}, "analysis_start_s": 3,
    "parameter_source": "engineering_assumption_not_measured",
    "wavelengths": waves}
(here/"engineering_example.json").write_text(json.dumps(config, indent=2)+"\n", encoding="utf-8")
