# RapidOCR 本地字段簇小实验计划

## 背景

OCR 引擎选型调研已经完成，当前结论是：

- OCR 仍有必要，但只作为标题栏字段簇证据层。
- 第一轮本地小实验优先选择 RapidOCR。
- PaddleOCR / PP-OCR 作为能力上限和第二路线。
- 云 OCR 只作为用户明确批准后的上限对照。

本计划用于下一阶段 RapidOCR 本地小实验。核心约束是：必须能在普通配置机器上运行，不能把 OCR 变成重型依赖或主流程瓶颈。

## 普通机器运行约束

本阶段按以下普通机器假设设计：

- Windows 本地环境。
- CPU-only，不要求 NVIDIA GPU、CUDA 或专用加速卡。
- 内存按 8GB 到 16GB 档设计。
- 不要求长时间训练或大模型推理。
- 不处理完整 PDF，不全量 OCR 整页图纸。
- 只处理现有 8 到 16 个标题栏候选 crop。
- 单次实验应在分钟级完成；如果明显超时，应停止扩大范围。
- OCR 失败不能影响现有 OpenCV、YOLO/OBB 和 teacher rule 后处理结果。

## 目标

1. 在本机确认 RapidOCR 是否可用。
2. 只对现有重点候选 crop 运行 OCR 字段簇探针。
3. 输出可审计的字段簇证据：
   - OCR 引擎名。
   - OCR 状态。
   - 原始识别文本摘要。
   - 流程字段命中。
   - 属性字段命中。
   - 字段簇强弱。
   - 失败原因。
4. 判断 RapidOCR 是否值得进入后续 `teacher_rule_flags` 接入计划。

## 非目标

本阶段不做：

- 不训练 OCR 模型。
- 不微调 OCR 模型。
- 不启用 GPU-only 路线。
- 不接入 PaddleOCR 完整文档解析链路。
- 不调用云 OCR。
- 不上传图纸。
- 不处理完整 PDF。
- 不把 OCR 结果写入 ground truth。
- 不把 OCR 结果直接用于自动接受。

## 输入

优先使用已有本地诊断 crop：

```text
local_data/title_block_ocr_diagnostic/crops/
```

如需重新生成 crop，沿用：

```text
python scripts/ocr/build_title_block_ocr_diagnostic.py
```

但本计划阶段只规划，不执行安装和实验。

## 输出

继续沿用现有 OCR 诊断输出目录：

```text
local_data/title_block_ocr_diagnostic/
```

需要保持或新增字段：

```text
ocr_capability
ocr_engine
ocr_status
ocr_text_excerpt
role_field_hits
property_field_hits
field_cluster_score
ocr_probe_decision
```

## 技术策略

### 第一层：RapidOCR CPU 路线

- 优先使用 RapidOCR 的 CPU 推理路径。
- 优先选择轻量模型或默认模型。
- 不引入 GPU/CUDA 条件。
- 不同时安装多个 OCR 引擎，避免变量混杂。

### 第二层：失败降级

如果 RapidOCR 安装失败、模型下载失败或运行成本过高：

- 保留 `ocr_unavailable` 或 `ocr_error:*`。
- 不阻塞现有诊断脚本。
- 不继续扩大样本。
- 再单独规划 Tesseract baseline 或 PaddleOCR 对照。

### 第三层：证据接入延后

即使 RapidOCR 输出正常，也只先进入诊断报告。是否接入后处理，需要另一个计划判断：

- 是否能稳定命中真实标题栏字段簇。
- 是否能拒绝普通明细表反例。
- 是否不会显著增加普通机器运行成本。
- 是否有人工复核证据支持。

## 样本范围

第一轮只使用当前 hard-case 和代表性样本：

- `sample_001`
- `unclear90_001_from_sample_001`
- `sample_009`
- `sample_010`
- `sample_020`
- `aug90_002_from_sample_010`
- `aug90_007_from_sample_020`
- `sample_040`

候选数量以现有诊断报告为准，预计 8 到 16 个 crop。不得在第一轮直接扩展到全量 PDF。

## 验收标准

计划完成后，进入实现阶段时应满足：

- 有明确回滚点。
- 只安装或启用一个 OCR 引擎变量。
- 脚本在 OCR 不可用时仍能正常输出报告。
- OCR 成功时能处理全部重点 crop。
- 普通明细表反例不因单个关键词被判定为强标题栏。
- 真实标题栏至少出现稳定字段簇命中，否则不进入后处理规则。
- 全部结果仅作为诊断证据，不自动修改 ground truth、标签或主流程判断。

## 风险与控制

| 风险 | 控制 |
| --- | --- |
| 普通机器安装依赖过重 | 首选 RapidOCR CPU，小样本验证；失败即停止扩大 |
| 模型下载慢或失败 | 记录失败，不绕过审批，不改用云端上传 |
| OCR 对小字号标题栏召回弱 | 只保留日志，不接入自动接受 |
| 普通明细表误命中关键词 | 必须结合字段簇数量、结构反证和人工复核 |
| OCR 运行时间过长 | 保持 crop 级小实验，不处理整页或全量 PDF |

## 后续实现步骤

实现阶段必须另起回滚点后执行：

1. 检查当前 Python 环境和现有 OCR capability。
2. 安装或启用 RapidOCR CPU 依赖。
3. 修改 `scripts/ocr/build_title_block_ocr_diagnostic.py`，新增 RapidOCR 尝试路径。
4. 运行 py_compile。
5. 运行 8 到 16 个重点 crop 诊断。
6. 检查报告与 HTML。
7. 将结论写回 RPD 和 TODO。

## 回滚点

本计划、RPD 和 TODO 提交后作为 RapidOCR 本地字段簇小实验实现前回滚点。

