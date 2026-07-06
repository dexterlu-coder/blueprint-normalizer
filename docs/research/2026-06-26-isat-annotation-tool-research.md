# ISAT 标注工具调研记录

日期：2026-06-26

## 一、问题

用户反馈：有相关评论认为 ISAT 比 Labelme 更好用。需要判断当前 YOLO/OBB 标题栏冒烟标注是否应改用 ISAT。

当前任务特点：

- 只标注 16 张冒烟样本。
- 每张图只需要一个 `title_block`。
- 目标是四点 polygon，后续转换为 Ultralytics OBB。
- 图纸不能上传，必须本地处理。
- 用户希望界面尽量少噪声，图像查看方便。

## 二、结论

建议调整为：

```text
ISAT 优先
Labelme 备用
```

原因：

1. ISAT 是本地交互式半自动标注工具，可用 `pip install isat-sam` 安装并通过 `isat-sam` 启动。
2. ISAT 支持手动 polygon，点击方式可逐点添加顶点。
3. ISAT 支持按住 `Shift` 约束水平、垂直和 45 度方向，这对标题栏、文档、标牌等规则形状有帮助。
4. ISAT 支持预览、快速浏览和逐个实例检查，人工复核体验可能比 Labelme 更好。
5. ISAT 支持 ISAT、COCO、YOLO、LABELME、VOC 等格式转换，至少具备较好的格式中转能力。

但有一个重要限制：

ISAT 官方文档中的 YOLO 转换更偏 segmentation 格式，不应直接假设它就是 Ultralytics OBB。对本项目更稳妥的方式是：

```text
ISAT 标注 polygon
  -> 导出/转换为 Labelme JSON
  -> 使用现有 convert_labelme_to_yolo_obb.py 转 YOLO OBB
```

或者后续新增 `convert_isat_to_yolo_obb.py`，直接读取 ISAT JSON 中的 `objects[].segmentation`。

## 三、与 Labelme 对比

| 维度 | ISAT | Labelme | 当前判断 |
| --- | --- | --- | --- |
| 本地运行 | 是 | 是 | 都满足 |
| 手动画 polygon | 支持 | 支持 | 都满足 |
| 规则形状辅助 | Shift 约束水平/垂直/45 度 | 支持基础 polygon，约束能力较弱 | ISAT 更优 |
| SAM 辅助 | 内置 SAM/SAM2/SAM3 等 | 有 AI 辅助，但不是它的核心优势 | ISAT 更优，但本项目可先不用 |
| 检查体验 | 有 preview、quick browsing、detail inspection | 基础查看 | ISAT 更优 |
| 格式转换 | 支持 ISAT/COCO/YOLO/LABELME/VOC | JSON 简单，易自定义转换 | 都可用 |
| 安装复杂度 | pip 可装，但 SAM 相关功能可能带来依赖压力 | pip 或独立应用，更轻 | Labelme 更轻 |
| OBB 直出 | 未确认直出 Ultralytics OBB | 不直出，需要转换 | 都需要项目转换 |

## 四、推荐流程

优先尝试 ISAT：

```text
安装 ISAT
  -> 打开 smoke 样本
  -> 用 Draw Polygon 画 4 点 title_block
  -> 导出/转换 Labelme JSON
  -> 项目脚本转换为 YOLO OBB
  -> validate + visualize
```

若 ISAT 安装或导出链路不顺，再回退 Labelme。

## 五、执行建议

下一步不要直接标注全部 16 张。建议先做 1 张兼容性验证：

1. 安装/启动 ISAT。
2. 标注 `sample_009` 或 `sample_010`。
3. 导出 Labelme JSON 或 ISAT JSON。
4. 我检查 JSON 结构。
5. 确认能转换为 YOLO OBB 后，再标注剩余 15 张。

## 六、参考

- ISAT GitHub：https://github.com/yatengLG/ISAT_with_segment_anything
- ISAT 文档：https://isat-sam.readthedocs.io/en/latest/
- ISAT 安装文档：https://isat-sam.readthedocs.io/en/latest/install.html
- ISAT 标注文档：https://isat-sam.readthedocs.io/en/latest/annotation.html
- ISAT 导出文档：https://isat-sam.readthedocs.io/en/latest/export.html
- Labelme GitHub：https://github.com/wkentaro/labelme
