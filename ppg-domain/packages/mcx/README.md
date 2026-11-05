# MCX 光学包

MCX 负责给定体素材料、光源和探测器后的光子传输；几何和材料由外部模型提供，MCX 不从血压推导组织搏动。源代码版本：`49ec9f155107b7b54dece66d24e3c77a208cf2e8`，运行后端为官方 PMCX CUDA 0.8.1，二者分别固定并记录，不假定源码提交和 wheel 二进制完全相同。

```sh
python3 -m venv /path/to/ppg-domain/.runtime/mcx/venv
/path/to/ppg-domain/.runtime/mcx/venv/bin/pip install -e /path/to/ppg-domain/packages/mcx
mcx doctor --json
mcx simulate --config mcx_examples/skin_vessel_660.json --output /path/to/new-run
```

本机完整示例（目标目录必须不存在）：

```sh
cd /data/liuyihan/FermiLink/ppg-domain
.runtime/mcx/venv/bin/python packages/mcx/mcx_examples/run_examples.py /data/liuyihan/FermiLink/ppg-domain/runs/mcx-example
```

脚本分别运行两个波长的真实 MCX、吸收重加权、replay 和独立种子直接状态，结果与配置、日志和 manifest 一起存放。

同一组光子的吸收线性化函数见 `mcx_optics.linear` 与知识索引。

源探测位置和半径单位为体素；`voxel_mm` 为体素边长。材料表每行为 `[mua, mus, g, n]`，前两列单位为 mm⁻¹，行号对应体素标签，0 是背景。两种波长配置是工程假设，散射不同，因此须各自仿真。模拟将保存真实探测光子分段光程、初始权重、replay seeds 和 MCX 日志；`collected_fraction` 是入射单位功率的收集功率分数，除以有限探测圆面积得到每平方毫米读数（输出字段名沿用 `reflectance_per_mm2`）。示例为透射式几何：光源在 10 mm 组织板上表面，半径 2 mm 的探测器在对侧表面中心，对应指夹式 PPG。标准误估算按独立发射光子近似。路径与输出解释见 [知识索引](mcx_knowledge/index.md)。

重加权配置：`{"baseline":"/absolute/run", "cases":[{"name":"case", "mua_per_mm":[...]}]}`；mua 列表从材料标签 1 开始。`mcx reweight --config config.json --output /path/to/new-output`。仅在固定几何、散射、g、n、源探测与边界和时间窗下适用。`mcx sensitivity --config replay.json --output /path/to/new-output` 的配置只需 `{"baseline":"/absolute/run"}`；输出真实 MCX replay Jacobian，不是各层实际 PPG 贡献。每条命令要求新的输出目录，避免覆盖。
