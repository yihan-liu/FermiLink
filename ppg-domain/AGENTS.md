# ppg-domain 工作规则

本项目位于 `/data/liuyihan/FermiLink/ppg-domain`。所有自建代码、知识、注册表、配置、工作区、缓存与报告均放在此目录。FermiLink 本体及 `project_history.md` 不属于本项目写入范围；Pulse、MCX 上游源码为只读来源，包实现文件由各包负责人维护。

## 包路由

- `pulse`：全身循环模型与 Pulse 真实运行适配。
- `mcx`：给定组织几何、材料和探测器配置后的真实 MCX 光传输。
- `peripheral-ppg`：项目科学知识、局部血流动力学、混合光学以及跨包分析。

每个数值和结论标注其空间范围与证据类别（软件事实、文献证据、建模假设、项目发现）。全身动脉压力、器官 compartment 数据、局部状态和探测器读数不互换解释。一次仿真支持的是其配置和工作点下的结果，不自动成为人体通用规律。

## 环境与集成

阅读 `reports/environment.md` 后再运行求解器。FermiLink 包注册必须通过 `scripts/integrate_fermilink.py` 或显式设置：

```bash
export FERMILINK_SCIPKG_ROOT="$PWD/.runtime/fermilink-registry"
```

不得依赖 `~/.fermilink/scientific_packages` 的默认注册表。知识 overlay 只暴露各包 `skills/` 与唯一知识目录；PPG 对 Pulse/MCX 的依赖通过 FermiLink `external_packages/` 机制建立。不要未经协调使用 `--force`。

FermiLink 本地安装会用默认 `shutil.copytree()` 跟随 symlink。包如需访问上游源码，先用 `scripts/integrate_fermilink.py` 的 staging 安装流程，再在安装目录恢复到本项目上游 checkout 的绝对链接；不得直接将含有上游链接的包传给 `install --local-path`。

## 运行和报告

运行产物写入 `runs/` 或 `.runtime/` 下明确隔离的新目录，不覆盖既有科研运行。真实求解器不可用、示例未执行或接口未就绪时，报告为 `blocked` 并说明对象；不能以 mock、静态模板或跳过替代实际通过。根级集成只维护环境、FermiLink 注册、工作区导航和跨包验收，不改写其他包负责的源码。
