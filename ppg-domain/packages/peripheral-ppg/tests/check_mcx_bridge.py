"""One-wavelength integration smoke: synthetic pressures, real MCX only."""
import json
import sys
from pathlib import Path
from peripheral_ppg.model import local_model, blood_fraction
from peripheral_ppg.cli import run_wave

package = Path(__file__).resolve().parents[1]
config = json.loads((package / "ppg_examples/engineering_example.json").read_text())
config["mcx_executable"] = str((package / "ppg_examples" / config["mcx_executable"]).resolve())
rows = local_model([0, 0.1, 0.2], [90, 100, 110], config["local"])
blood_fraction(rows, {**config["mixture"], "V_ref_mL": config["local"]["V_ref_mL"]})
out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=False)
run_wave(out, config, config["wavelengths"][0], rows)
print(json.dumps({"data_origin": "synthetic test input", "mcx": "real", "rows": rows}, indent=2))
