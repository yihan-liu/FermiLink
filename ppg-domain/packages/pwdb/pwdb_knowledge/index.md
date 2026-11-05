# PWDB source conventions

The cached subject JSON contains the published geometry (inlet/outlet nodes, length, inlet/outlet radius, terminal total R and C), model configuration (density, viscosity, DBP/MBP, outflow pressure, stiffness k1/k2/k3, viscosity b0/b1) and root/radial/digital P/U/A arrays.

Reference radii are at diastolic pressure, not zero pressure. Default stiffness: `Eh = 0.1 (k1 exp(k2 100 r) + k3) r` (source units converted), `B = 4 Eh/(3 r)`, `Pe = Pd + B (sqrt(A/Ad) - 1)`.

Waveforms are exported at 500 Hz starting at each site's local foot. `reference` restores common root time by adding each site's published onset (subject 1: radial 0.084 s, digital 0.090 s) to native `j/500` sample times and interpolating periodically over the common period. Do not stretch local arrays to the period, align sites independently, rescale amplitudes or patch endpoints.
