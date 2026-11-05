# ART-to-area models, observation operator and metrics

## Signals and units

ART is mmHg, time seconds, frequency Hz, PLETH device units. Models accept 50 or 500 Hz inputs (`fs_hz` in params). Outputs are area-change proxies with arbitrary constant scale; the window gain removes scale.

## Model ladder

Modules expose `predict(art, params)`, `PARAM_BOUNDS`, `PARAM_PRIORS` and `DEFAULT_PARAMS`. Bounds are effective-parameter search ranges, not measured ranges.

- **M0:** second-order lowpass times two lead/lag sections `(1+s/wz)/(1+s/wp)`; equal pole/zero pairs recover M1.
- **M1:** `H(s)=wn^2/(s^2+2 zeta wn s+wn^2)`, fixed pressure-to-area scale.
- **M2:** M1 transmission followed by `V/Vscale=1/2+atan((P-Pexternal-Pmid)/width)/pi` (mmHg). ART DC is retained before the nonlinearity.
- **M3:** `peripheral_ppg.model.local_model` with fixed Rin/Rout and fitted `tau=C (Rin||Rout)` (s).
- **M4:** tapered radial-to-digital line, `dP/dx=-(R+i w L)Q`, `dQ/dx=-i w C P`; `R=8 pi mu/A^2`, `L=rho/A`, `C=A/(rho c^2)`; terminal `Zbed=Rbed/(1+i w tau)`. SI units inside; ART converted from mmHg. Optional paired `operating_map_mmHg`/`reference_map_mmHg` set `q=1+(M-Mref)/(2 rho c0^2)`, `r=rref q`, `A=Aref q^2`, `c=c0 sqrt(q)`; `resistance_scale` multiplies Rb and tau with Cb fixed. `transfer_function(frequency_hz, params)` gives the line's complex response.

A fitted effective parameter's physiological meaning needs evidence beyond waveform agreement.

## Observation operator and catheter

`PLETH(t) = gain * BP[sign * dA(t - device_delay - PTT)] + offset`, with a causal Butterworth band-pass (`lo_hz`, `hi_hz`, `order`), positive gain and fractional delay. Device delay and case PTT are identifiable only through their sum; filter phase can also absorb timing.

Catheter `H(f)=1/(1-(f/fn)^2+2i zeta f/fn)`; a damped successive-peak estimate gives `fn=fd/sqrt(1-zeta^2)`. Both branches receive the same 15 Hz eighth-power taper; the corrected branch also receives the inverse catheter response. Missing estimates make correction unavailable.

## Fitting

`fit_case(windows, model, operator_params, ...)` fits one case: physiology and residual PTT shared, positive gain and offset profiled per window, variance-normalized waveform residuals on a fixed interior support. PTT starts from a fixed seed grid before one bounded optimizer call. `fixed_physiology` fits only PTT and nuisance gains. `analysis_masks` restrict residuals (for example to odd or even beats). `evaluate=False` skips ensemble metrics.

## Ensemble waveform metrics

`NMSE = sum((prediction-target)^2)/sum((target-mean(target))^2)`, `R2 = 1-NMSE`, on foot-aligned ensemble means (`ppg_transfer.beats.ensemble`). Noise floor `n1 n2/(n1+n2)^2` times odd/even squared difference over the full-mean centered sum of squares; ceiling R2 = 1 - floor. Morphology: foot-to-peak time, notch presence/time/depth, half-height systolic width and matched-foot delay; missing features stay undefined.
