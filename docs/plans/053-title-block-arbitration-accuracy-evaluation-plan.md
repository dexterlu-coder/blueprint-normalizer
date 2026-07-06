# 标题栏仲裁准确率评估固化计划

## 背景

`scripts/ocr/build_title_block_arbitration_records.py` 已经能把 YOLO/OBB 后处理、OpenCV 方向结果和 RapidOCR 字段簇诊断汇总为 `ArbitrationRecord`。临时命令曾验证当前 30 条仲裁记录与已有 ground truth 一致，但该验证尚未固化为可重复脚本和报告。

在进入 PDF 旋正、标题栏 OCR 图号抽取和文件命名 dry-run 之前，需要先把“标题栏位置判断是否足以进入下一步”的证据固化下来，避免只凭口头结论推进。

## 本轮目标

1. 新增一个只读评估脚本，对 `arbitration_records.jsonl` 与已有 ground truth 做可重复对比。
2. 同时评估标题栏粗位置和派生旋转角度。
3. 分别统计记录级、去重样本级、自动接受记录和人工分流记录。
4. 输出 JSON/CSV 报告，便于后续追溯。
5. 明确结论边界：可进入下一阶段 dry-run，不等于可直接正式批量改 PDF 或重命名。

## 非目标

本轮不做：

- 不处理完整 PDF。
- 不旋正 PDF。
- 不重命名 PDF。
- 不调用 VLM。
- 不修改 ground truth。
- 不生成新的人工审核入口。
- 不优化或重训标题栏检测模型。

## 输入

评估脚本默认读取：

```text
local_data/title_block_arbitration/arbitration_records.jsonl
local_data/ground_truth/rotation_ground_truth.json
local_data/ground_truth/rotation_ground_truth_augmented_90.json
local_data/ground_truth/rotation_ground_truth_augmented_90_unclear.json
```

其中：

- `rotation_ground_truth.json` 是原始人工确认集。
- `rotation_ground_truth_augmented_90.json` 是由人工确认样本派生的 90 度增强集。
- `rotation_ground_truth_augmented_90_unclear.json` 是由人工确认样本派生的低清晰度增强集。

## 输出

建议输出到本地忽略目录：

```text
local_data/title_block_arbitration/evaluation/
```

输出文件：

- `accuracy_summary.json`
- `accuracy_details.csv`
- `accuracy_errors.csv`
- `accuracy_missing_truth.csv`

## 评估口径

记录级：

- `record_count`
- `records_with_truth`
- `position_correct_records`
- `rotation_correct_records`
- `position_accuracy`
- `rotation_accuracy`

去重样本级：

- `unique_sample_count`
- `unique_samples_with_truth`
- `unique_position_error_count`
- `unique_rotation_error_count`

分流状态：

- `decision_status_counts`
- `auto_accept_position_accuracy`
- `auto_accept_rotation_accuracy`
- `needs_human_review_position_accuracy`
- `needs_human_review_rotation_accuracy`

真值来源：

- `manual_review_full`
- `synthetic_augmented_90`
- `synthetic_augmented_90_unclear`

## 通过标准

进入下一阶段 dry-run 的最低标准：

1. 所有当前仲裁记录都能找到 ground truth，或缺失项明确列入 `accuracy_missing_truth.csv`。
2. 标题栏位置与 ground truth 不存在已知错误。
3. 派生旋转角度与 ground truth 不存在已知错误。
4. 自动接受记录没有发现位置或旋转错误。
5. 输出报告明确写明评估范围和限制。

如果出现错误：

- 不进入 PDF dry-run。
- 先回到标题栏位置仲裁规则或输入证据修正。
- 错误样本应进入后续人工复核或 hard-case 归档。

## 结论边界

即使当前评估通过，也只能说明：

- 在已有人工确认样本、增强样本和当前仲裁回放记录范围内，没有发现标题栏位置和旋转角度错误。
- 当前证据足以进入下一阶段 dry-run，暴露 PDF 旋正、标题栏 crop、OCR 图号抽取和命名风险。

不能说明：

- 新图纸包或未知版式的工业级泛化准确率为 100%。
- 可以直接无人值守覆盖原 PDF。
- 可以直接按 OCR 图号正式重命名文件。

## 下一步

1. 提交本计划、RPD 和 TODO 回滚点。
2. 实现 `scripts/ocr/evaluate_title_block_arbitration_records.py`。
3. 运行评估并记录结果。
4. 通过后再规划 PDF 旋正与图号抽取 dry-run。

