# 外周 PPG 项目工作区

本目录包含三个 FermiLink 包，用明确的模型假设连接全身循环、局部外周模型与组织光学。新增注册、脚本、配置、工作区、报告和运行结果均在本目录。

FermiLink 0.3.10 显式使用项目隔离 registry：FERMILINK_SCIPKG_ROOT=.runtime/fermilink-registry。全局默认 registry 与 active package 未被更改。集成脚本处理 FermiLink copytree 对 symlink 的解引用；workspace 位于 workspaces/fermilink-validation，PPG 入口在工作区根目录，Pulse 与 MCX 依赖位于 external_packages/。

## 环境与注册

在服务器项目根目录运行：

```bash
python3 scripts/check_environment.py
python3 scripts/integrate_fermilink.py --install --workspace
```

集成脚本只会刷新能从 registry 元数据核实为本任务托管的快照；遇到未登记但已存在的目标路径时会停止。求解器环境相互独立，PPG CLI shim 位于 .runtime/ppg-venv。

## FermiLink 工作区与 Codex CLI

Codex CLI 0.166.0 位于项目私有目录 .runtime/codex-cli。以下 PATH 只在当前 shell 及其子进程生效，不修改全局 PATH 或 FermiLink provider 配置：

```bash
PPG_DOMAIN_ROOT="$PWD"
export FERMILINK_SCIPKG_ROOT="$PPG_DOMAIN_ROOT/.runtime/fermilink-registry"
export PATH="$PPG_DOMAIN_ROOT/.runtime/codex-cli:$PATH"
cd "$PPG_DOMAIN_ROOT/workspaces/fermilink-validation"
"$PPG_DOMAIN_ROOT/.runtime/codex-cli/codex" login status
```

实测状态为 Not logged in。若要启用 agent 短任务，请用户先在个人 ChatGPT 安全设置或 workspace 权限中启用 device code login，再自行交互运行：

```bash
"$PPG_DOMAIN_ROOT/.runtime/codex-cli/codex" login --device-auth
"$PPG_DOMAIN_ROOT/.runtime/codex-cli/codex" login status
TASK_OUTPUT="$PPG_DOMAIN_ROOT/runs/agent-task-$(date +%Y%m%d-%H%M%S)-$$"
"$PPG_DOMAIN_ROOT/../.venv/bin/fermilink" exec --package peripheral-ppg \
  "Read skills/ppg-model/SKILL.md and ppg_knowledge/index.md. Run the engineering example from this workspace with the project CLI: simulate --config ppg_examples/engineering_example.json --output $TASK_OUTPUT. Then run validate-run $TASK_OUTPUT and report the manifest run_id."
"$PPG_DOMAIN_ROOT/.runtime/ppg-venv/bin/peripheral-ppg" validate-run "$TASK_OUTPUT"
```

设备码登录需在浏览器完成用户验证并输入一次性代码。我们没有启动登录流程。见 [OpenAI 官方认证说明](https://learn.chatgpt.com/docs/auth)。

## 端到端 PPG 运行

以下命令为每次运行生成新的输出目录，并在运行后调用 validate-run：

```bash
CLI="$PPG_DOMAIN_ROOT/.runtime/ppg-venv/bin/peripheral-ppg"
RUN_DIR="runs/ppg-demo-$(date +%Y%m%d-%H%M%S%N)-$$"
"$CLI" doctor --json
"$CLI" simulate --config packages/peripheral-ppg/ppg_examples/engineering_example.json --output "$RUN_DIR"
"$CLI" validate-run "$RUN_DIR"
```

配置中的求解器路径相对配置文件解析，不依赖当前工作目录。示例参数是工程假设，输出是模拟数据。

## 验收状态

python3 scripts/run_acceptance.py --quick 检查结构、registry、workspace 与 solver doctor；默认 full 模式还会真实运行 Pulse、MCX 和 PPG、执行数值测试及单位/来源核对。结果写入新的 runs/acceptance 子目录。

确定性验收通过。当前 agent 短任务 blocked：Codex CLI 已安装，但 login status 为 Not logged in。登录由用户自行交互完成；验收脚本不会发起登录。详见 reports/acceptance.md、reports/architecture.md、reports/implementation.md、reports/sources.md 与 reports/environment.md。
