"""VitalDB access contract enforced by the readers and the run audit.

These values restate the workspace split manifest (split-v1): raw records come
only from the vital_dev source directory, only Train or explicitly opted-in
Validation cases are readable, and only the first RECORD_FRACTION of each
record is in scope. A new split version that changes them changes this file.
"""
SOURCE_DIR = "vital_dev"
FORBIDDEN_PATH_PARTS = ("vital", "dev_reserve")
ALLOWED_SPLITS = ("train", "validation")
RECORD_FRACTION = 0.8
TRACKS = ("SNUADC/ART", "SNUADC/PLETH")
EVENT_TRACKS = ("Orchestra/*_RATE", "drugpump*/*_RATE", "*/drugpump*_RATE")
EVENT_POLICY = "owner-20261104-drugpump-rate-nibp"
