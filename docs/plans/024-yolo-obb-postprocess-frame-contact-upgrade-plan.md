# YOLO/OBB 后处理贴图框线规则升级计划

## 背景

YOLO/OBB 后处理失败样本复查已完成。用户补充了比“靠近页面边缘”更强的业务规律：

- 标题栏一定会贴着图纸边缘的框线。
- 标题栏和图纸周围的框线不会存在任何空隙。
- 这个规律可以有效区分长得像标题栏的零件和真正标题栏。

当前 `scripts/yolo_obb/postprocess_yolo_obb_predictions.py` 只计算：

- `edge_proximity_score`：候选框是否靠近页面边缘。
- `center_region_penalty`：候选框中心是否落在页面主体区域。

这两个字段不足以表达“是否贴住图纸外框线”。复查结果也显示 `test/aug90_002_from_sample_010` 被误判为 `part_false_positive`，用户确认该样本识别没有错误，因此后处理需要更精细的贴图框线证据来降低误伤。

## 目标

1. 为后处理脚本新增图框线接触证据。
2. 将 `edge_proximity_score` 升级为 `frame_contact_score` 的辅助证据，而不是唯一几何依据。
3. 对候选框是否贴住图纸外框线输出可解释字段。
4. 降低零件误检样本自动通过风险。
5. 避免误伤用户确认可接受的 `test/aug90_002_from_sample_010`。

## 非目标

本轮不做：

- 不重新训练模型。
- 不修改 YOLO/OBB 数据集标签。
- 不发布新的人工审核入口。
- 不处理完整 PDF。
- 不引入 OCR/VLM。
- 不要求图框线检测达到完整 CAD 解析级别。

## 输入输出

继续使用现有后处理脚本输入：

```text
local_data/yolo_predictions/
local_data/yolo_obb_dataset_round2/
local_data/review_inbox/archive/round2_prediction_review_20260627_reviewed/prediction_review/review_form.csv
```

继续输出到：

```text
local_data/yolo_postprocess/round2_first_train/
```

输出文件保持兼容：

- `postprocess_report.json`
- `postprocess_summary.csv`
- `failure_case_manifest.json`

## 图框线检测策略

第一版采用轻量 OpenCV/图像投影策略：

1. 读取数据集原图。
2. 转灰度并二值化，提取暗色线条。
3. 在页面四周边缘带内统计暗像素投影。
4. 对每个方向估计最可能的图纸外框线位置：
   - left frame line
   - right frame line
   - top frame line
   - bottom frame line
5. 若某方向图框线证据不足，标记为 `unknown`，不静默通过。

该策略只服务于后处理质量门，不替代 OpenCV 主算法或人工标注。

## 候选框贴边计算

对每个预测候选：

1. 计算候选 bbox 到四个页面方向的距离。
2. 找到候选最靠近的图纸外框方向。
3. 将候选靠外侧 bbox 边与对应图框线位置比较。
4. 输出：
   - `nearest_frame_side`
   - `frame_line_position_normalized`
   - `frame_contact_gap_normalized`
   - `frame_contact_score`
   - `touches_frame_line`
   - `frame_contact_status`

建议初始阈值：

- `frame_search_band=0.18`：只在页面四周 18% 范围内找图框线。
- `frame_contact_threshold=0.025`：候选外侧边与图框线距离不超过 2.5% 页面尺度，视为接触。
- `frame_weak_threshold=0.004`：边缘带投影过弱时，认为该方向图框线证据不足。

阈值必须写入 `postprocess_report.json` 的 `config` 字段。

## 后处理规则调整

### 真实标题栏加权

若候选满足：

- `touches_frame_line=true`
- 面积不异常
- 不明显越界

则即使候选中心落在当前 `center_region` 范围，也不应直接标记为 `part_false_positive`。

该规则用于保护 `test/aug90_002_from_sample_010` 这类用户确认可接受样本。

### 零件误检降权

若候选满足：

- 位于图纸主体中部，或
- 与最近图框线存在明显间隙，或
- 图框线方向无法确认且候选不靠近任何边缘

则追加或保留 `part_false_positive`，并进入 `needs_review`。

### 图框线证据缺失

若图框线无法稳定检测：

- 不得自动通过疑似异常样本。
- 输出 `frame_contact_unknown`。
- 对原本已 accepted 的强正例不强制打回，但在报告中记录图框线证据不足。

## 回归样本

必须重点检查：

| 样本 | 期望 |
| --- | --- |
| `test/aug90_002_from_sample_010` | 不再因为中心区域惩罚被标记为 `part_false_positive` |
| `test/sample_001` | 继续进入 `needs_review`，保持零件误检风险 |
| `test/sample_010` | 继续进入 `needs_review`，保留范围过大问题 |
| `val/sample_009` | 继续进入 `needs_review`，保留多候选和补标需求 |
| `test/unclear90_001_from_sample_001` | 继续进入 `needs_review`，保留多候选/零件误检 |

## 验证标准

实现后最低验证：

1. `python -m py_compile scripts\yolo_obb\postprocess_yolo_obb_predictions.py` 通过。
2. `python scripts\yolo_obb\postprocess_yolo_obb_predictions.py` 通过。
3. 报告仍覆盖 14 条 val/test 样本。
4. `postprocess_report.json` 包含 `frame_detection` 和候选级 `frame_contact_*` 字段。
5. `test/aug90_002_from_sample_010` 不再出现 `part_false_positive`。
6. 用户确认不可接受的 5 条样本不得全部进入 `accepted`。
7. 多候选样本仍不得静默通过。
8. `git status --short` 不包含 `local_data/` 输出文件。

## 风险

- 扫描裁切、浅色图框线或噪声会导致图框线检测不稳定。
- OBB 框的外侧边不一定完全等于 bbox 外侧边，第一版用 bbox 是保守近似。
- 阈值过严会误伤真实标题栏，阈值过宽会放过零件误检。
- 因此第一版只用于 val/test 14 张后处理报告，不进入完整 PDF 批处理。

## 回滚点

本计划、RPD 和 TODO 提交后作为实现贴图框线后处理升级前的回滚点。

