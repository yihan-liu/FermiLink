# MCX 知识导航

执行任务先读对应 [技能](../skills/mcx-optics/SKILL.md)；源码为 [MCX](../mcx_source/)，相关固定版本 Python 接口 [README](../mcx_source/pmcx/README.md)、[detweight](../mcx_source/pmcx/pmcx/utils.py) 和 [replay 示例](../mcx_source/pmcx/examples/demo_mcxlab_replay.py)。源码与安装的 PMCX wheel 版本不同，具体后端以每次 manifest 为准。

## 几何与观测

体素标签映射材料表；分层与圆柱血管由例子生成，构型与材料由外部提供，不由 MCX 根据压力推导。`mua`、`mus` 为 mm⁻¹；约化散射 `mus_prime=mus*(1-g)`，输入 MCX 的是 `mus` 而非约化散射。源和有限圆形探测器以体素坐标表示，乘 `voxel_mm` 得 mm。探测光子权重之和除以发射数为无量纲的收集功率分数；再除探测圆面积得到每平方毫米读数。它与源功率成正比，不使用组织内部 fluence 点值充当探测读数。示例 660、940 nm 光学系数均为显式工程假设，不是从波长自动生成的人体光谱。

光子飞行时间窗以秒表示，通常为纳秒级，和心搏生理时间是不同维度。有限光子数带来 Monte Carlo 采样噪声；增加光子数或重复独立种子可评估误差。必须检查探测缓冲区是否截断以及时间窗是否足以收集关心的光子。

## 吸收重加权与局部灵敏度

固定几何、散射、折射率、光源、探测器、边界、时间窗时，保存的材料分段光程乘体素尺寸得到 mm。每个探测光子 `w=w0*exp(-sum(mua_j*L_j))`；除以发射光子数求和。改变散射或血管几何时不能使用此吸收重加权。`w0` 是初始权重，非吸收后权重。MCX 光子 replay 将基准探测记录及其种子送回 MCX，输出局部空间 Jacobian；默认 Rytov 归一化，体素值为 `-d ln(D)/d mua_voxel`，单位 mm，D 是基准收集功率分数。它是指定基准点的导数，不是组织层在实际 PPG 中的贡献比例；Born 与 Rytov 归一化不同。

方法来源：Yao, Intes & Fang, Biomed Opt Express 9:4588–4603 (2018), DOI [10.1364/BOE.9.004588](https://doi.org/10.1364/BOE.9.004588)；软件事实见上游对应代码与示例。
