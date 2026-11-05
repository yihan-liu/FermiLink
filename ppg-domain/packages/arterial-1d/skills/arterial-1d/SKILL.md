---
name: arterial-1d
description: Run individual public PWDB network simulation, comparison and manifest-audit commands.
---

# Individual command procedure

1. Read the requested command's `--help`, README configuration keys and relevant equations in `ppg_knowledge/index.md`. Obtain the concrete configuration, input run paths and output root from the calling goal.
2. Use the registered CLI and `FERMILINK_SCIPKG_ROOT=/data/liuyihan/FermiLink/ppg-domain/.runtime/fermilink-registry`. Choose a fresh output directory; commands refuse an existing one.
3. Run the requested command below. Preserve generated values, failed solver logs and blocked results. Correct inputs or code through the responsible developer and rerun in a fresh directory.
4. Run `arterial-1d validate-run RUN_DIR --out FRESH_AUDIT_DIR`. Return manifest run_id, status, audit errors, convergence evidence and the requested comparison outputs.

## Commands

- `doctor --out DIR`: run the small synthetic adapter check. Report its stdout/stderr and availability. This check does not perform public-baseline acceptance.
- `simulate --config FILE --out DIR`: supply a public-baseline JSON path, wall law, nodes and numerical settings. Langewouters requires `lang_shape`; Hughes requires an audited unscaled default `hughes_reference_run` on the same public baseline. Supply three positive `phase_wls_weights` when explicit phase weighting is needed. Outputs include prepared solver inputs, solver log/status, P/Q/A waveforms and radial-pressure/digital-area transfer when both sites are requested. Inspect periodic convergence and junction mass reporting.
- `acceptance --config FILE --simulation DIR --refinement DIR --out DIR`: supply a configuration containing the baseline, explicit tolerances and three positive `phase_wls_weights`, plus two distinct completed audited simulation directories. Keep physical network/blood/nodes/inflow identical, at least halve the requested spatial step, and use no looser CFL or convergence tolerance. Compare source-time waveforms and refinement without fitting shifts or amplitude scales; return the comparison figure and acceptance metrics.
- `validate-run DIR --out AUDIT_DIR`: validate metadata hashes and completion without editing the inspected run.
- `sweep --config FILE --out DIR`: supply `paths` A/B, `factors`, `stiffness_scales`, `wall_laws`, `hughes_zeta_per_mmhg`, `lang_shapes` and phase weights. Replace the example's Hughes-reference placeholder with the actual audited default run. Return every point's status, achieved radial/root MAP, complex-transfer references, H1 delay, k=1..3 group delay and gain ratio. Any blocked point leaves the grid blocked.

## Inputs and units

Use SI solver inputs and named `root`, `radial`, `digital` sites. Preserve the source's 500 Hz spacing, common period, onset offsets and reference-pressure convention. Keep the upstream solver checkout read-only. The supported wall switches are `default`, `hughes` and `langewouters`, with common Voigt viscosity. The CLI scales prescribed inflow or terminal total resistance at fixed source period, reports achieved radial MAP, and solves Hughes mean pressure self-consistently while freezing its modulus within each solve. It does not prescribe a target MAP.

Every command writes a new manifest-backed directory. Configuration and baseline metadata are explicit hashed inputs. The command implementation has no VitalDB reader. The calling goal supplies numerical tolerances, parameter envelopes and any experiment authorization.
