# MCP/VLM teacher 复盘与蒸馏可行性计划

## 背景

早期三方比对中，图像识别 MCP 在严格“当前屏幕坐标”prompt 下表现很好：

- 63 张原始样本中，MCP 与人工复核样本一致。
- `sample_009` 和 `sample_010` 中，MCP 与人工一致，定位出 OpenCV 高置信误判。
- 60 条 OpenCV/MCP 共识样本后来被逐步升级为人工确认 ground truth。

这说明 MCP/VLM 不应只被视为低优先级兜底。它可能适合作为：

- teacher：提供第二意见和结构化理由。
- 方法参考：帮助提炼全局版面、标题栏位置、图框关系、普通表格误检识别方法。
- 蒸馏源：生成可人工复核的弱标签、规则候选或小模型训练信号。

当前需要先复盘已有 MCP 结果和 prompt 需求，再决定是否直接接云端 VLM、蒸馏成规则、蒸馏成数据或训练轻量候选分类器。

## 目标

1. 复盘已有 MCP 三方比对结果，量化 MCP 作为 teacher 的价值。
2. 提取 MCP 对 OpenCV 高置信错误的纠偏样本。
3. 设计面向当前 YOLO/OBB hard-case 的 teacher prompt。
4. 明确 teacher 输出 JSON 协议。
5. 明确三类蒸馏路径：
   - 蒸馏成规则。
   - 蒸馏成数据。
   - 蒸馏成小模型。
6. 生成只读复盘报告，为下一步是否调用云端 VLM 或 MCP 做决策。

## 非目标

本阶段不做：

- 不调用新的 MCP/VLM。
- 不上传图纸。
- 不重新训练。
- 不修改 YOLO/OBB 标签。
- 不处理完整 PDF。
- 不发布新的固定审核入口。
- 不把 MCP/VLM 输出直接当最终真值。

## 输入

使用已有本地输出和报告：

```text
outputs/rotation-detection/comparison/mcp_results.json
outputs/rotation-detection/comparison/three_way_comparison.csv
outputs/rotation-detection/comparison/disagreements.csv
local_data/yolo_postprocess/routing/routing_report.json
local_data/yolo_postprocess/general_round3_diagnostic/postprocess_report.json
local_data/title_block_ocr_diagnostic/diagnostic_report.json
```

## 输出

输出到 ignored 本地目录：

```text
local_data/mcp_vlm_teacher_review/
```

输出文件：

```text
teacher_review_report.json
teacher_review_summary.csv
teacher_prompt_draft.md
distillation_candidates.csv
```

## teacher prompt 方向

teacher prompt 不应只问“标题栏在哪里”，而应要求输出结构化判断：

```json
{
  "title_block_position": "right|bottom|left|top|unknown",
  "rotation_degrees": 0,
  "is_true_title_block": true,
  "touches_drawing_frame": true,
  "ordinary_table_false_positive_risk": "low|medium|high",
  "evidence": [
    "标题栏贴住图框线",
    "表格内部字段组合符合标题栏",
    "候选区域不是普通明细表"
  ],
  "needs_human_review": false,
  "confidence": 0.0
}
```

对多候选或 crop 任务，teacher prompt 应逐候选判断：

- 该候选是否是真标题栏。
- 是否只是普通表格、明细栏、技术要求表或零件表格。
- 与图纸外框线是否无空隙接触。
- 是否具备标题栏字段组合或版式结构。

## 重点复盘样本

MCP/OpenCV/人工三方比对重点：

- `sample_009`：MCP 与人工一致，OpenCV 错。
- `sample_010`：MCP 与人工一致，OpenCV 错。
- `sample_042`：三方一致，但 OpenCV 低置信。

YOLO/OBB hard-case 重点：

- `sample_001`
- `sample_009`
- `sample_010`
- `unclear90_001_from_sample_001`
- `aug90_002_from_sample_010`

## 蒸馏路径

### 蒸馏成规则

将 teacher 理由转为后处理规则候选，例如：

- 标题栏必须贴图框线。
- 一图只有一个最终标题栏。
- 普通表格误检与方向无关。
- 字段簇组合优于单词命中。

### 蒸馏成数据

让 teacher 批量发现疑难样本或候选 crop，再经人工确认后进入：

- hard-case manifest。
- 保护性正例。
- 负例说明。
- 后续训练/验证分组。

### 蒸馏成小模型

若 teacher 能稳定区分候选 crop 是否为真实标题栏，可以考虑训练轻量候选分类器：

- 输入：YOLO/OBB 候选 crop + 几何/结构特征。
- 输出：`true_title_block` / `non_title_table` / `needs_review`。
- teacher 只提供弱标签，必须抽样人工复核。

## 验证

本阶段只做只读复盘脚本：

```text
python -m py_compile scripts/vlm/build_mcp_vlm_teacher_review.py
python scripts/vlm/build_mcp_vlm_teacher_review.py
```

期望：

- 统计 MCP 与人工一致率。
- 列出 MCP 纠偏 OpenCV 的样本。
- 列出适合 teacher prompt 小实验的 hard-case 样本。
- 生成 teacher prompt 草案。
- 生成蒸馏候选清单。

## 回滚点

本计划、RPD 和 TODO 提交后作为 teacher 复盘脚本实现前回滚点。

