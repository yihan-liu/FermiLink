# FermiLink 集成状态

项目使用显式 FERMILINK_SCIPKG_ROOT=.runtime/fermilink-registry；三个包已登记，PPG 显式依赖 Pulse 与 MCX。Overlay 和 workspace 导航均通过完整 deterministic acceptance。

最后一次正式 full 求解结果保留在 runs/acceptance/20261102-181142-fffe1405；其中 Pulse、MCX、PPG 真实运行及 7 项 PPG unittest、MCX photon detector 归一化、timestep/单位、source 路径检查全部通过。未重跑仿真。

2026-11-02 的 Agent 短任务因当时的项目私有 Codex CLI 0.166.0 未登录而 blocked（login status 为 Not logged in，exit code 1）。验收子进程仅修改自身 PATH，没有修改全局 PATH 或 provider 配置，也未启动登录。该项目私有 CLI 已于 2026-11-13 移除。
