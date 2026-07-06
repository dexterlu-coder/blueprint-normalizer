# JS2207 MVP PDF 旋正全量测试计划

日期：2026-07-02

## 背景

用户要求使用 `local_data/source_pdfs/JS2207-00-00升降平台.pdf` 测试 MVP PDF 旋正脚本，并保留输出内容供审核。

当前 MVP 工具位于：

```text
tools/pdf_rotation_mvp/
```

## 目标

1. 将 JS2207 源 PDF 放入 MVP 工具的 `input/`。
2. 使用 `tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py` 全量处理 JS2207。
3. 输出旋正后的单页 PDF 到 `tools/pdf_rotation_mvp/output/`。
4. 保留中间文件和机器报告到 `tools/pdf_rotation_mvp/work/`。
5. 将本轮需要用户审核的文件副本发布到固定入口：
   - `local_data/review_inbox/current/js2207_mvp_pdf_rotation_review/`

## 范围

- 只处理 JS2207 源 PDF。
- 使用 `qwen3.7-plus / 非思考`。
- 不修改 MVP 脚本逻辑。
- 不合并多页 PDF。
- 不按图号重命名。

## 审核包

固定入口应包含：

- 输出单页 PDF 副本。
- `report.csv`。
- `needs_review.csv`。
- `summary.json`。
- 简短 README。

若生成 HTML 审核页，应以页码顺序列出输出 PDF、状态和复核原因。

## 风险

- 当前模型在 JS2207 人工审核中仍存在第 15 页和第 22 页误判风险。
- MVP 输出应视为待审核产物，不是正式最终交付。
- `needs_review.csv` 为空也不代表完全可靠，仍需抽样或全量人工查看。

## 验收标准

1. JS2207 29 页均生成单页 PDF 输出或复核副本。
2. `output/report.csv` 覆盖 29 页。
3. `output/summary.json` 记录 corrected 与 needs_review 数量。
4. 固定审核入口已发布本轮审核材料。
5. `local_data` 和 MVP 输入输出产物不进入 Git。

## 回滚准备

先提交本计划、RPD 和 TODO。若后续批处理或审核包发布异常，可回退到本计划回滚点，保留脚本实现不变。
