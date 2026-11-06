# pwdb

Knowledge base for the public Pulse Wave DataBase (PWDB 0.2.0, Charlton et al. 2019): a database of simulated arterial pulse waves from a 1D model of 116 arterial segments (aorta, upper limbs, head, lower limbs) for 4,374 virtual subjects.

- Dataset: [Zenodo record 3275625](https://zenodo.org/records/3275625), PDDL-1.0. Paper: [Am J Physiol Heart Circ Physiol 2019, DOI 10.1152/ajpheart.00218.2019](https://doi.org/10.1152/ajpheart.00218.2019). Input generator (MIT): [create_input_files_for_a_simulation.m](https://github.com/peterhcharlton/pwdb/blob/master/pwdb_v0.1/create_input_files_for_a_simulation.m).
- Local cache: `/data/liuyihan/FermiLink/ppg-domain/.runtime/pwdb/` (`baseline-subject-0001.json` holds subject 1 geometry, model configuration and root/radial/digital P/U/A arrays).

- [Contents, sites and time conventions](pwdb_knowledge/index.md)
- [Procedure](skills/pwdb/SKILL.md)
- [Reference loader](pwdb_examples/pwdb_reference.py)
