# Ground Truth 与自动评估计划

## 背景

当前 OpenCV 阶段二在全量 63 张样本上，相对三方候选真值错误数为 0。但现有 `manual_results.json` 不是严格意义上的逐张人工精审真值，其中大部分样本来自 OpenCV 与 MCP 一致后的接受结果。

因此下一阶段要先把验证体系固定下来，避免后续算法优化只靠肉眼观察或临时表格。

## 目标

1. 生成规范化 ground truth 文件。
2. 明确每条 ground truth 的来源等级：
   - `manual_review`：人工重点复核。
   - `consensus_accepted`：OpenCV 与 MCP 一致后暂时接受。
3. 实现自动评估脚本，对 OpenCV 输出进行回归评估。
4. 输出准确率、错误样本、低置信样本和置信度摘要。

## 输入

- OpenCV 输出：`outputs/rotation-detection/stage1/results.json`
- 当前候选真值来源：`outputs/rotation-detection/comparison/manual_results.json`

## 输出

本地忽略目录：

- `local_data/ground_truth/rotation_ground_truth.json`
- `local_data/ground_truth/rotation_ground_truth.csv`
- `outputs/rotation-detection/evaluation/evaluation_summary.json`
- `outputs/rotation-detection/evaluation/evaluation_details.csv`
- `outputs/rotation-detection/evaluation/errors.csv`
- `outputs/rotation-detection/evaluation/review_required.csv`

公开仓库只提交脚本、计划、RPD 和 TODO，不提交 ground truth 与评估输出。

## 实现步骤

1. 新增 `scripts/rotation/build_ground_truth.py`。
2. 从现有 `manual_results.json` 生成规范化 ground truth。
3. 新增 `scripts/rotation/evaluate_rotation_results.py`。
4. 评估脚本读取 OpenCV 输出和 ground truth，生成指标与明细。
5. 跑全量 63 张评估，确认当前阶段二结果错误数为 0。

## 验收标准

- ground truth 文件包含 63 条记录。
- 每条记录包含样本编号、标题栏位置、旋转角度、来源等级和备注。
- 评估脚本能自动输出总数、正确数、错误数、准确率、复核数、最低/最高置信度。
- 当前 OpenCV 阶段二结果相对该 ground truth 错误数为 0。
- 本地私有数据和输出不进入 Git。

## 后续人工精审

当前 ground truth 是“候选真值集”，后续可以逐张人工精审并把 `source_level` 从 `consensus_accepted` 提升为 `manual_review`。在未完成逐张精审前，评估结果应表述为“相对候选真值”，不表述为最终工业级准确率。

## 执行结果

已完成：

- `scripts/rotation/build_ground_truth.py`
- `scripts/rotation/evaluate_rotation_results.py`

当前本地评估摘要：

- 总样本数：63。
- 正确数：63。
- 错误数：0。
- 相对候选真值准确率：1.0。
- 需要复核：1，`sample_042`。
- 人工重点复核 ground truth：3。
- OpenCV/MCP 共识接受 ground truth：60。

