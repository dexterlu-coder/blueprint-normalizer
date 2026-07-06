# 标题栏 crop 生成策略修复计划

## 背景

标题栏 crop 完整性专项审核已经完成并归档。63 条样本中，27 条完整，36 条未完整；主要问题是标题栏右侧图名/图号栏未全部覆盖。抽样视觉核对确认：

- `sample_006`、`sample_016`：右侧少量截断，图号尾部或比例栏贴近旧框边界。
- `sample_008`：旧框只覆盖左下技术要求和签字区，右侧图名/图号栏缺失。
- `sample_009`：旧框混入底部零件视图，真实右下标题栏未完整进入。
- `sample_035`、`sample_042`：crop 基本完整，但图号区域偏浅或有叠影，应留到图像预处理小实验处理。

当前 `scripts/ocr/build_full_63_title_block_ocr_dry_run.py` 使用 `outputs/rotation-detection/stage1/results.json` 中的 `best_candidate.bbox`，再加固定 `CROP_PADDING_RATIO=0.03` 裁剪。这会把 stage1 的局部候选错误直接传给 OCR 和命名审核。

## 目标

1. 修复标题栏 crop 生成源头，不再仅依赖 stage1 `best_candidate.bbox`。
2. 在已知正确旋转方向的基础上，先生成校正后页面，再在校正坐标系中生成完整标题栏 crop。
3. 对底部标题栏优先向右侧图名/图号栏和图纸外框线扩展。
4. 对明显只覆盖左半标题栏或混入主体的旧框，生成更保守的底部整带标题栏候选。
5. 产出修复后 crop、overlay、机器摘要和固定审核入口，供人工复核。
6. 在人工确认前，不恢复图号命名审核，不生成正式 PDF，不重命名 PDF。

## 非目标

- 不做 OCR 图像预处理增强。
- 不调整图号抽取评分规则。
- 不生成正式旋正 PDF。
- 不重命名 PDF。
- 不把修复后的 crop 自动视为通过。

## 技术策略

### 坐标系

1. 读取 `record["rotation"]["correction_degrees"]`。
2. 将原始页面 PNG 按 correction 角度旋正，得到校正后页面。
3. 将 stage1 `best_candidate.bbox` 从原始坐标变换到校正坐标，作为弱提示框。
4. 后续 crop 生成只在校正坐标系中进行。

### 完整标题栏候选

优先生成底部标题栏区域：

1. 在校正后页面下方 35% 到 45% 高度范围内寻找图框线和表格线。
2. 以弱提示框的底部位置作为参考，但不让它限制右边界。
3. 对标题栏候选的右边界，优先扩展到图纸内框右边界或页面安全边界。
4. 对标题栏候选的左边界，保留签字区和技术要求区域，避免只截右半部分。
5. 对明显异常旧框：
   - 宽度小于校正页面宽度 65%。
   - 右边界距离页面或图框右侧过远。
   - 框内标题栏表格线比例不足。
   - 使用保守底部整带候选替代。

### 质量门

每条记录输出：

- `crop_strategy`。
- `crop_box_px_corrected`。
- `stage1_hint_box_px_corrected`。
- `right_extension_applied`。
- `bottom_band_fallback_applied`。
- `needs_human_crop_review`。

凡命中以下情况，必须进入人工复核：

- 原审核中未完整。
- 使用底部整带 fallback。
- 右侧扩展超过原框宽度 20%。
- crop 高度或宽度超出经验范围。
- OCR 字段簇仍弱或未识别。

## 输出

修复 dry-run 输出目录建议：

```text
local_data/full_63_title_block_ocr_dry_run/crop_recovery_v1/
```

固定审核入口：

```text
local_data/review_inbox/current/title_block_crop_recovery_review/
```

审核入口必须包含：

- `review_index.html`
- `review_form.csv`
- `review_manifest.json`
- `assets/pages_corrected/`
- `assets/crops_recovered/`
- `assets/overlays_recovered/`

人工 CSV 只保留：

- `序号`
- `样本编号`
- `修复后crop判断`
- `问题类型`
- `备注`

## 验收标准

1. `sample_006`、`sample_016` 的右侧图号/比例栏不再被旧框截断。
2. `sample_008`、`sample_022`、`sample_032`、`sample_045`、`sample_048` 不再只覆盖左半标题栏。
3. `sample_009` 不再把主体零件视图作为主要 crop，必须完整覆盖右下标题栏。
4. 修复后审核包包含 63 条样本。
5. 固定审核入口只包含本轮待审核文件。
6. 人工 CSV 和 HTML 不暴露 bbox、score、候选 JSON、长路径或内部阻断字段。
7. 生成正式 PDF 与重命名 PDF 均保持 false。
8. 在用户审核修复后 crop 前，不继续重建图号命名审核包。

## 回滚准备

实现前提交本计划、RPD 和 TODO。若修复策略不可用，可回退到该提交，并继续保留已归档的用户审核结果：

```text
local_data/review_inbox/archive/title_block_crop_review_20260629_reviewed/
local_data/title_block_crop_quality_review/
```

