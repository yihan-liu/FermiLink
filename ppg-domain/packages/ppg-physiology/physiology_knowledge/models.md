# Pressure-to-volume models and the monitor observation

Units: ART mmHg, time s, frequency Hz, PLETH device units. Outputs below are area/volume-change proxies with arbitrary scale unless stated.

## Model ladder

- **M0, empirical filter:** second-order low-pass times two lead/lag sections `(1+s/wz)/(1+s/wp)` (4 poles, 2 zeros). Equal pole/zero pairs reduce it to M1. A flexible reference, not a mechanism.
- **M1, linear transmission:** `H(s) = wn^2/(s^2 + 2 zeta wn s + wn^2)`, volume proportional to transmitted pressure. Predicts a transfer function independent of mean pressure.
- **M2, nonlinear pressure-volume:** M1 transmission followed by `V/Vscale = 1/2 + atan((P - Pext - Pmid)/width)/pi` (mmHg). Mean pressure must be kept before the nonlinearity. Local compliance `dV/dP` peaks at transmural pressure Pmid, so small-signal gain changes with mean pressure.
- **M3, 2R1C bed:** `C dP/dt = (Pin - P)/Rin - (P - Pv)/Rout`, `V = Vref + C (P - Pref)` (mmHg, mL, s); identifiable time constant `tau = C (Rin || Rout)`.
- **M4, tapered transmission line:** `dP/dx = -(R + i w L) Q`, `dQ/dx = -i w C P`, `R = 8 pi mu/A^2`, `L = rho/A`, `C = A/(rho c^2)`; terminal bed `Zbed = Rbed/(1 + i w tau)`. A pressure-dependent version sets, for mean pressure M against reference Mref (Pa), `q = 1 + (M - Mref)/(2 rho c0^2)`, `r = rref q`, `A = Aref q^2`, `c = c0 sqrt(q)`, so wave speed rises with pressure.

Typical engineering search ranges used before (not measurements): M1 frequency 0.3-20 Hz, damping 0.15-3; M2 Pmid -20..120 mmHg, width 5..120 mmHg; M3 tau 0.02-2 s; M4 c 3-20 m/s, taper 0.3-1, bed tau 0.02-1 s, length 0.25 m, inlet radius 1.5 mm, rho 1060 kg/m^3, mu 0.004 Pa s.

## Monitor observation operator

`PLETH(t) = g * BP[ s * dV(t - d_device - PTT) ] + offset`, with sign s = +-1, causal Butterworth band-pass BP (corners lo/hi Hz, order n), positive window gain g, offset and a pure delay. Device delay and physiological delay (PTT) are identifiable only as a sum; filter phase also shifts timing. Clinical PLETH may include automatic gain changes; positive-gain-invariant descriptors avoid them.

A previously fitted monitor operator for this VitalDB cohort is a project artefact, not a property of the device; the goal supplies it when needed.

## Arterial catheter

Fluid-filled line: `H(f) = 1/(1 - (f/fn)^2 + 2 i zeta f/fn)`. A flush ring-down gives the damped frequency fd and damping zeta; `fn = fd/sqrt(1 - zeta^2)` assumes an underdamped second-order line. Correction divides by H with a band limit (previously a 15 Hz eighth-power taper on both branches); missing estimates make correction unavailable.

## Coupling to optics

Blood-volume change in the sampled tissue changes the blood fraction `f_b = f_ref + (V - Vref)/V_sampling`; see [optics.md](optics.md). Peripheral propagation delay and tissue deformation need their own models; a lumped bed's phase lag is not a propagation delay.
