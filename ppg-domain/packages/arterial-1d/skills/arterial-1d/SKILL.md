---
name: arterial-1d
description: Public PWDB arterial network and radial-pressure to digital-area simulations.
---

Read README.md and ppg_knowledge/index.md. Check `doctor` before numerical work.
Use a new output directory for each command. Source public data from the
package example config; never use patient recordings. Keep exactly default,
hughes and langewouters wall switches. Keep original Voigt viscosity for all.
Run full PWDB acceptance and sweeps only through the authorized FermiLink
DeepSeek loop. Check actual simulation outputs against shared-root reference
time; no independent site shifts or amplitude fitting. Report blocked numerical
capabilities plainly. Shapiro is a future extension point and is not implemented.
