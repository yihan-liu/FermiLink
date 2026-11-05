# ppg-transfer

Transfer descriptors between an input waveform and an output waveform: beat feet and ensembles, harmonic ratios H_k, H1 phase delay and the k=1..3 harmonic group delay.

Library only; it has no CLI. Observed records (ART -> PLETH) and model outputs (radial pressure -> digital area) use the same functions, so a delay defined on data and on a model is computed by one implementation.

| Module | Contents |
| --- | --- |
| `beats` | `feet`, `ensemble`, `FOOT_METHOD` |
| `harmonics` | `compute_tf_harmonics` (beat-segmented records), `periodic_phasors`, `periodic_transfer` (one periodic cycle) |
| `delay` | `fit_delay`, `fit_equal_weight_delay`, `operator_phase`, `freeze_harmonic_weights`, `half_branch_diagnostics` |

- [Definitions and units](transfer_knowledge/index.md)
- [Usage notes](skills/ppg-transfer/SKILL.md)
- [Example](transfer_examples/periodic_transfer.py)
