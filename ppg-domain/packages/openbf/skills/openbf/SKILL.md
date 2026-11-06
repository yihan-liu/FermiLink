---
name: openbf
description: Configure and run 1D arterial blood-flow simulations with upstream openBF, and adapt the solver in a project copy when a wall law or viscoelastic form is not supported.
---

# openBF procedure

1. Read `openbf_knowledge/index.md`, then the upstream docs in `openbf_source/docs/src/man/`. Check `openbf doctor`.
2. Write the YAML configuration and inlet file in the run's project folder. Start from `openbf_examples/` or `openbf_source/models/` when a similar network exists.
3. Run `openbf run --config FILE --out NEW_DIR` (or call Julia directly). Check convergence in `<project>.conv` and inspect the `.last` files before using them.
4. If the goal needs a wall law, stiffness distribution or viscosity coefficients that upstream does not support, copy the relevant `openbf_source/src/*.jl` into the project folder and modify the copy, using equations from the `arterial-walls` knowledge base. Never edit `openbf_source/`. Verify the modified solver against a known answer before production runs and report how.
5. Record parameter sources and remaining doubts in `projects/memory.md` and `summary.md`.
