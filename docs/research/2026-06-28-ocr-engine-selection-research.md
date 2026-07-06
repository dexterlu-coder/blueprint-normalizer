# OCR 引擎选型取经笔记

日期：2026-06-28

## 一、学习目标

- 我们真正要解决的问题：为机械图纸标题栏候选 crop 增加可解释的字段簇证据，帮助区分真实标题栏和普通明细表。
- 本轮不做的事情：不安装依赖、不下载模型、不调用云 OCR、不上传图纸、不改主流程、不把 OCR 纳入自动接受。
- 最终沉淀物：样本索引、横向调研笔记、选型 SOP。

## 二、样本索引

详见：

- `references/ocr-engine-selection/README.md`

## 三、对象模型

这个领域的核心对象不是“OCR 引擎”，而是：

- 候选 crop：来自 YOLO/OBB 的标题栏候选图像，只包含小范围局部区域。
- OCR engine：把 crop 转成文本、文字框和置信度的工具。
- 字段簇：能说明“这是标题栏”的关键词组合，例如设计、审核、批准、日期、图号、材料、比例。
- 反证字段：普通明细表、零件清单、均匀网格表格的结构或文本特征。
- 证据报告：把 OCR 文本命中、结构特征、贴框证据和后处理决策分开记录。
- 质量门：决定 OCR 是否只能记日志、是否可进入 teacher rule flags、是否必须人工复核。

## 四、工作协议

1. 前置判断：OCR 只服务字段簇证据，不服务全文提取和最终真值。
2. 中间产物：每个 crop 保存 OCR 原文、字段命中、文字框、置信度摘要和失败原因。
3. 人机分工：机器先做字段命中和反证分层，人只看低噪声复核入口和关键 crop。
4. 执行方式：先跑 8 到 16 个已知 hard-case crop，再决定是否扩大到全量候选。
5. 审核与打回：OCR 命中弱、字段错乱、普通表格误命中时不得自动接受。
6. 进化沉淀：把稳定字段簇写入规则，把失败样本放入 hard-case 清单。

## 五、横向对照

| 样本 | 强项 | 弱项 | 可迁移原则 | 不迁移 |
| --- | --- | --- | --- | --- |
| PaddleOCR / PP-OCR | 能力完整，中文和文档结构能力强，PP-OCRv6 有轻量到中等多档模型 | 依赖和配置较复杂 | 作为能力上限和后续精度路线 | 不直接引入完整文档解析链路 |
| RapidOCR | 安装和部署路径轻，默认支持中英文，适合离线小实验 | 上限依赖已转换模型 | 第一轮本地 crop 实验优先 | 不把轻量部署等同于识别一定可靠 |
| Tesseract | 稳定、传统、输出格式丰富 | 中文小字和表格线干扰下可能弱 | 做 baseline，确认现代 OCR 的收益 | 不作为主推路线 |
| EasyOCR | API 简单，支持中英文，返回框、文本、置信度 | PyTorch 依赖重，模型下载和启动成本高 | 快速对照 | 不作为默认 Windows 轻量方案 |
| CnOCR | 中文友好，支持竖排，模型场景划分清楚 | 依赖和模型授权边界要核对 | 中文/竖排备选 | 不默认使用付费或会员模型 |
| 云 OCR | 能力强、服务稳定、可能支持表格/文档智能 | 外发、费用、账号、合规成本 | 只做用户批准后的上限对照 | 不作为默认离线路线 |

## 六、不可变原则

1. OCR 不是主判定器，只能作为字段簇证据层。
2. 当前项目优先离线、本地、可复现、可回滚。
3. 先小样本 hard-case 验证，再谈接入主流程。
4. 字段命中必须与结构证据一起解释，不能只看关键词。
5. 云 OCR 必须经过用户明确批准，且限定外发范围。
6. 任何 OCR 结果都不能直接覆盖 ground truth 或训练标签。

## 七、项目建议

### 首选：RapidOCR

推荐作为下一轮本地 OCR 小实验首选。

理由：

- 官方定位包含快速离线部署，Python 调用简单。
- 默认支持中文和英文，贴合标题栏字段簇。
- 基于 PaddleOCR 模型转换路线，工程成本比完整 PaddleOCR 低。
- 对 8 到 16 个 crop 的小规模探针足够轻。

适合验证：

- `设计/审核/批准/日期` 等流程字段能否稳定命中。
- `图号/材料/比例/重量/单位` 等属性字段能否形成强字段簇。
- 普通明细表是否会被误判为标题栏。

### 第二路线：PaddleOCR / PP-OCR

推荐作为 RapidOCR 不足时的能力上限方案。

理由：

- 官方仓库显示其文档解析、结构化输出、多语种和工业文本场景持续更新。
- PP-OCRv6 提供 tiny/small/medium 分层模型，更利于做精度与成本权衡。
- 如果后续需要表格单元坐标、复杂文档解析或模型微调，PaddleOCR 的生态更完整。

代价：

- Windows 安装、模型下载、后端选择和版本兼容更复杂。
- 不适合在没有必要前直接接入主流程。

### Baseline：Tesseract / pytesseract

推荐作为低成本 baseline，而不是主力方案。

理由：

- 本项目已有 `pytesseract` 探测入口，脚本改造成本最低。
- Tesseract 输出格式丰富，适合证明“传统 OCR 是否已经够用”。

风险：

- 机械图纸标题栏小字号、扫描噪声、表格线密集、中文字段短词较多，可能导致召回不足。
- Windows 上还需要单独安装二进制和中文语言包。

### 备选：CnOCR

适合作为中文专用备选，尤其在竖排或旋转字段上做对照。

注意：

- 它支持中文、英文和竖排文字，并集成 PPOCR 模型路线。
- 需要核对依赖、模型下载、模型授权和 Windows 安装体验。

### 备选：EasyOCR

适合作为快速 API 对照。

注意：

- 使用 `['ch_sim', 'en']` 可覆盖简体中文和英文。
- PyTorch 依赖、模型首次下载、CPU 性能和模型加载时间可能不如 RapidOCR 轻。

### 云 OCR：只做审批后的上限对照

百度、腾讯、Azure、Google Cloud Vision 等云 OCR 能力完整，但默认不适合当前项目。

可用条件：

- 用户明确批准 provider、样本数量和外发范围。
- 优先只上传已脱敏 crop，而不是整页图纸。
- 输出只作为对照报告，不写入 ground truth、不直接接入自动接受。

## 八、下一轮验证

建议下一轮单独规划“RapidOCR 本地安装与字段簇小实验”：

- 输入：当前 `local_data/title_block_ocr_diagnostic/crops/` 中 8 到 16 个重点 crop。
- 输出：沿用 `diagnostic_report.json`、`diagnostic_manifest.csv`、`review_summary.html`。
- 成功标准：
  - OCR 环境 capability 从 unavailable 变为 available。
  - 至少能成功处理全部重点 crop。
  - 真实标题栏中有稳定字段簇命中。
  - 普通明细表反例不被误标为强字段簇。
- 失败处理：
  - 若 OCR 召回弱，只保留日志，不进入 teacher rule flags。
  - 若安装成本失控，回退到 Tesseract baseline 或继续 VLM provider 小实验。

## 九、来源

- PaddleOCR：https://github.com/PaddlePaddle/PaddleOCR
- RapidOCR：https://github.com/RapidAI/RapidOCR
- Tesseract：https://github.com/tesseract-ocr/tesseract
- EasyOCR：https://github.com/JaidedAI/EasyOCR
- CnOCR：https://github.com/breezedeus/CnOCR
- 百度智能云 OCR：https://cloud.baidu.com/product/ocr
- 腾讯云 OCR：https://cloud.tencent.com/product/ocr
- Azure OCR：https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-ocr
- Google Cloud Vision OCR：https://docs.cloud.google.com/vision/docs/ocr
