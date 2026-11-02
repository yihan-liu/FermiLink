# Pulse 导航

触发：需要全身血流动力学输出、稳定患者、状态分支或解释干预时。输入为患者参数或状态、时间与心血管参数；输出及单位见 `../README.md` 和 CSV 表头。

- [心血管方法](https://pulse.kitware.com/_cardiovascular_methodology.html)：集总电路的压力、流量、容积与电阻、顺应性及心室驱动，不能将集总变量当成局部波传播。引擎模型 `pulse_source/src/cpp/engine/common/system/physiology/CardiovascularModel.cpp`。
- 稳定：官方示例 `pulse_source/src/python/pulse/howto/HowTo_EngineUse.py` 展示 `SEPatientConfiguration` 初始化、状态 `serialize_from_file`；`PulseEngine.py` 提供 `serialize_to_file`。稳定状态可保存后从同一状态分支。缓存须与模型版本及条件一致。
- 修改：`HowTo_CardiovascularModification.py` 和 `HowTo_SystemModifiers.py` 演示 `SECardiovascularMechanicsModification`；可设置心率倍率等，直接机制修改不等于运动之类生理动作。初始患者基线、显式 mechanics 值与 multiplier 及反馈调节含义不同。`incremental` 决定是否执行动作引起的重新稳定；对比瞬态和重新稳定结果须标注时间及状态。
- 主动脉顺应性：该版本 `CardiovascularModel.cpp` 的 `m_AortaCompliancePaths` 应用 `ArterialCompliance` 和 `ArterialComplianceMultiplier`，其解剖对象是主动脉路径，而非指端或所有动脉。系统阻力与顺应性见同文件 `m_SystemicResistancePaths` 与 `m_SystemicCompliancePaths`。
- [神经反馈](https://pulse.kitware.com/_nervous_methodology.html)：压力感受器反馈会改变干预响应。结果不应仅凭设定倍率直接推断最终心率或压强方向。
- Data requests：`HowTo_EngineUse.py` 解释瞬时值、心搏汇总与 `Aorta` compartment 请求。引擎时间步长与输出间隔分别记录于 manifest；不插值，不能声称更高时间分辨率。
- 外部局部模型可读取 `data.csv` 的系统动脉压，必须自行声明从全身到局部入口的假设；Pulse 本接口没有指端传播时延。使用 `pulse_examples/` 的 baseline、control 和 intervention 实现同一起点比较。

来源版本：Pulse commit `5e29e5b13710a08cec90874be7d36ecb192ebcda`，官方源码 https://gitlab.kitware.com/physiology/engine ，2026-11-02 访问。
