# OCR 字段簇可用性探针计划

## 背景

当前 MCP/VLM teacher 能力已经完成结构化响应、蒸馏分析，并以可解释 teacher rule flags 接入通用 YOLO/OBB 后处理。

但后处理中的“字段簇”目前仍是结构代理，不是真实 OCR 文字命中。本阶段需要判断 OCR 是否值得继续作为证据增强层。

本机初步探测显示：

- Python OCR 包未安装：
  - `pytesseract`
  - `paddleocr`
  - `easyocr`
  - `rapidocr_onnxruntime`
  - `cnocr`
- `tesseract` 命令不在 PATH。

因此本阶段目标不是强行引入 OCR，而是做一个可复现的 OCR 能力与字段簇可用性探针。

## 目标

1. 增强现有 OCR 诊断脚本，让它显式输出 OCR capability 信息。
2. 对当前 8 到 16 个重点候选 crop 运行字段簇探针。
3. 如果本地 OCR 不可用，输出明确的 `ocr_unavailable` 结论和缺失原因。
4. 如果后续 OCR 可用，沿用同一报告格式输出：
   - role field hits。
   - property field hits。
   - field cluster score。
   - OCR status。
5. 保持实验小规模，不全量处理 PDF。

## 非目标

本阶段不做：

- 不安装 OCR 依赖。
- 不联网下载模型。
- 不调用云端 OCR/VLM。
- 不上传图纸。
- 不重训。
- 不改标签。
- 不处理完整 PDF。
- 不把 OCR 输出直接写入 ground truth。

## 输入

```text
local_data/yolo_predictions/
local_data/yolo_obb_dataset_round3/round3_manifest.csv
local_data/title_block_ocr_diagnostic/crops/
```

## 输出

继续使用：

```text
local_data/title_block_ocr_diagnostic/
```

增强报告字段：

```text
ocr_capability
ocr_missing_engines
ocr_probe_decision
```

## 判断标准

- 若 OCR 环境不可用：
  - 记录 `ocr_probe_decision=ocr_unavailable_locally`。
  - 不继续做 OCR 规则接入。
  - 下一步优先 provider/VLM 小实验或人工选择 OCR 安装方案。
- 若 OCR 可用但字段簇命中弱：
  - 记录 `ocr_probe_decision=ocr_not_reliable_for_current_scans`。
  - OCR 只保留为辅助日志，不参与自动接受。
- 若 OCR 可用且字段簇命中稳定：
  - 记录 `ocr_probe_decision=ocr_field_cluster_candidate`。
  - 后续再计划接入 `teacher_rule_flags`。

## 验证

运行：

```text
python -m py_compile scripts/ocr/build_title_block_ocr_diagnostic.py
python scripts/ocr/build_title_block_ocr_diagnostic.py
```

期望：

- 脚本不因 OCR 缺失崩溃。
- 报告明确说明 OCR capability。
- 当前重点候选 crop 仍正常生成。
- 不修改固定审核入口。

## 回滚点

本计划、RPD 和 TODO 提交后作为增强 OCR 字段簇探针前回滚点。

