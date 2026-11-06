# vitaldb

Knowledge base for the VitalDB intraoperative recordings used in this project: file format, tracks and units, derived scan metadata, and the data-access rules every run must follow.

Data are given to a run only through a read-only split view built by the research workspace, for example `/data/liuyihan/abp-ppg-fermilink/data/views/train/` (`vital/NNNN.vital`, `scan/windows/<caseid>.parquet`, `scan/events/<caseid>.json`, `cases.csv`). Use only the view path named in the goal.

- [Format, tracks, scan metadata and access rules](vitaldb_knowledge/index.md)
- [Procedure](skills/vitaldb/SKILL.md)
- [Reference window reader](vitaldb_examples/window_reader_reference.py) and [rule constants](vitaldb_examples/access_rules_reference.py)

Source: [VitalDB](https://vitaldb.net/), Lee et al., Sci Data 2022, DOI [10.1038/s41597-022-01411-5](https://doi.org/10.1038/s41597-022-01411-5).
