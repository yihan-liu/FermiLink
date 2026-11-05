# Arterial-network equations and units

## Constitutive state

Reference area Ad and pressure Pd follow the PWDB diastolic reference convention. Default elastic law: `Pe = Pd + B (sqrt(A/Ad) - 1)`, `B = 4 Eh/(3 r)`, `Eh = 0.1 (k1 exp(k2 100 r) + k3) r`. Wave speed `c^2 = (A/rho) dPe/dA`.

Hughes: the modulus is scaled once per run, `(Eh)_run = (Eh)_base exp(zeta (MAP_run - MAP_base))`, `zeta_per_mmhg` in 1/mmHg, fixed within a cycle. The reference MAP comes from a complete unscaled default-baseline run; the run MAP is solved self-consistently from the achieved distal-radial mean pressure (tolerance 0.1 mmHg, at most eight solves), keeping each child solve.

Langewouters: `A(P) = Am (1/2 + atan((P-P0)/P1)/pi)`, Am>0, P1>0, transmural P, inverse domain 0<A<Am. Matched to reference Ad and tangent Kd at Pd through dimensionless `q = lang_shape`: `F = 1/2 + atan(q)/pi`, `Am = Ad/F`, `P1 = Ad Kd/[pi F (1+q^2)]`, `P0 = Pd - q P1`.

The original Hughes coefficients are canine aortic and the Langewouters coefficients human aortic; neither gives finger-artery values. Parameter values come from the calling configuration.

## Conservation, taper and viscosity

Area A and flow Q evolve under continuity and 1D momentum with convective alpha=1 and parabolic-profile friction; mass and elastic total-head junction conditions; three-element Windkessel outlets. Taper `r(x) = rp + (rd-rp) x/L`.

All wall laws share the Voigt component `P = Pe + Bv A_t`, `Bv = Gamma/sqrt(A)`; continuity gives `Pv = -Bv Q_x`; momentum viscosity `(A/rho) d_x(Bv Q_x)`. Taper source `Pi_x|A - (A/rho) Pe_x|A` for `Pi_A = (A/rho) Pe_A`. Viscosity applies to segments longer than 0.011 m, as in the original generator.

Outlets: `Rtotal = R1 + R2`; R1 is the baseline characteristic impedance, `R2 = resistance_scale Rtotal_base - R1 > 0`. C in m^3/Pa, R in Pa s/m^3. Root flow is baseline source U A times `inflow_scale`.

## Units and output

SI throughout: Pa, m, s, m^3/s, m^2, kg/m^3. Output samples at 500 Hz over the last converged cycle on root time. Convergence: periodic pressure RMSE below `convergence_tolerance_pa`; junction mass error is reported, and above 1e-6 the run is blocked.

## Extension interface

The wall interface supplies elastic pressure, its area derivative, wave speed, the characteristic integral and pressure potential. A collapsible law (for example Shapiro) could be added through it; it is not an available switch.
