# OCR 图像预处理小实验计划

## 背景

OCR 图像预处理增强调研已经完成，结论是：对不清晰标题栏 crop，成熟做法不是覆盖原图或套单一滤镜，而是保留原始 crop，生成多个增强派生版本，分别 OCR，再用字段簇、图号候选和命名质量门判断是否真正改善。

当前 63 张全量标题栏 crop/OCR dry-run 中：

- `auto_dry_run_ready=40`
- `blocked=21`
- `needs_human_review=2`
- 非自动放行样本合计 23 条

本轮计划只针对这 23 条异常样本做小实验。

## 本轮目标

1. 为 23 条非自动放行样本生成有限数量的图像增强版本。
2. 对原图和增强版本分别运行 OCR。
3. 比较字段簇、图号候选、低置信/缺失/重名风险是否改善。
4. 输出机器报告和低噪声人工审核入口。
5. 不修改原始 crop、不正式重命名 PDF、不改 ground truth。

## 非目标

本轮不做：

- 不处理 40 条已自动 dry-run ready 样本。
- 不覆盖 `local_data/full_63_title_block_ocr_dry_run/crops/` 原始 crop。
- 不正式生成旋正 PDF。
- 不正式重命名单页 PDF。
- 不调用云端 OCR/VLM。
- 不引入深度学习超分辨率或生成式增强。
- 不切换 OCR 引擎。
- 不把增强 OCR 结果直接写入最终文件名。

## 输入

主要输入：

```text
local_data/full_63_title_block_ocr_dry_run/pdf_correction_dry_run_v2/dry_run_summary.csv
local_data/full_63_title_block_ocr_dry_run/full_63_ocr_arbitration_records.jsonl
local_data/full_63_title_block_ocr_dry_run/crops/
```

样本范围：

- `route != auto_dry_run_ready` 的 23 条记录。
- 包括：
  - `drawing_number_missing`
  - `drawing_number_low_confidence`
  - `ocr_field_cluster_not_strong`
  - `duplicate_filename_candidate`

## 增强配方

第一轮只测试 6 个版本，避免变量过多：

| recipe | 内容 | 目的 |
| --- | --- | --- |
| `original` | 原始 crop | baseline |
| `gray_clahe` | 灰度 + CLAHE | 提升浅扫描局部对比 |
| `gray_clahe_unsharp` | 灰度 + CLAHE + 小强度锐化 | 提升文字边缘 |
| `denoise_otsu` | 轻度去噪 + Otsu 二值化 | 降噪后强化文字 |
| `adaptive_gaussian` | 轻度去噪 + 自适应 Gaussian 阈值 | 处理背景不均 |
| `upscale2x_clahe_unsharp` | 2x 放大 + CLAHE + 小强度锐化 | 改善小字号 OCR |

参数原则：

- CLAHE 使用保守 clip limit。
- 锐化强度必须小，避免表格线压过文字。
- 二值化版本保留为派生图，不替代灰度版本。
- 若某 recipe 出错，记录失败，不中断其他 recipe。

## 输出

本地输出目录：

```text
local_data/ocr_image_preprocessing_experiment/
```

建议文件：

```text
experiment_summary.json
experiment_summary.csv
variant_ocr_results.jsonl
variant_ocr_results.csv
best_variant_candidates.csv
needs_review.csv
preprocessed_crops/
review_pack/
```

固定审核入口：

```text
local_data/review_inbox/current/
```

若生成审核入口，本轮只放用户需要看的文件副本：

- `README.md`
- `review_index.html`
- `review_form.csv`
- `assets/`

人工表只显示：

- 样本编号。
- 当前阻断原因。
- 原始 crop。
- 最佳增强 crop。
- 原始 OCR 摘要。
- 最佳增强 OCR 摘要。
- 原候选图号。
- 增强候选图号。
- 人工判断。
- 人工确认图号。
- 备注。

机器字段、完整 OCR、recipe 参数、路径和候选列表放在 JSON/CSV 机器报告中，不放入人工填写表。

## 选择逻辑

每个样本比较所有版本：

1. 优先看是否从 `missing` 变成有图号候选。
2. 再看是否从低置信变成高置信。
3. 再看字段簇是否从 weak 变 strong。
4. 若多个版本给出冲突图号，不自动选择，进入人工复核。
5. 若增强版本比原图差，保留原图结果。
6. 如果最佳增强结果仍存在重名、低置信、字段簇弱或缺失，继续阻断或人工复核。

## 质量门

必须满足：

1. 原始 crop 不被覆盖。
2. 23 条输入记录数量不变。
3. 每个样本至少有 `original` 版本结果。
4. 每个增强版本的 recipe 和参数可追溯。
5. 输出明确记录每条是否改善。
6. 增强结果不得绕过命名质量门。
7. 仍不得生成正式 PDF 或正式重命名。
8. 审核入口必须在 `local_data/review_inbox/current/`。

## 验收标准

计划审核通过后，实现阶段至少验证：

```text
python -m py_compile scripts\ocr\build_ocr_image_preprocessing_experiment.py
python -m scripts.ocr.build_ocr_image_preprocessing_experiment
```

预期：

- 只处理 23 条异常样本。
- 生成增强 crop 派生图。
- 输出原图与增强图 OCR 对比报告。
- 输出低噪声人工审核入口。
- `modified_pdf=false`
- `renamed_pdf=false`

## 风险与控制

| 风险 | 控制 |
| --- | --- |
| 增强让表格线压过文字 | 多 recipe 对比，失败版本不采纳 |
| 二值化吞掉小字 | 保留灰度/CLAHE 版本和原图 baseline |
| 锐化放大噪声 | 使用小强度参数，并记录 recipe |
| 增强产生冲突图号 | 进入人工复核，不自动选择 |
| 人工界面噪声过大 | 技术字段放机器报告，人工表只留必要字段 |

## 审核点

本计划需要用户审核后才能进入实现阶段。审核通过前，不生成增强图、不运行 OCR 小实验、不更新固定审核入口。
