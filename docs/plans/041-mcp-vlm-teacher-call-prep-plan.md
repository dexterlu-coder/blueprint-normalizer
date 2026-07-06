# MCP/VLM teacher 小规模调用实验准备计划

## 背景

MCP/VLM teacher 复盘结果显示：

- MCP 与人工在 63 张三方比对中一致率为 1.0。
- MCP 纠偏 OpenCV 高置信误判 2 条：`sample_009`、`sample_010`。
- 已生成 21 条蒸馏候选，覆盖 MCP 纠偏、低置信校准、hard-case 解释和普通表格误检。

下一步不应马上全量接入 VLM，也不应直接重训。应先准备一个小规模 teacher 调用实验包，用统一 prompt、统一输入、统一输出 schema 验证 teacher 是否能解释当前 hard-case，并能否产生可蒸馏信息。

## 目标

1. 从已有蒸馏候选中选出最小 teacher 调用任务集。
2. 为每条任务准备原图、overlay、候选 crop 和结构化问题。
3. 固化 teacher JSON 输出协议。
4. 生成本地实验准备包，后续可用于人工调用 MCP/VLM 或接入 provider。
5. 不在本阶段实际调用外部模型。

## 非目标

本阶段不做：

- 不调用 MCP/VLM。
- 不上传图纸。
- 不重新训练。
- 不修改标签。
- 不改后处理规则。
- 不处理完整 PDF。
- 不发布固定审核入口。

## 输入

```text
local_data/mcp_vlm_teacher_review/distillation_candidates.csv
local_data/mcp_vlm_teacher_review/teacher_prompt_draft.md
local_data/mcp_vlm_teacher_review/teacher_review_report.json
local_data/title_block_ocr_diagnostic/diagnostic_report.json
local_data/yolo_postprocess/general_round3_diagnostic/postprocess_report.json
outputs/rotation-detection/comparison/three_way_comparison.csv
outputs/rotation-detection/comparison/disagreements.csv
```

## 输出

输出到 ignored 本地目录：

```text
local_data/mcp_vlm_teacher_call_prep/
```

输出文件：

```text
teacher_call_manifest.csv
teacher_call_manifest.json
teacher_prompt.md
teacher_response_schema.json
assets/
```

其中 `assets/` 可包含：

- source 原图副本。
- prediction overlay 副本。
- candidate crop 副本。

## 最小任务集

第一轮只选 6 到 8 类任务，不追求数量：

1. `sample_009`：MCP 纠偏 OpenCV，高置信误判。
2. `sample_010`：MCP 纠偏 OpenCV，高置信误判。
3. `sample_042`：低置信但三方一致，用于置信校准。
4. `aug90_002_from_sample_010` selected candidate：真实标题栏保护性正例。
5. `aug90_002_from_sample_010` rejected candidate：普通表格误检反例。
6. `sample_001`：历史零件/表格误检 hard-case。
7. `unclear90_001_from_sample_001`：不清晰增强 hard-case。
8. `sample_040` 或 `aug90_007_from_sample_020`：约 3 度角度偏差可容忍正例。

## teacher 输出协议

必须输出 JSON，字段包括：

```json
{
  "task_id": "",
  "selected_candidate_index": 0,
  "title_block_position": "bottom|left|top|right|unknown",
  "rotation_degrees": 0,
  "candidate_judgments": [
    {
      "candidate_index": 0,
      "is_true_title_block": true,
      "touches_drawing_frame": true,
      "ordinary_table_false_positive_risk": "low|medium|high",
      "field_cluster_strength": "none|weak|medium|strong",
      "layout_evidence": [],
      "reject_reasons_if_not_title_block": []
    }
  ],
  "needs_human_review": false,
  "confidence": 0.0
}
```

## 验证

运行：

```text
python -m py_compile scripts/vlm/build_mcp_vlm_teacher_call_prep.py
python scripts/vlm/build_mcp_vlm_teacher_call_prep.py
```

期望：

- 生成 6 到 8 条 teacher 调用任务。
- 每条任务有清晰 `task_type` 和 `question`。
- 能找到的 source/overlay/crop 均复制到 `assets/`。
- manifest 中记录缺失资产，但不因非关键资产缺失失败。
- 不写入固定审核入口。

## 回滚点

本计划、RPD 和 TODO 提交后作为 teacher 调用准备包脚本实现前回滚点。

