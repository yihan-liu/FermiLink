---
name: ppg-transfer
description: Compute harmonic transfer descriptors and harmonic group delays for observed records or model waveforms with one shared implementation.
---

# Usage

1. Read `transfer_knowledge/index.md` for definitions, units and branch assumptions.
2. This package has no CLI. Stage code calls it through the ppg-python launcher (`/data/liuyihan/FermiLink/ppg-domain/.runtime/ppg-venv/bin/ppg-python`).
3. Observed records use `compute_tf_harmonics` and `fit_delay` with the frozen observation operator. Model waveforms use `periodic_transfer`, which calls the same `fit_delay` with no operator. Do not reimplement either estimator elsewhere.
4. Harmonic sets, weights and thresholds come from the calling goal; report undefined features as undefined.
