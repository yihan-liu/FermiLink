# Optical relations for PPG

## Absorption mixing

`mua_mix = f_b mua_blood + (1 - f_b) mua_matrix` (1/mm), with fixed geometry and scattering. Blood absorption from hemoglobin extinction: `mua (1/mm) = 2.303 eps (cm^-1/M) * Hb (g/L) / 64500 (g/mol) / 10`, mixing HbO2 and Hb by saturation ([Prahl spectra](https://omlc.org/spectra/hemoglobin/summary.html)). Oxygenated blood scattering at Hct 45% ([Bosschaart et al. 2014](https://pmc.ncbi.nlm.nih.gov/articles/PMC3953607/)): 660 nm mus 92.29/mm, g 0.9850; 940 nm mus 56.84/mm, g 0.9768. Volume mixing of scattering: `mus = f mus_blood + (1-f) mus_matrix`, g weighted by mus.

## Same-photon absorption reweighting

With fixed scattering, geometry, source and detector, each detected photon's weight after an absorption change is `w = w0 exp(-sum_j mua_j L_j)` (L partial path length, mm). Detected intensity is the weight sum over launched photons. This does not apply when scattering or geometry change.

## Log-intensity linearization

For `X = sum_i delta_mua_i L_i` over detected photons with baseline weights: `ln(I1/I0) = ln E_w[exp(-X)] = -E_w X + 0.5 Var_w X + ...`. Quadratic-to-linear ratio `0.5 Var_w X / abs(E_w X)`; exact remainder `abs(ln E_w exp(-X) + E_w X)/abs(E_w X)`. Use stable log-sum-exp and the same photons for both states; estimate uncertainty between seeds. Optical AC/DC is peak-to-peak detected intensity over the cycle mean. Clinical PLETH units (band-passed, gain-controlled) give no absolute optical DC.

Reference code: `mcx_examples/absorption_linearization_reference.py`.
