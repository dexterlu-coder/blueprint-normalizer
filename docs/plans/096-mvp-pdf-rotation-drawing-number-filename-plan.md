# PDF 旋正 MVP 增加图号命名工序计划

日期：2026-07-03

## 背景

用户同意当前图号 OCR 审核结论：在 JS2207 样本上，`qwen3.7-plus` 与 `qwen3.7-max-2026-06-08` 的标题栏图号提取人工审核正确率均为 100%，而 `qwen3.5-ocr` 和 `qwen-vl-ocr-latest` 不适合作为当前主链路。

用户要求修改此前的拆分、旋转图纸 Python 脚本：

```text
tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py
```

新增最后一道读取图号的工序，并要求最终输出的若干单个图纸 PDF 文件名必须是图纸图号。

## 目标

1. 保留现有流程：
   - 读取 `input/` PDF。
   - 拆分单页 PDF。
   - 渲染 PNG。
   - 调用 `qwen3.7-plus` 判断标题栏位置。
   - 根据标题栏位置旋正单页 PDF。
2. 新增图号读取工序：
   - 对旋正后的单页 PDF 再渲染 PNG。
   - 裁切底部标题栏候选区域。
   - 使用 `qwen3.7-plus` 提取标题栏图号或图样代号。
3. 新增最终发布工序：
   - 只有旋正可靠、图号读取可靠、图号唯一且文件名安全时，才输出到主图纸目录。
   - 主图纸目录中的 PDF 文件名必须是 `<图号>.pdf`。
   - 读不到图号、重复图号、图号含非法文件名字符、方向/解析失败、无标题栏的页面进入 `needs_review/`，不得用页码伪装为最终图纸名。
4. 更新报告：
   - `report.csv`
   - `needs_review.csv`
   - `summary.json`
   - `work/` 下保留方向识别和图号识别的请求、响应、决策。

## 非目标

- 不重新设计标题栏位置判断 prompt。
- 不引入 OCR 模型作为主链路。
- 不修正历史第 22 页方向问题。
- 不取消人工复核质量门。
- 不读取、打印或提交 `.env/.env` 密钥。

## 设计要点

### 输出目录

主输出建议保持按源 PDF 分组：

```text
output/<源PDF名>/<图号>.pdf
```

需要复核的页面放入：

```text
output/<源PDF名>/needs_review/<task_id>.pdf
```

这样主目录内的正式单页图纸 PDF 均满足“文件名必须是图号”，而异常页不会产生误导性图号文件名。

### 图号命名质量门

最终命名前必须同时满足：

- 方向识别 API 成功。
- 方向 JSON parse/schema 成功。
- 可派生校正角度。
- 图号识别 API 成功。
- 图号 JSON parse/schema 成功。
- `selected_drawing_number` 非空。
- 模型未标记 `needs_human_review=true`。
- 图号不含 Windows 文件名非法字符。
- 同一输出分组内图号唯一。

不满足任一条件，进入 `needs_review/`。

### 阿里云联网执行

按 `AGENTS.md` 规则，真实调用阿里云百炼 / DashScope / OpenAI-compatible endpoint 时，直接使用已批准命令前缀或 `sandbox_permissions=require_escalated`，不先在普通沙箱中试跑联网请求。

## 验收标准

1. `python -m py_compile tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py` 通过。
2. `--dry-run --limit-pages 1` 可运行，且不产生看似成功的图号命名输出。
3. README 更新用法与输出说明。
4. 报告中包含图号字段、最终命名路径、复核原因。
5. 实现提交后，若进行 JS2207 smoke，结果保留在 `tools/pdf_rotation_mvp/output/` 和 `work/` 供用户审核。

