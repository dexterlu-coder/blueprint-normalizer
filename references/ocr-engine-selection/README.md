# OCR 引擎选型样本索引

日期：2026-06-28

## 学习目标

为机械图纸标题栏候选 crop 选择合适的 OCR 证据层。OCR 在本项目中只负责识别标题栏字段簇，不负责替代 YOLO/OBB 标题栏检测、OpenCV 方向判断或 VLM teacher 解释。

## 样本索引

| 样本 | 类型 | 来源 | 本地路径 | 一句话价值 | 不适合照搬 |
| --- | --- | --- | --- | --- | --- |
| PaddleOCR / PP-OCR | 开源 OCR / 文档解析工具链 | https://github.com/PaddlePaddle/PaddleOCR | 未拉取 | 中文、英文、多语种和文档结构能力最完整，适合作为能力上限和第二阶段方案 | 生态较大，依赖和模型选择复杂，不适合作为第一步无脑接入 |
| RapidOCR | 开源 OCR 推理部署工具链 | https://github.com/RapidAI/RapidOCR | 未拉取 | 基于 PaddleOCR 模型做 ONNX/OpenVINO 等多后端部署，轻量、离线、Python 集成友好 | 模型能力上限依赖已转换模型，复杂场景仍需回到 PaddleOCR 或重新微调 |
| Tesseract / pytesseract | 传统开源 OCR 引擎 | https://github.com/tesseract-ocr/tesseract | 未拉取 | 安装后可做稳定、低成本 baseline，输出格式丰富 | 对小字号、表格线、中文扫描 crop 的鲁棒性通常不如现代深度学习 OCR |
| EasyOCR | 开源 PyTorch OCR | https://github.com/JaidedAI/EasyOCR | 未拉取 | API 简单，支持 `ch_sim` + `en`，适合快速对照 | PyTorch 依赖偏重，模型首次加载和下载成本较高 |
| CnOCR | 中文/英文 OCR Python 包 | https://github.com/breezedeus/CnOCR | 未拉取 | 中文场景友好，支持竖排文字，集成 PPOCR 模型路线 | 依赖栈和模型授权需要单独核对，部分增强模型存在商业/会员边界 |
| 百度智能云 OCR | 云 OCR / 私有化对照 | https://cloud.baidu.com/product/ocr | 不适用 | 产品矩阵完整，支持公有云、离线 SDK 和私有化部署 | 默认会涉及图纸外发或商业部署审批，不能作为默认路线 |
| 腾讯云 OCR | 云 OCR / 私有化对照 | https://cloud.tencent.com/product/ocr | 不适用 | 通用印刷体、表格识别和文档智能能力可作为云端上限对照 | 默认涉及图纸外发与费用，必须用户批准 |
| Azure OCR / Read | 云 OCR / 可容器化对照 | https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-ocr | 不适用 | Read OCR 支持云服务和容器部署，输出位置与置信度 | 商业服务和部署授权复杂，不适合作为当前默认实验 |
| Google Cloud Vision OCR | 云 OCR 对照 | https://docs.cloud.google.com/vision/docs/ocr | 不适用 | `TEXT_DETECTION` 与 `DOCUMENT_TEXT_DETECTION` 可作为通用云端 OCR 上限 | 需要云账号、计费和数据外发审批 |

## 不纳入第一轮的方向

| 方向 | 原因 |
| --- | --- |
| 完整文档解析框架 | 当前只处理 8 到 16 个标题栏候选 crop，完整 PDF 解析会把问题做重 |
| 表格结构识别专用系统 | 标题栏字段簇只需要字段命中与位置证据，不需要还原完整表结构 |
| 云 OCR 默认接入 | 与图纸隐私、费用和可回滚性冲突 |
| OCR 直接决定方向 | OCR 只提供证据，不应越过 YOLO/OBB、teacher rule 和人工复核质量门 |
