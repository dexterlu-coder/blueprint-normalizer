# JS2207 真实 VLM Excel 审核结果归档计划

日期：2026-07-02

## 背景

用户已完成 `JS2207` 真实 PDF 原向 VLM 标题栏位置审核，并明确说明：

- 已填写 Excel 表格。
- CSV 表格没有填写。

因此本轮只能以 Excel 为人工审核结果来源，CSV 只能作为机器生成参考，不得作为人工填写结果读取。

## 输入

固定审核入口：

```text
local_data/review_inbox/current/js2207_real_vlm_title_block_review/
```

人工填写文件：

```text
vlm_title_block_review.xlsx
```

参考文件：

```text
vlm_title_block_review.csv
review_manifest.json
review_index.html
images/
```

## 目标

1. 读取 Excel 中的人工填写结果。
2. 只解析低噪声人工字段：
   - `位置是否正确`
   - `正确标题栏位置`
   - `备注`
3. 与机器结果按 `序号`、`页码`、`样本编号`、`模型` 对齐。
4. 生成审核摘要：
   - 总记录数。
   - 已填写数。
   - 正确/错误/不确定/空白分布。
   - 需要修正的页和模型。
   - 双模型同页人工结论分布。
5. 归档当前固定审核入口。
6. 重置 `local_data/review_inbox/current/` 为无待审核任务。

## 非目标

- 不读取 CSV 作为人工审核结果。
- 不修改用户填写的 Excel。
- 不生成正式旋正 PDF。
- 不重命名 PDF。
- 不把 `local_data/` 归档输出提交到 Git。
- 不基于本轮结果直接改模型 prompt 或策略。

## 输出

业务摘要目录：

```text
local_data/js2207_real_vlm_title_block_review/
```

计划输出：

- `excel_review_rows.json`
- `excel_review_rows.csv`
- `excel_review_summary.json`
- `excel_review_summary.csv`
- `human_summary.md`

归档目录：

```text
local_data/review_inbox/archive/js2207_real_vlm_title_block_review_<timestamp>_reviewed/
```

## 验证

- 确认 Excel 可解析。
- 确认记录数为 58 行。
- 确认 CSV 未作为人工结果源。
- 确认旧 `current` 已归档。
- 确认新 `current/README.md` 表示当前无待审核任务。
- 确认不生成正式 PDF、不重命名 PDF。

## 回滚准备

实现前提交本计划、RPD 和 TODO，作为 Excel 审核归档实现前回滚点。
