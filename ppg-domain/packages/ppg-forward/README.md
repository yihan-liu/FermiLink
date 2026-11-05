# ppg-forward

ART-driven waveform models, selective VitalDB window access, fitting, physical-time metrics, native-sample harmonic descriptors and detected-photon optical calculations.

## Installation

From the FermiLink root, register with:

```bash
PPG_FORWARD_PYTHON=/home/liuyihan/.venvs/bp/bin/python python3 ppg-domain/scripts/integrate_fermilink.py --install
```

The CLI shim is `ppg-domain/.runtime/ppg-venv/bin/ppg-forward`. Use the project registry at `ppg-domain/.runtime/fermilink-registry`. Runtime dependencies are in `pyproject.toml`.

## Commands

| Command | Inputs and function |
| --- | --- |
| `doctor --out DIR` | Inspect Python dependencies, drivers and MCX executable availability; runs no solver. |
| `select-segments --split CSV --cases LIST --config FILE --event-policy NAME --out DIR` | Select and verify explicit case windows. `--allow-splits` defaults to `train`. |
| `fit --segments DIR --models M0,M1 --operator fit-global --out DIR` | Fit selected models and a global operator. Use `--operator frozen:FILE` to supply a saved operator. |
| `evaluate --fits DIR --prereg FILE --out DIR` | Evaluate saved fits using the supplied criteria file. |
| `cross-window --fits DIR --out DIR` | Compute within-case cross-window predictions and diagnostic reference fits. |
| `mcx-linear --config FILE --out DIR` | Run the configured detected-photon optical calculation and requested direct MCX comparisons. |
| `validate-run DIR --out AUDIT_DIR` | Audit a saved manifest, metadata hashes and raw-access scopes without changing the inspected run. |

Use each command's `--help` for optional arguments. Selection settings are supplied in JSON: `scan_dir`, `gain_step_factor`, `ibi_cv_cutoff`, `selection_mode`, and the options consumed by that mode. Sliding mode accepts `stride_s` and `min_qualifying_time_s`; choose settings in the experiment's prompt. There are no `tf-extract`, `tf-decompose` or `tf-predict` CLI commands. Python harmonic and statistical helpers are documented in the knowledge index.

## Run and access rules

Every command creates a fresh output directory and refuses an existing one. Its `manifest.json` records status, timestamps, code version, metadata input/output SHA256 values and actual raw opens. Raw VitalDB recordings are audited by case, track and time interval; they are not hashed or copied as command metadata.

Readers accept explicitly listed cases in the supplied split and only `VitalDB_raw/vital_dev/NNNN.vital`. Train is the default; Validation needs explicit `--allow-splits validation`. Test, `dev_reserve` and `vital/` sources are refused. Waveform decoding is restricted to approved ART/PLETH windows inside the first 80% of the record. The reader requires the supported recorded-event policy before PLETH access; its exact policy identifier and exclusions are described by the selection input and saved metadata.

`validate-run` requires a complete run, matching metadata hashes and valid explicit case/time/track authorizations. A doctor result describes environment checks, not an experimental result.

- [Command procedures](skills/ppg-forward/SKILL.md)
- [Equations and units](ppg_knowledge/index.md)
- [Configurations](ppg_examples/)
- [Synthetic and access checks](tests/)
