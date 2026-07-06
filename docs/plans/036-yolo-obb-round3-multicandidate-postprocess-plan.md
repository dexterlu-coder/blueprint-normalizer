# YOLO/OBB round3 多候选后处理仲裁升级计划

## 背景

round3 训练和预测复查已经完成。最新人工诊断复查结论显示：

- `round3_val / aug90_002_from_sample_010` 的额外候选是图纸中另外表格的一部分，不是标题栏。
- `round3_round2_test / aug90_002_from_sample_010` 的额外候选同样不是标题栏。
- `round3_train / sample_001`、`round3_train / sample_009`、`round3_train / unclear90_001_from_sample_001` 没有问题。
- `round3_val / aug90_007_from_sample_020`、`round3_val / sample_040` 的识别框整体约逆时针 3 度，但大致可接受。

现有计划已经有“一页最终只允许一个标题栏候选”和“多候选需要仲裁”的骨架，但还缺少针对普通表格在任意方向被误检为标题栏的专门质量门。`aug90_002_from_sample_010` 是当前代表样本，不是方向特例。

## 调研与复核结论

外部通用预测过滤方法，如 YOLO predict 的 `conf`、`iou`、`max_det` 或 OpenCV/PyTorch NMS，只能解决置信度过滤和重叠框压制。它们不能判断任意方向上的普通表格是否属于标题栏主体。

因此，本项目不能只靠：

- 提高 `conf`
- 调整 `iou`
- 设置 `max_det=1`
- 只保留最高置信框

来解决当前问题。必须引入业务后处理仲裁，并保留人工复核门。

## 目标

1. 升级 round3 预测后处理，明确每页最终只有一个 `selected_title_block`。
2. 对所有未选候选输出 `rejected_candidates`，并记录拒绝原因。
3. 将 `aug90_002_from_sample_010` 的额外候选作为必须拒绝的非标题栏表格误检回归样本，并明确类似误检可能出现在任意方向。
4. 保持 `sample_001`、`sample_009`、`unclear90_001_from_sample_001` 可接受结果不被误伤。
5. 保持约 3 度 OBB 角度偏差的保护性正例可接受。

## 非目标

本阶段不做：

- 不重新训练模型。
- 不修改 YOLO 标签。
- 不处理完整 PDF。
- 不接入 OCR/VLM。
- 不发布新的固定审核入口。
- 不把 NMS 或 `max_det=1` 当作唯一解决方案。

## 输入

优先使用已有本地预测：

```text
local_data/yolo_predictions/round3_train/
local_data/yolo_predictions/round3_val/
local_data/yolo_predictions/round3_round2_test/
local_data/yolo_predictions/round3_round2_val/
local_data/yolo_obb_dataset_round3/round3_manifest.csv
local_data/title_block_ocr_diagnostic/diagnostic_report.json
```

## 输出

计划输出到 ignored 本地目录：

```text
local_data/yolo_postprocess/round3_multicandidate/
```

输出文件：

```text
postprocess_report.json
postprocess_summary.csv
selected_candidates.csv
rejected_candidates.csv
review_summary.html
overlays/
```

说明：

- `postprocess_report.json` 保存完整候选、分数、拒绝原因和配置。
- `selected_candidates.csv` 保存每个预测记录最终选中的标题栏候选。
- `rejected_candidates.csv` 保存所有未选候选及拒绝原因。
- `review_summary.html` 用于人工快速复核，不要求用户填写。

## 仲裁对象模型

每条预测记录拆成：

- `PredictionRecord`：一个 `(prediction_dir, sample)`。
- `Candidate`：模型输出的单个 OBB 候选。
- `SelectedTitleBlock`：最终保留的标题栏候选。
- `RejectedCandidate`：未选候选及拒绝原因。
- `RegressionExpectation`：人工已确认的样本级期望。

## 仲裁规则

### 1. 单候选

若只有一个候选：

- 默认可作为 `selected_title_block`。
- 仍检查是否明显越界、面积异常、远离图框线。
- 小角度 OBB 偏差不作为失败，只记录定位备注。

### 2. 多候选

若有多个候选：

1. 每页只保留一个 `selected_title_block`。
2. 候选按综合分排序：
   - 模型置信度。
   - 图框贴边分。
   - 面积/长宽比合理性。
   - 标题栏位置先验。
   - 表格结构证据。
3. 未选候选全部写入 `rejected_candidates`。
4. 若未选候选符合以下任一条件，追加拒绝原因：
   - `non_title_table_false_positive`
   - `uniform_grid_like`
   - `lower_confidence_duplicate_or_neighbor`
   - `not_selected_by_single_title_block_rule`

### 3. 特定回归期望

必须显式验证：

| 预测记录 | 期望 |
| --- | --- |
| `round3_val / aug90_002_from_sample_010` | 选中真实标题栏候选，普通表格误检候选进入 rejected |
| `round3_round2_test / aug90_002_from_sample_010` | 选中真实标题栏候选，普通表格误检候选进入 rejected |
| `round3_train / sample_001` | accepted |
| `round3_train / sample_009` | accepted |
| `round3_train / unclear90_001_from_sample_001` | accepted |
| `round3_val / aug90_007_from_sample_020` | accepted，小角度偏差可容忍 |
| `round3_val / sample_040` | accepted，小角度偏差可容忍 |

## 评分草案

第一版采用可解释启发式：

```text
candidate_score =
  confidence
  + frame_contact_score * 0.25
  + edge_proximity_score * 0.15
  + size_score * 0.20
  + structure_score * 0.10
  - uniform_grid_penalty * 0.35
  - center_region_penalty * 0.40
  - out_of_bounds_penalty * 0.50
```

注意：

- 评分只用于排序，不直接宣称候选正确。
- 多候选即使选出最终候选，也要保留 rejected 记录。
- 任何规则冲突仍可输出 `needs_review`。

## 实现方式

新增脚本：

```text
scripts/yolo_obb/postprocess_yolo_obb_round3_multicandidate.py
```

脚本职责：

1. 读取 round3 四组预测。
2. 读取 round3 manifest。
3. 读取诊断报告中的结构证据。
4. 对每个 `(prediction_dir, sample)` 执行仲裁。
5. 生成 JSON/CSV/HTML/overlay 输出。
6. 输出回归检查摘要。

## 质量门

1. 覆盖 16 条 round3 重点预测记录。
2. `aug90_002_from_sample_010` 两条多候选记录中，普通表格误检候选必须进入 rejected；后续扩展样本时同类误检不得受方向限制。
3. 每条多候选记录最终只保留 1 个 selected。
4. 保护性正例 `aug90_007_from_sample_020`、`sample_040` 不应因约 3 度角度偏差被拒绝。
5. 历史误检修复样本 `sample_001`、`sample_009`、`unclear90_001_from_sample_001` 保持 accepted。
6. 输出不进入 Git。
7. 脚本实现后必须运行 `py_compile` 和本地回归。

## 后续决策

若质量门通过：

- 后续可把仲裁逻辑合并回通用 YOLO/OBB 后处理链路。
- 暂不重训。

若质量门不通过：

- 不直接调阈值掩盖问题。
- 先生成小范围人工复查包，确认失败原因。
- 再决定是否补 hard-case 或引入 OCR/VLM 字段簇证据。

## 回滚点

本计划、RPD 和 TODO 提交后作为实现 round3 多候选仲裁脚本前回滚点。

