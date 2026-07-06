# YOLO/OBB sample_009 复查归档与难例补强计划

## 背景

用户已完成 `sample_009` 补标复查表。

复查结论：

- 当前标题栏标注可沿用：是。
- 是否需要重新标注标题栏边界：否。
- 是否作为难例补强：是。
- 误检零件是否只记录为负例说明：是。
- 备注：左下角零件误检为标题栏，作为难例补强。

这说明当前 `sample_009` 的 ground truth 标注不需要修改；后续应把它作为 hard-case 进入再训练或数据重采样规划，而不是重新画标题栏边界。

## 目标

1. 归档当前固定审核入口。
2. 重置 `local_data/review_inbox/current/` 为无待审核任务。
3. 记录 `sample_009` 复查结论。
4. 明确不修改当前标题栏标签。
5. 将 `sample_009` 标记为后续 hard-case 补强输入。

## 非目标

本轮不做：

- 不重新训练。
- 不修改 `sample_009` 的 JSON 或 YOLO/OBB 标签。
- 不转换新标签。
- 不生成 overlay 复查包。
- 不处理完整 PDF。
- 不新增负例类别或负框。

## 归档目标

```text
local_data/review_inbox/archive/sample_009_supplement_review_20260627_reviewed/
```

归档内容：

- `README.md`
- `sample_009_supplement_review/review_index.html`
- `sample_009_supplement_review/review_form.csv`
- `sample_009_supplement_review/machine_report.json`
- `sample_009_supplement_review/images/`
- `sample_009_supplement_review/labels/`
- `sample_009_supplement_review/to_label/`

归档后重置：

```text
local_data/review_inbox/current/README.md
```

## 后续决策

本轮归档后，下一步应规划 hard-case 再训练准备：

- 将 `sample_009` 作为多候选/零件误检 hard-case。
- 继续沿用现有 title_block 标签。
- 将左下角误检零件作为负例说明记录到机器报告或 hard-case 清单。
- 不为误检零件新增 YOLO 标签。
- 在再训练前，先规划是否补充更多类似零件误检样本、是否调整采样权重、是否生成 hard-case 清单。

## 质量门

完成标准：

1. 当前固定入口已归档。
2. `current/` 已重置为无待审核任务。
3. RPD 记录用户复查结论和归档位置。
4. TODO 进入 hard-case 再训练准备规划。
5. `git status --short` 不包含 `local_data/` 归档材料。

## 回滚点

本计划、RPD 和 TODO 提交后作为归档当前审核入口前的回滚点。
