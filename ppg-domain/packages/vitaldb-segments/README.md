# vitaldb-segments

Audited reading of explicit VitalDB ART/PLETH windows and scan-based window selection.

## Commands

| Command | Function |
| --- | --- |
| `doctor --out DIR` | Check reader dependencies; opens no data. |
| `select-segments --split CSV --cases LIST --config FILE [--allow-splits train] [--event-policy NAME] --out DIR` | Select windows for an explicit case list from derived scan metadata, then verify each selected raw window. |
| `validate-run DIR --out AUDIT_DIR` | Audit a run's hashes and every recorded raw open against its selection metadata. |

The CLI shim is `ppg-domain/.runtime/ppg-venv/bin/vitaldb-segments`. Every command creates a fresh directory and refuses an existing one. Selection outputs are `work/selection.json`, `work/windows.csv`, `work/cases.csv`.

## Selection configuration

JSON keys: `scan_dir`, `raw_dir` (a `vital_dev` directory), `gain_step_factor` (number or `train-p995`), `ibi_cv_cutoff`, `event_policy`, `selection_mode`.

- `spaced`: `windows_per_case` (3-5) windows of 30 s at least 600 s apart, largest MAP-separated pair first; `n_cases` stratified by MAP/HR tertile and damping.
- `sliding`: every 30 s window on a `stride_s` grid inside qualifying time; a case is eligible when its qualifying time (union of quality- and event-qualified 10 s scan bins) is at least `min_qualifying_time_s`.

## Enforced access contract

`vitaldb_segments/rules.py` holds the contract the readers and the audit enforce. It restates the workspace split manifest (split-v1):

- raw files only as `<raw_dir>/NNNN.vital` with `raw_dir` named `vital_dev`; paths through `vital/` or `dev_reserve` are refused;
- only cases of the explicit list whose split is `train`, or `validation` with `--allow-splits validation`;
- only the first 80% of each record;
- PLETH only after the recorded-event policy has excluded positive-rate pump infusions, every rate change +/-600 s and NIBP measurements +/-60 s;
- waveform tracks SNUADC/ART and SNUADC/PLETH only.

Raw recordings are never hashed or copied; the manifest records each open with case, tracks and interval.

- [Command procedure](skills/vitaldb-segments/SKILL.md)
- [Reader and selection details](vitaldb_knowledge/index.md)
- [Example configuration](vitaldb_examples/selection_sliding.json)
