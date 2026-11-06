---
name: vitaldb
description: Read VitalDB ART/PLETH windows from the project's read-only split view under the project's data-access rules.
---

# VitalDB procedure

1. Read the access rules in `vitaldb_knowledge/index.md` first. Use only the view path given by the goal.
2. Use scan metadata to choose candidate intervals before opening any `.vital` file; apply the event exclusions before reading PLETH.
3. Read only the needed intervals inside the first 80% of each record, adapting `vitaldb_examples/window_reader_reference.py`.
4. Save derived values, never raw waveforms. List the cases and intervals read in `summary.md`.
