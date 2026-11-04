"""Run real MCX examples in a new directory; use the MCX virtualenv Python."""
import copy
import json
import math
from pathlib import Path
import sys

from mcx_optics import run_simulation, reweight, sensitivity

out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=False)
here = Path(__file__).resolve().parent
cfg = json.loads((here / 'skin_vessel_660.json').read_text())
cfg940 = json.loads((here / 'skin_vessel_940.json').read_text())
run_simulation(cfg, out/'baseline660')
run_simulation(cfg940, out/'baseline940')
rw = {'baseline': str(out/'baseline660'), 'cases': [
    {'name': 'baseline', 'mua_per_mm': [0.04, 0.02, 0.2023]},
    {'name': 'increased_absorption', 'mua_per_mm': [0.04, 0.03, 0.2023]}]}
readings = reweight(rw, out/'reweight')
sensitivity({'baseline': str(out/'baseline660')}, out/'replay')
direct = copy.deepcopy(cfg)
direct['optical_properties'][2][0] = 0.03
direct['seed'] += 99
direct_reading = run_simulation(direct, out/'direct')
estimate = readings[1]
combined_se = math.hypot(estimate['standard_error'], direct_reading['standard_error'])
if combined_se <= 0 or not math.isfinite(combined_se):
    raise ValueError('invalid combined sampling standard error')
z = (estimate['collected_fraction'] - direct_reading['collected_fraction']) / combined_se
comparison = {'reweighted': estimate['collected_fraction'],
              'direct': direct_reading['collected_fraction'],
              'difference': estimate['collected_fraction'] - direct_reading['collected_fraction'],
              'combined_standard_error': combined_se, 'z': z,
              'criterion': 'absolute z <= 4', 'passed': abs(z) <= 4}
(out/'comparison.json').write_text(json.dumps(comparison, indent=2)+'\n')
if not comparison['passed']:
    raise RuntimeError(f'direct versus reweighted difference exceeds 4 combined standard errors: z={z}')
print(f'Outputs: {out}')
