# ppg-physiology knowledge map

Use this package when a goal involves relating arterial pressure to finger PPG: choosing or implementing a model, a wall law for a 1D network, a timing or transfer descriptor, or an optical relation.

- Models from pressure to blood volume and the monitor's observation of it: [models.md](models.md).
- Wall laws for 1D arterial networks (openBF, PWDB): [arterial_walls.md](arterial_walls.md), with the [Langewouters table](langewouters1984_table2.md).
- Timing, harmonics and reliability: [transfer.md](transfer.md).
- Optics: [optics.md](optics.md).
- References: [sources.md](sources.md).

## Evidence labels

Keep these distinct in reports: literature facts (cited), modelling assumptions (stated), engineering parameter choices (declared ranges, not measurements) and project findings (linked to a run). Agreement between a fitted model and a waveform does not identify unique physiology.

## Reference code (`physiology_examples/`)

| File | Implements |
| --- | --- |
| `model_ladder/models/m0..m4*.py` | `predict(art, params)` with `PARAM_BOUNDS`, `DEFAULT_PARAMS` for M0-M4 |
| `model_ladder/observation_operator.py`, `model_ladder/catheter.py` | Monitor operator and catheter correction |
| `transfer_reference.py` | Beat feet, ensembles, beat-segmented and periodic harmonic transfer, weighted harmonic group delay |
| `ensemble_metrics_reference.py` | Ensemble NMSE, odd/even noise ceiling, morphology features |
| `absorption_linearization_reference.py` | Same-photon absorption reweighting and log-intensity linearization |

These passed synthetic checks when written; numbers they produce are not validated physiology.
