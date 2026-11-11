# openbf

[openBF](https://github.com/INSIGNEO/openBF) 2.8.0 (Apache-2.0, INSIGNEO, University of Sheffield): a 1D finite-volume blood-flow solver for arterial networks. The package's single implementation is `openbf_param/` (openBF 2.8.0, revision `fae58658e060640fb523141e47001e1522b88b0b`, with added options). The unmodified release is a read-only reference at `/data/liuyihan/reference/openBF-upstream-2.8.0`, used for its documentation and model files and for bitwise checks in approved solver-development goals; it is never run or included.

## Thin CLI

| Command | Function |
| --- | --- |
| `openbf doctor` | Check that Julia and openBF load; print the openBF version. |
| `openbf run --config FILE.yaml --out DIR` | Call `openBF.run_simulation(config; save_stats=true, savedir=DIR)` in a fresh directory with `openbf_param/`; save a copy of the config, `openbf.log` and `run.json`. |

Solver: `openbf_param/` (configurable stiffness law, viscoelastic coefficients, exact taper, balanced taper source and the options in the skill; defaults reproduce openBF 2.8.0). Its source files are read-only. Shim: `/data/liuyihan/FermiLink/ppg-domain/.runtime/ppg-venv/bin/openbf`. Julia environment: `ppg-domain/.runtime/julia/project-param` (develops `openbf_param`), depot `.../depot` (override the root with `OPENBF_JULIA_RUNTIME`). Recreate the param environment with `julia --project=.runtime/julia/project-param -e 'using Pkg; Pkg.develop(path="packages/openbf/openbf_param")'`. Julia can also be called directly: `.runtime/julia/runtime/julia-1.11.2/bin/julia --project=.runtime/julia/project-param` with `JULIA_DEPOT_PATH=.runtime/julia/depot`.

- [How openBF works, configuration and limits](openbf_knowledge/index.md)
- [Procedure](skills/openbf/SKILL.md)
- [Example: openBF Circle of Willis model](openbf_examples/)
