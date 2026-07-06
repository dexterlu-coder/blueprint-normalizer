# 标题栏粗 crop 与图号 OCR 下游策略资料索引

日期：2026-06-30

## 学习目标

为“标题栏完整性 crop 已经覆盖完整，但范围偏大，是否会增加图号 OCR 复杂性”这个问题寻找成熟做法。重点不是继续调一个更漂亮的框，而是判断成熟文档 OCR 流程如何处理“粗定位”和“字段级识别”的关系。

## 样本索引

| 样本 | 类型 | 来源 | 一句话价值 | 不适合照搬 |
| --- | --- | --- | --- | --- |
| PaddleOCR PP-StructureV3 | 官方文档 | https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/pipeline_usage/PP-StructureV3.html | 把文档处理拆成版面检测、表格识别、公式/印章/图表等模块，说明成熟 OCR 不依赖整页无差别识别 | 模型能力强于当前本地轻量路线，不能直接引入为默认依赖 |
| PaddleOCR Layout Detection | 官方文档 | https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/module_usage/layout_detection.html | 明确先检测页面区域，再把不同区域交给不同后续模块 | 版面类别偏通用文档，机械图纸标题栏仍需本项目规则约束 |
| PaddleOCR Table Structure Recognition | 官方文档 | https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/module_usage/table_structure_recognition.html | 表格结构识别支持把表格拆成结构和单元格级信息，适合借鉴标题栏单元格定位思想 | 标题栏表格线浅、扫描变形时仍要保留几何规则和人工复核 |
| RapidOCR | 开源 OCR | https://rapidai.github.io/RapidOCRDocs/main/install_usage/rapidocr/usage/ | OCR 输出包含文本框、文本、置信度和方向等结果，可用于粗 crop 后按位置过滤文本框 | 只用正则扫完整 OCR 文本会引入图纸主体噪声，必须结合位置和字段规则 |
| LayoutParser | 论文/开源工具 | https://arxiv.org/abs/2103.15348 | 将文档处理建模为布局区域对象，适合借鉴“先区域、再内容”的对象模型 | 通用文档布局模型不一定认识机械图纸标题栏，需要本地数据或规则适配 |
| Table Transformer / PubTables-1M | 论文 | https://arxiv.org/abs/2110.00061 | 将表格检测和表格结构识别分开，说明表格类任务常用“表格区域 -> 结构/单元格”的两层处理 | 训练和部署成本较高，不适合作为当前 63 张样本的第一步 |
| Amazon Textract AnalyzeDocument | 官方文档 | https://docs.aws.amazon.com/textract/latest/dg/how-it-works-analyzing.html | 商业文档 AI 也把表格、表单和 key-value 单独解析，并返回几何信息 | 云服务不作为当前默认路线，外发和版本稳定性要单独审批 |
| KVPFormer | 论文 | https://arxiv.org/abs/2304.07957 | 关键信息抽取关注 key-value 关系，说明“字段值”应从局部证据中抽取，不是全文 OCR 后猜测 | 需要训练/推理模型，不适合马上迁入 |
| Engineering Drawing Parsing | 论文 | https://arxiv.org/abs/2504.08645 | 工程图纸自动解析通常把图纸拆成标题栏、符号、尺寸、BOM 等对象再处理 | 研究方向较大，本项目应只吸收分层对象思想 |

## 结论摘要

成熟方案的共识是：

```text
整页/粗区域
  -> 版面块或表格块定位
  -> 字段/单元格级 ROI
  -> OCR 或 key-value 抽取
  -> 质量门与人工复核
```

因此，本项目不应把“完整性 crop”和“图号 OCR 输入”合并成一个产物。完整性 crop 可以继续保守，图号 OCR 应新增细 ROI。
