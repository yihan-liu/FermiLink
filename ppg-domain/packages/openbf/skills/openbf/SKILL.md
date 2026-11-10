---
name: openbf
description: Configure and run 1D arterial blood-flow simulations with the available openBF solver options.
---

## Solver changes

Never modify, copy-and-modify, or patch the openBF solver. If a result looks like a solver defect, stop that line of work, write a minimal reproducing case (smallest network, settings, observed vs expected) in summary.md under 'Suspected solver defects', and continue only with steps that do not depend on it.

# openBF procedure

1. Read `openbf_knowledge/index.md`, then the upstream docs in `openbf_source/docs/src/man/`. Check `openbf doctor`.
2. Write the YAML configuration and inlet file in the run's project folder. Start from `openbf_examples/` or `openbf_source/models/` when a similar network exists.
3. Run `openbf run --config FILE --out NEW_DIR` (or call Julia directly). Check convergence in `<project>.conv` and inspect the `.last` files before using them.
4. For PWDB-type networks, use the available parameterized options (`stiffness_law: pwdb`, `visco_law: pwdb`, `exact_taper`, `balanced_taper`). If the goal requires an unsupported solver change, stop that line of work and report the limitation.
5. Record parameter sources and remaining doubts in `projects/memory.md` and `summary.md`.
