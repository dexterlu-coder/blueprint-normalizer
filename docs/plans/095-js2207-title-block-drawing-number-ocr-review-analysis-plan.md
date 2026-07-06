# JS2207 标题栏图号 OCR 审核结果统计计划

日期：2026-07-03

## 背景

用户已完成 `local_data/review_inbox/current/js2207_title_block_drawing_number_ocr_review/js2207_title_block_drawing_number_ocr_review.xlsx` 的人工审核填写。

本轮审核对象是 JS2207 MVP 旋正输出 PDF 的标题栏图号 OCR 四模型测试结果，模型包括：

- `qwen3.7-plus`
- `qwen3.7-max-2026-06-08`
- `qwen3.5-ocr`
- `qwen-vl-ocr-latest`

## 目标

1. 读取用户填写后的 Excel 审核表。
2. 按模型统计正确率、错误数、空结果数和人工修正情况。
3. 识别第 3 页无标题栏、第 22 页方向错误等风险页对统计的影响。
4. 生成机器可读统计报告和人工摘要。
5. 归档当前审核入口，重置 `local_data/review_inbox/current/`。
6. 更新 RPD 和 TODO，提交公开记录。

## 非目标

- 不重新调用任何阿里云模型。
- 不修改用户填写的 Excel。
- 不修正第 22 页方向。
- 不修改 OCR prompt 或模型选择逻辑。

## 输入

- 人工审核表：
  - `local_data/review_inbox/current/js2207_title_block_drawing_number_ocr_review/js2207_title_block_drawing_number_ocr_review.xlsx`
- 机器报告：
  - `local_data/js2207_title_block_drawing_number_ocr_test/decisions.jsonl`
  - `local_data/js2207_title_block_drawing_number_ocr_test/run_summary.json`

## 输出

- 业务统计目录：
  - `local_data/js2207_title_block_drawing_number_ocr_test/review_analysis/`
- 固定入口归档：
  - `local_data/review_inbox/archive/`
- 公开记录：
  - `reports/rpd-rotation-detection.md`
  - `TODO.md`

## 统计口径

- `图号是否正确` 中表达正确的值视为正确，例如 `是`、`正确`、`对`、`y`、`yes`、`1`、`true`。
- 表达错误的值视为错误，例如 `否`、`错误`、`错`、`n`、`no`、`0`、`false`。
- 未填写或无法识别的审核值单独统计为 `unreviewed_or_unknown`，不混入准确率分母，除非用户后续要求按错误处理。
- 若模型提取图号为空且用户标为正确，则视为正确，适用于无标题栏页。
- 第 3 页、第 22 页保留单独风险页统计，避免影响主流程判断。

## 验收标准

1. 成功读取 116 条审核记录。
2. 每个模型均有独立统计。
3. 统计报告包含整体结果、去除风险页结果、风险页明细。
4. 当前审核入口归档，`current` 重置为无待审核任务。
5. 私有 Excel、图片、模型响应和统计 JSON 不进入 Git。

