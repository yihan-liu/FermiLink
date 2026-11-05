---
name: openbf-walls
description: Run PWDB arterial-network simulations with the adapted openBF solver and its three wall laws, and audit the runs.
---

# Individual command procedure

1. Read `--help`, the README and `openbf_knowledge/index.md`. Take the configuration, input runs and output root from the calling goal. Use public PWDB inputs only; this package reads no patient data.
2. Run `doctor` before numerical work. Use the shim `/data/liuyihan/FermiLink/ppg-domain/.runtime/ppg-venv/bin/openbf-walls` and a fresh output directory per command.
3. Keep exactly the `default`, `hughes` and `langewouters` switches with the common Voigt viscosity. Keep the upstream checkout read-only.
4. Inspect periodic convergence and junction mass in `result.json`; preserve failed and blocked solves.
5. Run `openbf-walls validate-run RUN_DIR --out FRESH_AUDIT_DIR`. Report run_id, status, audit errors and convergence evidence.
