# PDF 旋正与图号抽取 dry-run 计划

## 背景

标题栏位置多证据仲裁已经形成 `ArbitrationRecord`，并通过正式评估脚本验证：

- 当前 30 条仲裁记录均有 ground truth。
- 标题栏位置正确率：30/30。
- 派生旋转角度正确率：30/30。
- 自动接受记录：25/25。

这说明当前证据足以进入下一阶段 dry-run，但仍不允许直接正式批量覆盖 PDF 或按 OCR 图号重命名文件。

## 最终目标链路

用户的最终目标是：

1. 将图纸包 PDF 拆分为一张图纸一个 PDF。
2. 将每张图纸旋转到正确角度。
3. 定位并保存标题栏区域。
4. 对标题栏区域 OCR。
5. 抽取标题栏中的图纸图号。
6. 用图纸图号重命名单页 PDF。
7. 默认无人参与，只有证据不足、冲突或命名风险高时才进入人工判断。

## 本轮目标

本轮只规划 dry-run，不正式改写业务 PDF。

目标包括：

1. 设计单页 PDF 旋正 dry-run 输出结构。
2. 设计旋正后标题栏 crop 保存策略。
3. 设计标题栏 OCR 原文保存策略。
4. 设计图号候选抽取与命名风险检查。
5. 设计人工异常队列的触发条件。
6. 明确实现前的回滚点和验证标准。

## 非目标

本轮不做：

- 不覆盖原始 PDF。
- 不正式重命名单页 PDF。
- 不把 OCR 图号直接作为最终文件名。
- 不调用云端 VLM。
- 不新增训练或重训。
- 不修改 ground truth。
- 不跳过人工异常队列。

## 输入

第一版 dry-run 优先使用已有产物：

```text
local_data/title_block_arbitration/arbitration_records.jsonl
```

后续接完整 PDF 图纸包时，还需要输入：

- 原始图纸包 PDF。
- 已拆分的一页一个 PDF，或可重复拆分脚本的输出。
- 每页渲染图像。

若当前记录缺少 `source_pdf_path`、`single_page_pdf_path` 或可定位原 PDF 的路径，第一版实现应允许只对已有实验图像生成 dry-run 计划，不应伪造 PDF 输出。

## 输出

建议输出到：

```text
local_data/pdf_correction_dry_run/
```

建议文件：

- `dry_run_records.jsonl`
- `dry_run_summary.json`
- `dry_run_summary.csv`
- `rotation_plan.csv`
- `drawing_number_candidates.csv`
- `naming_risks.csv`
- `needs_review.csv`
- `previews/`
- `title_block_crops/`
- `ocr/`

所有输出均为本地可再生 dry-run 产物，不提交 Git。

## DryRunRecord 草案

每页建议保存：

```json
{
  "record_id": "",
  "sample_id": "",
  "input": {},
  "arbitration": {},
  "rotation_plan": {},
  "title_block_crop": {},
  "ocr": {},
  "drawing_number": {},
  "rename_plan": {},
  "review_routing": {},
  "artifacts": {}
}
```

### input

- `source_pdf_path`
- `page_index`
- `single_page_pdf_path`
- `rendered_image_path`
- `arbitration_record_path`

### arbitration

- `decision_status`
- `title_block_position`
- `detected_rotation_degrees`
- `correction_degrees`
- `confidence_level`
- `decision_reasons`

### rotation_plan

- `can_rotate_pdf`
- `would_rotate_degrees`
- `corrected_pdf_candidate_path`
- `dry_run_only`
- `blockers`

阻断条件：

- 仲裁记录不是 `auto_accept`。
- 没有单页 PDF 路径。
- 没有明确校正角度。
- 输入文件不存在。
- 输出路径会覆盖已有文件且未启用安全策略。

### title_block_crop

- `can_crop`
- `source_image_path`
- `crop_path`
- `normalized_crop_path`
- `crop_source`
- `blockers`

第一版可以复用 `ArbitrationRecord.ocr.title_block_crop_path` 或候选 crop；若没有可靠 crop，应标记缺失，不伪造。

### ocr

- `ocr_engine`
- `ocr_status`
- `ocr_text_path`
- `ocr_text_excerpt`
- `field_cluster_hits`
- `ocr_confidence`
- `blockers`

第一版优先保存已有 OCR 诊断文本；是否重新跑 RapidOCR 需要另行确认，因为完整 PDF 阶段应只对标题栏 crop 做 OCR，不做整页 OCR。

### drawing_number

- `candidates`
- `selected_candidate`
- `selection_status`
- `confidence`
- `extraction_rule_version`
- `blockers`

图号候选抽取初版规则：

- 从 OCR 文本中优先查找 `图号`、`图样代号`、`代号` 附近的编号。
- 其次识别常见机械图号模式，例如包含大写字母、数字、连字符的长编号。
- 排除日期、IP 地址、路径片段、公司电话、页码和明显 OCR 噪声。
- 若多个候选分数接近，不自动选择。

### rename_plan

- `can_rename`
- `filename_safe_value`
- `renamed_pdf_candidate_path`
- `would_overwrite`
- `duplicate_name_group`
- `illegal_character_removed`
- `blockers`

阻断条件：

- 无图号候选。
- 多个候选冲突。
- 图号低置信。
- 文件名非法字符清洗后为空或变化过大。
- 与其他页候选文件名重复。
- 目标文件已存在。
- 上游旋正或 OCR 阻断。

### review_routing

- `route`
  - `auto_dry_run_ready`
  - `needs_human_review`
  - `blocked`
- `route_reasons`
- `human_visible_fields`

人工表仍必须低噪声，只显示判断必须看到的信息：

- 样本编号或页码。
- 旋正前后预览。
- 标题栏 crop。
- OCR 摘要。
- 图号候选。
- 阻断原因。

完整 JSON、分数、路径和调试字段只保存在机器报告。

## 验证标准

实现 dry-run 后最低验证：

1. 不修改原始 PDF。
2. 不正式重命名文件。
3. 所有输出计划均标记 `dry_run_only=true`。
4. `needs_human_review` 仲裁记录不得进入自动旋正和命名。
5. 缺少 PDF 路径时必须显式阻断，不得伪造输出。
6. 图号候选、OCR 原文和标题栏 crop 必须保存或明确记录缺失。
7. 重名、非法字符、低置信和多候选必须进入风险清单。
8. 若生成审核入口，必须统一放入 `local_data/review_inbox/current/`。

## 推进顺序

1. 提交本计划、RPD 和 TODO 回滚点。
2. 实现 dry-run 记录构建脚本。
3. 先在现有 30 条仲裁记录上运行，不处理完整 PDF。
4. 检查阻断原因是否符合预期。
5. 再决定是否接入真实图纸包 PDF 的单页文件路径。

## 结论

标题栏位置识别当前不需要继续无目标打磨。下一阶段的主要风险已经转移到：

- PDF 页面的安全旋正。
- 旋正后标题栏 crop 的一致性。
- OCR 图号抽取可靠性。
- 文件名清洗、重名和覆盖风险。

因此下一步应进入 dry-run，而不是正式无人批处理。
