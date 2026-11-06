"""Create an explicitly conditional record for an existing coupled run."""
import json
import os
import sys
from pathlib import Path
from peripheral_ppg.records import save_record

run, target = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
manifest = json.loads((run/"manifest.json").read_text(encoding="utf-8"))
def rel(path):
    return os.path.relpath(path, target.parent)
record = {"question": "Can the assumed local volume variation drive a detectable model optical response?",
          "hypothesis": "Under fixed geometry and scattering, mixed absorption varies with local blood fraction.",
          "parameters_and_sources": {"source": "engineering assumptions", "configuration": rel(run/"config.json")},
          "run_id": manifest["run_id"], "evidence": [rel(run/"manifest.json"), rel(run/"coupled.csv"), rel(run/"analysis.json")],
          "conditional_conclusion": "The linked simulation provides an optical response under its configured assumptions; it is not a human validation.",
          "ambiguities": ["Unvalidated parameter values", "No arterial propagation or dynamic tissue deformation"],
          "next_question": "How does the model response change within justified local parameter ranges?"}
save_record(target, record)
