# 验收

运行: 512a1048-c301-4281-aedb-421a3c79457c  
模式: full  
总体: **blocked**  
确定性检查: **passed**

| 检查 | 状态 | 结果 |
| --- | --- | --- |
| `package:pulse` | **passed** | required package structure exists |
| `package:mcx` | **passed** | required package structure exists |
| `package:peripheral-ppg` | **passed** | required package structure exists |
| `doctor:pulse` | **passed** | doctor returned explicit available=true |
| `doctor:mcx` | **passed** | doctor returned explicit available=true |
| `fermilink:setup` | **passed** | registered: pulse (snapshot matches current source) registered: mcx (snapshot matches current source) registered: peripheral-ppg (snapshot matches current source) overlay: pulse: skills,pulse_knowledge overlay: mcx: skills,mcx_knowledge overlay: peripheral-ppg: skills,ppg_knowledge,ppg_examples dependencies: peripheral-ppg -> pulse, mcx PPG CLI shim: /data/liuyihan/FermiLink/ppg-domain/.runtime/ppg-venv/bin/peripheral-ppg refreshing package-linked workspace: /data/liuyihan/FermiLink/ppg-domain/workspaces/fermilink-validation workspace ready: /data/liuyihan/FermiLink/ppg-domain/workspaces/fermilink-validation {"status": "ready", "registry": "/data/liuyihan/FermiLink/ppg-domain/.runtime/fermilink-registry", "packages": ["pulse", "mcx", "peripheral-ppg"]}  |
| `fermilink:registry` | **passed** | all packages registered in isolated registry |
| `fermilink:workspace` | **passed** | PPG entry, both dependency skills/knowledge/source links are readable and collision-free |
| `doctor:peripheral-ppg` | **passed** | doctor returned explicit available=true |
| `pulse:baseline` | **passed** | real Pulse CLI run completed |
| `pulse:control` | **passed** | real Pulse CLI run completed |
| `pulse:intervention` | **passed** | real Pulse CLI run completed |
| `mcx:simulate:660nm` | **passed** | real PMCX simulation produced finite-area detector reading |
| `mcx:simulate:940nm` | **passed** | real PMCX simulation produced finite-area detector reading |
| `mcx:reweight` | **passed** | absorption-only photon path reweight |
| `mcx:reweight-direct-comparison` | **passed** | direct vs reweighted difference is -2.56 combined SE |
| `mcx:replay` | **passed** | real MCX photon replay Jacobian |
| `peripheral-ppg:end-to-end` | **passed** | Pulse → 2R1C → MCX coupled run and validation |
| `peripheral-ppg:unit-tests` | **passed** | PPG analytical, conservation, timestep-refinement, alignment, volume and invalid-record-reference tests |
| `mcx:detector-normalization-units` | **passed** | Independent raw photon check of voxel path conversion, unit collected fraction, detector area in mm2 and reflectance in mm-2 |
| `ppg:pulse-step-units` | **passed** | Real manifests agree on engine/output timestep and explicit time, pressure, cardiac-output, volume and absorption units |
| `sources:local-citations` | **passed** | All cataloged local source and knowledge paths resolve |
| `fermilink:agent-task` | **blocked** | agent task not run: project-local Codex CLI codex-cli 0.166.0 is installed but not authenticated (login status: Not logged in; exit code 1; checked 2026-11-02T11:31:52.582853+00:00; PATH is child-process only) |

被阻断项表示验收未完成，不计为通过。
