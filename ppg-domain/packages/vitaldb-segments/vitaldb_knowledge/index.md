# VitalDB window reader and selection

## Reader

`segments.load_window(caseid, start_s, end_s, authorization, fs_hz)` decodes only SNUADC ART/PLETH samples inside an approved interval; other packet bytes are skipped without building sample values. Native rate is 500 Hz; `fs_hz=50` returns a polyphase-resampled copy. ART is mmHg, PLETH device units, time seconds from record start. A window with missing or nonfinite samples is refused.

Before any read the authorization is checked: case in the explicit list and allowed split, raw path under the `vital_dev` raw directory, interval listed exactly in the approved windows and wholly inside the readable record fraction. Before PLETH, recorded numeric pump-rate tracks are read over the readable fraction and the event exclusions are applied.

`load_selected_windows(selection_dir, fs_hz)` iterates the windows of a saved selection with the same checks.

## Event exclusions

Policy `owner-20261104-drugpump-rate-nibp`: every recorded positive-rate pump interval, +/-600 s around every rate change, +/-60 s around NIBP measurements (scan Solar8000/NIBP_SBP value change or >120 s since the previous sample), +/-10 s around flushes. Pump status before a track's first sample is unknown and excluded. Absent tracks do not establish drug absence.

## Scan-based quality

Selection uses derived 10 s scan bins (`<scan_dir>/windows/<caseid>.parquet`, `<scan_dir>/events/<caseid>.json`). ART columns are read first; PLETH columns only for bins left after event exclusion. A bin is quality-ok when ART/PLETH missingness, pressure ranges, HR, IBI CV (below the configured cutoff), PLETH floor/clip/amplitude and HR agreement pass. Amplitude steps larger than the gain factor between adjacent bins are flagged; `train-p995` sets the factor to max(1.5, exp(Q0.995 |delta log amplitude|)) over Train quality pairs.

Saved availability per case reports readable bins, event-excluded bins, quality bins, qualifying time and the selection reason.
