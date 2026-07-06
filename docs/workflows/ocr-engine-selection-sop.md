# OCR 引擎选型与验证 SOP

## 适用场景

当项目需要为标题栏候选 crop 增加文字字段簇证据时使用本 SOP。

## 输入

- YOLO/OBB 后处理候选 crop。
- 已知正例标题栏 crop。
- 已知普通明细表或均匀表格反例 crop。
- 当前 OCR capability 报告。

## 判断顺序

1. 先确认 OCR 只作为证据层，不作为最终方向或真值来源。
2. 优先选择本地离线 OCR。
3. 优先从 RapidOCR 小实验开始。
4. 若 RapidOCR 识别弱，再比较 PaddleOCR、CnOCR、EasyOCR。
5. 用 Tesseract 做 baseline，判断传统 OCR 是否足够。
6. 云 OCR 只在用户明确批准后做上限对照。

## 小实验质量门

必须同时满足：

- 全部重点 crop 都有可记录的 OCR 状态。
- OCR 失败不能导致诊断脚本崩溃。
- OCR 输出必须保留原文、字段命中、引擎名和失败原因。
- 真实标题栏至少稳定命中多个流程字段或属性字段。
- 普通明细表不得因单个关键词被判定为强标题栏字段簇。
- OCR 结果只进入诊断报告，不能直接进入 ground truth。

## 推荐流程

1. 建立安装计划和回滚点。
2. 安装一个 OCR 引擎，不同时安装多个变量。
3. 运行 `scripts/ocr/build_title_block_ocr_diagnostic.py`。
4. 查看 `ocr_capability`、`ocr_status_counts` 和字段簇命中。
5. 人工抽查正例和反例 crop。
6. 若通过，再规划接入 `teacher_rule_flags`。
7. 若失败，记录失败分层并停止接入。

## 反例清单

- 为了追求准确率直接上传整页图纸到云 OCR。
- OCR 一有关键词就自动接受候选。
- 同时安装多个 OCR 引擎，导致无法判断收益来自哪里。
- 只看识别文本，不看文字框、置信度和结构反证。
- 把 OCR 输出直接覆盖人工 ground truth。

## 当前推荐

当前最合适的下一步是：

1. 规划 RapidOCR 本地安装与字段簇小实验。
2. 使用现有 8 到 16 个重点 crop。
3. 若 RapidOCR 不足，再进入 PaddleOCR 或 CnOCR 对照。

