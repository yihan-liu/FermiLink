# openBF knowledge

Primary sources: `openbf_source/docs/src/man/` (quickstart, config, overview, examples) and `openbf_source/src/`. Read them before writing a configuration.

## Model

Each vessel is a 1D tube with area A(x,t) and flow Q(x,t). openBF solves continuity and momentum with a MUSCL finite-volume scheme, time step from the Courant number `Ccfl`. Elastic law (hard-coded in `src/vessel.jl:115`):

`P = Pext + beta (sqrt(A/A0) - 1)`, `beta = sqrt(pi/A0) h0 E / (1 - sigma^2)`, `sigma = 0.5`.

E is one Young's modulus per vessel (Pa). If `h0` is not given, wall thickness is an empirical function of R0 (`src/vessel.jl:170`). Radius may taper linearly from `Rp` to `Rd`.

Junctions: bifurcations, conjunctions and anastomoses solved by Newton iteration on mass and total-pressure continuity. Inlet: flow time series from the inlet file (node 1). Outlets: reflection coefficient `Rt`, two-element (`R1`, `Cc`) or three-element Windkessel (`R1`, `R2`, `Cc`, optional `Pout`).

## Viscoelasticity (upstream limits)

`visco-elastic: true` enables a Kelvin-Voigt term: `Gamma = b1 0.5/R0 + b0`, `Cv = Gamma/(rho sqrt(A0))`. It enters the solution through a diffusion step (`src/solver.jl:162`) and the saved pressure (`src/simulation.jl:32`). Two limits matter for literature reproductions:

1. `b0 = 0.6` and `b1 = 0.0015` are hard-coded (`src/vessel.jl:193`); per-vessel or per-subject coefficients need a source change.
2. Stiffness is one E per vessel with empirical h0; a radius-dependent stiffness such as `Eh(r)` along a taper needs a source change.

Any other wall law (exponential, arctangent, collapsible) also needs a source change: wave speed, fluxes, characteristic boundary equations and junction conditions all assume the square-root law above.

## Changing the solver

Do not edit `openbf_source/`. Copy the needed `src/*.jl` files into the run's project folder, keep the Apache-2.0 notice, change them there, and load the copy instead of the installed package. Check a modified solver on a case with a known answer before using it (for example the unmodified default law must reproduce upstream results, and a published reference network must reproduce within declared tolerances). Equations for alternative wall laws and viscoelastic forms are in the `arterial-walls` knowledge base.

## Configuration and output

YAML keys (full template in `docs/src/man/config.md`): `project_name`, `write_results` (P, Q, u, A), `inlet_file`, `solver` (`Ccfl`, `cycles`, `convergence_tolerance` in mmHg between consecutive cycles, `jump` samples per cycle), `blood` (`rho`, `mu`), `network` (per vessel `label`, `sn`, `tn`, `L`, `E`, `R0` or `Rp`/`Rd`, optional `M`, `h0`, `Pext`, `gamma_profile`, `visco-elastic`, outlet parameters).

Output per saved vessel: `<label>_<field>.last` (last cycle) with `jump` rows and 6 columns: time in cycle (s), inlet, 1/4, 1/2, 3/4 length, outlet. Units: P Pa, Q m^3/s, u m/s, A m^2. With `save_stats`, `<project>.conv` holds converged flag, cycles, elapsed time.
