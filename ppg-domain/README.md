# ppg-domain

FermiLink packages that DeepSeek uses as its toolbox for peripheral ABP/PPG simulation. Each package is a knowledge base for a mature tool or data source: skills, documentation, upstream source (read-only) and examples. Packages say how to use a tool, not what to study; research goals, cohorts, criteria and interpretation live in the research workspace (`/data/liuyihan/abp-ppg-fermilink`). Registered packages change rarely, through reviewed batches of DeepSeek's suggested skills updates.

## Packages

| Package | Contents | CLI |
| --- | --- | --- |
| `pulse` | Official Pulse whole-body circulation engine | `pulse` |
| `mcx` | Official MCX/PMCX photon transport, absorption reweighting, replay Jacobians | `mcx` |
| `openbf` | openBF 1D arterial blood-flow solver (single implementation `openbf_param/`, openBF 2.8.0 with added options) and its limits | `openbf` |
| `pwdb` | Public Pulse Wave DataBase: files, sites, wall model, time conventions | - |
| `vitaldb` | VitalDB format, tracks, scan metadata and the data-access rules | - |
| `arterial-walls` | Literature wall laws for 1D networks (square-root/PWDB, Voigt, Hughes, Langewouters) with verified parameters and reference closures | - |

Entry rule (same as mcx): upstream tools unchanged (openbf: one implementation, `packages/openbf/openbf_param`, whose added options default to openBF 2.8.0 behaviour), wrappers expose only the tool's own capabilities, knowledge explains use and contains no research decisions. Modified solvers, derivations from a particular round and research hypotheses do not enter a package.

## Registration

From the FermiLink root:

```bash
PPG_FORWARD_PYTHON=/home/liuyihan/.venvs/bp/bin/python python3 ppg-domain/scripts/integrate_fermilink.py --install
```

Before `--install`, run `chmod -R u+w ppg-domain/.runtime/fermilink-registry/packages/openbf`; afterwards restore its directories to 555 and files to 444.

This refreshes the isolated registry `ppg-domain/.runtime/fermilink-registry` and writes CLI shims to `ppg-domain/.runtime/ppg-venv/bin/` (`openbf`). Analysis Python for runs: `/home/liuyihan/.venvs/bp/bin/python` (NumPy, SciPy, pandas, pyarrow, vitaldb; statsmodels under `.runtime/analysis-python`). Julia for openBF: `.runtime/julia`. PWDB cache: `.runtime/pwdb`.

Round 2 used the earlier `ppg-forward` package; its code is at git tag `round2-final`. Project-specific models, transfer definitions and the Round 1 `peripheral-ppg` pipeline live in the research workspace (`rounds/2026-11-05-round3/methods/`, `archive/legacy-code/reference-implementations/`); the old acceptance scripts are in `archive/`.
