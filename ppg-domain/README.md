# ppg-domain

FermiLink toolbox packages for peripheral ABP/PPG research. Each package does one job and contains no experiment design; rounds, cohorts, criteria and thresholds live in the research workspace (`/data/liuyihan/abp-ppg-fermilink`, stage goals under `projects/<round>/prompts/`, stage code under `projects/<round>/code/`).

## Packages

| Package | One-sentence scope | Depends on | CLI |
| --- | --- | --- | --- |
| `pulse` | Official Pulse whole-body circulation runs. | upstream Pulse | `pulse` |
| `mcx` | MCX photon transport, absorption reweighting, replay Jacobians and same-photon absorption linearization. | upstream MCX/PMCX | `mcx` |
| `peripheral-ppg` | Pulse pressure through a local 2R1C bed and MCX optics to simulated PPG. | pulse, mcx | `peripheral-ppg` |
| `vitaldb-segments` | Audited VitalDB ART/PLETH window reading and window selection under the split-v1 access contract. | ppg-runkit | `vitaldb-segments` |
| `ppg-transfer` | Beat ensembles, harmonic transfer H_k, H1 phase delay and k=1..3 group delay, shared by data and models. | - | library |
| `ppg-models` | ART-to-area model ladder M0-M4, observation operator, catheter correction, fitting and ensemble waveform metrics. | ppg-transfer, peripheral-ppg | library |
| `pwdb` | Public PWDB subjects: geometry, wall coefficients and source-time references. | - | library |
| `openbf-walls` | PWDB-network simulations with an adapted openBF solver and three wall laws (not yet numerically accepted). | pwdb, ppg-runkit | `openbf-walls` |
| `ppg-runkit` | Run directories, hashes and validation (library, not registered). | - | - |

Dependencies point only downward; no package imports a sibling at the same level or above.

## Registration and launchers

From the FermiLink root:

```bash
PPG_FORWARD_PYTHON=/home/liuyihan/.venvs/bp/bin/python python3 ppg-domain/scripts/integrate_fermilink.py --install
```

This refreshes the isolated registry `ppg-domain/.runtime/fermilink-registry` and writes CLI shims to `ppg-domain/.runtime/ppg-venv/bin/`: `peripheral-ppg`, `vitaldb-segments`, `openbf-walls`, and `ppg-python`, a launcher that runs a stage script with every package source importable:

```bash
ppg-domain/.runtime/ppg-venv/bin/ppg-python projects/<round>/code/<script>.py ...
```

Runtime directories: `.runtime/julia` (Julia project/depot for openbf-walls), `.runtime/pwdb` (cached PWDB subjects), `.runtime/analysis-python` (extra analysis libraries such as statsmodels).

## Checks

Package tests are synthetic and open no patient data. `python3 scripts/run_acceptance.py --quick` checks structure, registry and solver doctors for pulse, mcx and peripheral-ppg; each package also has its own `doctor`.

Round 2 results were produced by the earlier `ppg-forward` package; reproduce them from git tag `round2-final`.
