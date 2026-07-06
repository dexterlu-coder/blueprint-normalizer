# 图号人工校正记忆系统计划

## 背景

用户已完成当前细 ROI 与图号候选复核，并提出需要建立一个记忆系统，用于沉淀每次人工校准图号识别时发现的规律，方便后续迁移到其他批次或项目。

当前项目已经具备：

- 细 ROI 复核入口：`local_data/review_inbox/current/fine_roi_review/`
- 机器候选记录：`local_data/ocr_fine_roi_experiment/fine_roi_records.jsonl`
- 图号候选抽取规则：`scripts/ocr/build_pdf_correction_dry_run.py`

但当前还缺少：

- 将人工校准结果从审核表稳定导入机器记录的流程。
- 保存人工校准事实、OCR 易错规律和 ROI 裁剪建议的长期记忆库。
- 可迁移导出格式，供后续项目复用。

## 目标

1. 归档当前已填写的细 ROI 审核入口，保留用户原始填写表和审核资产。
2. 建立本地私有图号校正记忆库，记录每次人工校准事实。
3. 从人工校准中提炼可迁移规律：
   - 机器候选被确认可用的样本。
   - 机器候选被人工修正的样本。
   - OCR 未识别但人工补充的图号。
   - 无法确认、需要人工识别的样本。
   - ROI 过大时的裁剪方向和比例建议。
   - OCR 字符或分段层面的常见混淆。
4. 生成机器可读 JSON/JSONL、人工可读 Markdown 摘要和可移植导出包。
5. 保持公开仓库只提交脚本、规划和规则说明，私有图号与图纸资产继续留在 `local_data/`。

## 非目标

本轮不做：

- 不自动修改图号识别算法。
- 不重新跑 OCR。
- 不重建 63 条命名审核包。
- 不执行浅字标题栏图像预处理实验。
- 不生成正式 PDF。
- 不重命名单页 PDF。
- 不把 `local_data/` 中的私有图号、图片或审核结果加入 Git。

## 记忆库设计

本地私有输出目录：

```text
local_data/drawing_number_calibration_memory/
```

建议文件：

```text
memory_events.jsonl
memory_patterns.json
memory_patterns.md
portable_export/drawing_number_calibration_memory_v1.json
portable_export/drawing_number_calibration_rules.md
```

### 事件记录

每条人工校准事件至少包含：

- `sample_id`
- `review_session_id`
- `fine_roi_judgment`
- `drawing_number_judgment`
- `machine_fine_candidate`
- `machine_coarse_candidate`
- `manual_confirmed_drawing_number`
- `final_drawing_number`
- `calibration_outcome`
- `human_note`
- `roi_note_tags`
- `modified_pdf=false`
- `renamed_pdf=false`

### 规律记录

规律摘要至少包含：

- 图号判断统计。
- ROI 判断统计。
- 机器候选通过、人工修正、人工补充、无法确认数量。
- OCR 候选与人工确认之间的差异对。
- 可复用的 ROI 裁剪建议标签。
- 需要保留人工识别兜底的样本列表。

## 固定审核入口处理

当前入口：

```text
local_data/review_inbox/current/fine_roi_review/
```

执行后必须：

1. 归档到 `local_data/review_inbox/archive/`。
2. 在归档目录保留原始 `review_form.csv`、HTML、manifest 和图片资产。
3. 重置 `local_data/review_inbox/current/README.md`，说明当前无待审核任务。
4. 记录归档位置。

## 验收标准

1. 能自动读取当前人工审核 CSV，包括 `utf-8-sig`、`utf-8`、`gb18030` 等常见编码。
2. 能将 32 条审核记录与机器候选记录按 `sample_id` 对齐。
3. 能输出人工校准事件、规律摘要和可迁移导出包。
4. 能归档当前固定审核入口并重置 `current`。
5. 输出 summary 明确 `modified_pdf=false`、`renamed_pdf=false`。
6. `git status --short` 不显示 `local_data/` 私有数据进入 Git。
7. 脚本通过 `python -m py_compile`。

## 回滚准备

本计划、RPD 和 TODO 提交后作为实现前回滚点。若记忆库 schema 或归档流程不合适，可回退到该提交后重新设计。

