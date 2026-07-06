# 图号抽取低置信候选优化与命名质量门计划

## 背景

63 张全量标题栏 crop/OCR dry-run 已完成：

- 标题栏 crop：63/63。
- OCR 文本：63/63。
- RapidOCR 状态：63 条 `ok`。
- 字段簇强度：60 条 `strong`，3 条 `weak`。
- PDF 旋正计划：上游旋转阻断为 0。
- 自动 dry-run ready：6 条。
- 仍需处理：53 条 `blocked`，4 条 `needs_human_review`。

当前主要风险已经从标题栏定位转移到图号候选抽取、候选置信度、歧义处理和命名质量门。

## 当前问题

现有图号抽取规则偏保守：

- `near_label` 候选给 0.95。
- `global_pattern` 候选统一给 0.65。
- 单候选若低于 0.9 会被 `drawing_number_low_confidence` 阻断。
- 多候选如果第一名优势不足，会进入 `drawing_number_ambiguous`。

这导致大量看起来可能正确的单候选无法进入自动 dry-run ready；但不能简单降低阈值，因为 OCR 会混入明细表零件号、路径片段、重复总成号、日期和误识别字符。

## 本轮目标

1. 优化图号候选评分，不再只按 `near_label/global_pattern` 两档打分。
2. 加入标题栏语义上下文、图名邻近、字段标签、候选模式完整度和噪声惩罚。
3. 保留严格命名质量门，自动放行只允许证据充分且无重名、无歧义、无上游阻断的记录。
4. 输出更可审计的候选原因，便于后续人工复核或 VLM/OCR provider 对照。
5. 重新运行 63 张全量 dry-run，记录自动 ready、blocked、needs review 的变化。

## 非目标

本轮不做：

- 不正式旋正 PDF。
- 不正式重命名单页 PDF。
- 不覆盖原始 PDF。
- 不调用云端 OCR/VLM。
- 不修改 ground truth。
- 不新增人工审核入口。
- 不重训 YOLO/OBB。
- 不把 OCR 图号直接当最终真值。

## 输入

默认输入：

```text
local_data/full_63_title_block_ocr_dry_run/full_63_ocr_arbitration_records.jsonl
```

复用 dry-run 脚本：

```text
scripts/ocr/build_pdf_correction_dry_run.py
```

对照输出：

```text
local_data/full_63_title_block_ocr_dry_run/pdf_correction_dry_run/
```

## 设计策略

### 候选抽取

保留现有标签窗口和全局模式，同时增加分层证据：

- 标签邻近：`图号/规格`、`图样代号`、`图号`、`代号` 后方候选优先。
- 图名邻近：候选前方若存在短中文图名，增加可信度。
- 标题栏流程字段邻近：候选附近出现 `标记`、`处数`、`更改文件号`、`签字`、`日期`、`设计` 等字段，增加可信度。
- 明细表反证：候选附近出现 `序号`、`数量`、`材料`、`备注` 且同时有多个零件号，降低可信度。
- 路径反证：上下文出现反斜杠、斜杠、`.ipt`、`.idw` 等路径或 CAD 文件片段，拒绝或大幅降权。

### 候选评分

候选分数仍保持 0 到 1：

- 基础分由来源决定。
- 模式完整度加分：大写字母、数字、连字符段数、项目编号前缀一致性。
- 上下文加分：标签、图名、标题栏流程字段。
- 噪声扣分：路径、日期、页码、明细表密集候选、明显 OCR 混淆。
- 分数必须可解释，候选输出中保存 `reasons` 和 `penalties`。

### 选择规则

建议选择状态：

- `single_high_confidence_candidate`：单候选或明显领先候选，且分数达到自动阈值。
- `single_candidate`：存在候选但未达自动阈值，继续 blocked。
- `ambiguous`：多候选接近，进入人工复核。
- `missing`：无候选，继续 blocked。

自动命名 dry-run ready 仍需同时满足：

- 上游旋正计划可执行。
- 有标题栏 crop。
- OCR 字段簇为 strong。
- 图号候选高置信且非歧义。
- 文件名清洗无高风险。
- 不与其他记录重复。
- 不会覆盖已有目标文件。

## 质量门

本轮只允许扩大 dry-run ready，不允许绕开风险：

- 低置信候选不得自动放行。
- 重名候选不得自动放行。
- 歧义候选必须进入 `needs_human_review`。
- OCR 字段簇弱的记录不得自动命名。
- 缺 OCR、缺 crop、缺 PDF 路径必须显式阻断。
- 输出仍必须包含 `dry_run_only=true`、`modified_pdf=false`、`renamed_pdf=false`。

## 验证标准

1. `python -m py_compile scripts\ocr\build_pdf_correction_dry_run.py` 通过。
2. 使用 63 张全量 OCR 仲裁记录重新运行 dry-run。
3. 输出记录数保持 63。
4. `rotation_blocker_counts` 仍为空。
5. `title_block_crop_blocker_counts` 仍为空。
6. `modified_pdf=false` 且 `renamed_pdf=false`。
7. `drawing_number_candidates.csv` 中候选带有可解释原因。
8. `dry_run_summary.json` 中自动 ready 的提升必须来自高置信候选，而不是阈值裸降。
9. RPD 记录最终结果和剩余阻断。

## 回滚点

提交本计划、RPD 和 TODO 后作为实现前回滚点。若后续评分规则误放行风险过高，应回退到该提交，再缩小规则范围或改为人工抽查优先。

