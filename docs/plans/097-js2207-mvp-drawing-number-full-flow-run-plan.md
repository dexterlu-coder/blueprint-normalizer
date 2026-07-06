# JS2207 MVP 图号命名全流程测试计划

日期：2026-07-03

## 背景

`tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py` 已增加图号读取与按图号命名输出工序，并已通过 1 页 smoke。用户要求清空 `tools/pdf_rotation_mvp/output/`，再次使用 `local_data/source_pdfs/JS2207-00-00升降平台.pdf` 进行全流程测试。

## 目标

1. 清空 MVP 工具输出目录：
   - `tools/pdf_rotation_mvp/output/`
   - 保留 `.gitkeep`。
2. 确认 JS2207 源 PDF 位于：
   - `tools/pdf_rotation_mvp/input/JS2207-00-00升降平台.pdf`
3. 运行 MVP 全流程：
   - PDF 拆分。
   - 原页渲染。
   - VLM 标题栏位置识别。
   - PDF 页面旋正。
   - 旋正页标题栏 crop。
   - VLM 图号读取。
   - 最终按图号命名发布。
4. 保留输出结果供审核：
   - `tools/pdf_rotation_mvp/output/`
   - `tools/pdf_rotation_mvp/work/`
5. 汇总运行摘要，重点检查：
   - 总页数。
   - 方向识别 API/解析/schema 成功数。
   - 图号识别 API/解析/schema 成功数。
   - `published_count`。
   - `final_needs_review_count`。
   - 主输出目录 PDF 文件名是否为图号。

## 质量门

- 不读取、打印或提交 `.env/.env` 密钥。
- 不把 `tools/pdf_rotation_mvp/input/`、`output/`、`work/` 和 `local_data/` 产物纳入 Git。
- 清空目录前必须确认目标路径在 `tools/pdf_rotation_mvp/output/` 内。
- 真实调用阿里云模型时直接使用已批准的 MVP 脚本命令或提权执行，不先走普通沙箱试错。
- 方向失败、无标题栏、图号失败、图号重复或文件名非法的页面必须进入 `needs_review/`，不得用页码伪装为图号文件。

## 验收标准

1. `tools/pdf_rotation_mvp/output/` 已被清空旧结果并重新生成本轮结果。
2. `summary.json` 可读取，且 `page_count` 应为 29。
3. `report.csv` 行数应覆盖 29 页。
4. 主输出目录中的正式 PDF 文件名均来自图号。
5. 若存在 `needs_review.csv`，能从 `final_blockers` 看出原因。

