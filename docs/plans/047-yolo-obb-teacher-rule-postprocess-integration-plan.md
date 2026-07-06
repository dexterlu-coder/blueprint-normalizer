# YOLO/OBB teacher 规则蒸馏到通用后处理计划

## 背景

8 条 MCP/VLM teacher 响应已经完成结构化填写、校验和蒸馏分析。蒸馏结果显示 8 条响应全部具备规则价值，当前最稳的下一步是把确定性规则落到通用 YOLO/OBB 后处理，而不是直接重训或扩大 VLM 调用。

现有通用后处理已经具备：

- 候选评分。
- 图框线贴边检测。
- 多候选单标题栏仲裁。
- `uniform_grid_like` 普通表格误检反证。
- 诊断报告接入。

当前缺口是：teacher 蒸馏规则还没有在通用后处理中显式记录为可解释 flags，也没有形成独立的 rule adjustment 证据。

## 目标

1. 在 `scripts/yolo_obb/postprocess_yolo_obb_predictions.py` 中新增 teacher rule flags。
2. 将 teacher 规则转为可解释的候选证据：
   - `teacher_frame_field_proxy_positive`
   - `teacher_uniform_table_negative`
   - `teacher_small_angle_tolerated`
   - `teacher_faint_scan_confidence_proxy`
3. 在候选记录中输出 teacher rule 证据和分数调整。
4. 保持现有单标题栏候选仲裁语义。
5. 运行 round2 首训与 round3 重点预测回归，确认不退化。

## 非目标

本阶段不做：

- 不调用 VLM。
- 不接入 OCR。
- 不上传图纸。
- 不重训 YOLO/OBB。
- 不改标签。
- 不处理完整 PDF。
- 不发布新的固定审核入口。
- 不把 teacher 输出写入 ground truth。

## 规则落地边界

当前 OCR 字段簇仍不可用，因此本阶段不能把文字字段命中作为已落地规则。

本阶段只使用结构代理：

- 贴图纸外框线。
- 非均匀格子结构。
- `small_large_cell_mix_score`。
- `uniform_grid_like`。
- `frame_contact_score`。
- 候选是否 near edge。

后续若 OCR 可用，再把文字字段簇命中接入同一 flags 体系。

## 输入

现有通用后处理输入不变：

```text
local_data/yolo_predictions/
local_data/yolo_obb_dataset_round2/
local_data/yolo_obb_dataset_round3/
local_data/title_block_ocr_diagnostic/diagnostic_report.json
```

## 输出

仍输出到现有本地后处理目录：

```text
local_data/yolo_postprocess/round2_first_train/
local_data/yolo_postprocess/general_round3_diagnostic/
```

候选记录新增：

```text
teacher_rule_flags
teacher_rule_adjustment
teacher_rule_evidence
```

## 验证

运行：

```text
python -m py_compile scripts/yolo_obb/postprocess_yolo_obb_predictions.py
python scripts/yolo_obb/postprocess_yolo_obb_predictions.py
python scripts/yolo_obb/postprocess_yolo_obb_predictions.py --dataset-dir local_data/yolo_obb_dataset_round3 --review-form local_data/missing_review_form.csv --output-dir local_data/yolo_postprocess/general_round3_diagnostic --prediction-dirs round3_train round3_val round3_round2_test round3_round2_val --diagnostic-report local_data/title_block_ocr_diagnostic/diagnostic_report.json --diagnostic-only
```

期望：

- round2 首训仍覆盖 14 条。
- round2 的 5 条人工不可接受样本仍为 `needs_review`，不被静默放行。
- round3 重点预测仍覆盖 16 条。
- round3 仍全部 `accepted=16`。
- `aug90_002_from_sample_010` 的普通表格误检候选仍被拒绝。
- 报告中新增 teacher rule flags 和 adjustment。

## 回滚点

本计划、RPD 和 TODO 提交后作为实现 teacher 规则蒸馏到通用后处理前回滚点。

