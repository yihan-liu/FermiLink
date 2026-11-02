# 环境检查

检查时间：2026-11-02；求解器能力以 full acceptance 的 doctor 与运行结果为准。

| 项目 | 实测状态 |
| --- | --- |
| FermiLink | 0.3.10，commit 1677243；Python 3.12.3 |
| Pulse | PyPulse 4.4.0，commit 5e29e5b；doctor available=true |
| MCX | PMCX CUDA 0.8.1，mcx-optics 0.1.0；doctor available=true，两张 GPU 可见 |
| PPG | peripheral-ppg 0.1.0；项目 CLI shim doctor 确认两个求解器可用 |
| 隔离 registry | .runtime/fermilink-registry；三个包和依赖均已登记 |
| Workspace | workspaces/fermilink-validation；PPG 主入口与 Pulse/MCX 依赖导航通过，无 collision |
| Codex CLI | 项目私有 .runtime/codex-cli/codex，版本 0.166.0；2026-11-02 10:28:50 UTC 的 login status 为 Not logged in，exit code 1 |

Full acceptance 的全部确定性检查通过。Agent task 因本地 CLI 未认证而 blocked，未执行登录。验收子进程仅在自身 PATH 前置项目私有 codex-cli 和 solver bin 目录；没有修改全局 PATH 或 FermiLink provider 配置。用户可按 README 的 device-auth 步骤自行登录，详见 [OpenAI 官方认证说明](https://learn.chatgpt.com/docs/auth)。
