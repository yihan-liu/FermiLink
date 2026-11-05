# arterial-1d

Public PWDB network implementation for the model transfer from radial pressure
(segment 22 distal end) to digital luminal area (segment 112 distal end).
Digital area is a haemodynamic state. Optical finger PPG requires a separate
observation model.

## Implementation status

The public geometry loader, native shared-time reference reconstruction and run
metadata are implemented. The numerical adapter is under architecture review.
Upstream openBF 2.8.0 is Apache-2.0 and remains read-only at
`ppg-domain/upstream/openBF` (fae58658e060640fb523141e47001e1522b88b0b).
No full-network simulation or acceptance run has been performed.

## Required numerical adaptation

The openBF Vessel type and flux, wave speed, Riemann invariants, inlet,
Windkessel and junction routines all specialize the square-root elastic law.
A faithful three-law implementation needs an explicit constitutive state in
those routines. Replacing output pressure alone changes neither propagation
nor boundary impedance. PWDB also contains anastomoses, requiring both merge
and split junctions. The package must retain original Voigt viscosity for all
three elastic choices.

The upstream constructor computes radius increment per cell and then multiplies
it by dx. The public geometry adapter uses r(x)=rp+(rd-rp)*x/L directly and
retains small-vessel taper. The upstream taper tolerance also discards radius
changes below 1e-4 m. Neither behavior is used by the public-data loader.

## Public reference inputs and units

PWDB 0.2.0, https://zenodo.org/records/3275625, PDDL-1.0. Cached public subject 1:
`.runtime/pwdb-round3/baseline-subject-0001.json` under ppg-domain. The JSON
contains the 116-segment published geometry, terminal total R/C, model settings,
and root/radial/digital P/U/A reference arrays. SI solver units: Pa, m, s,
m3/s, m2, kg/m3. Source pressure is mmHg (133.322387415 Pa/mmHg).
The reference radius is at DBP, not zero pressure. Default elastic law is
Pe=Pd+B*(sqrt(A/Ad)-1), B=4Eh/(3r),
Eh=0.1*(k1*exp(k2*100r)+k3)*r.
The original input-generator Gamma expression is exposed separately; converting
it to the PDE diffusion coefficient remains subject to source verification.

Waveforms were exported starting at each site's local foot at native 500 Hz.
Restore source onset offsets before periodic interpolation; radial 0.084 s,
digital 0.090 s in subject 1. Preserve native j/500 samples and the common HR
period. Do not stretch each array to the period, independently align sites,
rescale amplitudes, detrend a second time or patch endpoints.

## Sources

- Original input generator (MIT):
  https://github.com/peterhcharlton/pwdb/blob/master/pwdb_v0.1/create_input_files_for_a_simulation.m
- PWDB paper: https://doi.org/10.1152/ajpheart.00218.2019
- openBF: https://github.com/INSIGNEO/openBF
- Hughes: https://doi.org/10.1177/016173467900100406
- Langewouters: https://doi.org/10.1016/0021-9290(84)90034-4
