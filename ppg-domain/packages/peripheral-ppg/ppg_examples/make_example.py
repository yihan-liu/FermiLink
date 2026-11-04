"""Build a portable example configuration from the installed MCX examples."""
import json
import math
from pathlib import Path

here = Path(__file__).resolve().parent
packages = here.parent.parent
# Whole blood, Hb 150 g/L, SaO2 0.98; molar extinction (cm^-1/M) of HbO2 and Hb
# from Prahl's compilation. mua (1/mm) = ln(10) * eps * Hb / 64500 / 10.
HB_G_PER_L, SAO2 = 150, 0.98
EPSILON = {660: (319.6, 3226.56), 940: (1214.0, 693.44)}


def blood_mua(nm):
    hbo2, hb = EPSILON[nm]
    return math.log(10) * (SAO2*hbo2 + (1-SAO2)*hb) * HB_G_PER_L / 64500 / 10


waves = []
for nm, matrix in [(660, 0.02), (940, 0.015)]:
    source = packages / "mcx" / "mcx_examples" / f"skin_vessel_{nm}.json"
    optical = json.loads(source.read_text(encoding="utf-8"))
    blood = round(blood_mua(nm), 4)
    optical["optical_properties"][3][0] = blood  # vessel holds the same blood
    waves.append({"wavelength_nm": nm, "mua_blood_per_mm": blood, "mua_matrix_per_mm": matrix,
                  "mixture_label": 2, "mcx_config": optical})
config = {
    "pulse_executable": "/data/liuyihan/FermiLink/ppg-domain/.runtime/pulse/bin/pulse",
    "mcx_executable": "/data/liuyihan/FermiLink/ppg-domain/.runtime/mcx/venv/bin/mcx",
    "pulse_config": {"duration_s": 10, "sample_interval_s": 0.02},
    "local": {"R_in_mmHg_s_per_mL": 1000, "R_out_mmHg_s_per_mL": 1500,
              "C_mL_per_mmHg": 0.001, "P_venous_mmHg": 5, "P_ref_mmHg": 62,
              "V_ref_mL": 0.1, "P_initial_mmHg": 62},
    "mixture": {"f_b_ref": 0.1, "V_sampling_mL": 1}, "analysis_start_s": 3,
    "parameter_source": "engineering_assumption_not_measured",
    "wavelengths": waves}
(here/"engineering_example.json").write_text(json.dumps(config, indent=2)+"\n", encoding="utf-8")
