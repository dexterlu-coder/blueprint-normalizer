# 标题栏 OCR 与后处理诊断脚本实现计划

## 背景

`docs/plans/032-ocr-title-block-diagnostic-experiment-plan.md` 已明确实验目标：用字段簇、贴图框线、位置和表格结构证据解释历史误检、多候选和保护性正例。

本阶段进入脚本实现前规划。按照项目规则，本计划、RPD 和 TODO 提交后，才允许新增脚本并运行本地诊断实验。

## 目标

1. 新增一个本地诊断脚本，读取 round3 预测候选和 round3 manifest。
2. 对计划中的重点样本输出候选 crop、overlay、CSV 摘要、JSON 机器报告和 HTML 查看页。
3. 复用现有后处理中的预测标签解析、图框线检测和贴边评分思路。
4. 增加表格结构诊断：横竖线密度、单元格估算、格子面积差异、均匀网格惩罚。
5. 增加 OCR 可用性探测：若本地 OCR 不可用，明确输出 `ocr_unavailable`，不阻塞其他诊断证据。

## 非目标

本阶段不做：

- 不重新训练 YOLO/OBB。
- 不改 YOLO 标签。
- 不改已有后处理最终决策。
- 不发布固定审核入口。
- 不处理完整 PDF。
- 不安装 OCR 依赖；若依赖缺失，只记录不可用。

## 新增脚本

计划新增：

```text
scripts/ocr/build_title_block_ocr_diagnostic.py
```

默认输出：

```text
local_data/title_block_ocr_diagnostic/
```

默认输入：

```text
local_data/yolo_predictions/
local_data/yolo_obb_dataset_round3/round3_manifest.csv
```

## 样本与候选选择

脚本默认覆盖以下样本：

- `sample_001`
- `unclear90_001_from_sample_001`
- `sample_009`
- `sample_010`
- `sample_020`
- `aug90_002_from_sample_010`
- `aug90_007_from_sample_020`
- `sample_040`

候选来源按优先级读取：

1. `round3_train`
2. `round3_val`
3. `round3_round2_test`
4. `round3_round2_val`

同一样本若在多个预测目录出现，保留每个 `(prediction_dir, sample)` 组合，便于观察回归差异。

## 实现策略

### 1. 预测标签读取

- 复用 YOLO OBB 预测标签格式：`class x1 y1 x2 y2 x3 y3 x4 y4 [confidence]`。
- 对缺失标签输出 `missing_prediction_label`。
- 对格式错误输出 `format_error`，不中断其他样本。

### 2. 图片路径解析

优先从 round3 manifest 找样本图片：

- 读取 `sample -> image_path` 映射。
- 对预测目录中存在但 manifest 不含的样本，回退搜索 round2 数据集图片或预测图。
- 若原始图片缺失，仍记录错误并跳过 crop/结构诊断。

### 3. 候选裁剪与 overlay

- 使用候选 OBB 的归一化点转像素点。
- crop 先用外接矩形，保留少量 padding，保证稳定。
- overlay 在原图上绘制候选多边形、候选编号和诊断摘要。

本轮不强制实现透视旋正裁剪，避免把几何变换引入新误差；如后续 OCR 需要，再单独规划。

### 4. 图框贴边与位置证据

- 复用 `postprocess_yolo_obb_predictions.py` 中的图框线检测和贴边评分思路。
- 输出：
  - `touches_frame_line`
  - `frame_contact_score`
  - `frame_gap_px`
  - `nearest_frame_side`
  - `candidate_side`
  - `rotation_angle_from_candidate`

### 5. OCR 字段簇

脚本按可用性探测 OCR：

1. 优先尝试 `pytesseract`。
2. 若不可用，记录：
   - `ocr_engine=unavailable`
   - `ocr_status=ocr_unavailable`
   - 字段簇命中为空。

本阶段不安装依赖、不联网下载 OCR 模型。

字段簇统计：

- 人员与流程字段簇：设计、制图、校对、工艺、标准、标准化、审核、批准、日期。
- 图纸属性字段簇：图名、名称、图号、图样代号、材料、比例、重量、表面积、单位。

### 6. 表格结构诊断

对 crop 灰度图做二值化和线条提取：

- 横线/竖线密度。
- 轮廓/交叉区域估算单元格数量。
- 单元格面积方差。
- 小格/大格混合分数。
- 均匀网格惩罚。

若图像过小或线条提取失败，记录 `structure_status=insufficient_grid`.

## 输出

```text
local_data/title_block_ocr_diagnostic/diagnostic_manifest.csv
local_data/title_block_ocr_diagnostic/diagnostic_report.json
local_data/title_block_ocr_diagnostic/review_summary.html
local_data/title_block_ocr_diagnostic/crops/
local_data/title_block_ocr_diagnostic/overlays/
```

CSV 只保留高价值摘要：

- prediction_dir
- sample
- candidate_index
- prediction_count
- confidence
- candidate_side
- touches_frame_line
- frame_contact_score
- frame_gap_px
- role_field_hits
- property_field_hits
- field_cluster_score
- grid_line_density
- cell_count_estimate
- cell_area_variance
- uniform_grid_penalty
- diagnostic_flags

完整 OCR 文本、路径、参数和中间证据写入 JSON。

## 验证命令

计划执行：

```text
python -m py_compile scripts/ocr/build_title_block_ocr_diagnostic.py
python scripts/ocr/build_title_block_ocr_diagnostic.py
```

运行后检查：

- JSON/CSV/HTML 是否生成。
- `crops/` 和 `overlays/` 是否非空。
- 是否覆盖 8 个计划样本。
- 每个样本至少有一条诊断记录，或有明确缺失原因。
- `local_data/` 不进入 Git。

## 质量门

1. 脚本错误不能静默吞掉，必须进入 `errors` 或候选 flags。
2. OCR 不可用不能导致实验失败。
3. 多候选样本不能被直接判失败，只输出证据。
4. 保护性正例不能被脚本强行标记为不可接受；本脚本只做诊断。
5. 运行完成后必须把摘要写回 RPD/TODO，并提交公开源码和文档。

## 回滚点

本计划、RPD 和 TODO 提交后作为脚本实现前回滚点。

