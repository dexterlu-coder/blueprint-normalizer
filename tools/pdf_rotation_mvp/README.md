# PDF Rotation MVP

这个目录是当前 MVP 工具入口。

## 用法

1. 将待处理 PDF 放入本目录的 `input/`。
2. 在项目根目录执行：

```powershell
python tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py
```

脚本会：

- 将输入 PDF 拆分为单页 PDF。
- 渲染单页 PNG 供 VLM 判断标题栏位置。
- 使用 `qwen3.7-plus / 非思考` 识别方向。
- 将可明确校正的页面先写入 `work/corrected_pdfs/`。
- 对旋正后的页面裁切底部标题栏候选区域，并使用 `qwen3.7-plus / 非思考` 提取图号。
- 只有方向可靠、图号可靠且图号唯一时，才将最终单页 PDF 输出到 `output/<源PDF名>/<图号>.pdf`。
- 将无法明确校正、无法读取图号、图号重复或需要人工复核的页面输出到 `output/<源PDF名>/needs_review/`，并写入 `needs_review.csv`。

## 目录

- `input/`：放待处理 PDF。
- `output/`：输出按图号命名的最终单页 PDF、`needs_review/` 和报告。
- `work/`：中间单页 PDF、PNG、VLM 原始响应和机器日志。

## 报告

- `output/report.csv`：每页最终状态，重点看 `final_pdf_path`、`final_status`、`drawing_number`、`final_blockers`。
- `output/needs_review.csv`：只包含需要人工复核的页面。
- `output/summary.json`：本次运行的 API、解析、旋正、发布数量摘要。
- `work/orientation_*.jsonl`：标题栏位置识别请求、响应和决策。
- `work/drawing_number_*.jsonl`：图号识别请求、响应和决策。

## 注意

当前工具只是 MVP，不是无人值守正式批处理工具。请先查看 `output/report.csv`、`output/needs_review.csv` 和 `output/summary.json`。

主输出目录中的 PDF 文件名应为图号；若某页无法满足图号命名质量门，脚本不会用页码伪装成最终文件名，而是放入 `needs_review/`。
