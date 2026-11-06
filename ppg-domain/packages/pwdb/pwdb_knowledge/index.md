# PWDB contents and conventions

## Files

The public record contains per-subject waveforms (CSV and WFDB, 500 Hz), `pwdb_data.mat`, and `geo.zip` with one geometry CSV per subject. The [geometry wiki](https://github.com/peterhcharlton/pwdb/wiki/geo) lists inlet/outlet nodes, segment lengths and radii, and terminal Windkessel total resistance and compliance. The [data wiki](https://github.com/peterhcharlton/pwdb/wiki/pwdb_data.mat) defines sites.

The local cache JSON (`.runtime/pwdb/baseline-subject-0001.json`) has `geometry` (seg_no, inlet_node, outlet_node, length m, inlet_radius m, outlet_radius m, peripheral_r Pa s/m^3, peripheral_c m^3/Pa), `model_config` (density, viscosity, DBP/MBP mmHg, p_out, k1/k2/k3, b0/b1), `waveforms` (`<Site>_<P|U|A>`), `onset_times`, `fs_hz` = 500, `period_s`, `wave_units` (P mmHg, U m/s, A m^2).

## Sites

Root: segment 1 proximal (AorticRoot). Left radial: distal end of segment 22. Left digital: distal end of segment 112.

## Model used by PWDB

1D network solved with Nektar1D (access needs author approval). Tapered vessels; Voigt-type viscoelastic wall; three-element Windkessel outlets. Reference radii are at diastolic pressure, not zero pressure. Elastic stiffness from the generator: `Eh = 0.1 (k1 exp(k2 100 r) + k3) r` (source units converted to SI), `B = 4 Eh/(3 r)`, `Pe = Pd + B (sqrt(A/Ad) - 1)`. Viscous input `Gamma` from b0, b1 and radius as in the generator; it is applied only to segments longer than 0.011 m. Equations for reproducing this wall model are in the `ppg-physiology` knowledge base (arterial walls).

## Time convention

Each site's waveform is exported starting at that site's local pulse foot, at native 500 Hz. To place sites on a common root time, add the site's published onset (subject 1: radial 0.084 s, digital 0.090 s) to native sample times `j/500` and interpolate periodically over the common period. Do not stretch each local array to the period, align sites independently, rescale amplitudes or patch endpoints. Subject 1: 412 root/digital samples and 411 radial samples after removing trailing NaN padding.
