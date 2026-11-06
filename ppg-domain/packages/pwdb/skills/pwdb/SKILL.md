---
name: pwdb
description: Use public PWDB virtual-subject geometry, model settings and reference pulse waves, including the common-root time reconstruction.
---

# PWDB procedure

1. Read `pwdb_knowledge/index.md`. Use the local cache under `.runtime/pwdb/`; fetch other subjects from the public record only when the goal asks.
2. `pwdb_examples/pwdb_reference.py` is a reference loader (geometry, wall coefficients, source-time references). Copy or adapt it in the project folder.
3. Compare simulations with references on the common root time; never shift, stretch or rescale reference arrays. Record which subject and which sites were used.
