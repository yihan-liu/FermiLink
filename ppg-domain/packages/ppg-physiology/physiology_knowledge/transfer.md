# Timing, harmonic transfer and reliability

## Beat feet and ensembles

A robust foot: the last local minimum within 250 ms before the maximum systolic upstroke of a prominent peak (peaks >= 0.35 s apart, prominence >= 15% of the 5-95 percentile range, detected on a zero-phase 10 Hz low-pass copy), refined by a three-point parabola. Using the same rule on observed and predicted signals matters more than the rule itself.

Physical-time ensemble: cut complete foot-to-foot beats on one time grid (shortest complete RR), normalize each beat once by its foot and peak-minus-foot amplitude, average. Do not time-warp beats.

## Harmonic transfer from beat-segmented records

With input x (ART) and output y (PLETH) at native 500 Hz, take ART feet to define common beats with phase `u = (t - foot)/RR` for both channels. Per beat, remove the DC integral and compute `X_bk = integral_0^1 x_b(u) exp(-2 pi i k u) du` (trapezoid on native samples with interpolated endpoints), k = 1..5; likewise Y. Ensemble ratio `H_k = mean_b(Y_bk)/mean_b(X_bk)`, frequencies `f_k = k/mean(RR)`. Odd and even beats give split-half estimates on the same grid. With variable RR, H is a beat-phase ensemble descriptor, not a stationary LTI response.

Gain-invariant descriptors: `abs(H_k)/abs(H_1)`; residual phase `psi_k = Arg(H_k (conj(H_1)/abs(H_1))^k)`.

## Harmonic transfer of a periodic simulation

Fit a constant and k = 1..5 sine/cosine terms on the common period by least squares for input and output; `H_k = Y_k/X_k`.

## Phase delay and group delay

- H1 phase delay: `-phase(H_1)/omega_1`. A near-constant phase offset phi0 (for example from a minimum-phase filter) makes it `tau_g - phi0/omega_1`, which varies as 1/HR.
- Weighted harmonic group delay: fit `phase(H_k) = intercept - omega_k tau` over k = 1..3 by weighted least squares with an intercept; tau is the delay. The intercept absorbs phi0. With few harmonics k = 1..2 is the fallback.
- Phase branch: unwrap the residual after removing a known operator phase (for example the monitor's band-pass and device delay), assuming adjacent residual increments lie in (-pi, pi); then restore the operator phase and fit the raw phase. Report the branch margin.
- Weights: inverse split-half phase-noise variance `v_k = 0.25 E[(odd - even)^2]`, estimated with equal case weighting on development data, then frozen. Use the same estimator and weights for observations and models.
- Subtracting each case's mean delay removes constant device and catheter offsets; within-case slopes remain.

## Reliability

Split-half (odd/even beat) correlation within cases, Spearman-Brown `2r/(1+r)` for the full-window value (parallel-halves approximation). Features with reliability below a threshold chosen before analysis are excluded.

## Within-case slope analysis

For a feature y and covariates MAP, HR and time: per-case OLS slopes (use these, not mixed-model BLUPs, to count sign agreement, because shrinkage inflates agreement), mixed models with random case slopes for pooled effects, time-aware HAC errors, and a negative control that circularly shifts the MAP residual within continuous runs. Report MAP-HR collinearity (VIF). Pulse pressure is a mediator, not a covariate.

## Waveform comparison metrics

`NMSE = sum((pred - target)^2)/sum((target - mean)^2)` on ensemble means; odd/even noise floor `n1 n2/(n1+n2)^2 * sum((odd - even)^2)/sum((full - mean)^2)`; ceiling R2 = 1 - floor. Morphology: foot-to-peak time, dicrotic notch presence/time/depth, half-height systolic width. Shape agreement alone did not separate physical models from flexible filters in earlier work.
