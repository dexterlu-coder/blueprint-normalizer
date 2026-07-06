# JS2207 VLM 提示词调整复测计划

日期：2026-07-02

## 背景

用户已完成 JS2207 真实 PDF 原向 VLM 标题栏位置审核，并补充说明：

- 部分图纸按纸张竖向绘制。
- 标题栏位于下方并刚好占满图纸宽度。
- 因此 Excel 中多处填写 `下方` 是合法位置，不是模糊描述。

上一轮结果：

- 58 条模型结果。
- 人工判断正确 24 条。
- 人工判断错误 34 条。
- 需关注 18 页。

## 目标

1. 根据用户填写的 Excel 和补充说明调整 VLM prompt/schema。
2. 新增或明确支持：
   - `bottom_edge`：底边满宽或接近满宽标题栏。
   - `top_edge`、`left_edge`、`right_edge`：边位置。
   - `no_title_block`：没有可确认标题栏。
3. 明确禁止将零件表格、明细表、技术要求表误认为标题栏。
4. 使用同一份 JS2207 原向 PNG、不旋转、不压缩重新调用 `qwen3-vl-flash` 和 `qwen3-vl-plus`。
5. 用已归档 Excel 审核结果作为真值自动评估新版结果。
6. 生成新旧正确率对比报告。

## 非目标

- 不让用户先进行二次人工审核。
- 不修改已归档 Excel。
- 不生成正式旋正 PDF。
- 不重命名 PDF。
- 不把 `local_data/` 输出提交到 Git。
- 不针对 JS2207 页码写特判规则。

## 输入

- 源 PDF：`local_data/source_pdfs/JS2207-00-00升降平台.pdf`
- 旧审核摘要：`local_data/js2207_real_vlm_title_block_review/excel_review_summary.json`
- 旧审核逐行结果：`local_data/js2207_real_vlm_title_block_review/excel_review_rows.json`
- 长期规则：`rules/mechanical-drawing-rotation.md`

## 输出

本地输出目录：

```text
local_data/js2207_real_pdf_vlm_title_block_prompt_retest/
```

计划输出：

- 新版请求、响应、决策与双模型对比。
- 基于旧 Excel 真值的自动评估 JSON/CSV。
- 新旧正确率对比摘要。
- 可选发布新的 HTML/Excel 审核包到 `local_data/review_inbox/current/` 供抽查。

## 验证

- 确认 prompt/schema 包含边位置和 `no_title_block`。
- 确认使用 PNG 原图，不旋转、不压缩。
- 确认请求数仍为 58。
- 确认无模型级 API 失败。
- 确认评估以 Excel 人工结果为真值，不读取 CSV 作为人工结果。
- 确认不生成正式 PDF、不重命名 PDF。

## 回滚准备

实现前提交本计划、RPD 和 TODO，作为 prompt 复测实现前回滚点。
