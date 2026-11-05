---
name: pwdb
description: Load public PWDB subjects and reconstruct their source-time reference waveforms.
---

# Usage

1. Read `pwdb_knowledge/index.md` for time and pressure conventions.
2. Library only; call it through the ppg-python launcher. The cached subject path comes from the calling goal.
3. Use `reference` for comparisons; never shift, stretch or rescale reference arrays.
