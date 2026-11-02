# 实施与运行

三个包为 pulse-physiology、mcx-optics、peripheral-ppg。所有新增注册、脚本、配置、工作区、报告与运行结果均位于本目录。

scripts/integrate_fermilink.py 显式设置 FERMILINK_SCIPKG_ROOT=.runtime/fermilink-registry；staging 排除 symlink 和生成目录，避免 FermiLink 默认 copytree 把上游源码复制进注册快照。包内 pulse_source、mcx_source 以相对链接定位 upstream，安装脚本将其解析到当前项目的真实 upstream 目录后，在隔离 registry 副本中恢复绝对链接。

Overlay 仅暴露 skills 和唯一知识目录；PPG 另暴露唯一 ppg_examples。PPG 通过 FermiLink dependencies 关联 Pulse 和 MCX。workspace 为 workspaces/fermilink-validation，依赖链接位于 external_packages。PPG CLI shim 位于项目 .runtime/ppg-venv。

scripts/run_acceptance.py 的 full 模式运行真实 Pulse baseline/control/intervention、MCX 660/940 nm 仿真、吸收重加权、独立直接仿真、replay、PPG coupled run/validator；随后执行 PPG unittest、MCX 原始光子 detector 归一化及单位检查、真实 manifest 时间步和单位检查、sources.json 本地路径检查。每次生成新的 runs/acceptance 子目录。

验收子进程的 PATH 只在项目内 process environment 中将 .runtime/codex-cli 与各求解器 bin 目录置于前端；没有修改用户全局 PATH。Agent 检查读取 FermiLink provider 配置，并运行项目本地 Codex CLI 的 login status。当前 0.166.0 返回 Not logged in 和 exit code 1，因而不执行 FermiLink agent task。若已认证，脚本才从专用 workspace 调用读取 skills/ppg-model/SKILL.md 与 PPG 知识索引、调用 ppg_examples/engineering_example.json 生成全新运行目录并核验 manifest 和 validate-run valid=true 的验收任务。脚本不会运行登录命令或提示登录。

设备码登录命令为项目内 .runtime/codex-cli/codex login --device-auth；用户需先在 ChatGPT 安全设置或 workspace 权限中启用 device code login，并自行完成浏览器验证。官方说明：[OpenAI Codex authentication](https://learn.chatgpt.com/docs/auth)。
