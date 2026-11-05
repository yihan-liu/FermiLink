# Transfer descriptors

## Beat feet and ensembles

`beats.feet(x, fs_hz)` returns sub-sample local-minimum times (s) before prominent systolic upstrokes: peaks >=0.35 s apart with prominence >=15% of the 5-95 percentile range on a zero-phase 10 Hz second-order Butterworth copy; the last local minimum within 250 ms before the maximum upstroke; a three-point parabola gives sub-sample timing.

`beats.ensemble(x, fs_hz, duration_s, foot_times)` cuts complete foot-to-next-foot beats on one physical-time grid (shortest complete RR), normalizes each beat once by its foot and peak-minus-foot amplitude, and returns full beats, mean and coverage. No beat is time-warped.

## Beat-segmented harmonics

`harmonics.compute_tf_harmonics(art, pleth, fs_hz=500, foot_times=None)` requires aligned native 500 Hz records. ART feet (supplied, or detected on ART only) define complete common beats with phase `u=(t-foot)/RR` for both channels. Per beat, DC is removed and `X_bk = integral_0^1 x_b(u) exp(-2 pi i k u) du` (trapezoid on native samples with interpolated endpoints), k=1..5. `H_k = mean_b(Y_bk)/mean_b(X_bk)`. Odd and even beats give split-half estimates on the same frequency grid `f_k = k/mean(RR)`.

Features: `abs(H_k)/abs(H_1)`; residual phase `psi_k = Arg(H_k (conj(H_1)/abs(H_1))^k)`; adjacent residual group delays from principal increments. Positive gain and offset leave all features unchanged. With variable RR, H is a beat-phase ensemble descriptor.

## Periodic-cycle harmonics

`harmonics.periodic_phasors(t, y, period)` fits a constant and k=1..5 sine/cosine terms on a common period by least squares. `periodic_transfer(t, x, y, period, phase_weights)` returns `H_k = Y_k/X_k`, `h2_over_h1`, `h1_phase_delay_s = -Arg(H_1) T/(2 pi)` and the k=1..3 group delay from `fit_delay` with no observation operator. Units of H follow the inputs (for example m^2/Pa for radial pressure to digital area).

## Harmonic group delay

`delay.fit_delay(H, frequencies_hz, operator, weights, harmonics=(1,2,3))` fits `phase(H_k) = intercept - omega_k tau` by weighted least squares with positive weights; tau is seconds. Phase branches: a known observation operator's continuous phase (`operator_phase`, causal Butterworth band-pass, sign and device delay at 500 Hz) guides the unwrapping of the residual phase, then is restored, so the slope is fitted to the raw H phase. With `operator=None` the guide is zero. Adjacent residual increments are assumed to lie in (-pi, pi); `branch_margin_rad` reports the distance to that limit. `h1_phase_delay_s` is `-phase_1/omega_1` on the same branch.

`freeze_harmonic_weights(records, harmonics)` estimates per-harmonic split-noise variance `v = 0.25 E[(odd-even)^2]` with equal case weighting and returns weights `1/v`; zero or missing variance leaves the weights undefined. `half_branch_diagnostics(full, odd, even)` reports whole-cycle branch disagreements between full and half estimates.

Which harmonics, weights, reference centering and reliability criteria are used is decided by the calling goal.
