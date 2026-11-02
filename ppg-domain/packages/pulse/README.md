# pulse

调用固定版本的官方 Pulse Python/PyPulse 成人全身模型。`doctor --json` 检查真实后端；`run --config FILE --output NEW_DIR` 在新目录保存数据、状态、日志及 manifest。配置见 `pulse_examples/`；相对状态路径相对配置文件。输出系统动脉压、心率、逐搏汇总 SBP/DBP/MAP、心输出量及主动脉 compartment 压力；并非指端压力。具体建模语义及源码入口见 `pulse_knowledge/index.md`。

源码 commit：5e29e5b13710a08cec90874be7d36ecb192ebcda。官方 superbuild 需 C++17、CMake、Python 和下载的 C++ 依赖；运行须有生成的 Pulse 数据和 PyPulse。示例心率倍率是直接模型参数修改，incremental=true 不触发动作的再稳定阶段；反馈仍可影响响应。

从项目根执行（示例输出目录必须不存在）：

```sh
.runtime/pulse/bin/pulse doctor --json
.runtime/pulse/bin/pulse run --config packages/pulse/pulse_examples/baseline.json --output runs/pulse-baseline-real
.runtime/pulse/bin/pulse run --config packages/pulse/pulse_examples/control.json --output runs/pulse-control-real
.runtime/pulse/bin/pulse run --config packages/pulse/pulse_examples/intervention.json --output runs/pulse-intervention-real
```

本机使用 Python 3.12、GCC 13、CMake 4.4.4、OpenJDK 21；构建目录 `.runtime/pulse-build`、虚拟环境 `.runtime/pulse`、JDK `.runtime/pulse-jdk`。安装包命令为 `.runtime/pulse/bin/pip install -e packages/pulse`。官方源码使用固定 commit；建立独立 Python 环境并安装源码 `requirements.txt` 及 `cmake ninja pybind11 protobuf`，将 `JAVA_HOME` 指向 JDK 后：

```sh
export PATH="$PWD/.runtime/pulse/bin:$PATH"
cmake -S upstream/pulse -B .runtime/pulse-build -G Ninja -DCMAKE_BUILD_TYPE=Release -DPulse_JAVA_API=ON -DPulse_GEN_DATA=OFF -DPulse_PYTHON_API=ON -DPulse_PYTHON_HOME_DIR="$PWD/.runtime/pulse" -DPulse_JAVA_HOME_DIR="$JAVA_HOME" -DCMAKE_POLICY_VERSION_MINIMUM=3.5
cmake --build .runtime/pulse-build -j 6
cd .runtime/pulse-build/install/bin
export PYTHONPATH="$PWD/../python:$PWD" LD_LIBRARY_PATH="$PWD"
../../../pulse/bin/cmake -DTYPE=genData -P run.cmake
```

这是固定版本官方构建与数据生成流程；首次构建下载 C++ 依赖。服务器曾遇到 GitHub release 下载中断，使用同版本官方 codeload 归档（MD5 `a8a8a3de136df18dbe87b47c174e7c16`）后继续。标准男患者通过初始化运行时稳定，并保存为 `state.json`。恢复后 CSV 时间保留引擎绝对模拟时间。配置路径相对配置文件解析，输出目录不可覆盖已有运行。
