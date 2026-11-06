---
name: ppg-physiology
description: Look up pressure-to-PPG model equations, arterial wall laws with verified literature parameters, transfer-function and delay definitions, waveform metrics and optical absorption relations, with reference code to adapt.
---

# Using the physiology knowledge

1. Start from `physiology_knowledge/index.md` and open only the topic file the goal needs.
2. Implement in the run's project folder. Reference code in `physiology_examples/` may be copied and adapted; state what was changed.
3. Before using an implementation on real data, check it on a synthetic signal with a known answer (for example a known delay or gain) and report the check.
4. Label literature values, modelling assumptions, declared parameter ranges and run findings separately. Cite `physiology_knowledge/sources.md` for literature values.
5. If a definition here looks wrong or incomplete, say so under suggested skills updates in `summary.md`.
