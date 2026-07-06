# YOLO/OBB 标签可视化与数据集校验工具计划

## 背景

YOLO/OBB 调试方案调研已经确认：正式标注和训练前，必须先具备两个基础工具：

1. 标签可视化：把 OBB 标签画回原图，人工确认框是否圈住标题栏。
2. 数据集校验：检查标签格式、坐标范围、类别、图片/标签匹配和同源拆分泄漏。

## 目标

新增两个本地脚本：

- `scripts/yolo_obb/visualize_obb_labels.py`
- `scripts/yolo_obb/validate_obb_dataset.py`

它们只处理本地文件，不上传图纸，不依赖 Ultralytics，不启动训练。

## 输入约定

默认使用本地忽略目录：

- 图片清单：`local_data/yolo_obb_annotation_pack/smoke/smoke_manifest.csv`
- 标签目录：`local_data/yolo_obb_annotation_pack/smoke/labels/`
- 可视化输出：`local_data/yolo_obb_annotation_pack/smoke/overlays/`

标签格式为 Ultralytics OBB：

```text
class_index x1 y1 x2 y2 x3 y3 x4 y4
```

坐标为归一化坐标，必须在 `[0, 1]` 范围内。

## 可视化脚本范围

`visualize_obb_labels.py` 需要：

- 读取 manifest 中的图片路径。
- 寻找对应 `.txt` 标签文件。
- 将归一化四点坐标转换为像素坐标。
- 在图片上绘制 OBB 多边形、类别名、样本编号。
- 输出 overlay PNG。
- 对缺失标签和空标签给出清晰提示。

## 校验脚本范围

`validate_obb_dataset.py` 需要检查：

- manifest 是否可读取。
- 图片是否存在。
- 标签文件是否存在。
- 每行是否恰好 9 个字段。
- 类别 id 是否为 `0`。
- 坐标是否为数字且在 `[0, 1]` 内。
- 多边形面积是否大于 0。
- 同一 `source_sample` 是否跨多个 split。
- 输出 JSON 和 CSV 报告。

## 验收标准

- 两个脚本能在当前尚未标注的 smoke 集上运行。
- 当前阶段允许报告 16 个缺失标签，因为人工还没画 OBB 框。
- 输出报告位于 ignored 本地目录，不进入 Git。
- 公开仓库只提交脚本、RPD 和 TODO。

## 后续步骤

脚本完成后，下一步才进入人工标注 16 张标题栏 OBB 框。标注完成后必须先运行：

```text
validate_obb_dataset.py
visualize_obb_labels.py
```

然后人工查看 overlay 图，确认无误后再考虑 YOLO/OBB 训练冒烟。

