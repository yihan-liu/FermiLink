---
name: vitaldb-segments
description: Select and verify explicit VitalDB ART/PLETH windows under the enforced access contract, and audit runs that read raw records.
---

# Individual command procedure

1. Read the command's `--help`, the README and `vitaldb_knowledge/index.md`. Take the split CSV, explicit case list, selection configuration, allowed splits and output root from the calling goal.
2. Before any new raw read, the calling goal's data-use record must name the case list, intervals and purpose.
3. Run the command with the CLI shim `/data/liuyihan/FermiLink/ppg-domain/.runtime/ppg-venv/bin/vitaldb-segments` into a fresh directory. Never enumerate raw directories or write a separate VitalDB reader.
4. Run `vitaldb-segments validate-run RUN_DIR --out FRESH_AUDIT_DIR`. Report run_id, status, audit errors, raw-open coverage and availability per case. A refused or blocked selection stays a reported result.
