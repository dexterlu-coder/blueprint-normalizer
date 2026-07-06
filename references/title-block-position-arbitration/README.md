# 标题栏位置多证据仲裁资料索引

本目录记录“先定位标题栏，再由标题栏位置推导旋转角度”的外部案例和技术依据。调研目标不是证明某一个工具可以单独完成全部工作，而是确认本项目的对象拆分是否合理：标题栏检测、图框/表格几何校验、OCR 字段簇、VLM 疑难解释和人工异常复核应分别承担不同证据角色。

## 样本索引

| 样本 | 类型 | 来源 | 一句话价值 | 不适合照搬 |
| --- | --- | --- | --- | --- |
| Title block detection and information extraction for enhanced building drawings search | 论文 / AEC 图纸案例 | https://arxiv.org/abs/2504.08645 | 明确采用“标题栏检测 -> 标题栏信息抽取 -> 图纸检索/分组”的流水线，支持先定位标题栏再抽取元数据 | 建筑图纸和机械图纸版式不同，且使用 GPT-4o，不适合作为本项目默认数据安全路线 |
| An Approach to Engineering Drawing Organization: Title Block Detection and Processing | 论文 / 工程图纸案例 | https://doi.org/10.1109/access.2023.3244603 | 题名即覆盖工程图纸标题栏检测与处理，说明标题栏可作为工程图纸组织的核心对象 | Crossref 摘要信息有限，不能据此复刻其具体算法细节 |
| A Study on Extraction Method of Non Geometry Information in Engineering Drawing Title Block | 论文 / 工程图纸信息抽取 | https://doi.org/10.4028/www.scientific.net/amr.383-390.995 | 将工程图纸中的非几何信息聚焦到标题栏，支持后续从标题栏抽取图号等元数据 | 研究较早，不能直接代表当前 OCR/检测模型能力 |
| ISO 7200:2004 | 标准 | https://www.iso.org/standard/35446.html | ISO 页面明确该标准主题是标题栏和文档头的数据字段，支持把标题栏字段作为规范对象保存 | 官网公开页不是标准全文，不能过度声称具体字段位置或尺寸 |
| PaddleOCR Layout Detection | 官方文档 / 文档版面分析 | https://github.com/PaddlePaddle/PaddleOCR | 官方说明结构分析会识别文本、表格、标题等区域并给出坐标，支持“先区域定位，再区域 OCR/解析”的对象模型 | 通用文档布局模型不等于机械图纸标题栏检测器 |
| Ultralytics OBB | 官方文档 / 旋转目标检测 | https://docs.ultralytics.com/tasks/obb/ | OBB 用旋转框描述目标，适合标题栏这类可能随页面旋转的长条区域 | OBB 只给候选框，不直接证明候选是真标题栏 |
| OpenCV Morphological Line Detection | 官方文档 / 几何线条提取 | https://docs.opencv.org/4.x/dd/dd7/tutorial_morph_lines_detection.html | 官方教程说明可用形态学提取水平/垂直线，支持表格线、图框线和候选结构证据 | 规则视觉无法可靠理解字段语义，需与 OCR/检测器仲裁 |
| Tesseract Command Line Usage | 官方文档 / OCR 与方向线索 | https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html | 官方文档提到 OSD 数据、TSV/HOCR 坐标输出，支持 OCR 作为文字方向和字段位置证据 | Tesseract 不是本项目首选 OCR，且整页 OCR 不适合普通机器默认路线 |

## 横向结论

1. “标题栏检测 -> 信息抽取”有直接案例支撑，尤其在工程/AEC 图纸检索和归档场景中，标题栏被视为图纸元数据入口。
2. “先区域定位，再区域识别”是文档 AI 常见范式，PaddleOCR 版面分析和标题栏论文都体现了这一点。
3. “标题栏位置决定旋转角度”是本项目结合机械制图规则形成的工程化映射；外部资料支持标题栏是规范对象，但具体旋转映射仍应以项目规则和本地图纸验证为准。
4. 多源证据合理，但证据不应平权投票：YOLO/OBB 给候选位置，OpenCV 给几何校验，OCR 给字段簇真实性，VLM 解释疑难样本，人工只处理异常队列。
5. 严格数据安全或普通机器约束下，本地主线应优先使用 OpenCV、YOLO/OBB 和 crop 级 OCR；云端 VLM 只能作为经过批准的疑难兜底或上限对照。

## 后续使用

- 设计结论沉淀在 `docs/decisions/title-block-position-arbitration-design.md`。
- 横向调研笔记沉淀在 `docs/research/2026-06-28-title-block-position-arbitration-research.md`。
- 旧三方比对计划保留在 `docs/plans/016-three-way-rotation-comparison-plan.md`，当前仅作为历史 ground truth 建立方案追溯。
