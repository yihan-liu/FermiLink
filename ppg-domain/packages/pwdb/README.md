# pwdb

Public Pulse Wave DataBase (PWDB 0.2.0) subjects: network geometry, wall coefficients and source-time reference waveforms.

Library only; it has no CLI. `openbf-walls` builds solver networks from it and stage code compares simulations with its references.

| Function (`pwdb.data`) | Purpose |
| --- | --- |
| `load_baseline(path)` | Read a cached subject JSON; checks P/U/A source units (mmHg, m/s, m^2). |
| `network(data)` | Published segments: lengths/radii m, terminal R Pa s/m^3, C m^3/Pa. |
| `radius(segment, x)` | Linear taper `r(x)=rp+(rd-rp) x/L`. |
| `wall_parameters(data, r)` | Reference area Ad and square-root coefficient B. |
| `nektar_gamma(data, r)` | Original generator viscosity input Gamma. |
| `reference(data, site, at)` | Root/radial/digital P (Pa), U, A, Q on common root time. |
| `periodic_interpolate` | Periodic interpolation of native samples. |

Sites: root = segment 1 (AorticRoot), radial = distal segment 22, digital = distal segment 112. `MMHG_PA = 133.322387415`.

- [Source conventions](pwdb_knowledge/index.md)
- [Usage notes](skills/pwdb/SKILL.md)
- [Example](pwdb_examples/reference.py)

Source: [PWDB record 3275625](https://zenodo.org/records/3275625), PDDL-1.0; [paper](https://doi.org/10.1152/ajpheart.00218.2019); [input generator](https://github.com/peterhcharlton/pwdb/blob/master/pwdb_v0.1/create_input_files_for_a_simulation.m) (MIT).
