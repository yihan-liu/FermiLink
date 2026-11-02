---
name: ppg-model
description: 解释并运行外周 PPG 简化耦合模型，区分全身、局部与光学量。
---

# 外周 PPG

处理指端压力、局部流量和吸收型光学观测时使用。以下路径相对 FermiLink 项目工作区根目录。先读取 `ppg_knowledge/index.md`，明确输入测点、单位、参考体积、材料来源、初始过渡和固定几何假设；Pulse 与 MCX 的知识入口分别是 `external_packages/pulse-physiology/pulse_knowledge/index.md` 和 `external_packages/mcx-optics/mcx_knowledge/index.md`。

工作区中使用 `ppg_examples/engineering_example.json` 作为明确标记的工程假设示例。当前服务器 CLI 为 `/data/liuyihan/FermiLink/ppg-domain/.runtime/ppg-venv/bin/peripheral-ppg`；执行前用 `doctor --json` 检查，然后运行 `simulate --config ppg_examples/engineering_example.json --output runs/unique-name`，最后运行 `validate-run runs/unique-name`。输出目录必须不存在。时间序列、直接状态对照、单位和研究记录用法见知识索引。

输出应区分真实求解器执行、模拟数据与工程假设；局部支路流量不是全身心输出量。尚未实现的传播、形变和机制识别不得标为已执行。
