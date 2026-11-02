# 外周 PPG 知识与能力

## 工作区导航与运行

以下路径以 FermiLink 项目工作区根目录为基准：Pulse 知识入口为 `external_packages/pulse-physiology/pulse_knowledge/index.md`，MCX 知识入口为 `external_packages/mcx-optics/mcx_knowledge/index.md`；工程示例配置为 `ppg_examples/engineering_example.json`。示例材料、几何和局部参数均为工程假设，不是人体测量值。

当前服务器上的 CLI 是 `/data/liuyihan/FermiLink/ppg-domain/.runtime/ppg-venv/bin/peripheral-ppg`。先以 `doctor --json` 检查，再运行 `simulate --config ppg_examples/engineering_example.json --output runs/unique-name`，完成后运行 `validate-run runs/unique-name`。上述各子命令均跟在 CLI 路径之后；输出目录必须不存在。配置路径解析到源文件后，配置中的求解器相对路径以配置文件目录为基准。

`coupled.csv` 包含 Pulse 压力、局部 P/Q/V、血液分数、混合吸收和每波长探测功率分数；`analysis.json` 使用分析区间的峰峰值、均值和它们的比。每个波长目录中的 `comparison.json` 比较重加权与独立种子直接计算并记录组合标准误。所有输出都是模拟数据。可用 `/data/liuyihan/FermiLink/ppg-domain/.runtime/ppg-venv/bin/python ppg_examples/record_example.py runs/unique-name records/example.json` 创建条件性研究记录；该脚本核验运行产物引用。

## 空间与方程

Pulse 输出是其系统循环测点的压力；把它直接视为指端局部模型入口是工程边界假设，既未实现动脉传播、反射，也不改变全身负载。局部流量 Q 是模型支路的进出流，不是 Pulse 全身心输出量。局部模型使用 mmHg、mL 和 s，R 的单位为 mmHg·s/mL，C 为 mL/mmHg：

`C dP/dt=(Pin-P)/Rin-(P-Pv)/Rout; V=Vref+C(P-Pref)`。

输入两点间线性插值，解析积分；明确指定初始压力和静脉压，并用配置指定初始过渡剔除时间。参考体积、采样体积、参考血液体积分数必须采用同一组织体积约定。`f_b=f_ref+(V-V_ref)/V_sampling` 越界即报错，不裁剪。`mua_mix=f_b*mua_blood+(1-f_b)*mua_matrix` 假设固定几何和散射；同一血液变化不能再次通过血管几何变化计入。

## 光学与信号

每个波长的材料参数由外部提供，波长本身不会自动生成组织光谱。几何、散射、g、n、边界及源探测设定固定时，MCX 保存的探测路径可用于吸收重加权；不同波长光学性质不同，应分别模拟。探测功率分数为探测权重之和除以发射光子数。飞行时间是光传播时间，区别于生理时间。理想线性电子读数应声明增益和符号；保留光学原始信号。AC 定义为分析区间峰峰值，DC 为算术均值，AC/DC 为其比值。

MCX 空间 Jacobian 是局部光学扰动的导数，不等同于生理参数有限差分。模型输入参数对信号的局部敏感性受工作点、步长和共同变化参数影响，不能单独证明生理机制或真实组织层贡献。多种组织、血液和接触效应可能产生类似变化；外周时延或组织形变需要额外传播/力学模型，接口应分别输出局部压力边界或时间相关几何，不能冒充现有模型能力。指端工程参数不自动适用于腕部。

条件比较应保存原始共同起点的时间轴；若另做波形对齐，应保留偏移并说明依据，不能通过最大相关对齐抹去真实相位差。2R1C 的时间常数产生局部滤波相位滞后，不等于模型已实现外周传播延迟。

## 来源与证据标签

软件事实参照所安装版本的 Pulse 与 MCX 包及其官方源码；上述局部耦合与混合是建模假设。光学建模背景：Chatterjee 等，Physiological Measurement 41, 084001 (2020), https://doi.org/10.1088/1361-6579/aba008；光子 replay：Yao 等，Biomedical Optics Express 9, 4588–4603 (2018), https://doi.org/10.1364/BOE.9.004588。项目发现应记录为指定条件下模拟结果，并关联实际运行，不能自动升级为普适人体规律。
