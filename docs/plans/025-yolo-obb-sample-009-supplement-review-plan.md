# YOLO/OBB sample_009 补标与复查计划

## 背景

YOLO/OBB 后处理失败样本复查已经完成。用户在复查表中明确：

- `val/sample_009` 最终候选不可接受。
- `val/sample_009` 需要补标。
- `val/sample_009` 不需要修正原标注。
- 备注：把左下角的零件误认为标题栏。

同时，后处理贴图框线规则已完成第一版升级，`sample_009` 仍保持 `needs_review`，原因包括：

- 多候选框。
- 疑似零件误检。
- 人工判定不可接受。
- 标题栏未完整覆盖。

因此下一步需要做一个极小范围的补标/复查入口，只围绕 `sample_009`，确认应采取哪种数据动作，而不是直接重训。

## 目标

1. 为 `sample_009` 生成固定审核入口。
2. 让用户只判断当前必须确认的信息：
   - 当前正确标题栏标注是否仍可沿用。
   - 是否需要重新打开标注工具微调标题栏边界。
   - 是否将该样本作为多候选/零件误检难例补强。
   - 左下角误检零件是否只记录为负例说明。
3. 保留预测图、原图、当前标注 overlay 和机器报告，便于后续归档。
4. 不重新训练，不修改现有数据集，不处理完整 PDF。

## 非目标

本轮不做：

- 不立即训练新模型。
- 不批量补标其他样本。
- 不修改 `local_data/yolo_obb_dataset_round2/`。
- 不新增 YOLO 类别。
- 不尝试给零件误检区域画 `negative` 框。

说明：当前 YOLO/OBB 数据集只有 `title_block` 一个类别；零件误检区域不能直接通过新增负框表达。该信息应进入难例说明、后处理规则或未来负样本设计，而不是混入标题栏标签。

## 输入材料

优先使用已有本地材料：

```text
local_data/yolo_obb_dataset_round2/images/val/sample_009.png
local_data/yolo_obb_dataset_round2/labels/val/sample_009.txt
local_data/yolo_predictions/round2_val/sample_009.jpg
local_data/yolo_predictions/round2_val/labels/sample_009.txt
local_data/review_inbox/archive/round2_overlay_review_20260626_approved/overlays/sample_009_overlay.png
local_data/review_inbox/archive/round2_overlay_review_20260626_approved/to_label/sample_009.png
local_data/review_inbox/archive/round2_overlay_review_20260626_approved/to_label/sample_009.json
local_data/yolo_postprocess/round2_first_train/postprocess_report.json
```

## 固定审核入口

发布到：

```text
local_data/review_inbox/current/
```

建议结构：

```text
local_data/review_inbox/current/
  README.md
  sample_009_supplement_review/
    review_index.html
    review_form.csv
    machine_report.json
    images/
    labels/
    to_label/
```

其中 `to_label/sample_009.png` 和 `to_label/sample_009.json` 只作为用户需要重新标注时的就近材料副本；若用户确认无需重画，则不需要打开标注工具。

## 人工表字段

CSV 只保留：

```text
序号
样本编号
当前标题栏标注是否可沿用
是否需要重新标注标题栏边界
是否作为难例补强
误检零件是否只记录为负例说明
备注
```

建议用户填写值：

- `是` / `否`
- 备注简短说明即可。

## 复查页面

HTML 应将以下图片靠近展示：

1. 预测结果图：显示模型多候选/误检情况。
2. 当前人工标注 overlay：显示当前真实标题栏标签。
3. 数据集原图：必要时查看标题栏与图框线关系。

页面不展示长 JSON、坐标列表、模型评分等内部字段。

## 质量门

本轮完成标准：

1. 固定入口只包含 `sample_009` 当前任务。
2. `review_form.csv` 只有 1 条记录。
3. 复查页面图片均为 `current/` 内副本。
4. 当前 `local_data/review_inbox/current/` 在发布前为空任务。
5. `git status --short` 不包含 `local_data/` 审核包文件。

## 后续决策

用户填写后再决定：

- 若当前标注可沿用且无需重画：记录为难例补强，后续规划小规模再训练或 hard-case 数据重采样。
- 若需要重新标注标题栏边界：归档后再转换 JSON、校验 overlay，再决定是否更新数据集。
- 若只记录负例说明：将左下角误检零件写入错误分层，不把它作为 YOLO 标签。

## 回滚点

本计划、RPD 和 TODO 提交后作为发布 `sample_009` 补标复查入口前的回滚点。
