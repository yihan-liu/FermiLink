# ART-driven waveform tools

## Signals and units

ART is in mmHg, time in seconds and frequency in Hz. The selective reader decodes native 500 Hz SNUADC ART/PLETH windows and can return 50 Hz resampled inputs for fitting. PLETH amplitude is in device units. Native timing and harmonic calculations use 500 Hz inputs.

## Model equations

Modules expose `predict(art, params)`, `PARAM_BOUNDS`, `PARAM_PRIORS` and `DEFAULT_PARAMS`. Bounds are effective-parameter search inputs.

- **M0:** second-order lowpass times two lead/lag sections, each `(1+s/wz)/(1+s/wp)`. Frequency parameters are Hz and damping is dimensionless; the added pole/zero pairs recover M1 when equal.
- **M1:** `H(s)=wn^2/(s^2+2*zeta*wn*s+wn^2)`, with fixed pressure-to-area scale.
- **M2:** M1 transmission followed by `V/Vscale=1/2+atan((P-Pexternal-Pmid)/width)/pi`. Pressure coordinates and width are mmHg. Retain ART DC before this nonlinear operation.
- **M3:** `peripheral_ppg.model.local_model`, with fixed Rin/Rout and fitted `tau=C*(Rin||Rout)` in seconds; output volume is mL before nuisance gain.
- **M4:** tapered radial-to-digital line, `dP/dx=-(R+i*w*L)Q`, `dQ/dx=-i*w*C*P`; `R=8*pi*mu/A^2`, `L=rho/A`, `C=A/(rho*c^2)`. Terminal `Zbed=Rbed/(1+i*w*tau)`. Geometry uses metres, density kg/m^3, viscosity Pa*s and pressure Pa; convert ART mmHg before computing fractional area.

M4 accepts paired `operating_map_mmHg` and `reference_map_mmHg` inputs. With pressure difference converted to Pa, `q=1+(M-Mref)/(2*rho*c0^2)`, `r=rref*q`, `A=Aref*q^2`, and `c=c0*sqrt(q)`, requiring q>0. The whole line uses one prescribed mean pressure. Baseline absolute bed resistance is `Rb0=ratio*rho*c0/Aref_prox` and capacitance is `Cb0=tau0/Rb0`. Prescribed `resistance_scale` multiplies Rb and tau while keeping Cb fixed; pressure-dependent c/A do not redefine that load. Without prescribed pressure inputs, geometry and c retain their configured reference values.

Use the model module's declared bounds when constructing a fit configuration. A fitted effective parameter's physiological interpretation requires evidence beyond waveform agreement.

## Catheter and observation operator

Catheter response is `H(f)=1/(1-(f/fn)^2+2i*zeta*f/fn)`. For an underdamped successive-peak estimate `fd`, `fn=fd/sqrt(1-zeta^2)`. Unavailable estimates make correction unavailable. Both branches receive the common bandwidth filter; the corrected branch additionally receives the inverse catheter response.

The observation operator applies sign, filtering, positive window gain, offset and a fractional pure delay. Filter corners are Hz, delays seconds, gain positive and filter order integral. Device delay and case delay share a timing gauge; filtering phase can also absorb timing.

## Physical-time metrics

`metrics.ensemble` detects local-minimum feet before systolic upstrokes. Each beat is normalized by its raw foot and full-beat peak-minus-foot amplitude. Its common physical-time support is the shortest complete reference RR. The helper returns full/odd/even means and coverage.

`NMSE=sum((prediction-target)^2)/sum((target-mean(target))^2)`, and `R2=1-NMSE`. The noise floor is `n1*n2/(n1+n2)^2` times odd/even squared difference divided by the full-mean centered sum of squares. Morphology includes foot-to-peak time, notch presence/time/depth, systolic width and matched-foot delay; missing features retain undefined values.

## Native beat-phase harmonics

`tf_harmonics.compute_tf_harmonics(art, pleth, fs_hz=500, foot_times=None)` is a Python API. Supplied feet are seconds from sample zero; default detection uses ART only. Complete common foot-to-next-foot beats define `u=(t-foot)/RR` for both channels.

For each beat, subtract its DC integral and compute `X_bk=integral_0^1 x_b(u)*exp(-2*pi*i*k*u)du`, and similarly Y, by trapezoidal integration of native samples with interpolated endpoints. No beat amplitude normalization is applied. `H_k=mean_b(Y_bk)/mean_b(X_bk)` for k=1..5. Common phase-grid means are display/audit outputs. Full and alternating odd/even estimates retain coefficients and undefined harmonics.

Gain ratios are `abs(H_k)/abs(H_1)`; residual phase is `psi_k=Arg(H_k*(conj(H_1)/abs(H_1))^k)`. Adjacent residual group delay is `-Delta(psi)/(2*pi*Delta(f))`, using fixed principal adjacent increments. Frequencies are `f_k=k/mean(RR)`, HR is `60/mean(RR)`. Delays are seconds and branch-aliased modulo mean RR. With variable RR, H is a beat-phase ensemble descriptor.

`tf_statistics.decompose_feature` is a Python helper for case-centered MAP, HR and time regressions, mixed effects, OLS case slopes, timestamp-based Bartlett HAC errors and continuous-run residual-shift controls. Bandwidth, shift duration, repetitions and seed are explicit inputs; slopes are returned per mmHg and per bpm. These helpers have no dedicated CLI.

## Detected-photon optics

Absorption mixing is `mu_a=f_b*mu_a_blood+(1-f_b)*mu_a_matrix`; optical paths are mm and absorption coefficients 1/mm. With fixed scattering and `X=sum_i(delta_mu_a_i*L_i)`, `ln(I1/I0)=ln(E_w exp(-X))`, its linear term is `-E_w X` and quadratic term `Var_w(X)/2`. The helpers also compute the exact remainder using the same photons. Optical AC/DC is peak-to-peak detected intensity divided by cycle mean. Device PLETH units supply no absolute optical DC calibration.

See the README for enforced raw-access and manifest rules. Experiment cohorts, criteria and authorization belong in the calling goal and its input files.

## Harmonic phase-slope API

`tf_delay.fit_delay(H, frequencies_hz, operator, weights, harmonics)` fits `phase(H)=intercept-omega*tau` with positive supplied weights; tau is seconds. It uses the known causal operator phase to guide residual-phase unwrapping, then restores that continuous operator phase before fitting raw H. Residual adjacent harmonic phase increments are assumed to lie in (-pi, pi); diagnostics expose split-half branch differences. `freeze_harmonic_weights` estimates case-balanced odd/even phase-noise variance and returns inverse-variance weights for a saved configuration. Exact harmonic support, reference centering, feature selection and reliability criteria are inputs from the calling goal.
