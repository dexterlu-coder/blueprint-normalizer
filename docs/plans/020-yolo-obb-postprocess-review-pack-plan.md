# YOLO/OBB 预测后处理与失败样本复查包计划

## 背景

YOLO/OBB 首训预测复查显示：14 张 val/test 预测图中 9 张可以接受、5 张不可接受。

当前已完成前置计划：

- `docs/plans/019-yolo-obb-prediction-error-improvement-plan.md`

该计划明确下一步优先做后处理安全约束和失败样本复查，而不是直接再训练。

本计划细化两个具体工作：

1. 设计 YOLO/OBB 预测后处理规则。
2. 设计失败样本复查包，让用户确认错误归因和改进方向。

## 目标

1. 定义预测后处理输入、输出和机器报告字段。
2. 明确“一页只有一个标题栏”的仲裁规则。
3. 对多框、零件误检、越界/过大、未完整覆盖进行机器分层。
4. 设计固定审核入口中的失败样本复查包。
5. 保证用户审核表低噪声，只保留当前判断需要的字段。

## 非目标

本阶段不做：

- 不直接实现后处理脚本。
- 不生成新的审核入口。
- 不修改训练数据。
- 不启动再训练。
- 不接入 OCR/VLM。
- 不处理完整 PDF。

## 输入

后续实现时的输入应来自本地 ignored 目录：

```text
local_data/yolo_predictions/
local_data/yolo_obb_dataset_round2/
local_data/review_inbox/archive/round2_prediction_review_20260627_reviewed/
```

需要读取：

- YOLO predict 输出的预测框、置信度和类别。
- val/test 原图副本。
- val/test 标注 overlay 或标签文件。
- 人工填写的 `review_form.csv`。
- 当前 RPD 中记录的错误分层。

## 输出

机器输出应保存到本地 ignored 目录，不进入 Git：

```text
local_data/yolo_postprocess/round2_first_train/
```

建议输出：

- `postprocess_report.json`：机器可读后处理结果。
- `postprocess_summary.csv`：简表，用于调试和后续分析。
- `failure_case_manifest.json`：失败样本复查包清单。
- `review_inbox/current/`：仅在生成复查包时发布人工入口。

## 后处理状态定义

每张图最终只能进入以下状态之一：

| 状态 | 含义 | 是否自动通过 |
| --- | --- | --- |
| `accepted` | 单一标题栏候选，满足置信度、位置和几何约束 | 是 |
| `needs_review` | 多候选、冲突、疑似零件误检、边界异常或规则不一致 | 否 |
| `rejected` | 候选明显不符合标题栏规则，不能作为标题栏证据 | 否 |

模型原始预测框不得直接等同于最终标题栏结果。

## 单标题栏仲裁规则

业务规则：一份图纸只有一个标题栏。

后处理必须执行：

1. 若无预测框：输出 `needs_review`，问题类型 `missing_title_block`。
2. 若只有一个预测框：仍需检查位置、几何和边界。
3. 若有多个预测框：
   - 计算每个候选的综合分。
   - 若最高分候选明显优于其余候选，可输出该候选，但状态仍建议先为 `needs_review`，等待人工确认阈值。
   - 若候选分数接近或位置冲突，输出 `needs_review`。
   - 不允许多个框同时作为最终标题栏。

## 候选评分字段

每个预测候选建议计算：

- `model_confidence`：YOLO 输出置信度。
- `edge_proximity_score`：候选框靠近页面边缘程度。
- `center_penalty`：候选框位于图纸主体中部的惩罚。
- `size_score`：候选框面积、长宽比是否接近标题栏。
- `boundary_penalty`：是否明显超出图纸有效边界。
- `opencv_agreement_score`：是否与 OpenCV 标题栏候选区域一致。
- `rotation_consistency_score`：候选框位置是否能映射到合理旋转方向。
- `final_candidate_score`：综合分，只用于机器仲裁，不暴露给人工表格。

## 错误类型字段

机器报告中必须支持以下错误类型：

- `multi_candidate`：多框候选。
- `part_false_positive`：疑似零件误检为标题栏。
- `boundary_too_large`：框范围过大。
- `out_of_page_bounds`：框明显超出图纸有效边界。
- `partial_title_block`：标题栏未完整覆盖。
- `missing_title_block`：无标题栏候选。
- `low_confidence`：模型置信度低。
- `opencv_conflict`：与 OpenCV 候选区域冲突。
- `unknown`：无法归因，需要人工判断。

## 失败样本复查包

复查包应只针对失败样本和必要对照样本，不把全部训练产物丢给用户。

首轮建议包含：

- 5 个不可接受样本。
- 2 到 3 个可以接受样本作为正例对照。

每个样本应靠近展示：

1. 原始图或预测用图。
2. YOLO 预测 overlay。
3. 标注 overlay。
4. 后处理选中的最终候选框。
5. 若有 OpenCV 候选图，可作为参考放在同一行或相邻区域。

页面布局要求：

- 图片清晰，允许逐张放大。
- 同一样本相关图片必须靠近展示。
- 默认不显示模型分数、长路径、JSON 或调试字段。
- 对多框样本，要能明显看到多个候选框。

## 人工填写表

人工表只保留当前判断需要的字段：

```text
序号
样本编号
问题类型是否正确
最终候选是否可接受
是否需要补标
是否需要修正原标注
备注
```

不得暴露：

- 模型置信度列表。
- 候选框坐标。
- 长 JSON。
- 内部路径。
- 自动评分细节。

机器报告可单独保存完整字段。

## 固定审核入口

若生成复查包，必须发布到：

```text
local_data/review_inbox/current/
```

建议结构：

```text
local_data/review_inbox/current/
  README.md
  yolo_postprocess_failure_review/
    review_index.html
    review_form.csv
    images/
    machine_report.json
```

其中 `machine_report.json` 仅供自动流程使用，不作为用户主要入口。

用户完成审核后，必须归档到：

```text
local_data/review_inbox/archive/
```

并在 RPD 记录归档位置。

## 实现前检查

实现脚本前必须确认：

1. 当前 `local_data/review_inbox/current/` 没有未归档任务。
2. 预测复查归档目录存在。
3. YOLO 预测图和标签文件仍可定位。
4. 失败样本清单与 RPD 中记录一致。
5. 输出目录在 `.gitignore` 覆盖范围内。

## 质量门

后处理脚本可进入实现的最低标准：

1. 输入输出契约明确。
2. 多框不能静默通过。
3. 一页只输出一个最终标题栏候选。
4. 失败原因能机器分层。
5. 人工复查包能让用户快速判断错误归因。

后处理结果可进入下一阶段的最低标准：

1. 5 个失败样本全部有机器归因。
2. 多框样本进入 `needs_review` 或被明确仲裁。
3. 零件误检不会自动通过。
4. 越界/过大框被单独标记。
5. 用户复查包完成并归档。

## 风险

- 过强的几何约束可能误伤真实标题栏，尤其是旋转、裁切或扫描偏移样本。
- 只用模型置信度仲裁会放大零件误检风险。
- 后处理可以降低误通过，但不能替代训练数据质量。
- 人工复查包如果信息过多，会降低审核效率。

## 回滚点

本计划提交后作为实现预测后处理脚本和失败样本复查包前的回滚点。
