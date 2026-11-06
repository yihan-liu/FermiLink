# ppg-physiology

Domain knowledge for peripheral arterial pressure and photoplethysmography modelling: model equations, arterial wall laws with verified literature parameters, transfer-function and timing definitions, waveform metrics and optical absorption relations. Knowledge and reference code only; no CLI and no experiment design.

| File | Topic |
| --- | --- |
| [physiology_knowledge/index.md](physiology_knowledge/index.md) | Map of topics and how to use the reference code |
| [models.md](physiology_knowledge/models.md) | ART-to-volume models M0-M4, 2R1C bed, monitor observation operator, catheter response |
| [arterial_walls.md](physiology_knowledge/arterial_walls.md) | 1D arterial wall laws: square-root (PWDB), Voigt viscosity, Hughes exponential, Langewouters arctangent |
| [langewouters1984_table2.md](physiology_knowledge/langewouters1984_table2.md) | Verified transcription of Langewouters 1984 Table 2 (65 aortas) |
| [transfer.md](physiology_knowledge/transfer.md) | Beat feet, ensembles, harmonic transfer H_k, phase and group delay, split-half reliability |
| [optics.md](physiology_knowledge/optics.md) | Blood-volume absorption mixing and same-photon log-intensity linearization |
| [sources.md](physiology_knowledge/sources.md) | Verified references |

When a run pins this package, the `openbf`, `pwdb`, `vitaldb`, `mcx` and `pulse` knowledge bases are available under `external_packages/<id>/`.

Reference code in `physiology_examples/` shows one tested way to implement the definitions. It is not a fixed estimator: copy and adapt it in a project folder, and state any change.
