# openBF knowledge

Primary sources: the openBF 2.8.0 documentation in `/data/liuyihan/reference/openBF-upstream-2.8.0/docs/src/man/` (quickstart, config, overview, examples) and the running source `openbf_param/src/`. Read them before writing a configuration.

## Model

Each vessel is a 1D tube with area A(x,t) and flow Q(x,t). openBF solves continuity and momentum with a MUSCL finite-volume scheme, time step from the Courant number `Ccfl`. Elastic law (hard-coded in `src/vessel.jl:115`):

`P = Pext + beta (sqrt(A/A0) - 1)`, `beta = sqrt(pi/A0) h0 E / (1 - sigma^2)`, `sigma = 0.5`.

E is one Young's modulus per vessel (Pa). If `h0` is not given, wall thickness is an empirical function of R0 (`src/vessel.jl:170`). Radius may taper linearly from `Rp` to `Rd`.

Junctions: bifurcations, conjunctions and anastomoses solved by Newton iteration on mass and total-pressure continuity. Inlet: flow time series from the inlet file (node 1). Outlets: reflection coefficient `Rt`, two-element (`R1`, `Cc`) or three-element Windkessel (`R1`, `R2`, `Cc`, optional `Pout`).

## Solver: `openbf_param/`

`openbf run` uses `openbf_param/`, the package's only openBF implementation: openBF 2.8.0 with added options (see `openbf_param/PARAMETERS.md` and the skill). With no added option set, its results are identical to openBF 2.8.0 (all 99 output files of the Circle of Willis example matched byte for byte on 2026-11-06). Experiment goals do not change the solver.

Per-vessel options added (all default to upstream behaviour):

| Key | Values | Effect |
| --- | --- | --- |
| `stiffness_law` | `openbf` (default) / `pwdb` | `pwdb`: `beta = (4/3) 0.1 (k1 exp(k2 100 r) + k3)` per cell from `k1` [g/s^2/cm], `k2` [1/cm], `k3` [g/s^2/cm] (PWDB `Eh = 0.1 (k1 exp(k2 100 r) + k3) r`, `beta = 4 Eh/(3 r)`); `E` not needed |
| `b0`, `b1` | numbers | Viscoelastic coefficients of the upstream form `Gamma = b1 0.5/R0 + b0`, `Cv = Gamma/(rho sqrt(A0))` (defaults 0.6, 0.0015) |
| `visco_law` | `openbf` (default) / `pwdb` | `pwdb`: PWDB generator `Gamma_in = (4/pi)(b1/(2 100 r) + b0)/1000/(2r)^2` with `b0` [g/s], `b1` [g cm/s]; `Bv = Gamma_in/sqrt(A)`, `Cv = Gamma_in sqrt(A0)/rho` (linearized `(A/rho) d/dx(Bv dQ/dx)`). Requires `visco-elastic: true` |
| `exact_taper` | `false` (default) / `true` | Upstream sets `R0[i] = Rp + (Rd-Rp)/(M-1) (i-1) dx`, which tapers by only about dx/L of the intended amount, and skips the taper source when the radii differ by less than 0.1 mm. `true` uses `R(x) = Rp + (Rd-Rp) x/L` at cell centres and per-metre `dA0/dx` |
| `balanced_taper` | `false` (default) / `true` | Requires `exact_taper`. Replaces upstream taper source terms with the one derived from the flux form, `-(A/rho)(sqrt(A/A0) - 1 - sqrt(A)/(3 sqrt(A0))) dbeta/dx + beta A^1.5 dA0/dx/(3 rho A0^1.5)`, valid for any `beta(x)`. At rest it cancels the flux gradient: interior spurious acceleration fell from ~3e-3 to ~2e-7 m^3/s^2 on a 3->1.5 mm, 126 mm PWDB-stiffness vessel (`tests/check_balanced_taper.jl`); a residual remains in the first cells next to the inlet ghost |
| `wb_pressure` | `false` (default) / `true` | Per-vessel pressure-based well-balanced scheme with minmod limiting. For tapered vessels set `exact_taper: true` and omit `balanced_taper`; stepped straight tubes are no longer needed. |

Upstream defaults to know: one Young's modulus per vessel with empirical `h0(R0)` when `h0` is absent; viscoelastic coefficients fixed unless `b0`/`b1` are given; a zero inflow history gives NaN results (use a tiny positive flow for rest tests).

Other wall laws (exponential, arctangent, collapsible) change wave speed, fluxes, characteristics and junctions; they need a solver-development goal approved by Yihan (see the skill), which uses the `arterial-walls` knowledge base and verifies against this package with the default law.

## Configuration and output

YAML keys (full template in `docs/src/man/config.md`): `project_name`, `write_results` (P, Q, u, A), `inlet_file`, `solver` (`Ccfl`, `cycles`, `convergence_tolerance` in mmHg between consecutive cycles, `jump` samples per cycle), `blood` (`rho`, `mu`), `network` (per vessel `label`, `sn`, `tn`, `L`, `E`, `R0` or `Rp`/`Rd`, optional `M`, `h0`, `Pext`, `gamma_profile`, `visco-elastic`, outlet parameters).

Output per saved vessel: `<label>_<field>.last` (last cycle) with `jump` rows and 6 columns: time in cycle (s), inlet, 1/4, 1/2, 3/4 length, outlet. Units: P Pa, Q m^3/s, u m/s, A m^2. With `save_stats`, `<project>.conv` holds converged flag, cycles, elapsed time.
