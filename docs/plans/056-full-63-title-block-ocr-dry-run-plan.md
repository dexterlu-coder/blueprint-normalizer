# 63 张全量标题栏 crop/OCR dry-run 计划

## 背景

63 张全量 PDF dry-run 已经验证：

- `local_data/experiment_samples/all/pdf/` 中 63 个单页 PDF 均可匹配。
- `local_data/experiment_samples/all/png/` 中 63 个渲染 PNG 均可匹配。
- 63 条记录均可形成 PDF 旋正计划。
- 没有修改 PDF，也没有正式重命名。
- 全部命名被 `drawing_number_missing` 阻断，因为尚未对 63 张全量标题栏区域做 OCR。

下一步需要补齐全量标题栏 crop、OCR 原文和图号候选 dry-run，验证命名链路的真实风险。

## 本轮目标

1. 对 63 张人工确认样本生成标题栏 crop。
2. 只对标题栏 crop 跑 OCR，不做整页 OCR。
3. 保存每页标题栏 crop、OCR 原文、字段簇命中和图号候选。
4. 将 OCR 结果回填到全量 dry-run 输入记录。
5. 复用 `scripts/ocr/build_pdf_correction_dry_run.py` 重新生成命名风险报告。
6. 仍然不改 PDF、不正式重命名。

## 非目标

本轮不做：

- 不覆盖原始 PDF。
- 不生成正式旋正 PDF。
- 不正式重命名。
- 不整页 OCR。
- 不调用云端 VLM。
- 不修改 ground truth。
- 不新增人工审核入口。
- 不重训 YOLO/OBB。

## 输入

默认输入：

```text
local_data/full_63_pdf_dry_run/full_63_arbitration_records.jsonl
outputs/rotation-detection/stage1/results.json
local_data/experiment_samples/all/png/
local_data/experiment_samples/all/pdf/
```

说明：

- `stage1/results.json` 中的 `best_candidate.bbox` 作为第一版标题栏 crop 来源。
- `full_63_arbitration_records.jsonl` 提供 PDF 路径、PNG 路径、旋转角度和 dry-run 结构。
- 本轮不重新做标题栏位置判断，只复用已通过评估的方向结果。

## 输出

建议输出到：

```text
local_data/full_63_title_block_ocr_dry_run/
```

输出文件：

- `full_63_ocr_arbitration_records.jsonl`
- `ocr_summary.json`
- `ocr_summary.csv`
- `drawing_number_candidates.csv`
- `crops/`
- `ocr_text/`

随后复用 PDF dry-run 脚本输出：

```text
local_data/full_63_title_block_ocr_dry_run/pdf_correction_dry_run/
```

## crop 策略

第一版使用 OpenCV stage1 结果：

- 读取 `best_candidate.bbox`。
- 在原始 PNG 上按 bbox 裁剪。
- 加少量 padding，避免裁掉标题栏边界文字。
- crop 文件保存到 `crops/`。

如果某页缺少：

- `stage1` 结果。
- `best_candidate`。
- `bbox`。
- PNG 文件。

则不伪造 crop，记录 blocker。

## OCR 策略

第一版使用本地 OCR 能力：

- 优先 RapidOCR。
- 仅对标题栏 crop 尝试有限旋转角。
- 旋转角候选复用标题栏当前位置：
  - `top`: 180, 270
  - `bottom`: 0, 90
  - `left`: 90, 180
  - `right`: 0, 270

OCR 输出：

- `ocr_engine`
- `ocr_status`
- `ocr_rotation_angle`
- `ocr_text`
- `ocr_confidence_summary`
- `role_field_hits`
- `property_field_hits`
- `field_cluster_score`
- `ocr_ready_for_number_extraction`

## 图号候选

图号候选抽取仍由 `scripts/ocr/build_pdf_correction_dry_run.py` 负责，避免重复规则。

本轮关注：

- 63 张中多少张能抽到图号候选。
- 多少张为单候选。
- 多少张多候选或低置信。
- 多少张因重复文件名、非法字符或缺图号阻断。

## 验证标准

1. 不修改原始 PDF。
2. 不正式重命名。
3. 不做整页 OCR。
4. 63 条输入记录数量不变。
5. 每页有 crop 或明确 blocker。
6. OCR 原文保存到本地 dry-run 目录。
7. PDF dry-run 重新运行后，`modified_pdf=false` 且 `renamed_pdf=false`。
8. 命名风险必须显式输出，不能静默通过。

## 预期结果

预期本轮会显著减少 `drawing_number_missing`，但不预期直接达到正式自动命名条件。

原因：

- OCR 可能把 `YKJ` 识别成 `YEJ`。
- OCR 可能混入路径、IP、日期或模型文件名。
- 多张样本可能包含相同总图号或重复图号。
- 文件名去重和低置信规则必须继续拦截。

## 后续分支

若图号候选召回较好：

1. 规划候选图号人工抽查或机器一致性检查。
2. 设计只读命名 dry-run 报告。
3. 进一步测试 PDF 旋正视觉预览。

若 OCR 质量不足：

1. 改进 crop 边界或旋正 crop。
2. 只对失败样本做 OCR 参数实验。
3. 必要时再考虑 VLM/OCR provider 兜底，不作为默认主流程。

