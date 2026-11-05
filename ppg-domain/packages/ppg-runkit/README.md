# ppg-runkit

Fresh run directories, input/output SHA256 hashes and run validation, shared by the ppg-domain packages.

This is a library, not a FermiLink-registered package. Each command package exposes its own `validate-run`.

## API (`ppg_runkit.runs`)

| Name | Function |
| --- | --- |
| `Run(out, command, inputs, parameters, *, input_guard, raw_record, code)` | Context manager. Creates `out` (refuses an existing directory), writes `manifest.json` with run_id, status, times, code version, hashed inputs, and on exit hashes every output file. |
| `Run.raw_open(path, **scope)` | Appends an audited raw-data open; requires a `raw_record` hook. |
| `validate_run(directory, *, raw_check, input_guard)` | Checks completion, required fields, input/output hashes and, if raw opens exist, the supplied `raw_check`. Never rewrites the inspected run. |
| `dump`, `digest`, `unique_output`, `code_version` | JSON writing, SHA256 with an optional guard, unique sibling directory names, package version plus git commit. |

Hooks are supplied by data packages. `vitaldb-segments` uses them to refuse hashing raw recordings and to validate raw-access scopes.

Final run status is `complete`, `prepared` or `blocked`; an exception records `failed`.
