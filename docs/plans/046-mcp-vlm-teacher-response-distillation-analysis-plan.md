# MCP/VLM teacher 响应蒸馏分析计划

## 背景

8 条 MCP/VLM teacher 小实验响应已经填写并通过 schema 校验。当前已具备结构化输入，可以进入蒸馏分析阶段。

本阶段的重点不是继续调用 VLM，也不是立即重训，而是把 teacher 响应中的证据拆成可落地的后续方向：

- 规则蒸馏。
- hard-case 数据整理。
- 候选 crop 小分类器样本。
- 后续 provider 自动调用实验依据。

## 目标

1. 读取 `local_data/mcp_vlm_teacher_provider/validated_responses.json`。
2. 汇总 8 条响应的标题栏位置、候选真假、贴边证据、字段簇强度和普通表格误检风险。
3. 生成只读蒸馏分析报告。
4. 将每条响应归类到 rule、data、model、provider 四类后续用途。
5. 生成 CSV 清单，方便后续选择先做规则、数据还是 provider 小实验。
6. 不改 ground truth、不改训练标签、不发布新的人工审核入口。

## 非目标

本阶段不做：

- 不调用云端 VLM。
- 不上传图纸。
- 不接入 API key。
- 不重训 YOLO/OBB。
- 不改标签。
- 不处理完整 PDF。
- 不把 teacher 输出直接当最终真值。

## 输入

```text
local_data/mcp_vlm_teacher_provider/validated_responses.json
```

## 输出

```text
local_data/mcp_vlm_teacher_distillation/
```

包含：

```text
teacher_distillation_report.json
teacher_distillation_summary.csv
teacher_distillation_actions.csv
teacher_rule_candidates.md
```

## 分析维度

- `field_cluster_strength`：字段簇强度。
- `touches_drawing_frame`：是否贴图纸外框。
- `ordinary_table_false_positive_risk`：普通表格误检风险。
- `is_true_title_block`：候选是否真实标题栏。
- `reject_reasons_if_not_title_block`：反例拒绝原因。
- `layout_evidence`：可蒸馏的布局证据。
- `needs_human_review`：是否仍需人工复核。

## 验证

运行：

```text
python -m py_compile scripts/vlm/build_mcp_vlm_teacher_distillation.py
python scripts/vlm/build_mcp_vlm_teacher_distillation.py
```

期望：

- 读取 8 条 validated responses。
- 输出报告覆盖 8 条任务。
- 至少产生规则候选、数据候选和 provider 实验候选。
- 不修改固定审核入口。

## 回滚点

本计划、RPD 和 TODO 提交后作为实现 teacher 响应蒸馏分析脚本前回滚点。

