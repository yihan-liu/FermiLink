---
name: ppg-forward
description: Run individual audited ART-driven waveform, selective-window, fitting, metric and optical commands.
---

# Individual command procedure

1. Read the requested command's `--help` and the relevant equations in `ppg_knowledge/index.md`. Take the explicit input files, configuration, allowed split and output root from the calling goal.
2. Use the registered CLI with `FERMILINK_SCIPKG_ROOT=/data/liuyihan/FermiLink/ppg-domain/.runtime/fermilink-registry`. Choose a fresh output directory. Existing directories are refused.
3. Execute the requested command below. A dependency or input failure remains a failed/blocked result; preserve it and use a fresh directory after correction.
4. Run `ppg-forward validate-run RUN_DIR --out FRESH_AUDIT_DIR`. Inspect status, validation errors and actual raw-access scopes. Return the command, run directory, manifest run_id, audit result and concrete missing inputs.

## Command inputs

- `doctor --out DIR`: inspect imports, driver availability and MCX executable help. This command runs no solver and establishes no experimental acceptance.
- `select-segments --split CSV --cases LIST --config FILE --event-policy NAME --out DIR`: supply an explicit nonempty case list, split CSV and JSON settings. The supported event policy is `owner-20261104-drugpump-rate-nibp`; it may also be supplied in the configuration. Train is default. `--allow-splits validation` is an explicit opt-in. Select `selection_mode` and its configuration options from the calling goal.
- `fit --segments DIR --models LIST --operator fit-global --out DIR`: supply selected-window metadata and model names. To reuse an operator use `--operator frozen:FILE`. Optional search limits and operator-candidate inputs are exposed in `--help`.
- `evaluate --fits DIR --prereg FILE --out DIR`: supply saved fits and the criteria file. Return coverage and undefined metrics alongside scored outputs.
- `cross-window --fits DIR --out DIR`: supply saved fit metadata; retain transferred-window and independent-window diagnostic outputs.
- `mcx-linear --config FILE --out DIR`: supply optical geometry, photon, wavelength and sensitivity settings. Use real MCX when the configuration requests direct simulations.
- `validate-run DIR --out AUDIT_DIR`: audit the inspected run without changing it.

## Enforced data access and output audit

Use package readers and explicit case/window metadata. They allow only selected Train or explicitly opted-in Validation cases from `VitalDB_raw/vital_dev/NNNN.vital`; Test, `dev_reserve`, `vital/` and windows beyond the first 80% are refused. PLETH access requires the supported recorded-event policy. Native ART/PLETH reads are limited to the approved intervals; numeric-event reads carry a separate first-80% audit scope.

The manifest records actual opens, tracks and intervals. Metadata inputs and outputs are hashed; native recordings are not hashed or copied as metadata. Validation checks completion, hashes and explicit raw authorizations. Preserve generated values and report failures through the command result.

The available CLI commands are listed above. Harmonic and statistical Python helpers do not expose `tf-*` CLI commands. The calling goal determines experiment order, cohorts, scientific criteria and owner decisions.
