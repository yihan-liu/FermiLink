# openbf

Upstream [openBF](https://github.com/INSIGNEO/openBF) 2.8.0 (Apache-2.0, INSIGNEO, University of Sheffield): a 1D finite-volume blood-flow solver for arterial networks. Source is read-only at `openbf_source/` (upstream revision `fae58658e060640fb523141e47001e1522b88b0b`).

## Thin CLI

| Command | Function |
| --- | --- |
| `openbf doctor` | Check that Julia and openBF load; print the openBF version. |
| `openbf run --config FILE.yaml --out DIR` | Call `openBF.run_simulation(config; save_stats=true, savedir=DIR)` in a fresh directory; save a copy of the config, `openbf.log` and `run.json`. |

Shim: `/data/liuyihan/FermiLink/ppg-domain/.runtime/ppg-venv/bin/openbf`. Julia project and depot: `ppg-domain/.runtime/julia` (override with `OPENBF_JULIA_RUNTIME`). Julia can also be called directly: `.runtime/julia/runtime/julia-1.11.2/bin/julia --project=.runtime/julia/project` with `JULIA_DEPOT_PATH=.runtime/julia/depot`.

- [How openBF works, configuration and limits](openbf_knowledge/index.md)
- [Procedure](skills/openbf/SKILL.md)
- [Example: upstream Circle of Willis model](openbf_examples/)
