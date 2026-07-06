# YOLO/OBB 通用后处理多候选仲裁集成计划

## 背景

round3 多候选后处理仲裁已经通过人工复查样本回归：

- 每条预测记录最终只保留一个 `selected_title_block`。
- 未选候选进入 `rejected_candidates`，并记录拒绝原因。
- `aug90_002_from_sample_010` 的普通表格误检候选已被拒绝。
- 约 3 度 OBB 小角度偏差不作为拒绝真实标题栏的理由。

当前已验证逻辑仍在 `scripts/yolo_obb/postprocess_yolo_obb_round3_multicandidate.py` 中，通用后处理脚本 `scripts/yolo_obb/postprocess_yolo_obb_predictions.py` 仍主要面向 round2 val/test，且多候选会整体进入 `needs_review`。后续若进入更大范围预测或完整 PDF 批处理，需要先把已验证的仲裁契约合并到通用链路。

## 目标

1. 让通用后处理支持任意预测目录与数据集 split，而不是写死 round2 val/test。
2. 在通用报告中输出 `selected_title_block` 与 `rejected_candidates`。
3. 多候选记录默认执行单标题栏仲裁，最终只保留一个候选。
4. 普通表格误检规则保持方向无关，不写死顶部、底部、左侧或右侧。
5. 保持 round2 首训后处理结果不退化。
6. 保持 round3 16 条重点预测回归通过。

## 非目标

本阶段不做：

- 不重新训练 YOLO/OBB。
- 不修改标签或数据集。
- 不引入 OCR/VLM。
- 不处理完整 PDF。
- 不发布新的固定审核入口。
- 不把 `max_det=1`、NMS 或最高置信框当作唯一解决方案。

## 输入

通用脚本默认仍兼容当前 round2 首训输入：

```text
local_data/yolo_predictions/
local_data/yolo_obb_dataset_round2/
local_data/review_inbox/archive/round2_prediction_review_20260627_reviewed/prediction_review/review_form.csv
```

新增可配置输入用于 round3 回归：

```text
local_data/yolo_predictions/round3_train/
local_data/yolo_predictions/round3_val/
local_data/yolo_predictions/round3_round2_test/
local_data/yolo_predictions/round3_round2_val/
local_data/yolo_obb_dataset_round3/
local_data/title_block_ocr_diagnostic/diagnostic_report.json
```

## 输出

默认输出仍位于 ignored 本地目录：

```text
local_data/yolo_postprocess/
```

通用输出至少包含：

```text
postprocess_report.json
postprocess_summary.csv
failure_case_manifest.json
selected_candidates.csv
rejected_candidates.csv
```

说明：

- `postprocess_report.json` 保存完整候选、最终选择、拒绝候选、规则配置和路径。
- `postprocess_summary.csv` 保存样本级低噪声摘要。
- `selected_candidates.csv` 保存每条记录最终选中的标题栏候选。
- `rejected_candidates.csv` 保存所有未选候选及拒绝原因。
- `failure_case_manifest.json` 继续服务后续人工复查包。

## 集成策略

### 1. 输入抽象

新增预测记录模式：

- `prediction_dir_name`：例如 `round2_val`、`round3_val`。
- `split`：数据集 split，例如 `val`、`test`、`train`。
- `sample`：样本编号。
- `prediction_image`、`prediction_label`、`dataset_image`、`ground_truth_label`。

保留旧参数兼容：

- 旧的 `--splits val test` 仍映射到 `round2_val`、`round2_test`。
- 新增显式预测目录参数时，按目录名逐个处理。

### 2. 候选仲裁

从 round3 专用脚本迁移已验证的候选排序思想：

```text
candidate_score =
  confidence
  + frame_contact_score
  + edge_proximity_score
  + size_score
  - center_region_penalty
  - boundary_penalty
  - uniform_grid_penalty
```

第一版若没有 OCR/结构诊断字段，`uniform_grid_penalty` 默认为 0；若提供诊断报告，则合并 `uniform_grid_like` 等结构证据。

### 3. 拒绝原因

未选候选至少记录：

- `not_selected_by_single_title_block_rule`
- `lower_score_duplicate_or_neighbor`
- `non_title_table_false_positive`
- `uniform_grid_like`
- `center_region_without_frame_contact`
- `out_of_page_bounds`
- `size_abnormal`

`non_title_table_false_positive` 必须是方向无关语义。

### 4. 状态判定

- 无候选：`needs_review`。
- 单候选且无硬错误：可 `accepted`。
- 多候选但仲裁通过：可 `accepted`，同时记录 `multi_candidate_resolved`。
- 多候选存在冲突、结构证据缺失或人工历史拒绝：`needs_review`。
- 人工已明确不可接受的 round2 首训样本不得被静默改为 `accepted`。

### 5. 保护性正例

以下情况不得被误伤：

- `test/aug90_002_from_sample_010` 在 round2 首训中曾被过严后处理误拦截，后续贴边规则已修正。
- `round3_val/aug90_007_from_sample_020` 与 `round3_val/sample_040` 的约 3 度 OBB 角度偏差可容忍。

## 质量门

实现后必须运行：

```text
python -m py_compile scripts/yolo_obb/postprocess_yolo_obb_predictions.py
python scripts/yolo_obb/postprocess_yolo_obb_predictions.py
```

并新增 round3 回归运行，期望：

- round2 首训 14 条仍全覆盖。
- round2 中用户人工不可接受样本不得全部自动通过。
- round3 16 条重点预测全覆盖。
- round3 两条 `aug90_002_from_sample_010` 多候选记录仍拒绝普通表格误检候选。
- 每条多候选记录最终只保留一个 selected。
- 小角度偏差正例不因角度被拒绝。

## 回滚点

本计划、RPD 和 TODO 提交后作为修改通用后处理脚本前的回滚点。

