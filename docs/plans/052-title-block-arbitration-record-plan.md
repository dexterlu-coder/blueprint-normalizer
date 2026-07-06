# 标题栏位置仲裁记录规划

## 背景

当前设计已经从“无条件全量三方平权投票”升级为“标题栏位置多证据仲裁”。用户最终目标不是让人参与常规判断，而是让自动流程完成：

1. 图纸包 PDF 拆分为一页一个 PDF。
2. 判断每页标题栏位置。
3. 根据标题栏位置推导旋转角度并旋正图纸。
4. 保存标题栏区域和 OCR 结果。
5. 从标题栏中抽取图纸图号。
6. 用图号重命名单页 PDF。
7. 仅在证据不足、冲突或命名风险高时进入人工异常队列。

要进入 PDF 旋正和图号重命名前，需要先建立每页的统一证据记录。否则后续即使自动流程给出结果，也难以追溯“为什么这么旋转、为什么用这个图号命名”。

## 本轮目标

本轮规划 `ArbitrationRecord`，作为后续标题栏位置仲裁、旋正、OCR 图号抽取和文件命名 dry-run 的结构化证据骨架。

目标包括：

1. 定义每页必须保存的证据字段。
2. 明确自动接受、VLM 兜底、人工复核的分流状态。
3. 明确只读汇总阶段使用哪些已有产物。
4. 明确后续实现脚本的输入、输出和验证方式。
5. 保证下一阶段先 dry-run，不直接改原始 PDF、不直接重命名文件。

## 非目标

本轮不做：

- 不处理完整 PDF。
- 不旋正 PDF。
- 不重命名 PDF。
- 不调用云端 VLM。
- 不训练或重训 YOLO/OBB。
- 不改 ground truth。
- 不生成新的人工审核入口。
- 不把 OCR 结果直接写成最终图号。

## 输入来源

第一阶段只做只读汇总，优先复用已有本地产物：

- YOLO/OBB 后处理结果。
- OpenCV 方向检测或评估结果。
- RapidOCR 标题栏字段簇诊断报告。
- 既有 ground truth / 人工确认记录。
- 既有 hard-case、round2、round3 重点样本清单。

如果某一页缺少某类证据，记录中应明确写入 `missing`，不得静默假设。

## ArbitrationRecord 草案

每页记录建议包含以下顶层对象：

```json
{
  "record_version": "0.1",
  "sample_id": "sample_001",
  "page": {},
  "title_block_candidates": [],
  "evidence": {},
  "arbitration": {},
  "rotation": {},
  "ocr": {},
  "drawing_number": {},
  "output_plan": {},
  "review_routing": {},
  "artifacts": {}
}
```

### page

保存页面来源：

- `source_pdf_path`
- `page_index`
- `single_page_pdf_path`
- `rendered_image_path`
- `dataset_name`

第一阶段允许这些路径为空或缺失，但必须显式记录状态。

### title_block_candidates

保存标题栏候选：

- `candidate_id`
- `source`：`yolo_obb`、`opencv`、`manual`、`vlm`
- `bbox` 或 `obb_points`
- `position`：`top`、`right`、`bottom`、`left`
- `precise_position`
- `confidence`
- `accepted_by_source`
- `reject_reason`

一页可以有多个候选，但最终仲裁只能有一个 `selected_candidate_id`，或进入复核。

### evidence

保存多源证据：

- `yolo_obb`
  - 原始模型分数。
  - 后处理分数。
  - teacher rule flags。
  - 多候选仲裁结果。
- `opencv`
  - 图框贴边证据。
  - 表格线结构证据。
  - 边侧密度证据。
  - 候选竞争情况。
- `ocr`
  - OCR 引擎。
  - OCR 状态。
  - OCR 方向。
  - 字段簇命中。
  - OCR 原文摘要。
- `vlm`
  - 仅在触发时保存请求、响应和结构化判断路径。
- `manual`
  - 仅在人工复核后保存人工结论来源。

### arbitration

保存仲裁结论：

- `selected_candidate_id`
- `title_block_position`
- `decision_status`
  - `auto_accept`
  - `needs_vlm`
  - `needs_human_review`
  - `rejected`
- `confidence_level`
  - `high`
  - `medium`
  - `low`
- `decision_reasons`
- `conflicts`
- `missing_evidence`

### rotation

保存旋转相关信息：

- `detected_rotation_degrees`
- `correction_degrees`
- `rotation_rule_version`
- `rotation_ready`

映射规则继续使用 `rules/mechanical-drawing-rotation.md`。

### ocr

保存标题栏 OCR 结果：

- `title_block_crop_path`
- `normalized_crop_path`
- `ocr_text`
- `ocr_tokens`
- `field_cluster_hits`
- `ocr_confidence`
- `ocr_ready_for_number_extraction`

第一阶段只保存已有诊断报告中的 OCR 结果，不重新跑 OCR。

### drawing_number

保存图号候选：

- `candidates`
- `selected_drawing_number`
- `selection_status`
  - `not_attempted`
  - `single_candidate`
  - `ambiguous`
  - `missing`
- `filename_safe_value`
- `naming_risks`

第一阶段不正式抽取图号，只预留字段；后续图号抽取必须单独规划。

### output_plan

保存后续 PDF 输出计划：

- `corrected_pdf_path`
- `renamed_pdf_path`
- `dry_run_only`
- `would_overwrite`
- `duplicate_name_group`

在 dry-run 通过前，`dry_run_only` 必须为 `true`。

### review_routing

保存是否进入异常队列：

- `route`
  - `auto`
  - `vlm`
  - `human`
- `route_reason`
- `review_priority`
- `human_visible_fields`

若进入人工复核，人工表只显示用户完成判断必须看到的信息；机器证据继续保存在 JSON 或报告中。

### artifacts

保存调试和追溯文件：

- `overlay_image_path`
- `candidate_crop_paths`
- `ocr_report_path`
- `source_report_paths`
- `arbitration_record_path`

## 自动接受条件

第一版自动接受只作为建议，不直接执行 PDF 改写：

1. 存在唯一选中标题栏候选。
2. 候选贴图纸外框线，或有可信的裁切/缺线解释。
3. YOLO/OBB 与 OpenCV 的位置判断一致，或冲突被规则解释。
4. OCR 字段簇为 strong，或 OCR 缺失但结构证据足够强。
5. 标题栏位置能唯一映射旋转角度。
6. 不存在图号命名风险。

只要涉及图号缺失、多个图号候选、重名、非法字符或低置信 OCR，后续文件命名必须进入异常分流。

## 输出

计划后续实现脚本输出到本地忽略目录，例如：

```text
local_data/title_block_arbitration/
```

建议文件：

- `arbitration_records.jsonl`
- `arbitration_summary.json`
- `arbitration_summary.csv`
- `missing_evidence.csv`
- `needs_review.csv`

本轮只规划，不生成这些文件。

## 验证标准

实现阶段完成后应验证：

1. 每条输入样本都有一条 `ArbitrationRecord`。
2. 缺失证据被显式记录。
3. 每页最多一个最终选中标题栏候选。
4. 标题栏位置能映射到旋转角度。
5. dry-run 不改原始 PDF、不重命名文件。
6. 人工可见字段不暴露长 JSON、调试分数或冗余路径。

## 下一步

下一步应先提交本计划、RPD 和 TODO 回滚点，再实现只读汇总脚本。

建议实现脚本：

```text
scripts/ocr/build_title_block_arbitration_records.py
```

实现时先覆盖既有 hard-case 与 round3 重点样本，不直接扩展到完整 PDF 图纸包。

