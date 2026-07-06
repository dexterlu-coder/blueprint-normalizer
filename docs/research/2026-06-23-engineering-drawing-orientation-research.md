# 工程图纸方向识别取经笔记

日期：2026-06-23

## 一、学习目标

- 我们真正要解决的问题：提高机械图纸旋转方向识别的置信度，尤其是标题栏在右侧但与其他表格竞争时的判断可靠性。
- 本轮不做的事情：不改代码、不引入 OCR 实现、不训练模型、不处理全部 63 页。
- 最终沉淀物：样本索引、横向学习笔记、对置信度提升规划的修订建议。

## 二、样本索引

详细索引见 `references/drawing-rotation-research/README.md`。

## 三、对象模型

类似方案中反复出现的对象不是“页面边缘”，而是更细的对象：

- 页面：渲染后的图纸图像。
- 线条层：由形态学操作提取出的水平线和垂直线。
- 交点层：水平线与垂直线重叠形成的网格证据。
- 候选区域：可能是标题栏、明细表、技术要求表或其他表格。
- 标题栏候选框：在候选区域中同时满足边缘接近、表格结构、尺寸比例和位置规则的区域。
- 证据字段：线密度、交点密度、候选框面积、宽高比、距离边缘、竞争候选差距。
- 人工复核标记：算法证据不足或候选竞争明显时的质量门。

## 四、横向对照

| 资料 | 强项 | 弱项 | 可迁移原则 | 不迁移 |
| --- | --- | --- | --- | --- |
| OpenCV 线条提取官方示例 | 对表格线检测直接有用 | 不区分标题栏和其他表格 | 使用水平/垂直 kernel 分离线条 | 不照搬固定 kernel 比例 |
| OpenCV 形态学基础 | 解释 kernel 形状决定敏感目标 | 只是基础算子 | kernel 大小应与图纸尺寸和目标线段长度相关 | 不把形态学当完整判断器 |
| Tesseract TSV/HOCR | 能输出文字框和置信度 | 工程图纸 OCR 容易受线条干扰 | OCR 适合作为候选确认层 | 不把 OCR 作为第一层方向判断 |
| 标题栏检测论文 | 明确标题栏是图纸检索元数据区域 | 依赖 CNN/GPT-4o | 先检测标题栏，再抽信息 | 不在当前阶段引入大模型常规路径 |
| 技术图纸文本检测论文 | 明确传统 OCR 不可靠的原因 | 不解决标题栏定位 | 用领域结构和合成/增强数据提升鲁棒性 | 不在小样本阶段训练检测器 |
| OBB + Donut 工程图解析论文 | 以 OBB 检测标题栏等局部类别 | 需要标注数据和训练 | 标题栏应作为局部目标检测，而非整页判断 | 不引入深度学习训练 |

## 五、关键发现

1. OpenCV 官方线条提取方案支持我们当前的基础方向：用形态学操作抽取水平线和垂直线。关键是 kernel 必须跟目标形状匹配。
2. 近期工程图纸/建筑图纸信息抽取方案普遍不是直接做整页 OCR，而是先检测标题栏或关键区域，再抽结构化信息。
3. 技术图纸中的文字和符号经常被线条打断，传统 OCR 不能作为第一层判断依据。
4. OBB/目标检测路线说明“局部候选框”比“整条边带”更接近主流解法。
5. 对当前项目来说，最小可行迁移不是训练模型，而是把 OpenCV 的评分对象从边带改为候选框。

## 六、对当前规划的修正建议

原规划“局部标题栏候选评分”方向是对的，但需要更明确：

1. 先检测所有表格候选框，再判断哪个像标题栏。
2. 置信度不能只用第一名和第二名分差，应拆成：
   - 候选框自身质量。
   - 与其他候选框的差距。
   - 是否符合标题栏位置规则。
   - 是否存在明细表/技术要求表等强竞争候选。
3. 第 2 张低置信度不一定是坏事；如果右侧标题栏和顶部文字/线条竞争接近，算法应该说明“为什么低置信度”。
4. 调试图应显示候选框，而不是整条边带，这样人能判断算法是在看标题栏还是看错表格。
5. OCR 应在 OpenCV 候选框稳定后再加入，用来确认字段，而不是现在就引入。

## 七、我们的下一版工作协议

1. 前置判断：确认输入图像质量和图纸边框是否完整。
2. 中间产物：输出线条层、交点层、候选框列表、候选分数。
3. 人机分工：机器给候选和证据；低置信度由人复核并把误判原因写回规则。
4. 执行方式：先在前 5 张样例验证，再扩展到更多页面。
5. 审核与打回：若角度正确但证据框不在标题栏，应打回算法，不算通过。
6. 进化沉淀：每次低置信度都记录竞争候选类型，例如明细表、技术要求表、边框线、零件视图。

## 八、下一轮验证

- 测试样本：仍用当前前 5 张。
- 成功标准：
  - 角度保持全部正确。
  - 第 2 张置信度目标不低于 0.25，或保留复核标记但给出明确歧义证据。
  - 调试图中最终候选框必须落在标题栏区域。
- 可能失败点：
  - 标题栏线条太弱，候选框断裂。
  - 明细表比标题栏更完整。
  - 总装图中的大表格仍然压过标题栏。
  - 旋转后候选框宽高比规则写反。

## 九、参考来源

- OpenCV: Extract horizontal and vertical lines by using morphological operations: https://docs.opencv.org/4.x/dd/dd7/tutorial_morph_lines_detection.html
- OpenCV: Morphological Transformations: https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html
- Tesseract Command Line Usage: https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html
- Title block detection and information extraction for enhanced building drawings search: https://arxiv.org/abs/2504.08645
- Text Detection on Technical Drawings for the Digitization of Brown-field Processes: https://arxiv.org/abs/2205.02659
- Automated Parsing of Engineering Drawings for Structured Information Extraction Using a Fine-tuned Document Understanding Transformer: https://arxiv.org/abs/2505.01530
