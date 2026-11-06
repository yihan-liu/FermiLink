# Wall laws for 1D arterial networks

Notation: A lumen area, P transmural pressure, Ad and Pd a reference area and pressure, rho blood density. Wave speed `c^2 = (A/rho) dPe/dA`. Every elastic law below must provide, consistently in fluxes, characteristic boundaries and junctions: elastic pressure Pe(A), dPe/dA, wave speed, the characteristic integral and the pressure potential.

## Square-root law (PWDB default)

`Pe = Pd + B (sqrt(A/Ad) - 1)`, `B = 4 Eh/(3 r)`. PWDB stiffness (Charlton 2019 generator): `Eh = 0.1 (k1 exp(k2 100 r) + k3) r` with r in m and the generator's unit conversion; Ad and Pd are at diastolic pressure. openBF uses the same functional form with one E per vessel (see the `openbf` knowledge base).

## Voigt viscosity (PWDB)

Alastruey et al. 2012 (Eq. 4-5, Appendix 2): `P = Pe + Bv dA/dt`, `Bv = Gamma/sqrt(A)`, Gamma from the generator's b0, b1 and radius. Continuity gives `Pv = -Bv dQ/dx`; the momentum viscous term is `(A/rho) d/dx (Bv dQ/dx)`. Writing it as `d/dx((A Bv/rho) dQ/dx)` adds a term when A varies. The generator enables viscosity only for segments longer than 0.011 m. For a tapered vessel with `Pi_A = (A/rho) dPe/dA`, the taper source is `dPi/dx|_A - (A/rho) dPe/dx|_A`. Connections and Windkessel outlets use elastic pressure. The 2012 framework uses convective coefficient alpha = 1 with parabolic-profile friction.

## Hughes exponential modulus

Hughes, Babbs, Geddes and Bourland 1979 (canine abdominal and descending thoracic aorta, in vivo, mean pressure 40-200 mmHg): `E = E0 exp(a P)`. Reported means: abdominal E0 = 667 +/- 382 mmHg, a = 0.017 +/- 0.004 /mmHg; descending thoracic E0 = 687 +/- 241 mmHg, a = 0.016 +/- 0.004 /mmHg.

This is a dynamic modulus against mean distending pressure. It does not by itself define an instantaneous pressure-area law; substituting E(P) into the square-root law is a modelling choice. One closure scales the modulus once per simulated condition, `Eh_run = Eh_base exp(zeta (MAP_run - MAP_base))`, fixed within the cycle, solving MAP_run self-consistently with the simulated mean pressure. With that closure, wave speed rises with MAP by construction, so a delay that falls with MAP is not specific evidence for Hughes.

## Langewouters arctangent law

Langewouters, Wesseling and Goedhard 1984 (45 thoracic and 20 abdominal human aortas in vitro, static inflation 20-180 mmHg): `A(P) = Am (1/2 + atan((P - P0)/P1)/pi)`, Am > 0, P1 > 0, inverse domain 0 < A < Am. Compliance `C(P) = Am/(pi P1 (1 + ((P - P0)/P1)^2))`, maximal at P0 and halved at P0 +- P1. Parameters per specimen: [langewouters1984_table2.md](langewouters1984_table2.md) (cm^2, mmHg; SI: x1e-4 m^2, x133.322 Pa).

To keep a network's reference geometry, match reference area Ad and tangent stiffness Kd = dP/dA at Pd with a dimensionless shape `q = (Pd - P0)/P1`: `F = 1/2 + atan(q)/pi`, `Am = Ad/F`, `P1 = Ad Kd/(pi F (1 + q^2))`, `P0 = Pd - q P1`.

## Applicability

Both sources describe aortas (canine, human). Neither gives reliable finger-artery parameters; finger values are modelling inputs to declare and vary.

## Outlets and perturbations

Three-element Windkessel: `Rtotal = R1 + R2`, R1 often the characteristic impedance `rho c/A`. To change peripheral resistance with fixed R1: `R2 = s Rtotal_base - R1 > 0`. Mean pressure in a network can be changed by scaling terminal resistance (fixed inflow) or scaling inflow (fixed outlets); real changes mix both.
