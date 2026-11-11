---
name: openbf
description: Configure and run 1D arterial blood-flow simulations with the available openBF solver options.
---

## Solver changes

Do not modify, copy-and-modify, or patch the openBF solver unless the goal explicitly declares itself a solver-development goal. If a result looks like a solver defect, stop that line of work, write a minimal reproducing case (smallest network, settings, observed vs expected) in summary.md under 'Suspected solver defects', and continue only with steps that do not depend on it. In a solver-development goal: change only the goal's own copy, put every change behind an option whose default is upstream behaviour, show bitwise equality with the frozen package with all options off, add a known-answer test per change, change source only in stage 1, and never change code to make a criterion pass.

# openBF procedure

1. Read `openbf_knowledge/index.md`, then the upstream docs in `openbf_source/docs/src/man/`. Check `openbf doctor`.
2. Write the YAML configuration and inlet file in the run's project folder. Start from `openbf_examples/` or `openbf_source/models/` when a similar network exists.
3. Run `openbf run --config FILE --out NEW_DIR` (or call Julia directly). Check convergence in `<project>.conv` and inspect the `.last` files before using them.
4. For PWDB-type networks, use the available parameterized options (`stiffness_law: pwdb`, `visco_law: pwdb`, `exact_taper`, `balanced_taper`). If an experimental goal requires an unsupported solver change, stop that line of work and report the limitation.
5. Record parameter sources and remaining doubts in `projects/memory.md` and `summary.md`.

## Solver options

Set vessel options in the relevant network segment; set diagnostics options at the YAML top level.

- `wk_tolerance`: Windkessel Newton residual tolerance; default 0.0 Pa, meaning exactly 10 iterations.
- `wk_maxiter`: maximum Newton iterations when `wk_tolerance > 0`; default 10, dimensionless count.
- `diagnostics`: write cycle, volume, site and Windkessel diagnostics; default false, dimensionless boolean. Site means are checkpoint arithmetic means; the reported mean Windkessel residual averages the per-step maximum outlet residual.
- `diagnostics_sites`: site triples `[label, segment_label, position]`; default empty list, labels and positions dimensionless. Position is one of `inlet`, `quarter`, `midpoint`, `three_quarter`, `outlet`.
- `viscous_pressure_output`: add Gamma/sqrt(A)*dA/dt to pressure for viscoelastic vessels; default false, dimensionless boolean. This pressure also affects the convergence check.
- `alpha_conv`: momentum-flux convective coefficient; default 1.0, dimensionless. Choose a consistent `gamma_profile`: alpha=4/3 corresponds to gamma_profile=2. This changes the momentum flux only; CFL, boundary and junction relations retain the upstream alpha=1 approximation; alpha != 1 has not been validated as a consistent network model.
- `fix_pwdb_taper_source`: **Do not use.** This option changes the non-balanced tapered source for PWDB stiffness; default false, dimensionless boolean.
- Nonpositive or nonfinite area raises an error identifying the vessel and cell; always enabled, no option or units.
- `visco_velocity_sync`: set u=Q/A after the viscoelastic step; default false, dimensionless boolean.

## Known defects

- The upstream viscoelastic Crank–Nicolson step uses a=Cv·dt/dx² on both sides instead of a/2, doubling the effective viscous diffusion coefficient. A solver fix requires separate approval; treat viscoelastic results as comparisons only.
