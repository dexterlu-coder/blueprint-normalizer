# VLM 标题栏提示词泛化盲测计划

日期：2026-07-02

## 背景

用户质疑当前 VLM 提示词可能吸收 JS2207 人工反馈后过度适配该图纸包，忽略通用性。这个质疑成立，因此下一步不应继续只在 JS2207 上调 prompt。

项目内已有标题栏规范调研和长期规则，但当前 prompt 仍属于“规范启发 + JS2207 实证反馈”，不能宣称已经完全标准化。需要用另一个 PDF 做盲测，先观察模型在非 JS2207 图纸上的表现。

## 目标

1. 使用 `local_data/source_pdfs/` 中非 JS2207 的 PDF 做盲测：

```text
local_data/source_pdfs/YKJ125-00-00-2525铁屑压块机生产图（250911章）解密.pdf
```

2. 不修改现有 prompt/schema，不添加页码、文件名、图号样式或业务模板特判。
3. 按 PDF 页面顺序拆分并渲染原向 PNG。
4. 用原向 PNG 直接调用 `qwen3-vl-flash` 和 `qwen3-vl-plus`：
   - 不旋转图片。
   - 不 resize。
   - 不做有损 JPEG 压缩。
5. 只让模型判断当前屏幕坐标下标题栏位置，并由程序本地派生旋转角度。
6. 发布人工审核包到固定入口：

```text
local_data/review_inbox/current/
```

7. 审核包按页码顺序展示图片和两个模型判断，Excel 只保留人工审核必须字段。

## 盲测边界

- 本轮是非 JS2207 图纸包盲测，但该 PDF 属于项目早期 YKJ125 样本来源，不能代表跨企业、跨模板、跨行业全面泛化。
- 本轮结论只能判断：当前 prompt 是否明显依赖 JS2207 的局部特征。
- 不根据本轮模型输出继续改 prompt；必须先经人工审核。
- 若后续要宣称通用性，需要再加入更多来源的图纸包。

## 非目标

- 不调整 prompt/schema。
- 不根据 YKJ125 结果写特判。
- 不使用已有 YKJ125 人工真值参与模型调用或 prompt。
- 不生成正式旋正 PDF。
- 不重命名 PDF。
- 不读取或打印 `.env/.env` 中的 API Key。
- 不提交 `local_data/` 输出。

## 输出

本地机器输出目录：

```text
local_data/vlm_title_block_generalization_blind_ykj125/
```

固定审核入口：

```text
local_data/review_inbox/current/ykj125_vlm_title_block_blind_review/
```

计划输出：

- `review_index.html`
- `vlm_title_block_blind_review.xlsx`
- `vlm_title_block_blind_review.csv`
- `review_manifest.json`
- `images/`
- 机器侧请求、响应、决策、双模型对比和摘要文件

## 审核入口处理

当前 `local_data/review_inbox/current/` 中仍有 JS2207 prompt 复测审核包。发布本轮盲测入口前必须先归档当前入口，并在本轮 manifest 和最终汇报中记录归档位置。

## 验证

- 确认当前审核入口已归档。
- 确认渲染 PNG 和审核 HTML 图片均按 PDF 页码顺序排列。
- 确认 VLM 输入为原向 PNG，不旋转、不 resize、不做有损压缩。
- 确认两个模型结果均写入 Excel。
- 确认审核表只暴露低噪声字段。
- 确认 HTML 图片副本位于 `current` 内。
- 确认未生成正式 PDF、未重命名 PDF。
- 确认未提交 `local_data/` 私有输出。

## 回滚准备

实现和批处理前提交本计划、RPD 和 TODO，作为盲测执行前回滚点。
