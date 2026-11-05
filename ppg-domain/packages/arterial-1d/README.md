# arterial-1d

Public PWDB arterial-network simulation with radial pressure at distal segment 22 and digital luminal area at distal segment 112. Digital area is a haemodynamic state; an optical observation model is a separate input.

## Commands

| Command | Function |
| --- | --- |
| `doctor --out DIR` | Run the small synthetic Julia adapter check; perform no public-baseline acceptance or patient analysis. |
| `simulate --config FILE --out DIR` | Solve the configured network and save requested P/Q/A node waveforms and harmonic transfer. |
| `acceptance --config FILE --simulation DIR --refinement DIR --out DIR` | Compare saved simulations and a refinement with the source reference using explicit configured tolerances. |
| `validate-run DIR --out AUDIT_DIR` | Audit saved manifest hashes and completion. |
| `sweep --config FILE --out DIR` | Run the explicit fixed-HR resistance/inflow and wall-parameter grid; save achieved MAP and transfer descriptors per point. |

Every command creates a fresh directory with a manifest and refuses an existing directory. Configuration and metadata inputs/outputs are hashed. A blocked result is not a completed simulation. Use command `--help` for exact arguments.

Register through `python3 ppg-domain/scripts/integrate_fermilink.py --install` from the FermiLink root and use `ppg-domain/.runtime/fermilink-registry`. The package uses the isolated Julia project/depot under `ppg-domain/.runtime/julia-round3`; upstream openBF remains read-only.

## Configuration and units

A JSON configuration supplies `baseline`, optional `wall_law` (`default`, `hughes`, `langewouters`), `nodes` (`root`, `radial`, `digital`), spatial step `dx_m`, `cfl`, `max_cycles`, `convergence_tolerance_pa`, `stiffness_scale`, `resistance_scale` and `inflow_scale`. Hughes accepts `zeta_per_mmhg`; Langewouters requires explicit `lang_shape`. The source period stays fixed; `inflow_scale` scales prescribed root flow and `resistance_scale` scales terminal total R while retaining R1 and requiring R2>0. MAP is the achieved distal-radial mean pressure, not a prescribed target.

A sweep supplies `paths` (`A` for resistance, `B` for inflow), `factors`, `stiffness_scales`, `wall_laws`, `hughes_zeta_per_mmhg` and `lang_shapes`. Hughes requires `hughes_reference_run` pointing to a complete audited unscaled default-baseline run using the same public input; its achieved radial MAP sets the wall reference. Each Hughes point solves for mean pressure self-consistently with modulus fixed during each solve and preserves child-run evidence.

`phase_wls_weights` supplies three positive weights for the k=1..3 phase-slope fit with an intercept. The transfer output retains those weights, complex harmonics and group delay. Acceptance config requires explicit phase weights and `tolerances`; the refinement must be a distinct run with unchanged physical parameters/inflow, at least halved spatial step and no looser CFL/convergence tolerance.

Solver units are Pa, m, s, m^3/s, m^2 and kg/m^3. Source pressure is mmHg; `133.322387415 Pa = 1 mmHg`. `waveforms.csv` contains `t_s,node,P_pa,Q_m3_s,A_m2`. `transfer.json` describes radial-P to digital-A harmonics; its H units are m^2/Pa.

PWDB reference arrays retain native 500 Hz sample spacing, published site-onset offsets and one common source period. The loader reconstructs common root time without fitted site shifts, amplitude scaling or time stretching.

- [Equations and source units](ppg_knowledge/index.md)
- [Individual command procedures](skills/arterial-1d/SKILL.md)
- [Example configuration](ppg_examples/baseline.json)

## Verified original sources

- [PWDB 0.2.0 dataset, PDDL-1.0](https://zenodo.org/records/3275625) and [original paper](https://doi.org/10.1152/ajpheart.00218.2019).
- [PWDB original input generator, MIT](https://github.com/peterhcharlton/pwdb/blob/master/pwdb_v0.1/create_input_files_for_a_simulation.m).
- [openBF, Apache-2.0](https://github.com/INSIGNEO/openBF).
- [Hughes et al. original source](https://docs.lib.purdue.edu/bmepubs/52/).
- [Langewouters et al. original-paper record](https://dspace.library.uu.nl/handle/1874/25204).
- [Alastruey et al. 2012 governing framework](https://kclpure.kcl.ac.uk/ws/files/55965844/Alastruey_et_al_2012_Arterial_pulse_wave_haemodynamics.pdf).
