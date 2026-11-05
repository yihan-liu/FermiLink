# openbf-walls

PWDB arterial-network simulation with a package-owned adaptation of openBF and three elastic wall laws (default square-root, Hughes, Langewouters) sharing the original Voigt viscosity.

**Status:** modified solver. Its numerical acceptance against the published PWDB waveforms has not been run; treat its outputs as unvalidated research code until an accepted acceptance run exists.

## Commands

| Command | Function |
| --- | --- |
| `doctor --out DIR` | Run the small synthetic Julia adapter check; no public-baseline acceptance. |
| `simulate --config FILE --out DIR` | Solve the configured network; save solver input, log, convergence status and `waveforms.csv` (`t_s,node,P_pa,Q_m3_s,A_m2`). |
| `validate-run DIR --out AUDIT_DIR` | Audit saved manifest hashes and completion. |

CLI shim: `ppg-domain/.runtime/ppg-venv/bin/openbf-walls`. Julia project and depot: `ppg-domain/.runtime/julia` (override with `OPENBF_WALLS_JULIA_RUNTIME`). Upstream openBF stays read-only at `ppg-domain/upstream/openBF`. Transfer descriptors of a simulation are computed by callers with `ppg-transfer`.

## Configuration

`baseline` (cached PWDB subject), `wall_law` (`default`, `hughes`, `langewouters`), `nodes` (`root`, `radial`, `digital`), `dx_m`, `cfl`, `max_cycles`, `convergence_tolerance_pa`, `stiffness_scale`, `resistance_scale` (terminal total R, R1 kept, R2>0), `inflow_scale` (root flow, period fixed). Hughes takes `zeta_per_mmhg` and `hughes_reference_run` (a complete, valid, unscaled default run on the same baseline); Langewouters requires `lang_shape`. MAP is the achieved distal-radial mean pressure, not a target.

- [Equations and units](openbf_knowledge/index.md)
- [Command procedure](skills/openbf-walls/SKILL.md)
- [Examples](openbf_examples/)

Sources: [openBF](https://github.com/INSIGNEO/openBF) (Apache-2.0, see LICENSE-openBF and NOTICE); [Alastruey et al. 2012 framework](https://kclpure.kcl.ac.uk/ws/files/55965844/Alastruey_et_al_2012_Arterial_pulse_wave_haemodynamics.pdf); [Hughes et al. 1979](https://doi.org/10.1177/016173467900100406); [Langewouters et al. 1984](https://doi.org/10.1016/0021-9290(84)90034-4).
