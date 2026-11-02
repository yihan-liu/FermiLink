# 软件与方法来源

机器可读清单见 [sources.json](sources.json)。固定源码取得脚本为 [prepare_upstream.sh](../scripts/prepare_upstream.sh)：目标目录不存在时才 clone 并 checkout 固定 commit；已有目录必须已在目标 commit，否则脚本停止且不修改 checkout。

| 来源 | 固定版本 / 引用 | 用途 |
| --- | --- | --- |
| FermiLink | 0.3.10，commit 1677243；[registry resolver](../../src/fermilink/runner/scientific_packages.py) | 隔离 registry 与受支持的包集成接口 |
| Pulse | commit 5e29e5b13710a08cec90874be7d36ecb192ebcda；[本地源码](../upstream/pulse)，[官方方法](https://pulse.kitware.com/_cardiovascular_methodology.html) | 成人全身集总循环 |
| MCX | commit 49ec9f155107b7b54dece66d24e3c77a208cf2e8；[本地源码](../upstream/mcx) | 体素光子传输源码 |
| PMCX | wheel 0.8.1；[README](../packages/mcx-optics/README.md) | 实际 CUDA 后端；版本与 MCX 源码提交分别记录 |
| Yao, Intes 与 Fang (2018) | [DOI 10.1364/BOE.9.004588](https://doi.org/10.1364/BOE.9.004588)，[本地索引](../packages/mcx-optics/mcx_knowledge/index.md) | Photon replay 与基准点局部 Jacobian |
| Chatterjee 等 (2020) | [DOI 10.1088/1361-6579/aba008](https://doi.org/10.1088/1361-6579/aba008)，[本地索引](../packages/peripheral-ppg/ppg_knowledge/index.md) | PPG 光学建模背景，不验证本示例生理因果 |

运行后端版本、设备和执行状态以实际 acceptance manifests 为准。
