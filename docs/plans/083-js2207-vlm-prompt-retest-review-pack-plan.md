# JS2207 VLM Prompt 复测人工审核包发布计划

日期：2026-07-02

## 背景

用户要求对 JS2207 VLM prompt 复测结果进行人工审核。

当前复测已完成：

- 输入为 JS2207 原向 PNG。
- 图片未旋转、未压缩、未 resize。
- 模型为 `qwen3-vl-flash` 和 `qwen3-vl-plus`。
- 已生成 58 条新版 VLM 决策和自动评估结果。

## 目标

1. 基于已有复测结果生成低噪声人工审核包。
2. 审核入口统一发布到：

```text
local_data/review_inbox/current/
```

3. 审核包包含：
   - 单页 HTML，对照 29 张原向图纸和两个模型的新版标题栏位置。
   - Excel 审核表，按页码和模型顺序排列。
   - CSV 机器参考表。
   - 图片副本。
   - manifest。
4. 人工表只保留用户判断需要字段，不暴露长 JSON、调试字段或 API 响应。

## 非目标

- 不重新调用 VLM。
- 不改 prompt/schema。
- 不修改已归档 Excel。
- 不读取 CSV 作为人工结果。
- 不生成正式旋正 PDF。
- 不重命名 PDF。
- 不提交 `local_data/` 输出。

## 输出

固定审核入口：

```text
local_data/review_inbox/current/js2207_vlm_prompt_retest_review/
```

计划文件：

- `review_index.html`
- `vlm_prompt_retest_review.xlsx`
- `vlm_prompt_retest_review.csv`
- `review_manifest.json`
- `images/`

## 验证

- 确认 `current` 发布前没有未归档审核任务。
- 确认 HTML 图片均来自 `current` 内副本。
- 确认 Excel 共 58 行，顺序为页码、模型。
- 确认审核表字段低噪声。
- 确认不重新联网、不生成正式 PDF、不重命名 PDF。

## 回滚准备

实现前提交本计划、RPD 和 TODO，作为发布审核包前回滚点。
