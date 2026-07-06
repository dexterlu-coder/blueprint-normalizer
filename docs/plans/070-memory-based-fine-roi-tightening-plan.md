# 基于人工记忆的细 ROI 收窄实验计划

## 背景

上一轮细 ROI 与图号候选审核已经归档，并生成图号人工校正记忆库。

关键结论：

- 32 条样本的 `细ROI判断` 全部为 `范围太大`。
- 高频人工建议为：
  - 上侧减少约 20%。
  - 左侧向右减少约 25%。
- 本轮用户明确要求集中处理 ROI 收窄，暂时不把图号识别正确性作为优化目标。

## 目标

1. 基于人工记忆生成新版收窄细 ROI。
2. 生成旧 ROI、新 ROI 和新旧位置对比图，方便人工判断收窄效果。
3. 发布低噪声固定审核入口，只要求用户判断新版 ROI 是否更合适。
4. 保留图号 OCR 只作为机器侧护栏，不进入人工填写表。
5. 输出机器报告，记录面积变化、收窄策略、资产缺失和安全标记。

## 非目标

本轮不做：

- 不修正图号识别规则。
- 不把 OCR 图号正确性作为本轮优化指标。
- 不重新生成 63 条图号命名审核包。
- 不执行浅字标题栏 OCR 图像预处理实验。
- 不生成正式 PDF。
- 不重命名单页 PDF。
- 不把 `local_data/` 中的私有图片、审核结果或记忆库加入 Git。

## 收窄策略

输入：

- `local_data/drawing_number_calibration_memory/current_session_events.csv`
- `local_data/ocr_fine_roi_experiment/fine_roi_records.jsonl`
- `local_data/ocr_fine_roi_experiment/fine_roi_ocr_results.jsonl`

规则：

- 对 `上侧减少约N%`：在旧 ROI 内将上边界向下移动 `N% * ROI高度`。
- 对 `左侧向右减少约N%`：在旧 ROI 内将左边界向右移动 `N% * ROI宽度`。
- 对“蓝框更好”样本：优先用旧候选中的 `bottom_right_band_roi` 作为基础框，再应用明确的左侧收窄。
- 对 `sample_009`：按人工建议生成收窄 ROI，但保持人工兜底标记，不允许自动命名。
- 若收窄后宽高低于安全阈值，则保留旧 ROI 并标记为 `tightening_rejected_too_small`。

## 审核入口

固定入口：

```text
local_data/review_inbox/current/
```

本轮文件：

```text
README.md
fine_roi_tightening_review/review_index.html
fine_roi_tightening_review/review_form.csv
fine_roi_tightening_review/review_manifest.json
fine_roi_tightening_review/assets/
```

人工 CSV 只保留：

- `序号`
- `样本编号`
- `新版ROI判断`
- `相对旧ROI是否更好`
- `问题类型`
- `备注`

## 验收标准

1. 覆盖 32 条上一轮细 ROI 审核样本。
2. 审核入口资产缺失数为 0。
3. 人工 HTML 展示完整性 crop、旧 ROI、新 ROI、新旧位置对比图。
4. 人工 CSV 不暴露 bbox、score、长路径、JSON、OCR 候选或完整 OCR 文本。
5. 输出 summary 包含面积变化统计、收窄策略统计、`modified_pdf=false`、`renamed_pdf=false`。
6. `local_data/review_inbox/current/` 只包含本轮需要用户直接打开、填写或参考的文件。
7. 脚本通过 `python -m py_compile`。

## 回滚准备

本计划、RPD 和 TODO 提交后作为实现前回滚点。若收窄策略过激或审核界面不适合人工判断，可回退到该提交后重新设计。
