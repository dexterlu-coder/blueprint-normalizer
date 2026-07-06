# 人工精审辅助包计划

## 背景

当前 ground truth 中 63 条记录里，只有 3 条属于人工重点复核，另外 60 条来自 OpenCV 与 MCP 共识接受。若要提高后续算法评估可信度，需要把这 60 条逐步升级为真正的人工确认记录。

## 目标

生成一个本地人工精审辅助包，让用户可以逐张查看图纸、候选判断和算法证据，并记录确认或纠正结果。

## 输入

- 全量 PNG 样本：`local_data/experiment_samples/all/png/*.png`
- 候选 ground truth：`local_data/ground_truth/rotation_ground_truth.json`
- OpenCV 评估明细：`outputs/rotation-detection/evaluation/evaluation_details.csv`

## 输出

本地忽略目录：

- `outputs/rotation-detection/manual_review/review_index.html`
- `outputs/rotation-detection/manual_review/review_form.csv`
- `outputs/rotation-detection/manual_review/review_sheet.json`

公开仓库只提交生成脚本、计划、RPD 和 TODO，不提交图纸图片或人工复核输出。

## 人工填写表字段

人工填写 CSV 只呈现用户复核时必要的信息：

- 序号。
- 样本编号。
- 候选标题栏位置。
- 候选旋转角度。
- 人工判断，默认为空，可填写 `正确` 或 `错误`。
- 正确标题栏位置，候选错误时填写。
- 正确旋转角度，候选错误时填写。
- 备注，默认为空。

完整机器字段保留在 `review_sheet.json` 中，避免干扰人工填写。

## HTML 报告要求

- 按优先级排序：需要复核、非人工确认、低置信度优先。
- 每张图纸显示缩略图和当前候选判断。
- 默认只展示人工复核所需信息，不展示 OpenCV/MCP 细节。
- 不直接修改 ground truth，只作为人工复核入口。

## 验收标准

- 生成 63 条复核记录。
- HTML 能在本地浏览器打开并看到图纸缩略图。
- CSV/JSON 能作为后续人工修订和回写 ground truth 的输入。
- 图纸和本地输出继续保持在 `.gitignore` 覆盖范围内。

## 执行结果

已完成：

- `scripts/rotation/build_manual_review_pack.py`
- `outputs/rotation-detection/manual_review/review_index.html`
- `outputs/rotation-detection/manual_review/review_form.csv`
- `outputs/rotation-detection/manual_review/review_sheet.json`

复核包包含 63 条记录。排序规则已生效：`sample_042` 作为需要复核样本排在第一位，其余样本按低置信度优先排列。

## 人工表简化调整

用户反馈 `review_sheet.csv` 字段过多，不适合一边对照 HTML 一边填写。

调整要求：

- CSV 改为 `review_form.csv`，只保留人工填写必要字段。
- HTML 默认不展示 OpenCV 位置、置信度、来源等技术字段。
- JSON 继续保留完整机器字段，用于后续自动回写或审计。

执行结果：

- 已生成 `outputs/rotation-detection/manual_review/review_form.csv`。
- 已删除旧的复杂 `review_sheet.csv`。
- `review_index.html` 默认只展示样本编号、候选标题栏位置和候选旋转角度。
- `review_sheet.json` 继续保留完整机器字段。

## 人工复核结果回写计划

用户已完成 `review_form.csv` 人工复核：

- 63 条旋转角度全部正确。
- 自动标题栏粗位置判断全部正确。
- 用户补充了更精确的标题栏位置标注。

下一步需要：

- 新增脚本读取 `review_form.csv`，兼容 UTF-8 BOM 和 GBK 编码。
- 将 `人工判断=正确` 的记录升级为人工确认 ground truth。
- 将 `正确标题栏位置` 写入 `precise_title_block_position` 字段。
- 保留原有粗粒度 `title_block_position`，用于当前旋转方向评估。
- 重新运行评估，确认 63 条 ground truth 全部为人工确认。

执行结果：

- 已新增 `scripts/rotation/import_manual_review_form.py`。
- 已将 63 条 ground truth 升级为 `manual_review_full`。
- 已写入 `precise_title_block_position`。
- 精确位置分布为：`右上方` 30、`右侧` 2、`上方` 30、`下方` 1。
- 重新评估后，OpenCV 相对人工确认 ground truth 为 63/63 正确。

