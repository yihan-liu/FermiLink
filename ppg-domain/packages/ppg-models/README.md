# ppg-models

ART-to-area model ladder M0-M4, the monitor observation operator, catheter correction, case-level fitting and normalized ensemble waveform metrics.

Library only; it has no CLI. Stage code calls it through the ppg-python launcher. M3 uses `peripheral-ppg`.

| Module | Contents |
| --- | --- |
| `models` | M0 empirical filter, M1 transmission, M2 nonlinear pressure-volume, M3 2R1C, M4 tapered line; each exposes `predict`, `PARAM_BOUNDS`, `PARAM_PRIORS`, `DEFAULT_PARAMS` |
| `operator` | `apply`: sign, causal band-pass, fractional pure delay, positive gain and offset |
| `catheter` | second-order catheter response, regularized inversion, common bandwidth filter |
| `fit` | `fit_case`, `evaluate_case`, `window_diagnostics`, `prepare_art`, `profile_amplitude` |
| `waveform_metrics` | `window_metrics` (ensemble NMSE, noise ceiling, morphology), `noise_ceiling`, `features`, `aggregate_cases` |

- [Equations and units](models_knowledge/index.md)
- [Usage notes](skills/ppg-models/SKILL.md)
- [Example operator](models_examples/operator.json)
