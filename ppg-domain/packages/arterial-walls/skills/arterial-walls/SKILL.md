---
name: arterial-walls
description: Choose supported arterial wall-law options for 1D arterial-network simulations using verified literature parameters.
---

## Solver changes

Do not modify, copy-and-modify, or patch the openBF solver unless the goal explicitly declares itself a solver-development goal approved by Yihan. If a result looks like a solver defect, stop that line of work, write a minimal reproducing case (smallest network, settings, observed vs expected) in summary.md under 'Suspected solver defects', and continue only with steps that do not depend on it. In a solver-development goal approved by Yihan: change only the goal's own copy, put every change behind an option whose default is upstream behaviour, show bitwise equality with the openbf package with all options off, add a known-answer test per change, change source only in stage 1, and never change code to make a criterion pass. A development goal's copy is used only inside that goal. After human review, accepted changes are merged into packages/openbf/openbf_param and re-registered; no other goal may call a goal's copy.

# Using the wall-law knowledge

1. Read `walls_knowledge/index.md`; take literature parameters only from `walls_knowledge/langewouters1984_table2.md` and `walls_knowledge/sources.md`.
2. For experimental goals, use only wall-law options supported by the installed solver (see `external_packages/openbf/`); if a required law is unsupported, stop that line of work and report the limitation.
3. Check the selected supported configuration against a known answer before production runs.
4. Finger-artery parameters are not in the sources; declare them as modelling inputs.
