# JS2207 真实 PDF VLM 标题栏位置审核计划

日期：2026-07-02

## 背景

用户要求使用真实图纸包：

```text
local_data/source_pdfs/JS2207-00-00升降平台.pdf
```

执行真实测试。明确要求：

- 不准自行旋转图纸。
- 先将 PDF 拆成一张张单独图纸。
- 直接测试原始方向图纸。
- 不压缩图片。
- 只判断标题栏当前位置。
- 输出 Excel 表格供审核。
- 生成单个 HTML 文件，按图片排列顺序展示，方便对照审查。

## 目标

1. 从源 PDF 重新拆分 29 个单页 PDF。
2. 将单页 PDF 原向渲染为 PNG，不做旋转、校正、裁切或压缩。
3. 使用 PNG 原图 Base64 data URL 发送给阿里云 VLM。
4. VLM 只判断当前屏幕坐标下标题栏位置。
5. 程序派生旋转角度，但审核表重点只展示标题栏位置。
6. 生成用户审核入口：
   - Excel：`vlm_title_block_review.xlsx`
   - HTML：`review_index.html`
7. 审核入口放到固定目录：
   - `local_data/review_inbox/current/`

## 非目标

- 不生成正式旋正 PDF。
- 不重命名单页 PDF。
- 不发布裁切后的标题栏图作为主判断依据。
- 不使用受控旋转样本。
- 不压缩上传图片。
- 不把 `local_data/` 输出提交到 Git。

## 图片策略

本轮上传给模型的是原向 PNG：

- 不转 JPEG。
- 不缩放。
- 不设置长边压缩。
- 不旋转。

风险：

- PNG Base64 请求体较大，可能导致单页请求慢或超出接口限制。
- 若出现请求体过大或超时，应按页记录失败并进入审核，不得自动改用压缩图替代本轮结论。

## 输出

业务输出目录：

```text
local_data/js2207_real_pdf_vlm_title_block/
```

固定审核入口：

```text
local_data/review_inbox/current/js2207_real_vlm_title_block_review/
```

审核入口应包含：

- `review_index.html`
- `vlm_title_block_review.xlsx`
- `vlm_title_block_review.csv`
- `review_manifest.json`
- `images/` 中的原向 PNG 副本
- `README.md`

Excel/CSV 人工审核字段保持低噪声：

- 序号
- 页码
- 样本编号
- 模型
- 模型标题栏位置
- 程序派生当前旋转角度
- 程序派生校正角度
- 位置是否正确
- 正确标题栏位置
- 备注

## 验证

- 编译新增脚本。
- 确认拆页数量为 29。
- 确认渲染 PNG 数量为 29。
- 确认 VLM 请求数量为 `29 * 模型数`。
- 确认审核入口图片按页码顺序排列。
- 确认 Excel/CSV/HTML 不暴露 API Key、长 JSON、调试分数或候选列表。
- 确认不生成正式 PDF、不重命名 PDF。

## 回滚准备

实现前提交本计划、RPD 和 TODO，作为真实 PDF VLM 批量测试实现前回滚点。
