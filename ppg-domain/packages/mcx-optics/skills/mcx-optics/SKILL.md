---
name: mcx-optics
description: 使用 MCX 模拟组织光传输，按材料吸收重加权，或通过 photon replay 求局部 Jacobian。
---

# MCX 组织光传输

用于输入明确的几何、各波长材料参数、光源和有限探测器，计算 MCX 探测读数。先读 [知识索引](../../mcx_knowledge/index.md) 与 [包 README](../../README.md)，再选取示例配置。用 `mcx-optics doctor --json` 检查 GPU；`simulate` 真实运行，`reweight` 在固定几何及散射条件下使用保存的路径，`sensitivity` 对基准探测光子进行 replay。它们各自要求配置和新输出目录；详见 README。探测分数按发射数归一化；局部 Jacobian 不是人体层贡献比例。材料工程假设与文献测量值应区分。
