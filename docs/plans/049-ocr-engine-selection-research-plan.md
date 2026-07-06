# OCR 引擎选型调研计划

## 背景

当前项目的主线已经转为：

1. OpenCV 基线用于方向识别回归。
2. YOLO/OBB 用于标题栏候选检测。
3. teacher 规则用于后处理可解释仲裁。
4. OCR 只作为字段簇证据层，不作为主识别路线。

最近一次 OCR 字段簇可用性探针显示，本机暂未安装可用 OCR 引擎：

- `pytesseract`
- `paddleocr`
- `easyocr`
- `rapidocr_onnxruntime`
- `cnocr`
- `tesseract`

因此需要先调研可选 OCR 引擎，明确哪类方案适合后续小规模离线实验。

## 目标

本轮调研回答三个问题：

1. 哪些 OCR 引擎适合机械图纸标题栏候选 crop 的中文字段簇识别。
2. 哪些 OCR 引擎适合作为本地离线小实验的首选、备选和 baseline。
3. 云端 OCR 是否值得作为对照，以及需要哪些隐私和人工审批约束。

## 非目标

本轮不做：

- 不安装 OCR 依赖。
- 不下载模型。
- 不调用云端 OCR。
- 不上传图纸。
- 不改主流程脚本。
- 不把 OCR 接入自动接受逻辑。
- 不处理完整 PDF。

## 候选范围

优先调研：

- PaddleOCR / PP-OCR。
- RapidOCR。
- Tesseract / pytesseract。
- EasyOCR。
- CnOCR。

作为对照调研：

- 阿里云、百度、腾讯等云 OCR。
- Azure AI Vision、Google Cloud Vision 等通用云 OCR。

## 评价维度

- 中文与英文混排识别能力。
- 小字号、扫描噪声、表格线干扰适应性。
- 旋转或竖排标题栏 crop 的处理方式。
- Windows 本地安装成本。
- Python 集成复杂度。
- 模型体积和运行依赖。
- 是否支持离线部署。
- 是否适合只跑 8 到 16 个候选 crop。
- 输出是否便于形成字段簇证据，而不是全文结果。
- 是否会引入图纸外发风险。

## 输出

按“他山”调研要求输出：

```text
references/ocr-engine-selection/README.md
docs/research/2026-06-28-ocr-engine-selection-research.md
docs/workflows/ocr-engine-selection-sop.md
```

必要时同步更新：

```text
docs/README.md
references/README.md
TODO.md
reports/rpd-rotation-detection.md
```

## 判断标准

- 若存在轻量、离线、中文友好、Windows 可控的方案，则推荐进入下一轮本地安装小实验。
- 若方案安装成本高但识别能力强，则列为备选，不直接进入主流程。
- 若方案需要外发图纸，则只能作为用户明确批准后的对照，不作为默认路线。
- 若 OCR 对标题栏字段簇不稳定，则继续保留 teacher/VLM 与结构代理，不把 OCR 纳入自动接受。

## 回滚点

本计划、RPD 和 TODO 提交后作为 OCR 选型调研前回滚点。
