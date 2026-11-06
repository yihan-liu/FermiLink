---
name: arterial-walls
description: Choose and implement arterial wall laws (square-root with PWDB stiffness, Voigt viscosity, Hughes exponential modulus, Langewouters arctangent) in a 1D arterial-network solver, with verified literature parameters.
---

# Using the wall-law knowledge

1. Read `walls_knowledge/index.md`; take literature parameters only from `walls_knowledge/langewouters1984_table2.md` and `walls_knowledge/sources.md`.
2. Implement a law in the run's project folder, in a copy of the solver (see `external_packages/openbf/`). Every law must supply elastic pressure, its area derivative, wave speed, characteristic integral and pressure potential consistently.
3. Check the implementation on a known answer before production runs: the square-root law must reproduce the unmodified solver.
4. Finger-artery parameters are not in the sources; declare them as modelling inputs.
