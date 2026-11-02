"""Check one real saved MCX run without invoking the solver.

Usage: python check_detector.py /absolute/path/to/baseline660
The saved raw buffer follows PMCX savedetflag='dspw': detector ID, one
scattering-count field per medium, one path field per medium, initial weight.
"""
import json
import math
from pathlib import Path
import sys

import numpy as np

run = Path(sys.argv[1]).resolve()
cfg = json.loads((run / 'config.json').read_text())
reading = json.loads((run / 'reading.json').read_text())
manifest = json.loads((run / 'manifest.json').read_text())
data = np.load(run / 'detected.npz')
raw = data['raw']
medium_count = len(cfg['optical_properties']) - 1
assert raw.ndim == 2 and raw.shape[0] == 2 + 2 * medium_count
assert raw.shape[1] == reading['detected_count'] and np.all(raw[0] == 1)
voxel_mm = cfg['geometry']['voxel_mm']
paths_mm = raw[1 + medium_count:1 + 2 * medium_count].T.astype(float) * voxel_mm
np.testing.assert_allclose(paths_mm, data['paths_mm'], rtol=0, atol=0)
w0 = raw[-1].astype(float)
np.testing.assert_array_equal(w0, data['w0'])
mua = np.asarray(cfg['optical_properties'], dtype=float)[1:, 0]
weights = w0 * np.exp(-np.sum(paths_mm * mua, axis=1))
launched = cfg['nphoton']
fraction = weights.sum() / launched
area_mm2 = math.pi * (cfg['detector']['radius_voxels'] * voxel_mm) ** 2
reflectance = fraction / area_mm2
assert launched == reading['launched_count'] and launched > len(weights)
assert manifest['units']['path'] == 'mm' and manifest['units']['mua'] == '1/mm'
assert math.isclose(fraction, reading['collected_fraction'], rel_tol=1e-12)
assert math.isclose(area_mm2, reading['detector_area_mm2'], rel_tol=1e-12)
assert math.isclose(reflectance, reading['reflectance_per_mm2'], rel_tol=1e-12)
print(json.dumps({'passed': True, 'run': str(run), 'detected': len(weights),
                  'launched': launched, 'collected_fraction': fraction,
                  'fraction_unit': '1', 'area_mm2': area_mm2,
                  'reflectance_per_mm2': reflectance}, indent=2))
