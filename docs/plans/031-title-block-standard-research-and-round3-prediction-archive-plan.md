# 标题栏规范调研与 round3 预测复查归档计划

## 背景

用户已完成 `local_data/review_inbox/current/round3_prediction_review/review_form.csv` 审核。

用户补充关键判断方向：

- 标题栏不是任意表格。
- 标题栏内部常有大小不一、行列不规则的格子。
- 标题栏内部文字具有组合规则。
- 容易混淆标题栏和其他表格时，应利用标题栏规范字段组合辅助判断。
- 需要先调研机械制图标题栏格式规范，再将规则沉淀到项目。

## 目标

1. 归档 round3 预测复查入口并重置 `current/`。
2. 读取并记录用户 round3 预测复查结论。
3. 调研机械制图标题栏规范，重点关注：
   - 标题栏常见字段。
   - 字段组合规则。
   - 标题栏与明细栏、技术要求表、零件局部表格的区别。
   - 标题栏内部表格结构特征。
4. 将调研结论沉淀为：
   - 样本/来源索引。
   - 横向调研笔记。
   - 长期规则更新。
5. 为后续 OCR/后处理/VLM 兜底提供可解释特征。

## 非目标

本阶段不做：

- 不重新训练模型。
- 不修改 YOLO 标签。
- 不处理完整 PDF。
- 不实现 OCR/VLM 代码。
- 不把标题栏字段规则当成单一充分条件。

## 归档位置

计划归档到：

```text
local_data/review_inbox/archive/round3_prediction_review_20260628_reviewed/
```

归档后：

```text
local_data/review_inbox/current/README.md
```

应显示当前无待审核任务。

## 调研输出

计划新增：

```text
references/title-block-standard-research/README.md
docs/research/2026-06-28-title-block-standard-research.md
```

并更新：

```text
rules/mechanical-drawing-rotation.md
reports/rpd-rotation-detection.md
TODO.md
```

## 调研原则

- 优先使用规范、标准介绍、工程制图教材/课程资料、CAD 标题栏模板说明等来源。
- 区分强规则和弱证据：
  - 强规则：标题栏贴图框线、位于规范位置。
  - 中强证据：规范字段组合同时出现。
  - 弱证据：单个词出现、单个表格形态相似。
- 明确反例：
  - 明细栏、技术要求表、零件表格可能包含少量相似词。
  - 单独出现“材料”或“日期”不能判定为标题栏。
  - 只有表格密集但不贴图框线，也不能判定为标题栏。

## 质量门

1. round3 预测复查入口已归档。
2. `current/` 已重置。
3. 调研来源已形成索引。
4. 调研笔记包含对象模型、字段组合、结构规则、反例和迁移建议。
5. 长期规则已补充“字段组合不是充分条件”的约束。
6. `local_data/` 不进入 Git。

## 回滚点

本计划、RPD 和 TODO 提交后作为归档与调研落地前回滚点。
