---
name: ppg-models
description: Use the M0-M4 ART-to-area models, monitor observation operator, catheter correction and case fitting from stage code.
---

# Usage

1. Read `models_knowledge/index.md` for equations, units and parameter meaning.
2. This package has no CLI. Stage code imports it through the ppg-python launcher (`/data/liuyihan/FermiLink/ppg-domain/.runtime/ppg-venv/bin/ppg-python`); read windows only through `vitaldb-segments`.
3. Operator settings, model lists and any frozen parameters come from the calling goal's input files. Report fit failures, bound hits and undefined metrics as results.
