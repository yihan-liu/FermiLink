# VitalDB knowledge

## Access rules (must follow)

1. Read only files inside the split view named in the goal. Never list or open the raw VitalDB directories (`VitalDB_raw/vital`, `vital_dev`, `dev_reserve`) directly.
2. Only the first 80% of each record is in scope. The last 20% is reserved for later evaluation. Record duration is `dur_s` in `scan/events/<caseid>.json`.
3. Exclude, before reading PLETH: every recorded positive-rate drug-pump interval, 600 s before and after every pump rate change, 60 s before and after each NIBP measurement, 10 s around each arterial-line flush. Pump status before a pump track's first sample is unknown and excluded. Absent pump tracks do not prove that no drug was given.
4. Do not copy raw waveforms into project folders; save derived values only.
5. State in `summary.md` which cases and time ranges were read.

## Format

A `.vital` file is gzip-compressed packets. Packet types used here: track info (track id, type, format, name, sample rate, gain, offset, device id), device info, and data records. Waveform tracks of interest are SNUADC (device) ART and PLETH at 500 Hz: ART in mmHg (radial arterial line), PLETH in device units (finger photoplethysmogram; probe model, wavelengths, internal filtering and automatic gain are unknown). Pump rates are numeric tracks named `*_RATE` on Orchestra or drugpump devices. NIBP is Solar8000/NIBP_SBP.

The `vitaldb` Python package (`vitaldb.VitalFile(path, track_names)`) loads whole tracks. `vitaldb_examples/window_reader_reference.py` decodes only samples inside a requested interval and checks interval, split and event rules before reading; adapt it rather than loading full tracks.

## Derived scan metadata (round-1 scan)

`scan/windows/<caseid>.parquet`: one row per 10 s bin starting at `t_s`. ART: `art_nan`, `art_min`, `art_max`, `map`, `sbp`, `dbp`, `hr`, `ibi_cv`, `n_art`, `art_hf`. PLETH: `ple_nan`, `ple_floor`, `ple_mean`, `ple_p5`, `ple_p95`, `ple_clip`, `hr_ple`, `ple_amp`, `n_ple`. Pairing: `n_pairs`, `r_art`, `r_ple`, `lag`, `lag_iqr`; `ecg_nan`. Read ART columns first and PLETH columns only for bins left after event exclusion.

`scan/events/<caseid>.json`: `caseid`, `dur_s`, `events` (each with `t_s`, `kind`, `name`, `before`, `after`; kinds include `nibp`, `tci` (target-controlled infusion, e.g. RFTN20_CT, PPF20_CT), `pump` and free-text `event`), and `flush` (each with `t_s`, `dur_s`, `plateau`, ring-down `fn_hz`, `zeta`, `n_osc`; NaN when not estimable). Pump-rate tracks are not in the scan; read them from the `.vital` numeric tracks over the first 80%.

A bin was quality-ok in previous rounds when ART/PLETH missingness <= 5%, DBP > 20, SBP < 250, max ART < 300, pulse pressure >= 15 mmHg, HR 30-180, IBI CV < 0.3, PLETH not floored, clipping < 10%, amplitude > 3, p95 < 200 and PLETH/ART HR agree within 10%. These thresholds are a starting point; the goal decides.

## Known gaps

The arterial line site per case is not verified (only aline1/aline2 records). PLETH processing is unknown. Header-readable files are not proven complete.
