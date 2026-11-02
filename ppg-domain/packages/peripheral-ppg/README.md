# peripheral-ppg

该包用于在明确假设下连接全身循环、局部 2R1C 与组织光学。状态及可用命令以运行环境和本目录实现为准；参数示例为工程假设，不代表人体测量值。模型、空间范围和证据规范见 [知识索引](ppg_knowledge/index.md)。

配置生成：`python packages/peripheral-ppg/ppg_examples/make_example.py`（从 ppg-domain 根目录）。随后运行 `peripheral-ppg simulate --config packages/peripheral-ppg/ppg_examples/engineering_example.json --output runs/example-unique`，最后 `peripheral-ppg validate-run runs/example-unique`。输出目录必须不存在。配置中的求解器可执行文件路径相对于配置文件；绝对路径亦可。`state_file` 同样相对配置路径解析。示例为工程参数，不是测量值，且固定血管结构没有随相同血液量变化而改变。

配置包括 Pulse 配置、局部 2R1C 所有初始/参考量、混合区体积、分析过渡时长和至少两个波长的 MCX 配置。每个波长独立运行基准 MCX；通过保留的探测光程仅改变混合区域的吸收系数，然后对相对于基准变化最大的时点运行独立随机种子的直接 MCX；比较与组合标准误写入 `comparison.json`。`validate-run` 检查主要文件及直接比较，差异超过四个组合标准误时报告未通过，应结合光子数和采样误差排查。此阈值是工程检查，不是生理验证。

输出 `coupled.csv` 保留原始时间、输入压力、局部 P/Q/V、血液分数、混合吸收和每波长光子检测功率分数及采样误差。初始过渡之后的 AC（峰峰值）、DC（算术均值）和 AC/DC 位于 `analysis.json`；未施加电子滤波或符号反转。所有 Pulse、MCX 子运行及日志保留在运行目录，真实求解器执行产生的是模拟数据。

`peripheral_ppg.analysis` 提供原始共同时间轴对齐、同起点差值和中心有限差分；差分的参数与步长、输出物理量和工作点由调用者指定。`peripheral_ppg.records.save_record(path, record)` 将问题、假设、参数与来源、运行 ID、证据路径、条件结论、歧义、下一问题写为 JSON，并在同目录维护 `index.jsonl`；检查每个证据路径存在且包含运行 ID 对应的已完成 manifest。证据相对路径以记录文件目录为基准，不覆盖已有记录。

记录示例：`python packages/peripheral-ppg/ppg_examples/record_example.py runs/example-unique workspaces/records/example.json`。该脚本只针对已完成的耦合运行，检查 manifest 声明的输出存在及所列哈希；文字仍保留为条件性模拟结论。
