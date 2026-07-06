# YOLO/OBB 调试方案取经笔记

日期：2026-06-25

## 一、学习目标

- 我们真正要解决的问题：在正式标注和训练标题栏 detector 前，建立一套可复用的 YOLO/OBB 调试协议。
- 本轮不做的事情：不安装训练依赖、不训练模型、不绘制真实 OBB 标签、不接入 VLM。
- 最终沉淀物：样本索引、调试笔记、标题栏 detector 调试协议。

## 二、关键判断

这次调研后，我认为用户的提醒非常关键：YOLO/OBB 不能直接进入“标注 -> 训练 -> 看准确率”。在小样本工程图纸场景里，最容易失败的不是模型参数，而是：

- 标注规则不一致。
- OBB 点序或坐标格式错误。
- 训练/验证拆分泄漏，尤其是原图和增强图同源。
- 模型只记住固定位置，而不是真的学会标题栏。
- 检测框正确但后处理把位置映射错。
- mAP 看起来可以，但实际方向判断不可靠。

## 三、对象模型

本项目的 YOLO/OBB 调试对象应拆成：

- `AnnotationRule`：标题栏主体、明细表边界、裁切标题栏、相似表格的标注规则。
- `OBBLabel`：`class_index x1 y1 x2 y2 x3 y3 x4 y4`，归一化四点坐标。
- `DatasetSplit`：按源图分组，避免原图和增强图泄漏。
- `SmokeSet`：16 张小样本，覆盖 `left/right/top/bottom` 和重点样本。
- `TrainingRun`：模型、参数、训练日志、plots、权重。
- `PredictionArtifact`：预测框图、保存的预测坐标、置信度。
- `PostprocessDecision`：框中心/边缘位置到标题栏粗位置和旋转角度的映射。
- `ErrorCase`：漏检、误检、定位不准、后处理错误、标注错误。

## 四、横向结论

Ultralytics OBB 文档说明，OBB 标签以四个角点表示，坐标归一化；内部训练会转为 `xywhr`。这意味着我们必须先做标签可视化，不能只看 `.txt` 是否存在。

Ultralytics 训练文档显示，训练过程本身支持 plots、fraction、batch、patience、angle 等设置。对我们来说，`plots=True` 是必须打开的；`fraction` 和小样本子集适合快速验证链路；`angle` 相关 loss 说明 OBB 角度质量确实是训练目标的一部分。

Ultralytics 指标文档把 precision、recall、mAP、IoU、F1/PR 曲线、混淆矩阵、val labels/pred 图列为常见观察物。单类别标题栏检测中，混淆矩阵价值不如召回、定位质量和可视化对照图。

Ultralytics 测试文档明确区分 evaluation 和 testing：evaluation 是有标签指标，testing 是看模型在真实/未见条件下行为是否符合业务目标。这对应到本项目，就是不能只看 mAP，还要看“框能否被正确映射成标题栏位置”。

工程图纸相关论文支持 detector-first 路线：先用 YOLO/OBB 或 layout detector 找 title block/annotation，再做 OCR 或 VLM 解析。它们的数据规模远大于我们，所以我们不照搬训练规模，但迁移其分工原则。

## 五、推荐调试协议

### 1. 标注前质量门

- 确认每个样本只标 `title_block` 一个类别。
- 确认 16 张冒烟集覆盖 `left/right/top/bottom`。
- 确认同源样本不会同时出现在 train 和 val/test_focus。
- 确认标注工具能导出或转换为 Ultralytics OBB 格式。

### 2. 标注后质量门

- 对每张已标注图片生成 label overlay。
- 检查四点是否闭合成正确旋转框。
- 检查是否框入了明细表、技术要求表或非标题栏表格。
- 检查标题栏裁切样本是否备注。
- 抽样让人复核，发现规则歧义就更新标注规范。

### 3. 训练冒烟

第一轮训练目的不是泛化，而是验证链路：

- 用 12 到 16 张训练/验证小样本。
- 使用 nano/small OBB 模型。
- 开启 plots。
- 训练很少轮次先看是否能正常加载、正常保存预测图。
- 若模型连训练样本都学不会，优先查标签格式和标注规则，而不是调参。

### 4. 过拟合检查

小样本阶段应主动让模型“能记住训练集”。如果训练集也检测不到标题栏，说明：

- 标签格式可能错。
- OBB 点序可能错。
- 类别 YAML 可能错。
- 图片路径或标签路径可能错。
- 标注目标不一致。

若训练集表现很好但验证/关注集差，说明：

- 样本太少。
- 标题栏版式覆盖不足。
- 增强策略或拆分策略需要调整。
- 模型学到了固定位置偏置。

### 5. 预测后错误分层

每个错误样本要归到一个主因：

| 错误类型 | 表现 | 优先动作 |
| --- | --- | --- |
| `label_error` | 人看标注就错 | 修标注，不调模型 |
| `format_error` | 框点序乱、框飞出图外 | 修转换脚本和可视化 |
| `false_negative` | 没检测到标题栏 | 补样本、检查召回、降低阈值做诊断 |
| `false_positive` | 检到明细表/技术要求表 | 补负例、收紧标注规则、检查版式混淆 |
| `localization_error` | 检到标题栏但框偏 | 改标注一致性，检查图片尺寸和 OBB 角度 |
| `postprocess_error` | 框对但位置映射错 | 修框中心/边缘映射规则 |
| `data_leakage` | 指标异常高但外观不可信 | 重做按源图分组拆分 |

## 六、本项目执行顺序修正

在真实标注 16 张之前，建议先补两个工具：

1. `visualize_obb_labels.py`：给定图片和 YOLO OBB 标签，输出 overlay 图。
2. `validate_obb_dataset.py`：检查标签数、坐标范围、点数、类别 id、同源拆分泄漏。

然后再进入：

```text
人工标注 16 张
-> 运行 validate + visualize
-> 人工看 overlay
-> 训练冒烟
-> predict 保存可视化结果
-> 错误分层
```

## 七、参考来源

- Ultralytics OBB Dataset Format：https://docs.ultralytics.com/datasets/obb/
- Ultralytics Train Mode：https://docs.ultralytics.com/modes/train/
- Ultralytics Performance Metrics：https://docs.ultralytics.com/guides/yolo-performance-metrics/
- Ultralytics Model Testing：https://docs.ultralytics.com/guides/model-testing/
- Ultralytics Data Collection and Annotation：https://docs.ultralytics.com/guides/data-collection-and-annotation/
- Automated Parsing of Engineering Drawings with OBB + Donut：https://arxiv.org/abs/2505.01530
- Multi-Stage Hybrid Engineering Drawing VLM Framework：https://arxiv.org/abs/2510.21862
