# ppg-forward

Round2 compares normalized fingertip PLETH shape and timing predicted from measured ART. The package provides the fixed M0-M4 ladder, a monitor observation operator, selective VitalDB reads, fitting, metrics and an absorption/MCX check. Codex develops and reviews the package. DeepSeek through FermiLink loop executes experiment stages in the research workspace.

## Installation and navigation

Register only with `PPG_FORWARD_PYTHON=/home/liuyihan/.venvs/bp/bin/python python3 ppg-domain/scripts/integrate_fermilink.py --install` from the FermiLink root. This creates the project-local CLI shim under `ppg-domain/.runtime/ppg-venv/bin/ppg-forward`. Runtime dependencies are declared in pyproject.toml; the local analysis interpreter already supplies NumPy/SciPy/pandas/VitalDB. M3 imports peripheral-ppg; optical runs use the registered mcx package and real solver.

- `skills/ppg-forward/SKILL.md`: step-by-step executor workflow.
- `ppg_knowledge/index.md`: equations, units, parameter bounds and interpretation.
- `ppg_examples/`: explicit pilot/operator and MCX configurations.
- `tests/`: synthetic numerical and data-access checks.

## Commands

`doctor`, `select-segments`, `fit`, `evaluate`, `cross-window`, `mcx-linear`, and `validate-run` are exposed through `ppg-forward`. Use each command's `--help` for its exact options. Commands create a fresh output directory and refuse an existing one. Every run records a manifest with input/output SHA256 values, code version, status, times and actual raw-file opens. Raw VitalDB files are never hashed as whole-record waveform inputs; their audited access list records the allowed case and time range separately from the explicitly hashed command input files.

Selection accepts an explicit case-list file and the existing split CSV. Train is the default allowed split. Validation is enabled explicitly only in the owner-approved validation stage. Test, dev_reserve and vital/ paths are refused before opening. Raw records stay in place; output artifacts contain selection metadata and fitted/aggregated results, not copied native recordings.

## Research execution

The workspace retains PROTOCOL.md, DATA_USE.md, PREREG.md, stage prompts, results and STATE.yaml. Commit the workspace before a stage. Launch `FERMILINK_SCIPKG_ROOT=/data/liuyihan/FermiLink/ppg-domain/.runtime/fermilink-registry /data/liuyihan/FermiLink/.venv/bin/fermilink loop <prompt> --package ppg-forward --max-iterations N --no-completion-commit` in a named tmux session. Codex registers the job, reviews manifest validation, confirms the loop preserved protocol/PREREG/package source, and commits accepted outputs.

Pilot:20 stratified Train cases x3 windows. Then finalize preregistration in its own commit and stop at Gate1 for Yihan. Batch:approximately200 non-pilot Train cases x3-5 windows; freeze code/operator/model parameters and stop at Gate2. Validation:approximately150 cases, once, with frozen global parameters. MCX may run in parallel. The round protocol and dated owner amendments govern every stage.

## Scope

Endpoints are normalized ensemble-beat NMSE and timing/morphology features. BP levels, SBP/DBP scoring, PPG-to-BP inversion, AC/DC fitting, per-case3D optics, wrist/ring work and new model variants are outside this round. The MCX AC/DC bound is a forward optical engineering input, separate from monitored PLETH amplitude fitting.

Built on FermiLink, peripheral-ppg and MCX. Literature and modeling assumptions are documented in the knowledge index.
