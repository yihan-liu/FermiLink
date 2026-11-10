---
name: arterial-walls
description: Choose and implement arterial wall laws (square-root with PWDB stiffness, Voigt viscosity, Hughes exponential modulus, Langewouters arctangent) in a 1D arterial-network solver, with verified literature parameters.
---

## Solver changes

Never modify, copy-and-modify, or patch the openBF solver. If a result looks like a solver defect, stop that line of work, write a minimal reproducing case (smallest network, settings, observed vs expected) in summary.md under 'Suspected solver defects', and continue only with steps that do not depend on it.

# Using the wall-law knowledge

1. Read `walls_knowledge/index.md`; take literature parameters only from `walls_knowledge/langewouters1984_table2.md` and `walls_knowledge/sources.md`.
2. Implement a law in the run's project folder, in a copy of the solver (see `external_packages/openbf/`). Every law must supply elastic pressure, its area derivative, wave speed, characteristic integral and pressure potential consistently.
3. Check the implementation on a known answer before production runs: the square-root law must reproduce the unmodified solver.
4. Finger-artery parameters are not in the sources; declare them as modelling inputs.
