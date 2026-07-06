# YOLO/OBB 调试方案取经样本索引

本目录记录 YOLO/OBB 标题栏检测实验前置调研样本。

## 样本索引

| 样本 | 类型 | 来源 | 一句话价值 | 不适合照搬 |
| --- | --- | --- | --- | --- |
| Ultralytics OBB Dataset Format | 官方文档 | https://docs.ultralytics.com/datasets/obb/ | 明确 OBB 标签格式是 `class_index x1 y1 x2 y2 x3 y3 x4 y4`，坐标归一化，训练前必须验证格式 | 示例来自 DOTA 航拍数据，不是工程图纸 |
| Ultralytics Train Mode | 官方文档 | https://docs.ultralytics.com/modes/train/ | 训练支持 `plots=True`、`fraction`、`batch`、`patience`、`angle` 等参数，适合构建小样本调试流程 | 默认参数面向通用检测，不能直接当成图纸最佳配置 |
| Ultralytics Performance Metrics | 官方文档 | https://docs.ultralytics.com/guides/yolo-performance-metrics/ | 指明应看 precision、recall、mAP、IoU、PR/F1 曲线、混淆矩阵、val labels/pred 对照图 | 单类别 title block 任务中混淆矩阵价值有限，需要更看重召回和定位质量 |
| Ultralytics Model Testing | 官方文档 | https://docs.ultralytics.com/guides/model-testing/ | 区分 evaluation 和 testing，强调测试集、预测可视化、过拟合/欠拟合和数据泄漏检查 | 文档面向通用模型测试，需要映射到“标题栏位置”后处理 |
| Ultralytics Data Collection and Annotation | 官方文档 | https://docs.ultralytics.com/guides/data-collection-and-annotation/ | 强调标注规则、准确性/一致性、异常标签、质量控制和复审机制 | 没有专门讨论机械制图标题栏 |
| Automated Parsing of Engineering Drawings with OBB + Donut | 论文 | https://arxiv.org/abs/2505.01530 | 工程图纸中使用 YOLOv11 检测 Title Blocks 等类别，再裁剪给解析模型，支持 detector 优先路线 | 目标是信息抽取，不是方向判断 |
| Multi-Stage Hybrid Engineering Drawing VLM Framework | 论文 | https://arxiv.org/abs/2510.21862 | 工程图纸中先用 YOLO layout/title block，再用 YOLO OBB 做细粒度检测，说明多阶段 detector 是合理架构 | 数据规模远大于本项目，不能照搬训练规模 |

## 当前结论

YOLO/OBB 调试必须前置于正式标注和训练。对本项目而言，最重要的不是先调参，而是建立质量门：

1. 标注前：检查规则是否可执行，样本是否覆盖四类标题栏位置。
2. 标注后：可视化每个 OBB 标签，检查点序、框形、是否误框明细表。
3. 训练前：用极小样本做格式加载和过拟合冒烟。
4. 训练中：观察 loss、precision、recall、mAP、预测样例。
5. 训练后：按 false negative、false positive、localization error、postprocess error 分层分析。
6. 进入融合前：必须验证 OBB 框中心到 `bottom/left/top/right` 的映射逻辑。
