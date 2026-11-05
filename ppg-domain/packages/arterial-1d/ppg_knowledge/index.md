# Arterial-network equations and units

## Constitutive state

The reference area Ad and pressure Pd use the PWDB diastolic reference convention. The default elastic law is `Pe=Pd+B*(sqrt(A/Ad)-1)`, with `B=4Eh/(3r)`. The original generator supplies the stiffness relation `Eh=0.1*(k1*exp(k2*100r)+k3)*r` with its source unit conversion. Wave speed is `c^2=(A/rho)*dPe/dA`.

The Hughes switch scales the modulus once per run: `(Eh)_run=(Eh)_base*exp(zeta*(MAP_run-MAP_base))`. MAP differences and zeta use matching pressure units; `zeta_per_mmhg` is 1/mmHg. The modulus is fixed within a cycle. The simulation bridge takes reference MAP from a complete unscaled default-baseline run and solves the run MAP self-consistently using achieved distal-radial mean pressure. Child solves retain their frozen wall MAP and achieved MAP.

The Langewouters law is `A(P)=Am*(1/2+atan((P-P0)/P1)/pi)`, with Am>0 and P1>0. P is transmural, Am is m^2, and P0/P1 are Pa. The inverse requires 0<A<Am. To match reference Ad and tangent Kd at Pd, supply dimensionless `q=lang_shape=(Pd-P0_source)/P1_source` and use:
`F=1/2+atan(q)/pi`, `Am=Ad/F`, `P1=Ad*Kd/[pi*F*(1+q^2)]`, `P0=Pd-q*P1`.

Original Hughes coefficients describe canine aortas; original Langewouters coefficients describe human aortas. They establish neither finger-artery parameter values nor a finger parameter envelope. Finger-specific inputs must be supplied by the calling configuration. References are linked in the README.

## Conservation, taper and viscosity

The adapter evolves area A and flow Q under continuity and one-dimensional momentum. It uses the framework's convective alpha=1 approximation with parabolic-profile friction, mass/elastic total-head junction conditions and three-element Windkessel outlets. Radius taper is `r(x)=rp+(rd-rp)*x/L`.

All three elastic choices share the original Voigt component: `P=Pe+Bv*A_t`, `Bv=Gamma_input/sqrt(A)`; continuity gives `Pv=-Bv*Q_x`. The momentum viscosity is `(A/rho)*d_x(Bv*Q_x)`. For `Pi_A=(A/rho)*Pe_A`, the taper source is `Pi_x|A-(A/rho)*Pe_x|A`. Original source coefficients and segment geometry determine viscosity eligibility.

Outlet total resistance is `Rtotal=R1+R2`; the bridge retains the baseline characteristic-impedance R1 and sets `R2=resistance_scale*Rtotal_base-R1`, requiring R2>0. Compliance C uses m^3/Pa, resistance Pa*s/m^3 and RC seconds. Root flow is derived from the baseline source U*A and multiplied by `inflow_scale`; the period stays fixed. Sweep path A varies total resistance at fixed inflow, and path B varies inflow at fixed baseline outlets. The independent variable saved for derivatives is achieved distal-radial mean pressure.

## Reference and output time

The public baseline uses 500 Hz local export samples. Reconstruct each site on common root time using its published onset; do not independently align sites or stretch local arrays. Model harmonics fit a constant and sine/cosine terms k=1..5 on the common period. `H_k=A_digital,k/P_radial,k` has units m^2/Pa; `abs(H2)/abs(H1)` is dimensionless and H1 phase delay `-Arg(H1)*T/(2*pi)` is seconds. The k=1..3 group delay is minus the weighted phase-versus-omega slope with an intercept. Harmonic-order unwrapping uses principal adjacent increments; the three positive weights are explicit configuration inputs retained in the transfer output.

Acceptance compares saved source-time waveforms and refinement outputs against explicit tolerance values in its JSON configuration. Numerical thresholds and experiment prediction envelopes belong in the calling stage goal. See the README for available commands and their configuration keys.

## Constitutive extension interface

The numerical wall interface supplies elastic pressure, its area derivative, wave speed, the characteristic integral and pressure potential. A collapsible Shapiro law can use that interface by defining these quantities and their physical area domain consistently in flux and boundary calculations; it is an extension point rather than an available wall switch.
