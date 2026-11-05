"""Example: radial and digital references of a cached subject on common root time."""
import sys

import numpy as np

from pwdb.data import load_baseline, reference

data = load_baseline(sys.argv[1])
at = np.arange(int(np.ceil(data["period_s"]*data["fs_hz"])))/data["fs_hz"]
radial, digital = reference(data, "radial", at), reference(data, "digital", at)
print(radial["P"].mean(), digital["A"].mean())
