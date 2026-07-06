# YOLO/OBB 预测后处理脚本实现计划

## 背景

已完成：

- YOLO/OBB 第二轮首训。
- val/test 预测复查。
- 预测复查归档。
- 错误分层与改进计划。
- 预测后处理与失败样本复查包计划。

下一步需要实现一个后处理脚本，但在实现前必须明确脚本职责、输入输出、校验方式和固定审核入口边界。

## 目标

1. 实现一个只处理 YOLO/OBB 首训预测结果的后处理脚本。
2. 将模型原始预测转换为 `accepted`、`needs_review`、`rejected`。
3. 强制执行“一页只有一个标题栏”的业务规则。
4. 输出机器可读报告和调试 CSV。
5. 为后续失败样本复查包生成提供 manifest。

## 非目标

本轮脚本不做：

- 不重新训练模型。
- 不修改训练数据或标签。
- 不处理完整 PDF。
- 不接入 OCR/VLM。
- 不自动发布固定审核入口。
- 不自动修正预测图片。

## 脚本命名

新增脚本：

```text
scripts/yolo_obb/postprocess_yolo_obb_predictions.py
```

职责：

- 读取 YOLO predict 的标签和图像。
- 读取人工预测复查表。
- 读取数据集标签和必要的样本元数据。
- 计算候选框几何特征和规则状态。
- 输出后处理报告。

不负责：

- 生成 HTML 复查页面。
- 拷贝图片到 `review_inbox/current/`。
- 执行 YOLO 推理。
- 训练模型。

后续可单独新增复查包脚本，例如：

```text
scripts/yolo_obb/build_yolo_postprocess_failure_review_pack.py
```

## 复用现有代码

应复用：

- `scripts/common/obb_utils.py`
  - `load_obb_labels`
  - `normalized_to_pixels`
  - `polygon_area`
- `scripts/yolo_obb/build_yolo_prediction_review_pack.py`
  - 路径组织和 review pack 风格可参考，但不直接混入后处理逻辑。
- `scripts/yolo_obb/build_obb_overlay_review_page.py`
  - HTML/CSV 低噪声风格可参考。

如发现通用函数需要复用，应优先小范围扩展 `obb_utils.py`，不要在多个脚本里复制复杂几何逻辑。

## 默认输入

```text
local_data/yolo_predictions/
local_data/yolo_obb_dataset_round2/
local_data/review_inbox/archive/round2_prediction_review_20260627_reviewed/prediction_review/review_form.csv
```

默认处理 split：

```text
val
test
```

预测标签路径：

```text
local_data/yolo_predictions/round2_val/labels/*.txt
local_data/yolo_predictions/round2_test/labels/*.txt
```

预测图片路径：

```text
local_data/yolo_predictions/round2_val/*.jpg
local_data/yolo_predictions/round2_test/*.jpg
```

数据集标签路径：

```text
local_data/yolo_obb_dataset_round2/labels/val/*.txt
local_data/yolo_obb_dataset_round2/labels/test/*.txt
```

数据集图片路径：

```text
local_data/yolo_obb_dataset_round2/images/val/*.png
local_data/yolo_obb_dataset_round2/images/test/*.png
```

## 默认输出

```text
local_data/yolo_postprocess/round2_first_train/
```

输出文件：

- `postprocess_report.json`
- `postprocess_summary.csv`
- `failure_case_manifest.json`

所有输出均在 ignored 本地目录，不进入 Git。

## 命令草案

```powershell
python scripts/yolo_obb/postprocess_yolo_obb_predictions.py `
  --predictions-dir local_data/yolo_predictions `
  --dataset-dir local_data/yolo_obb_dataset_round2 `
  --review-form local_data/review_inbox/archive/round2_prediction_review_20260627_reviewed/prediction_review/review_form.csv `
  --output-dir local_data/yolo_postprocess/round2_first_train `
  --splits val test
```

## 人工 CSV 编码

需要兼容：

- UTF-8 BOM。
- GBK/ANSI，用户用 Excel 保存时可能出现。

读取策略：

1. 先尝试 `utf-8-sig`。
2. 失败或字段异常时尝试 `gbk`。
3. 输出统一使用 `utf-8-sig`，方便 Excel 打开。

## 候选框解析

YOLO OBB predict 标签通常包含：

```text
class x1 y1 x2 y2 x3 y3 x4 y4 confidence
```

训练标签通常包含：

```text
class x1 y1 x2 y2 x3 y3 x4 y4
```

脚本必须区分：

- 9 字段：无置信度，通常是数据集标签。
- 10 字段：有置信度，通常是预测标签。

若字段数不符合预期，应记录为 `format_error`，不得静默跳过。

## 候选特征

每个预测候选输出：

- `candidate_index`
- `class_id`
- `confidence`
- `points_normalized`
- `area_normalized`
- `bbox_xyxy_normalized`
- `center_xy_normalized`
- `touches_or_near_edge`
- `center_region_penalty`
- `boundary_penalty`
- `size_score`
- `edge_proximity_score`
- `candidate_score`
- `candidate_flags`

第一版可先实现可解释的启发式，不追求复杂模型。

## 后处理规则

### 无候选

输出：

- `status=needs_review`
- `issue_types=["missing_title_block"]`

### 单候选

检查：

- 是否明显在图纸主体中部。
- 是否明显越界。
- 面积是否异常大或异常小。

若通过：

- `status=accepted`

若不通过：

- `status=needs_review`

### 多候选

强制：

- 最终只能选一个 `selected_candidate`。
- 样本整体默认 `status=needs_review`，除非后续人工确认阈值足够稳定。

第一版策略：

1. 计算候选综合分。
2. 选出最高分候选。
3. 记录所有候选和排序。
4. 标记 `issue_types=["multi_candidate"]`。
5. 若非最高候选疑似主体中部零件，追加 `part_false_positive`。

## 初始启发式

以下阈值只作为第一版草案，需在输出报告中记录：

- 中心区域：候选中心同时落在页面宽高的 20% 到 80% 内，触发 `center_region_penalty`。
- 靠边奖励：候选 bbox 任一边距离页面边缘小于 12%，增加边缘分。
- 越界检查：归一化点坐标超出 `[0, 1]` 或像素 bbox 裁剪后仍明显异常，标记 `out_of_page_bounds`。
- 面积异常：面积小于 0.001 或大于 0.20，标记 `size_abnormal`。

阈值必须写入 `postprocess_report.json` 的 `config` 字段。

## 输出 JSON 结构

```json
{
  "config": {},
  "summary": {},
  "records": [
    {
      "split": "val",
      "sample": "sample_009",
      "prediction_count": 2,
      "status": "needs_review",
      "issue_types": ["multi_candidate", "partial_title_block"],
      "selected_candidate_index": 1,
      "candidates": []
    }
  ]
}
```

summary 至少包含：

- `total`
- `accepted`
- `needs_review`
- `rejected`
- `missing_prediction_label`
- `multi_candidate`
- `part_false_positive`
- `boundary_or_size_issue`

## 输出 CSV 字段

```text
split
sample
prediction_count
status
issue_types
selected_candidate_index
selected_confidence
selected_score
manual_acceptance
manual_problem_type
notes
```

CSV 是机器调试简表，不作为用户填写表。

## 失败样本 manifest

`failure_case_manifest.json` 应包含：

- 所有 `needs_review` 和 `rejected` 样本。
- 人工不可接受样本。
- 少量人工可接受对照样本。

每条记录包含：

- split
- sample
- reason
- prediction_image
- dataset_image
- prediction_label
- ground_truth_label
- suggested_review_group

## 验证方式

实现后第一轮只运行 val/test 14 张。

必须检查：

1. 脚本退出码为 0。
2. 输出 JSON/CSV/manifest 存在。
3. `postprocess_report.json` 可被解析。
4. 14 条样本全部出现。
5. `val/sample_009` 和 `test/unclear90_001_from_sample_001` 被标记为 `multi_candidate`。
6. 人工不可接受样本不得全部进入 `accepted`。

## 固定审核入口边界

本脚本不直接发布审核入口。

若后续要发布失败样本复查包，应另起脚本和计划，并遵守：

```text
local_data/review_inbox/current/
```

当前 `current/` 中若存在未归档任务，任何复查包生成脚本都必须失败退出。

## 风险

- 仅靠几何启发式可能误伤真实标题栏。
- YOLO predict 标签字段格式可能随 Ultralytics 参数变化。
- 人工 CSV 编码如果处理不当，会丢失审核结论。
- 后处理规则可能提升安全性，但不能替代补样本和再训练。

## 回滚点

本计划提交后作为实现 `scripts/yolo_obb/postprocess_yolo_obb_predictions.py` 前的回滚点。

