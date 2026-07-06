# YOLO/OBB 后处理复查归档与贴边规则落地计划

## 背景

用户已完成 `local_data/review_inbox/current/yolo_postprocess_failure_review/review_form.csv`。

本轮复查包包含 9 条记录：

- 6 条 `needs_review`
- 3 条 `accepted` 正例对照

用户补充关键业务规律：

> 标题栏一定会贴着图纸边缘的框线，标题栏和图纸周围的框线不会存在任何空隙。通过这个规律可以有效区分长得像标题栏的零件和真正的标题栏。

该规律比“靠近页面边缘”更强，应升级为后处理和标注审核中的强规则。

## 目标

1. 归档当前固定审核入口。
2. 重置 `local_data/review_inbox/current/` 为无待审核任务。
3. 记录用户复查结论和归档位置。
4. 将“标题栏必须贴图纸外框线、无空隙”写入长期规则。
5. 为后续后处理脚本升级做准备。

## 非目标

本轮不做：

- 不立即重新训练。
- 不立即修改 YOLO/OBB 数据集标签。
- 不立即调整后处理阈值。
- 不处理完整 PDF。
- 不生成新的人工审核包。

## 当前复查结论

按用户填写结果统计：

- 复查记录：9 条。
- 最终候选可以接受：4 条。
- 最终候选不可接受：5 条。
- 需要补标：1 条，`val/sample_009`。
- 需要修正原标注：0 条。

逐条结论：

| 数据集 | 样本编号 | 最终候选 | 补标 | 修正原标注 | 备注 |
| --- | --- | --- | --- | --- | --- |
| val | `sample_009` | 不可接受 | 是 | 否 | 把左下角的零件误认为标题栏 |
| val | `sample_020` | 不可接受 | 否 | 否 | 预测框越界/范围过大 |
| test | `aug90_002_from_sample_010` | 可以接受 | 否 | 否 | 识别没有任何错误，说明当前误检规则过严 |
| test | `sample_001` | 不可接受 | 否 | 否 | 把图纸下方的零件误认为标题栏 |
| test | `sample_010` | 不可接受 | 否 | 否 | 只存在预测框范围过大问题 |
| test | `unclear90_001_from_sample_001` | 不可接受 | 否 | 否 | 多候选/零件误检 |
| val | `aug90_007_from_sample_020` | 可以接受 | 否 | 否 | 正例对照 |
| val | `aug90_012_from_sample_034` | 可以接受 | 否 | 否 | 正例对照 |
| val | `sample_040` | 可以接受 | 否 | 否 | 正例对照 |

## 归档计划

归档目标：

```text
local_data/review_inbox/archive/yolo_postprocess_failure_review_20260627_reviewed/
```

归档内容：

- 当前 `README.md`
- `yolo_postprocess_failure_review/review_index.html`
- `yolo_postprocess_failure_review/review_form.csv`
- `yolo_postprocess_failure_review/machine_report.json`
- `images/`
- `labels/`

归档后重置：

```text
local_data/review_inbox/current/README.md
```

内容说明当前无待审核任务，并记录本轮归档位置。

## 贴边规则

新增长期规则：

- 真正标题栏必须贴着图纸外框线。
- 标题栏外边界和图纸周围框线之间不应存在空隙。
- 仅靠近边缘但未贴住图框线的候选，应降权或进入 `needs_review`。
- 位于图纸主体内部、与外框线存在明显间隔的表格状零件或局部结构，不应作为标题栏。
- 对扫描裁切或图框线缺失样本，应单独标记为低置信，不应静默通过。

后续后处理脚本升级时，应把当前 `edge_proximity_score` 升级为更强的 `frame_contact_score` 或 `touches_frame_line` 证据。

## 质量门

本轮完成标准：

1. 当前固定入口已归档。
2. `current/` 已重置为无待审核任务。
3. RPD 记录用户复查结果、归档路径和贴边规则。
4. 长期规则文档记录贴边规则。
5. `git status --short` 不包含 `local_data/` 归档材料。

## 回滚点

本计划、RPD 和 TODO 提交后作为归档当前审核入口与更新规则前的回滚点。
