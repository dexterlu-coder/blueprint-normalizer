# 63 张全量 PDF dry-run 测试计划

## 背景

当前 `scripts/ocr/build_pdf_correction_dry_run.py` 已在 30 条仲裁记录上运行，验证了：

- 不会在缺少单页 PDF 路径时伪造旋正输出。
- 能保存已有 OCR 文本。
- 能抽取图号候选。
- 能发现命名风险。

但这 30 条记录来自 round2/round3 和增强样本回放，不是完整 63 张原始单页 PDF 链路。仓库中已经存在完整实验资产：

- 原始图纸包 PDF：`local_data/source_pdfs/`
- 已拆分单页 PDF：`local_data/experiment_samples/all/pdf/`
- 渲染 PNG：`local_data/experiment_samples/all/png/`
- 人工确认 ground truth：`local_data/ground_truth/rotation_ground_truth.json`

因此需要做一次 63 张全量 dry-run 测试，把真实单页 PDF 路径接入链路，验证下一阶段风险分布。

## 本轮目标

1. 基于 63 条人工确认 ground truth 构建全量 dry-run 输入记录。
2. 每条记录绑定：
   - `sample_id`
   - 单页 PDF 路径
   - 渲染 PNG 路径
   - 标题栏位置
   - 旋转角度
   - 校正角度
3. 复用 `scripts/ocr/build_pdf_correction_dry_run.py` 生成全量 dry-run 报告。
4. 验证 63 张是否都能匹配单页 PDF 和 PNG。
5. 验证 dry-run 是否仍不覆盖 PDF、不正式重命名。
6. 统计全量图号候选、命名风险、阻断原因和可进入下一阶段的样本数。

## 非目标

本轮不做：

- 不覆盖原始 PDF。
- 不把候选旋正 PDF 写回业务目录。
- 不正式按图号重命名。
- 不调用云端 VLM。
- 不修改 ground truth。
- 不新增人工审核入口。
- 不重新训练 YOLO/OBB。

## 输入

默认输入：

```text
local_data/ground_truth/rotation_ground_truth.json
local_data/experiment_samples/all/pdf/
local_data/experiment_samples/all/png/
```

注意：

- `all/png/` 中存在 `.json` 标注文件和 `isat.yaml`，不能按目录文件总数盲跑。
- 必须以 ground truth 的 63 个 `sample` 为主键精确匹配。

## 输出

建议输出到：

```text
local_data/full_63_pdf_dry_run/
```

建议文件：

- `full_63_arbitration_records.jsonl`
- `full_63_input_manifest.csv`
- `missing_assets.csv`
- `pdf_correction_dry_run/dry_run_records.jsonl`
- `pdf_correction_dry_run/dry_run_summary.json`
- `pdf_correction_dry_run/dry_run_summary.csv`
- `pdf_correction_dry_run/drawing_number_candidates.csv`
- `pdf_correction_dry_run/naming_risks.csv`
- `pdf_correction_dry_run/needs_review.csv`

## 输入记录策略

第一版不重新跑 YOLO/OBB 或 OCR，只用人工确认 ground truth 建立全量 dry-run 输入骨架。

每条构造出的记录应满足：

- `page.single_page_pdf_path` 指向 `local_data/experiment_samples/all/pdf/YKJ125-00-00-2525_sample_XXX.pdf`
- `page.rendered_image_path` 指向 `local_data/experiment_samples/all/png/YKJ125-00-00-2525_sample_XXX.png`
- `arbitration.decision_status=auto_accept`
- `arbitration.title_block_position` 来自 ground truth
- `rotation.detected_rotation_degrees` 来自 ground truth
- `rotation.correction_degrees=(360 - rotation_degrees) % 360`
- `rotation.rotation_ready=true`
- `ocr.ocr_text=""`
- `drawing_number.selection_status=not_attempted`
- `output_plan.dry_run_only=true`

这样可以先测试 PDF 路径接入、旋正计划、命名风险闸门和 dry-run 输出结构。

## 预期结果

因为第一版全量输入不重新跑标题栏 OCR，预期：

- 63 条都应匹配单页 PDF。
- 63 条都应匹配渲染 PNG。
- 63 条都应生成候选旋正 PDF 路径。
- 不实际写出候选旋正 PDF。
- 不实际重命名。
- 图号候选大概率全部缺失或无法自动命名。
- `can_rotate_pdf` 可以为 true，因为 PDF 路径、旋转角度和 auto_accept 已具备。
- `can_rename` 应为 false，因为图号抽取未完成。

若 `can_rotate_pdf` 不为 63，需要检查路径映射、PDF 文件存在性或旋转角度字段。

## 验证标准

1. `full_63_arbitration_records.jsonl` 有 63 条。
2. `missing_assets.csv` 数据行数为 0。
3. dry-run 汇总中 `record_count=63`。
4. `modified_pdf=false`。
5. `renamed_pdf=false`。
6. 所有记录 `dry_run_only=true`。
7. 所有单页 PDF 路径存在。
8. 所有 PNG 路径存在。
9. 无正式输出覆盖。
10. 图号缺失和命名阻断被明确记录。

## 后续分支

若本轮通过：

1. 再规划“全量标题栏 crop/OCR 小批量或全量执行”。
2. 只对标题栏 crop 跑 OCR，不做整页 OCR。
3. 复用本轮 63 条 PDF 映射记录，填充 OCR 文本和图号候选。
4. 继续 dry-run 命名，不正式重命名。

若本轮不通过：

1. 优先修正 PDF/PNG/sample 映射。
2. 不进入 OCR 和命名阶段。

