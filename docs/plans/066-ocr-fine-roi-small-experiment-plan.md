# OCR 用细 ROI 小实验计划

## 背景

用户已完成修复后标题栏 crop 复核。结果显示：

- 63 条修复后 crop 全部判断为正确。
- 31 条标注 `范围太大`。
- 典型备注为：左半边不是标题栏，而是图纸。

上一轮调研和决策已经确认：

- 当前粗 crop 适合作为标题栏完整性 crop，不能因为范围偏大而整体打回。
- 当前粗 crop 不适合作为最终图号 OCR 的唯一主输入。
- 下一步应新增 OCR 用细 ROI 或图号字段 ROI，用来减少非标题栏图纸区域对图号识别的干扰。

## 目标

1. 在不破坏当前完整性 crop 成果的前提下，为图号 OCR 生成更小的细 ROI。
2. 对比粗 crop OCR 和细 ROI OCR 的图号候选质量。
3. 判断细 ROI 是否能减少 `范围太大` 样本中的图纸主体噪声。
4. 输出可追溯机器报告和低噪声人工审核入口。
5. 为后续是否重建 63 条图号命名审核包提供依据。

## 非目标

本轮不做：

- 不修改当前粗 crop 生成策略。
- 不废弃 63/63 完整性 crop 审核结论。
- 不执行 OCR 图像预处理增强实验。
- 不生成正式旋正 PDF。
- 不正式重命名单页 PDF。
- 不调用云端 OCR/VLM。
- 不训练或引入新的表格结构模型。
- 不把细 ROI OCR 结果直接写入最终文件名。

## 样本范围

第一轮建议处理两类样本：

1. 31 条 `范围太大` 样本：
   - `sample_001`
   - `sample_002`
   - `sample_011`
   - `sample_019`
   - `sample_024`
   - `sample_033`
   - `sample_034`
   - `sample_035`
   - `sample_036`
   - `sample_037`
   - `sample_038`
   - `sample_039`
   - `sample_040`
   - `sample_041`
   - `sample_042`
   - `sample_043`
   - `sample_044`
   - `sample_046`
   - `sample_047`
   - `sample_049`
   - `sample_050`
   - `sample_051`
   - `sample_052`
   - `sample_053`
   - `sample_054`
   - `sample_055`
   - `sample_056`
   - `sample_057`
   - `sample_059`
   - `sample_061`
   - `sample_062`
2. 旧流程中图号易错或浅字风险样本：
   - `sample_009`：右下标题栏策略样本，OCR 可能把 `10` 识别成 `1Q`。
   - `sample_035`：浅字和短横线风险。
   - `sample_042`：浅字和叠影风险。

说明：`sample_035` 和 `sample_042` 已在 31 条范围太大样本内，不重复计数。预计首轮实验样本为 32 条。

## 输入

主要输入：

```text
local_data/full_63_title_block_ocr_dry_run/crop_recovery_v1/full_63_ocr_arbitration_records.jsonl
local_data/full_63_title_block_ocr_dry_run/crop_recovery_v1/ocr_summary.csv
local_data/full_63_title_block_ocr_dry_run/crop_recovery_v1/drawing_number_candidates.csv
local_data/title_block_crop_recovery_review/filled_review_summary.json
local_data/full_63_title_block_ocr_dry_run/crop_recovery_v1/corrected_pages/
local_data/full_63_title_block_ocr_dry_run/crop_recovery_v1/crops/
```

如果某些目录名与实际 dry-run 输出不同，实现阶段必须先只读检查并记录，不得猜测路径后静默失败。

## 细 ROI 候选策略

第一轮只做可解释、本地、轻量策略：

1. `right_band_roi`
   - 从完整性 crop 的右侧区域生成候选。
   - 目标是排除左半边图纸主体和技术要求。
2. `bottom_right_table_roi`
   - 在校正后页面或完整性 crop 中寻找右下表格线密集区域。
   - 优先贴近图纸右边框和底边框。
3. `ocr_textbox_filtered_roi`
   - 使用 OCR 文本框位置过滤，只保留标题栏右侧字段附近文本。
   - 本轮若 OCR 引擎不能稳定输出文本框，则记录能力缺口，不强行伪造。
4. `keyword_anchor_roi`
   - 若能识别 `图号`、`代号`、`图样代号` 等字段名，则围绕字段名邻近区域截取。
   - 关键词锚点只能加分，不能单独自动通过。

## 输出

本地输出目录：

```text
local_data/ocr_fine_roi_experiment/
```

建议输出文件：

```text
experiment_summary.json
experiment_summary.csv
fine_roi_records.jsonl
fine_roi_records.csv
fine_roi_ocr_results.jsonl
fine_roi_ocr_results.csv
drawing_number_comparison.csv
needs_review.csv
fine_rois/
overlays/
review_pack/
```

固定审核入口：

```text
local_data/review_inbox/current/
```

若生成审核入口，本轮只放用户需要看的文件副本：

- `README.md`
- `fine_roi_review/review_index.html`
- `fine_roi_review/review_form.csv`
- `fine_roi_review/assets/`

人工表只显示：

- 序号。
- 样本编号。
- 细 ROI 判断。
- 图号判断。
- 人工确认图号。
- 备注。

HTML 只展示：

- 校正后整页。
- 当前完整性 crop。
- 细 ROI。
- 细 ROI 位置示意。
- 粗 crop OCR 摘要。
- 细 ROI OCR 摘要。
- 粗 crop 候选图号。
- 细 ROI 候选图号。

不得在人工 CSV/HTML 中暴露 bbox、score、长路径、候选列表、完整 OCR JSON 或调试字段。

## 质量门

细 ROI 被视为可用，至少需要满足：

1. ROI 位于标题栏表格区域，而不是图纸主体。
2. ROI 不截断图号尾部。
3. ROI 相比完整性 crop 明显减少非标题栏区域。
4. OCR 图号候选来自细 ROI 或与细 ROI 位置一致。
5. 图号候选符合既有图号格式和命名质量门。
6. 粗 crop 与细 ROI 候选冲突时，必须进入人工审核。

必须进入人工审核的情况：

- 细 ROI 缺失。
- 细 ROI 明显过窄或截断图号栏。
- OCR 结果只来自粗 crop 混杂区域。
- 多个 ROI 给出不同图号候选。
- 图号候选存在 `0/O`、`1/I/l`、`10/1Q`、短横线缺失等混淆风险。

## 实现阶段验收标准

计划提交后，实现阶段至少验证：

```text
python -m py_compile scripts\ocr\build_ocr_fine_roi_experiment.py
python scripts\ocr\build_ocr_fine_roi_experiment.py
```

预期：

- 只处理计划内样本。
- 每条样本生成至少一种细 ROI 尝试，或明确记录失败原因。
- 输出粗 crop OCR 与细 ROI OCR 对比报告。
- 输出低噪声固定审核入口。
- `modified_pdf=false`
- `renamed_pdf=false`

## 风险与控制

| 风险 | 控制 |
| --- | --- |
| 细 ROI 过窄，重新截断图号尾部 | 细 ROI 审核页必须同时展示完整性 crop 和位置示意 |
| 细 ROI 只靠右侧比例裁剪，泛化差 | 同时记录表格线、图框线、OCR 文本框和关键词证据 |
| 浅字样本 OCR 仍失败 | 本轮只判断 ROI 是否减少噪声，浅字增强留到 OCR 图像预处理实验 |
| 粗 crop 与细 ROI 图号冲突 | 不自动选择，进入人工审核 |
| 人工审核界面噪声过大 | 人工表只保留判断字段，技术字段放机器报告 |

## 审核与暂停点

本计划、RPD 和 TODO 提交后作为实现前回滚点。随后可进入脚本实现和小实验运行。

实现完成并生成固定审核入口后，必须等待用户审核细 ROI 和图号候选，不得直接重建 63 条命名审核包。

