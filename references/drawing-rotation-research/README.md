# 工程图纸方向识别取经样本索引

日期：2026-06-23

## 学习目标

为机械图纸旋转方向识别寻找类似处理方案，重点关注：

- 扫描工程图纸中的标题栏检测。
- 表格/网格结构定位。
- OCR 或视觉模型在工程图纸中的适用边界。
- 如何提升方向判断置信度。

## 样本索引

| 样本 | 类型 | 来源 | 一句话价值 | 不适合照搬 |
| --- | --- | --- | --- | --- |
| OpenCV Extract horizontal and vertical lines | 官方文档 | https://docs.opencv.org/4.x/dd/dd7/tutorial_morph_lines_detection.html | 使用自定义线性 structuring element，通过腐蚀/膨胀提取水平线和垂直线，适合表格候选检测 | 示例不是工程图纸，需要加入标题栏位置和干扰表格过滤 |
| OpenCV Morphological Transformations | 官方文档 | https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html | 说明形态学操作依赖 kernel 形状，适合把算法参数和目标形状绑定 | 只提供基础操作，不解决标题栏判别 |
| Tesseract Command Line Usage | 官方文档 | https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html | TSV/HOCR 能输出文字框位置和置信度，可作为标题栏字段确认层 | 工程图纸文字常被线条/符号打断，不能作为第一判断依据 |
| Title block detection and information extraction for enhanced building drawings search | 论文 | https://arxiv.org/abs/2504.08645 | 近期方案将标题栏视为元数据区域，采用检测标题栏再抽信息的 pipeline | 使用 CNN + GPT-4o，超出当前 OpenCV 原型范围 |
| Text Detection on Technical Drawings for the Digitization of Brown-field Processes | 论文 | https://arxiv.org/abs/2205.02659 | 指出传统 OCR 在技术图纸上不可靠，原因是线条、符号和数据集稀缺 | 研究目标是文本检测，不是标题栏方向判断 |
| Automated Parsing of Engineering Drawings Using Document Understanding Transformer | 论文 | https://arxiv.org/abs/2505.01530 | 采用 OBB 检测标题栏等类别，再裁剪交给结构化解析，说明“先区域检测”是主流方向 | 需要标注数据和深度学习训练，不适合当前小样本阶段 |

## 初步结论

当前阶段最值得迁移的是：

1. 保留 OpenCV 形态学线条提取作为底层特征。
2. 从“整条边带评分”改为“局部标题栏候选框检测”。
3. 将 OCR 放到第二层，只用于字段确认和置信度增强。
4. 将视觉 MCP 放到低置信度兜底层，而不是常规路径。
5. 调试输出必须可视化候选框和证据，便于人工复核。
