# RPD：机械图纸旋转方向自动识别

## 需求概述

需要识别机械图纸扫描件相对于正确阅读方向被顺时针旋转了多少度。正确方向依据为：机械制图标题栏应位于页面下方或右下方。

## 用户价值

- 减少人工逐页查看图纸方向的工作量。
- 为后续批量拆分、校正和归档图纸提供基础能力。
- 形成可解释的方向判断结果，便于人工复核。

## 输入

- 单页 PDF 文件。
- 或由 PDF 渲染出的页面 PNG 图像。

## 输出

每页输出：

- 文件名或页码。
- 标题栏当前位置。
- 已顺时针旋转角度。
- 建议校正角度。
- 置信度。
- 是否需要人工复核。
- 调试图路径。

## 规则依据

依据 `rules/mechanical-drawing-rotation.md`：

| 当前标题栏位置 | 已顺时针旋转角度 |
| --- | --- |
| 下方或右下方 | 0 度 |
| 左侧 | 90 度 |
| 上方或左上方 | 180 度 |
| 右侧或右上方 | 270 度 |

## 非目标

当前阶段不做：

- OCR 全文提取。
- 图纸内容理解。
- 尺寸标注识别。
- 自动校正 PDF 页面。
- 处理全部 63 页。

## 阶段一范围

阶段一只实现 OpenCV 原型，用于前 5 张图纸方向识别。

审核状态：已通过，允许进入阶段一实现。

阶段一必须：

- 读取前 5 张 PNG 或 PDF。
- 检测标题栏候选区域。
- 输出 JSON 和 CSV。
- 生成调试图。
- 不修改原始 PDF。
- 不生成校正后的 PDF。

## 公开仓库整理要求

该项目将推送到 GitHub public 仓库，因此图纸原件、拆分 PDF、渲染 PNG、临时输出和个人草稿不得进入版本库。

必须满足：

- `.gitignore` 覆盖 `docs/**/*.pdf`、`output/`、`outputs/`、`tmp/`、`local_data/` 等路径。
- 当前本地图纸资料整理到 `local_data/` 下。
- Git 提交中只包含可公开的规则、规划、RPD、TODO、源码和必要说明。
- 推送前执行 `git status --short`，确认没有图纸资料处于 staged 状态。

## 验收标准

- 前 5 张图纸识别结果与已人工判断结果一致：
  - 第 1 张：270 度
  - 第 2 张：270 度
  - 第 3 张：180 度
  - 第 4 张：180 度
  - 第 5 张：180 度
- 每条结果包含标题栏位置和置信度。
- 每页至少生成一张调试图，标注候选标题栏区域。
- 低置信度结果必须标记为需要人工复核。

## 阶段一验证结果

阶段一 OpenCV 原型已在前 5 张样例图纸上运行，结果符合人工判断：

| 文件 | 标题栏位置 | 已顺时针旋转角度 | 置信度 | 复核标记 |
| --- | --- | --- | --- | --- |
| `YKJ125-00-00-2525_图纸_001.png` | 右侧或右上方 | 270 度 | 0.3582 | 否 |
| `YKJ125-00-00-2525_图纸_002.png` | 右侧或右上方 | 270 度 | 0.1217 | 是 |
| `YKJ125-00-00-2525_图纸_003.png` | 上方或左上方 | 180 度 | 0.3647 | 否 |
| `YKJ125-00-00-2525_图纸_004.png` | 上方或左上方 | 180 度 | 0.4093 | 否 |
| `YKJ125-00-00-2525_图纸_005.png` | 上方或左上方 | 180 度 | 0.4951 | 否 |

输出文件位于本地忽略目录 `outputs/rotation-detection/stage1/`。

## 置信度提升验证结果

已将检测脚本改为混合证据方案：

- 边侧表格线密度负责最终方向判断，保留前 5 张人工基准的稳定性。
- 局部候选框负责补充证据、输出调试框和候选特征。
- 置信度综合候选证据、边侧分差和竞争候选歧义。
- 默认输入已切换到 `local_data/experiment_samples/first20/png/`。

前 5 张人工基准复核结果：

| 文件 | 标题栏位置 | 已顺时针旋转角度 | 置信度 | 复核标记 |
| --- | --- | --- | --- | --- |
| `YKJ125-00-00-2525_sample_001.png` | 右侧或右上方 | 270 度 | 0.6200 | 否 |
| `YKJ125-00-00-2525_sample_002.png` | 右侧或右上方 | 270 度 | 0.3529 | 否 |
| `YKJ125-00-00-2525_sample_003.png` | 上方或左上方 | 180 度 | 0.6480 | 否 |
| `YKJ125-00-00-2525_sample_004.png` | 上方或左上方 | 180 度 | 0.6484 | 否 |
| `YKJ125-00-00-2525_sample_005.png` | 上方或左上方 | 180 度 | 0.7759 | 否 |

第 2 张置信度已从 0.1217 提升到 0.3529，超过 0.25 的阶段目标。

## 置信度提升需求

阶段一中第 2 张样例虽然角度判断正确，但置信度仅为 0.1217，触发人工复核。

审核状态：已通过，允许进入置信度提升实现。

后续需要提升置信度计算质量：

- 从整条边带评分改为局部标题栏候选框评分。
- 置信度应综合候选框自身质量、第一二名差距、几何形态和歧义程度。
- 输出更详细的证据字段，方便判断低置信度原因。
- 调试图应标注局部候选框，而不是只标注整条边带。

详细规划见 `docs/plans/015-confidence-improvement-plan.md`。

## 实验样本扩展需求

当前前 5 张样本过少，容易让置信度优化过拟合到少量页面。

在继续改算法前，需要从本地私有原 PDF 中抽取前 20 张图纸作为实验样本：

- 输出位置：`local_data/experiment_samples/first20/`
- 单页 PDF：`local_data/experiment_samples/first20/pdf/`
- 渲染 PNG：`local_data/experiment_samples/first20/png/`
- 样本目录必须保持在 `.gitignore` 覆盖范围内，不上传 GitHub。
- 抽取方式优先使用 `pypdf` 页面级复制，避免重采样或重压缩。
- PNG 仅用于算法实验和调试，可由 Ghostscript 从单页 PDF 渲染。

## 全量实验样本需求

为了进行更可靠的阈值校准，前 20 张样本仍然不足。需要将原 PDF 的全部 63 页抽取为实验样本：

- 输出位置：`local_data/experiment_samples/all/`
- 单页 PDF：`local_data/experiment_samples/all/pdf/`
- 渲染 PNG：`local_data/experiment_samples/all/png/`
- 样本目录必须保持在 `.gitignore` 覆盖范围内，不上传 GitHub。
- 抽取方式继续使用 `pypdf` 页面级复制。
- PNG 继续使用 Ghostscript 以 150 DPI 渲染。
- 后续阈值校准应基于全量样本，而不是只基于前 5 或前 20 张。

完成状态：已抽取并渲染全部 63 页。

全量检测当前摘要：

- 结果数量：63。
- 需要复核：1。
- 最低置信度：0.2362。
- 最高置信度：0.8535。
- 输出仍位于本地忽略目录 `outputs/rotation-detection/stage1/`。

## 三方比对需求

仅依赖 OpenCV 置信度不足以决定免复核阈值。需要引入图像识别 MCP 和人工复核结果，与 OpenCV 形成三方比对。

目标：

- 对全量 63 张图纸分别获得 OpenCV、MCP、人工三方判断。
- 找出三方一致样本，作为高可信候选真值。
- 找出分歧样本，定位 OpenCV 或 MCP 的误判模式。
- 为后续置信度阈值校准提供数据基础。

详细计划见 `docs/plans/016-three-way-rotation-comparison-plan.md`。

完成状态：已完成全量 63 张三方比对。

输出位于本地忽略目录 `outputs/rotation-detection/comparison/`：

- `mcp_results.json`
- `manual_results.json`
- `three_way_comparison.csv`
- `disagreements.csv`

当前结论：

- 总样本数：63。
- 三方需要关注样本：3。
- OpenCV 相对人工复核错误：2，分别是 `sample_009`、`sample_010`。
- OpenCV 低置信但方向正确：1，`sample_042`。
- MCP 在严格“当前屏幕坐标”prompt 下，与人工复核样本一致。

分歧明细：

| 样本 | OpenCV | MCP | 人工复核 | 结论 |
| --- | --- | --- | --- | --- |
| `sample_009` | 0 度 | 270 度 | 270 度 | OpenCV 误判 |
| `sample_010` | 270 度 | 0 度 | 0 度 | OpenCV 误判 |
| `sample_042` | 270 度，低置信 | 270 度 | 270 度 | OpenCV 方向正确但应复核 |

## OpenCV 阶段二误判修复需求

三方比对证明当前阶段一 OpenCV 结果存在两个高置信误判：`sample_009` 和 `sample_010`。

阶段二需要优先解决高置信误判：

- 将最终方向选择从单纯整边带评分升级为“局部标题栏候选框优先，整边带兜底”。
- 增加标题栏形态约束，区分竖向侧边标题栏与横向底部标题栏。
- 以 `sample_009`、`sample_010`、`sample_042` 作为重点回归样本。
- 全量 63 张运行后，不应新增相对当前三方候选真值的 OpenCV 分歧。

详细计划见 `docs/plans/003-opencv-stage2-error-fix-plan.md`。

完成状态：已完成 OpenCV 阶段二误判修复。

阶段二实现：

- 增加边缘滑窗候选，避免标题栏被整页大轮廓吞掉。
- 当局部标题栏候选足够强时优先采用局部候选方向。
- 对右侧兜底结果增加冲突仲裁，降低上方/左侧密集视图造成的误判。
- 将原型复核阈值从 0.25 调整为 0.30，使 `sample_042` 继续进入复核池。

阶段二全量验证结果：

- 总样本数：63。
- 相对当前三方候选真值的 OpenCV 错误数：0。
- 需要人工复核：1，`sample_042`。
- 最低置信度：0.2960。
- 最高置信度：0.8535。

重点回归样本：

| 样本 | 阶段一 OpenCV | 阶段二 OpenCV | 人工复核 | 结果 |
| --- | --- | --- | --- | --- |
| `sample_009` | 0 度 | 270 度 | 270 度 | 已修正 |
| `sample_010` | 270 度 | 0 度 | 0 度 | 已修正 |
| `sample_042` | 270 度，低置信 | 270 度，低置信 | 270 度 | 保持复核 |

## Ground Truth 与自动评估需求

为了避免后续优化只依赖临时人工观察，需要建立可重复的评估流程。

本阶段需要：

- 将现有三方比对得到的候选真值规范化为 ground truth 文件。
- 明确区分人工重点复核样本与 OpenCV/MCP 共识接受样本。
- 实现自动评估脚本，计算准确率、错误样本、复核样本和置信度摘要。
- 后续每次修改识别算法后，都应先跑评估脚本再判断是否变好。

详细计划见 `docs/plans/004-ground-truth-evaluation-plan.md`。

完成状态：已完成候选 ground truth 生成和自动评估脚本。

本地生成文件：

- `local_data/ground_truth/rotation_ground_truth.json`
- `local_data/ground_truth/rotation_ground_truth.csv`
- `outputs/rotation-detection/evaluation/evaluation_summary.json`
- `outputs/rotation-detection/evaluation/evaluation_details.csv`
- `outputs/rotation-detection/evaluation/errors.csv`
- `outputs/rotation-detection/evaluation/review_required.csv`

当前评估结果：

- 总样本数：63。
- 正确数：63。
- 错误数：0。
- 相对候选真值准确率：1.0。
- 需要复核：1，`sample_042`。
- 人工重点复核 ground truth：3。
- OpenCV/MCP 共识接受 ground truth：60。
- 最低置信度：0.2960。
- 最高置信度：0.8535。
- 平均置信度：0.614292。

注意：该准确率是相对候选真值集的回归评估结果，不应表述为最终工业级无人复核准确率。后续逐张人工精审后，可更新 ground truth 来源等级并重新评估。

## 人工精审辅助包需求

为了把 60 条 OpenCV/MCP 共识接受样本逐步升级为人工确认样本，需要生成本地人工精审辅助包。

本阶段需要：

- 生成人工复核 HTML 索引，方便逐张看图。
- 生成 CSV/JSON 复核清单，用于记录确认、纠正和备注。
- 按需要复核、未人工确认、低置信度排序，优先暴露风险样本。
- 不直接修改 ground truth，避免把未完成复核的状态误写为人工确认。

详细计划见 `docs/plans/005-manual-review-pack-plan.md`。

完成状态：已完成人工精审辅助包生成脚本和本地输出。

新增脚本：

- `scripts/rotation/build_manual_review_pack.py`

本地生成文件：

- `outputs/rotation-detection/manual_review/review_index.html`
- `outputs/rotation-detection/manual_review/review_sheet.csv`
- `outputs/rotation-detection/manual_review/review_sheet.json`

当前复核包结果：

- 复核记录：63。
- 优先显示需要复核样本：`sample_042`。
- 其余共识接受样本按低置信度优先排序。
- HTML 中可直接查看图纸缩略图，并点击打开原 PNG。

用户后续需要做的事情：

- 打开 `outputs/rotation-detection/manual_review/review_index.html`。
- 按顺序查看每张图纸标题栏是否位于候选位置。
- 若候选正确，在 `review_form.csv` 的 `人工判断` 填 `正确`。
- 若候选错误，在 `review_form.csv` 的 `人工判断` 填 `错误`，并填写 `正确标题栏位置` 与 `正确旋转角度`。

人工表简化需求：

- `review_sheet.csv` 字段过多，改为生成更适合用户填写的 `review_form.csv`。
- 人工填写表只保留样本编号、候选位置、候选角度、人工判断、正确位置、正确角度和备注。
- 技术字段继续保留在 `review_sheet.json`，不呈现在人工填写 CSV 中。

完成状态：已完成。

简化后的用户填写表：

- `outputs/rotation-detection/manual_review/review_form.csv`

字段为：

- `序号`
- `样本编号`
- `候选标题栏位置`
- `候选旋转角度`
- `人工判断`
- `正确标题栏位置`
- `正确旋转角度`
- `备注`

旧的复杂 `review_sheet.csv` 已从本地输出目录删除，避免误打开。完整机器字段仍保留在 `review_sheet.json`。

## 人工复核结果回写需求

用户已完成 `review_form.csv` 人工审核：

- 旋转角度全部正确。
- 自动标题栏粗位置判断全部正确。
- 人工补充了更精确的标题栏位置，包括 `右上方`、`右侧`、`上方`、`下方`。

本阶段需要：

- 将人工填写结果回写到本地 ground truth。
- 将全部 63 条记录升级为人工确认。
- 新增 `precise_title_block_position` 字段保存精确位置。
- 保持 `title_block_position` 为粗粒度位置，继续服务旋转角度评估。
- 重新运行自动评估，确认当前算法相对人工确认 ground truth 仍为 63/63。

完成状态：已完成。

新增脚本：

- `scripts/rotation/import_manual_review_form.py`

导入结果：

- 导入人工复核记录：63。
- 人工确认 ground truth：63。
- 共识接受 ground truth：0。
- 精确标题栏位置分布：
  - `右上方`：30。
  - `右侧`：2。
  - `上方`：30。
  - `下方`：1。

重新评估结果：

- 总样本数：63。
- 正确数：63。
- 错误数：0。
- 相对人工确认 ground truth 准确率：1.0。
- 需要复核：1，`sample_042`。
- 最低置信度：0.2960。
- 最高置信度：0.8535。
- 平均置信度：0.614292。

说明：`sample_042` 方向正确但置信度低，因此仍作为算法复核策略样本保留。

## 顺时针 90 度增强样本需求

用户发现原始样本中缺少顺时针旋转 90 度图纸，即标题栏位于左侧的样本。为避免算法在缺失类别上未被验证，需要扩充样本多样性。

本阶段需要：

- 从人工确认原始样本中随机抽取一批图纸。
- 将它们旋转到标题栏位于左侧，构造 `90 度` 增强样本。
- 生成独立增强 ground truth，不能覆盖原始 ground truth。
- 对增强样本独立运行 OpenCV 检测和评估。
- 后续算法优化必须同时参考原始人工确认集和增强 90 度集。

详细计划见 `docs/plans/006-augmented-90-sample-plan.md`。

完成状态：已完成。

新增脚本：

- `scripts/rotation/create_augmented_90_samples.py`

脚本改造：

- `scripts/rotation/detect_rotation_stage1.py` 支持 `--input-dir` 和 `--output-dir`。
- `scripts/rotation/evaluate_rotation_results.py` 支持 `--results`、`--ground-truth` 和 `--output-dir`。

增强样本生成结果：

- 增强 PNG：20 张。
- 目标旋转角度：全部为 `90 度`。
- 目标标题栏粗位置：全部为 `left`。
- 目标精确标题栏位置：全部为 `左侧`。
- 来源分布：
  - 原 `270 度` 样本：10 张，额外顺时针旋转 180 度。
  - 原 `180 度` 样本：9 张，额外顺时针旋转 270 度。
  - 原 `0 度` 样本：1 张，额外顺时针旋转 90 度。

增强样本初次评估结果：

- 总样本数：20。
- 正确数：16。
- 错误数：4。
- 准确率：0.8。
- 需要复核：1。
- 错误样本：`aug90_002_from_sample_010`、`aug90_012_from_sample_034`、`aug90_016_from_sample_042`、`aug90_020_from_sample_057`。

优化内容：

- 增加左侧候选仲裁规则：当左侧候选与 bottom/right 第一候选非常接近，且整边证据不强烈反对时，优先选择左侧。
- 保留原有右侧兜底保护，避免破坏原始右侧标题栏样本。

优化后评估结果：

- 原始人工确认集：63/63，准确率 1.0，需要复核 1。
- 增强 90 度集：20/20，准确率 1.0，需要复核 1。
- 增强集最低置信度：0.2823。
- 增强集最高置信度：0.8561。

说明：增强样本是合成样本，用于补齐类别覆盖和暴露算法弱点，不替代真实 90 度扫描样本。

## 联合评估需求

当前已经有两套必须同时关注的评估集：

- 原始人工确认集：63 张。
- 顺时针 90 度增强集：20 张。

后续算法优化需要一键同时跑两套评估，并输出总览，避免修复增强类别时破坏原始样本，或只看原始样本而遗漏 90 度类别。

本阶段需要：

- 新增联合评估脚本。
- 依次运行原始集检测与评估。
- 依次运行增强 90 度集检测与评估。
- 汇总输出两套数据和合计指标。
- 当前联合评估应达到 83/83。

详细计划见 `docs/plans/007-combined-evaluation-plan.md`。

完成状态：已完成。

新增脚本：

- `scripts/rotation/run_combined_evaluation.py`

本地输出：

- `outputs/rotation-detection/combined_evaluation/combined_summary.json`
- `outputs/rotation-detection/combined_evaluation/combined_summary.csv`

联合评估结果：

| 数据集 | 样本数 | 正确数 | 错误数 | 准确率 | 需要复核 |
| --- | --- | --- | --- | --- | --- |
| 原始人工确认集 | 63 | 63 | 0 | 1.0 | 1 |
| 顺时针 90 度增强集 | 20 | 20 | 0 | 1.0 | 1 |
| 合计 | 83 | 83 | 0 | 1.0 | 2 |

复核样本：

- 原始人工确认集：`sample_042`。
- 顺时针 90 度增强集：`aug90_016_from_sample_042`。

联合最低置信度：0.2823。联合最高置信度：0.8561。

## sample_042 低置信分析与优化需求

当前联合评估中只有两个低置信复核样本：

- `sample_042`
- `aug90_016_from_sample_042`

两者来自同一张源图，人工已确认方向正确。下一阶段需要分析该图纸低置信原因，并优化评分或仲裁逻辑。

要求：

- 不通过简单降低全局复核阈值来“消除”复核标记。
- 优先找出候选证据竞争的具体原因。
- 优化后必须运行联合评估，保证 83/83 不变。
- 目标是提高这两个已确认正确样本的置信度，最好不再触发复核。

详细计划见 `docs/plans/008-low-confidence-042-plan.md`。

完成状态：已完成。

低置信原因：

- `sample_042` 图纸线条较淡，局部候选证据本身正确但与多个边缘窗口竞争候选分数接近。
- 旧置信度公式对候选竞争惩罚过重，导致方向正确但置信度低于 0.30。
- 增强样本 `aug90_016_from_sample_042` 继承了同一问题。

优化内容：

- 新增局部候选置信度保底规则。
- 仅当局部候选 `evidence_score >= 0.45` 且候选分数达到第一名的 97% 以上时生效。
- 保底值为 0.32，只用于越过当前复核阈值，不改变高置信样本排序。
- 未降低全局复核阈值。

优化后结果：

- `sample_042`：置信度从 0.2960 提升到 0.3200，不再触发复核。
- `aug90_016_from_sample_042`：置信度从 0.2823 提升到 0.3200，不再触发复核。
- 原始人工确认集：63/63，准确率 1.0，复核数 0。
- 增强 90 度集：20/20，准确率 1.0，复核数 0。
- 联合评估：83/83，准确率 1.0，复核数 0。
- 联合最低置信度：0.3200。

## OCR + 图像识别大模型兜底流程需求

用户希望在 OpenCV 主流程之外，引入 OCR 和图像识别大模型，例如智谱、阿里视觉模型。当前疑问是这些流程应组成串行工作流，还是组成并行工作流并投票。

经他山调研后，本项目规划采用：

- OpenCV 主流程。
- 条件触发 OCR 与 VLM 并行兜底。
- 最后做证据融合，不做简单多数票。

原则：

- 当前 OpenCV 联合评估为 83/83，因此仍作为主识别器。
- OCR 和 VLM 只在低置信、冲突、新分布或抽检场景触发，且不等价、不默认同权。
- 若需要第三类方向证据，优先考虑专用标题栏检测模型或专用 4 类方向分类器。
- VLM 结果必须结构化输出，并保留证据。
- 外部 API 默认最小化调用，避免无必要上传图纸。

进一步调研结论：

- YOLO / OBB 可以作为本地小模型运行，适合训练 `title_block` 旋转框检测器。
- 本地开源 VLM 可作为在线 VLM 禁用时的兜底方案。
- 本地 VLM 候选包括 Qwen2.5-VL、SmolVLM、Florence-2、MiniCPM-V、InternVL 等。
- 当进入 VLM 兜底阶段时，第一轮应先用云端模型验证收益，再按配置压力测试本地模型。
- 流程表述统一为：`本地/云端 VLM 兜底解释疑难样本`。
- 对本项目来说，专用标题栏检测模型优先级高于 VLM；VLM 更适合处理 detector 和 OpenCV 冲突后的疑难样本。

优先级修正：

- OpenCV 当前作为基线冻结，不在没有新错误样本时继续硬调。
- 下一步主线改为本地 YOLO/OBB 标题栏检测小实验。
- OCR 排在 YOLO/OBB 之后，作为标题栏字段和文字方向证据。
- VLM 排在 OpenCV、YOLO/OBB、OCR 之后，用于疑难样本兜底解释。
- 第一轮执行动作是生成 YOLO/OBB 标注准备包，不直接训练模型。

标题栏位置投票设计状态修正：

- 用户重新明确：“投票”设计的目的不是让多个模型平权决定最终文件结果，而是服务标题栏位置判断。
- 当前主问题应表述为：
  - 先确定标题栏当前位置。
  - 根据机械制图规则，标题栏正确方向应位于下方或右下方。
  - 由标题栏当前位置推导页面校正角度。
  - 旋正页面后读取标题栏图号并用于单页 PDF 命名。
- 旧设计状态：
  - `docs/plans/016-three-way-rotation-comparison-plan.md` 保留为历史三方比对和早期 ground truth 建立方案，不删除。
  - 废弃“无条件全量三方平权多数票”作为最终自动决策机制。
  - 保留并升级“多源证据服务标题栏位置判断”的核心思想。
- 当前设计名称：
  - 标题栏位置多证据仲裁。
- 当前证据角色：
  - YOLO/OBB：标题栏候选框和边侧位置主证据。
  - OpenCV：图框、表格结构、边缘密度和几何独立校验。
  - OCR：标题栏字段簇真实性证据，并为后续图号抽取服务。
  - VLM：仅在本地证据冲突、低置信或新版式时作为疑难解释分支。
  - 人工：只处理自动证据不足、VLM 仍不确定或图号命名风险高的异常队列。
- 本轮需进一步调研外部案例和技术依据，验证“先定位标题栏，再由标题栏位置决定旋转，再读取图号”的设计是否有工程支撑。
- 计划文件：
  - `docs/plans/051-title-block-position-arbitration-research-plan.md`
- 本轮不改代码、不处理图纸、不调用模型，只做设计归档和横向调研。

YOLO/OBB 标注准备包执行结果：

- 新增脚本：`scripts/yolo_obb/build_yolo_obb_annotation_pack.py`。
- 本地输出目录：`local_data/yolo_obb_annotation_pack/`。
- 输出文件：`annotation_manifest.csv`、`annotation_manifest.json`、`classes.txt`、`labeling_guide.md`、`pack_summary.json`。
- 样本总数：83。
- 数据集分布：原始人工确认集 63，顺时针 90 度增强集 20。
- 建议拆分：`train` 57，`val` 14，`test_focus` 12。
- 标题栏粗位置分布：`right` 32，`top` 30，`left` 20，`bottom` 1。
- 该准备包只生成清单和标注说明，不复制图纸、不上传图纸、不训练模型。
- 用户已审核并同意 `docs/plans/013-yolo-obb-title-block-experiment-plan.md` 中的标注规范，允许进入 12 到 20 张 OBB 冒烟标注准备。

YOLO/OBB 冒烟标注子集执行结果：

- 脚本已扩展为同时生成 `local_data/yolo_obb_annotation_pack/smoke/`。
- 冒烟子集样本数：16。
- 数据集分布：原始人工确认集 10，顺时针 90 度增强集 6。
- 标题栏粗位置分布：`left` 6，`right` 5，`top` 4，`bottom` 1。
- 建议拆分来源：`test_focus` 12，`train` 4。
- 本地输出文件：`smoke_manifest.csv`、`smoke_manifest.json`、`smoke_review_index.html`、`smoke_labeling_task.md`、`smoke_summary.json`。
- 当前只完成冒烟标注子集准备，尚未绘制 OBB 框，不能进入训练。

YOLO/OBB 调试方案前置调研需求：

- 在开始真实 OBB 标注和训练前，需要先调研 YOLO/OBB 类似工程的调试方案。
- 调研重点包括数据集检查、标注可视化、小样本过拟合、训练指标、推理可视化、错误分层和后处理验证。
- 本轮不安装训练依赖、不启动训练、不绘制真实 OBB 标签。
- 详细计划见 `docs/plans/014-yolo-obb-debugging-research-plan.md`。

YOLO/OBB 调试方案他山调研结论：

- YOLO/OBB 正式训练前必须增加调试质量门，不能直接从标注跳到训练。
- 标注后必须生成 overlay 图，确认 OBB 四点、点序、标题栏边界和误框情况。
- 训练冒烟的第一目标是验证链路和小样本可过拟合，不是证明泛化。
- 训练后不能只看 mAP，还要看召回、定位质量、val labels/pred 对照图和后处理映射结果。
- 错误样本要分层为 `label_error`、`format_error`、`false_negative`、`false_positive`、`localization_error`、`postprocess_error`、`data_leakage`。
- 标注 16 张前，下一步应先实现 YOLO/OBB 标签可视化脚本和数据集校验脚本。
- 详细调研见 `references/yolo-obb-debugging-research/README.md` 和 `docs/research/2026-06-25-yolo-obb-debugging-research.md`。

YOLO/OBB 标签工具实现计划：

- 新增 `scripts/yolo_obb/visualize_obb_labels.py`，用于将 OBB 标签画回原图生成 overlay。
- 新增 `scripts/yolo_obb/validate_obb_dataset.py`，用于检查标签格式、坐标范围、类别、图片/标签匹配和同源拆分泄漏。
- 默认输入为 `local_data/yolo_obb_annotation_pack/smoke/smoke_manifest.csv`。
- 默认标签目录为 `local_data/yolo_obb_annotation_pack/smoke/labels/`。
- 当前尚未人工标注，因此允许校验报告中出现 16 个缺失标签。
- 详细计划见 `docs/plans/009-yolo-obb-label-tools-plan.md`。

YOLO/OBB 标签工具实现结果：

- 新增公共工具：`scripts/common/obb_utils.py`。
- 新增校验脚本：`scripts/yolo_obb/validate_obb_dataset.py`。
- 新增可视化脚本：`scripts/yolo_obb/visualize_obb_labels.py`。
- `python -m py_compile scripts\common\obb_utils.py scripts\yolo_obb\validate_obb_dataset.py scripts\yolo_obb\visualize_obb_labels.py` 通过。
- `python scripts\yolo_obb\validate_obb_dataset.py` 已运行，检查 smoke 集 16 张图片：图片均存在且可读取，当前 16 个标签文件均缺失，产生 16 个 `missing_label` 警告、0 个错误，符合尚未人工标注的预期。
- `python scripts\yolo_obb\visualize_obb_labels.py` 已运行，生成 16 张 overlay 图和 `overlay_report.json`。
- 本地输出目录：`local_data/yolo_obb_annotation_pack/smoke/validation/` 和 `local_data/yolo_obb_annotation_pack/smoke/overlays/`，均在 ignored 本地目录内，不进入 Git。

OBB 标注工具选择与人工界面规则需求：

- 用户没有标注工具，需要先调研并选择一个轻量、本地、支持旋转框或四点标注、可导出或转换为 Ultralytics OBB 格式的工具。
- 标注工具选择前不开始真实标注，不训练 YOLO/OBB，不上传图纸。
- 用户新增长期规则：需要人工填写的内容必须去掉不必要信息；所有图像排列必须优先考虑人工查看是否方便。
- 该规则需要写入 `rules/human-review-interface.md`。
- 详细计划见 `docs/plans/010-annotation-tool-selection-plan.md`。

OBB 标注工具选择结果：

- 当前推荐 `Labelme + 项目内转换脚本`。
- 选择理由：本地运行、支持 polygon、安装使用轻，适合 16 张冒烟样本；Labelme JSON 易转换为 Ultralytics OBB。
- CVAT 功能更强，但 Docker/Web 平台成本较高，更适合后续多人或大批量标注。
- 新增规则文件：`rules/human-review-interface.md`。
- 新增操作说明：`docs/workflows/labelme-obb-annotation-workflow.md`。
- 新增调研记录：`docs/research/2026-06-25-obb-annotation-tool-selection.md`。
- 新增调研索引：`references/annotation-tool-selection/README.md`。
- 新增转换脚本：`scripts/yolo_obb/convert_labelme_to_yolo_obb.py`。
- `scripts/yolo_obb/build_yolo_obb_annotation_pack.py` 的 smoke 查看页生成逻辑已按人工界面规则调整：减少展示字段、放大图像显示区域，方便查看标题栏。
- 使用临时输出目录验证过新的 smoke 查看页生成逻辑；正式 `local_data/yolo_obb_annotation_pack/smoke/smoke_manifest.csv` 当前被占用，未覆盖正式本地 smoke 包。
- `python -m py_compile scripts\yolo_obb\convert_labelme_to_yolo_obb.py` 通过。
- `python scripts\yolo_obb\convert_labelme_to_yolo_obb.py --allow-missing` 已运行；当前尚未标注，因此结果为 `converted=0`、`missing_json=16`、`errors=0`，符合预期。

ISAT 标注工具调研需求：

- 用户反馈有评论认为 ISAT 比 Labelme 更好用，需要在开始人工标注前重新调研。
- 本轮只比较工具能力、安装复杂度、导出/转换链路和当前 16 张冒烟样本适配度。
- 本轮不安装 ISAT、不开始标注、不训练 YOLO/OBB、不删除 Labelme 方案。
- 详细计划见 `docs/plans/011-isat-annotation-tool-research-plan.md`。

ISAT 标注工具调研结论：

- 推荐从 `Labelme 优先` 调整为 `ISAT 优先，Labelme 备用`。
- ISAT 支持手动 polygon，支持 Shift 约束水平、垂直和 45 度线，更适合标题栏这类规则形状。
- ISAT 提供预览、快速浏览和细节检查，人工复核体验可能优于 Labelme。
- ISAT 支持 ISAT/COCO/YOLO/LABELME/VOC 等格式转换，但其 YOLO 转换不应直接假设为 Ultralytics OBB。
- 对本项目最稳妥的链路是：ISAT 标注 polygon -> 导出/转换 Labelme JSON -> 使用现有 `convert_labelme_to_yolo_obb.py` 转为 YOLO OBB。
- 下一步不应一次性标完 16 张，而是先用 ISAT 标注 1 张样本，验证导出/转换/校验/overlay 链路。
- 新增记录：`docs/research/2026-06-26-isat-annotation-tool-research.md`。
- 新增操作说明：`docs/workflows/isat-obb-annotation-workflow.md`。

ISAT 单样本标注检查结果：

- 用户已用 ISAT 标注 `sample_009`。
- 本地 JSON：`local_data/yolo_obb_annotation_pack/smoke/labelme_json/YKJ125-00-00-2525_sample_009.json`。
- JSON 实际为 ISAT 结构，包含 `info` 和 `objects`，不是 Labelme `shapes` 结构。
- 文件中存在一个 `title_block` 对象，segmentation 为 4 点 polygon，适合转换为 YOLO/OBB。
- 文件中同时存在 `__background__` 对象，转换时应忽略。
- 下一步需要扩展 `scripts/yolo_obb/convert_labelme_to_yolo_obb.py`，兼容 ISAT JSON 和带原始文件名前缀的 JSON 文件名。

ISAT 单样本链路验证结果：

- `scripts/yolo_obb/convert_labelme_to_yolo_obb.py` 已扩展为兼容 Labelme `shapes` 与 ISAT `objects` 两种 JSON 结构。
- 转换脚本已支持按 `*sample_009.json` 匹配带原始文件名前缀的 ISAT JSON。
- `python scripts\yolo_obb\convert_labelme_to_yolo_obb.py --allow-missing` 已运行，结果：`converted=1`、`missing_json=15`、`errors=0`。
- 已生成 `local_data/yolo_obb_annotation_pack/smoke/labels/sample_009.txt`。
- `python scripts\yolo_obb\validate_obb_dataset.py` 已运行，结果：`samples_with_labels=1`、`samples_missing_labels=15`、`total_labels=1`、`error_count=0`。
- `python scripts\yolo_obb\visualize_obb_labels.py` 已运行，生成 overlay 图。
- 已人工查看 `sample_009_overlay.png`，红框正确圈住右侧标题栏主体，链路验证通过。
- 后续可以继续用 ISAT 标注剩余 15 张样本。

ISAT smoke 标注完成待处理：

- 用户已完成 smoke 标注，JSON 保存在两个图片目录中：
  - `local_data/experiment_samples/all/png/`
  - `local_data/experiment_samples/augmented_90/png/`
- 其中原始图片目录包含 smoke 所需的 10 张 JSON，也包含若干额外非 smoke JSON。
- 增强 90 度目录包含 smoke 所需的 6 张 JSON。
- 后续处理只应读取 `local_data/yolo_obb_annotation_pack/smoke/smoke_manifest.csv` 中的 16 张样本，额外 JSON 暂不进入转换和训练。
- 当前转换脚本默认只搜索 `smoke/labelme_json/`，需要扩展为也能搜索每条 manifest 对应图片所在目录。

ISAT smoke 全量转换与校验结果：

- `scripts/yolo_obb/convert_labelme_to_yolo_obb.py` 已扩展为优先搜索 `smoke/labelme_json/`，若不存在则搜索 manifest 中每张图片所在目录。
- 已运行 `python scripts\yolo_obb\convert_labelme_to_yolo_obb.py --allow-missing`，结果：`converted=16`、`missing_json=0`、`errors=0`。
- 已生成 16 个 YOLO/OBB 标签文件到 `local_data/yolo_obb_annotation_pack/smoke/labels/`。
- 已运行 `python scripts\yolo_obb\validate_obb_dataset.py`，结果：`total_samples=16`、`samples_with_labels=16`、`samples_missing_labels=0`、`total_labels=16`、`error_count=0`、`warning_count=0`、`source_split_leakage_count=0`。
- 已运行 `python scripts\yolo_obb\visualize_obb_labels.py`，结果：`overlay_written=16`、`missing_images=0`、`missing_labels=0`、`parse_errors=0`。
- 已抽查 `sample_010`、`aug90_002_from_sample_010`、`sample_020` overlay，标题栏框位置正确。
- 额外非 smoke JSON 暂不进入转换、校验或训练。

YOLO/OBB 冒烟训练准备需求：

- 当前 16 张 smoke 标签已具备进入训练链路验证的条件。
- 当前环境未安装 Ultralytics，因此先构建本地 Ultralytics OBB 数据集结构，不直接训练。
- 冒烟训练准备采用过拟合链路验证策略：`train=16`、`val=16`，该设置只用于验证数据加载和训练链路，不用于泛化评估。
- 本轮不安装 Ultralytics、不下载权重、不启动训练、不提交 `local_data/` 产物。
- 详细计划见 `docs/plans/012-yolo-obb-smoke-training-plan.md`。

YOLO/OBB smoke 数据集构建结果：

- 新增脚本：`scripts/yolo_obb/build_yolo_obb_smoke_dataset.py`。
- 已运行 `python -m py_compile scripts\yolo_obb\build_yolo_obb_smoke_dataset.py`，通过。
- 已运行 `python scripts\yolo_obb\build_yolo_obb_smoke_dataset.py`，生成本地数据集目录：`local_data/yolo_obb_dataset_smoke/`。
- 生成文件包括：`images/train/`、`images/val/`、`labels/train/`、`labels/val/`、`data.yaml`、`dataset_summary.json`。
- 数据集策略：`overfit_smoke_train_equals_val`。
- train 图片/标签：16/16。
- val 图片/标签：16/16。
- 类别：`0: title_block`。
- 已执行标签格式校验：所有 train/val 标签均为 1 行 9 字段，类别为 0，坐标在 `[0, 1]` 内，问题数为 0。
- 当前未安装 Ultralytics，尚未启动训练；下一步需要用户确认是否安装训练依赖并运行 YOLO/OBB 冒烟训练。

工业级稳定可靠优先规则：

- 用户明确要求最终结果稳定可靠为最优先选项。
- 当稳定可靠与速度、自动化程度、少走步骤发生冲突时，必须优先选择稳定可靠。
- YOLO/OBB smoke 数据集虽然已构建完成，但进入训练前必须先人工复查 16 张 overlay。
- 后续 OCR、VLM、YOLO 训练、PDF 校正等流程均不得绕过质量门。
- 规则已写入 `rules/human-review-interface.md`，并同步写入总规则入口 `AGENTS.md`。

人工填写与审核界面总规则：

- 所有需要用户填写的表格，只显示用户完成当前判断必须看到的信息。
- 用户无需看到的内部字段、调试分数、冗余路径、长 JSON、候选列表或算法细节必须放入机器报告或日志，不得塞进人工填写表。
- 所有需要用户审核图片的 HTML 页面，图片排列必须优先考虑人工审核是否方便。
- 审核 HTML 应保证图纸主体和标题栏足够清晰，按稳定顺序排列，减少无关文字和调试信息，并支持快速浏览和逐张放大。

YOLO/OBB overlay 人工复查页面结果：

- 新增脚本：`scripts/yolo_obb/build_obb_overlay_review_page.py`。
- 已运行 `python -m py_compile scripts\yolo_obb\build_obb_overlay_review_page.py`，通过。
- 已运行 `python scripts\yolo_obb\build_obb_overlay_review_page.py`，生成本地复查包。
- 本地输出：`local_data/yolo_obb_annotation_pack/smoke/overlay_review/review_index.html`。
- 人工填写表：`local_data/yolo_obb_annotation_pack/smoke/overlay_review/review_form.csv`。
- 复查样本数：16。
- `review_form.csv` 只保留 `序号`、`样本编号`、`标题栏位置`、`旋转角度`、`人工判断`、`备注`，符合人工界面简化规则。
- 当前还未进行人工复查，不得进入 YOLO/OBB 训练。

YOLO/OBB overlay 人工复查文件重写要求：

- 本轮人工审核目标只判断红框是否准确框住标题栏主体。
- `review_index.html` 只展示样本编号和 overlay 图片，不展示标题栏位置、旋转角度、模型字段或调试信息。
- `review_form.csv` 只保留 `序号`、`样本编号`、`红框是否正确`、`备注`。
- 标题栏位置和旋转角度等信息已存在于 manifest、ground truth 或机器报告中，不应进入本轮人工填写文件。
- 重写后仍不得进入 YOLO/OBB 训练，必须等待用户完成 16 张 overlay 人工复查。

完成状态：已完成。

重写结果：

- 已更新 `scripts/yolo_obb/build_obb_overlay_review_page.py`。
- 已重新生成 `local_data/yolo_obb_annotation_pack/smoke/overlay_review/review_index.html`。
- 已重新生成 `local_data/yolo_obb_annotation_pack/smoke/overlay_review/review_form.csv`。
- `review_form.csv` 当前只包含 `序号`、`样本编号`、`红框是否正确`、`备注`。
- `review_index.html` 当前只展示样本编号、打开大图入口和 overlay 图片，不再展示标题栏位置或旋转角度。

YOLO/OBB smoke overlay 人工复查结果：

- 用户已完成 `review_form.csv`。
- 15 张样本标记为红框正确。
- `sample_001` 被标记为错误/不好判断，用户备注指出需要更多难分辨图片作为人工参考。
- 因存在未通过或不清晰样本，当前不得将 smoke overlay 复查视为训练质量门已完全通过。
- 下一步暂缓 Ultralytics 训练，先生成第二轮 90 度补强与难例参考标注包。

第二轮 90 度补强与难例参考标注包需求：

- 必须纳入全部 20 张顺时针 90 度增强样本，补齐左侧标题栏场景。
- 必须纳入用户指出的 `sample_001`。
- 必须纳入此前暴露过误判、低置信或标题栏位置特殊的样本，例如 `sample_009`、`sample_010`、`sample_042`。
- 样本选择应优先覆盖不好分辨、容易混淆、标题栏边界不清或存在相似表格干扰的情况。
- 人工填写文件允许提供“详细参考说明”字段，但仍不得暴露内部调试字段和冗余路径。
- 该包用于补充人工参考和标注多样性，不直接替代训练集质量门。
- 所有当前需要用户审核的文件必须发布到固定入口 `local_data/review_inbox/current/`，不得让用户在多个业务目录中寻找。
- 用户审核完成后，`current` 中的文件再归档到对应业务目录，并记录归档位置。

完成状态：已完成。

新增脚本：

- `scripts/yolo_obb/build_yolo_obb_hardcase_pack.py`

执行结果：

- 已生成第二轮本地包：`local_data/yolo_obb_annotation_pack/hardcase_round2/`。
- 样本总数：28。
- 顺时针 90 度补强样本：20。
- 原始难例/参考样本：8。
- 标题栏位置分布：`left` 20，`right` 4，`bottom` 1，`top` 3。
- 人工查看入口：`local_data/yolo_obb_annotation_pack/hardcase_round2/review_index.html`。
- 人工填写入口：`local_data/yolo_obb_annotation_pack/hardcase_round2/reference_form.csv`。
- `reference_form.csv` 只保留 `序号`、`样本编号`、`是否完成标注`、`标题栏边界参考`、`难点说明`、`备注`。
- 机器清单另存为 `round2_manifest.csv` 和 `round2_manifest.json`，不作为人工填写入口。
- 脚本已兼容用户表格软件保存后的 `utf-8-sig` 与 `gb18030` 编码。

固定审核入口调整：

- 第二轮待审核内容改为发布到 `local_data/review_inbox/current/`。
- 用户当前只需要查看固定入口中的 `review_index.html` 和 `reference_form.csv`。
- 固定入口中新增 `README.md`，说明当前应打开的文件。
- 旧业务目录中的第二轮文件作为历史产物保留；后续用户审核完成后，再由执行者归档当前审核文件。

固定入口发布结果：

- 已生成 `local_data/review_inbox/current/README.md`。
- 已生成 `local_data/review_inbox/current/review_index.html`。
- 已生成 `local_data/review_inbox/current/reference_form.csv`。
- 当前用户只需要进入 `local_data/review_inbox/current/`，不需要再到其他目录寻找审核材料。

固定入口规则修正：

- 仅把 HTML/CSV 放进固定入口是不充分的。
- 对 ISAT 标注任务，用户实际需要打开的 PNG 图片也是当前审核/标注文件，必须复制到固定入口。
- 第二轮固定入口必须新增 `to_label/`，放全部待标注图片副本。
- 第二轮固定入口必须新增 `references/`，放参考图片副本。
- `review_index.html` 必须引用固定入口内的图片副本，不得引用其他业务目录中的原图。

完成状态：已完成。

修正结果：

- 已更新 `AGENTS.md`，明确固定入口必须包含用户实际要打开、填写、标注或参考的全部文件副本。
- 已更新 `scripts/yolo_obb/build_yolo_obb_hardcase_pack.py`，自动复制待标注图片和参考图片到固定入口。
- 当前 ISAT 待标注图片目录：`local_data/review_inbox/current/to_label/`。
- 当前参考图片目录：`local_data/review_inbox/current/references/`。
- `to_label/` 当前包含 28 张 PNG。
- `references/` 当前包含 20 张 PNG。
- `review_index.html` 当前只引用固定入口内的 `to_label/` 和 `references/` 图片。
- 脚本在 `reference_form.csv` 被表格软件占用时不会中断图片和 HTML 发布，会保留已有表格并继续生成其他入口文件。

不清晰 90 度增强样本需求：

- 用户发现当前 `to_label/` 中顺时针 90 度样本整体较清晰，希望增加更不好分辨的 90 度样本。
- 新样本应从原始人工确认图纸中选择线条更淡、锐度更低、局部对比度更差或标题栏更难辨认的图纸。
- 必须强制纳入用户指出难判断的 `sample_001` 和历史低置信样本 `sample_042`。
- 生成后的样本必须旋转为顺时针 90 度，即标题栏位于左侧。
- 新样本必须复制到固定审核入口 `local_data/review_inbox/current/to_label/`，参考图复制到 `local_data/review_inbox/current/references/`。
- 用户不需要手动寻找或复制任何图片。

完成状态：已完成。

新增脚本：

- `scripts/rotation/create_unclear_augmented_90_samples.py`

执行结果：

- 已生成不清晰来源顺时针 90 度增强样本：12 张。
- 输出目录：`local_data/experiment_samples/augmented_90_unclear/png/`。
- 本地 ground truth：`local_data/ground_truth/rotation_ground_truth_augmented_90_unclear.json`。
- 质量指标表：`local_data/ground_truth/unclear_source_quality_metrics.csv`。
- 新增样本源：`sample_001`、`sample_042`、`sample_040`、`sample_037`、`sample_036`、`sample_034`、`sample_050`、`sample_052`、`sample_035`、`sample_039`、`sample_044`、`sample_038`。
- `sample_001` 和 `sample_042` 为强制纳入样本；其余样本由锐度、对比度、边缘密度和暗线比例综合指标筛选。
- 已更新 `scripts/yolo_obb/build_yolo_obb_hardcase_pack.py`，将 `augmented_90_unclear` 纳入固定审核入口。
- 当前固定入口 `local_data/review_inbox/current/to_label/` 包含 40 张待标注 PNG。
- 当前固定入口 `local_data/review_inbox/current/references/` 包含 28 张参考 PNG。
- 当前 `reference_form.csv` 包含 40 条记录。

第二轮标注完成后的处理需求：

- 用户已完成 `local_data/review_inbox/current/to_label/` 中 40 张图片的 ISAT 标注。
- 当前 `to_label/` 中应有 40 张 PNG 和 40 个对应 JSON。
- 处理前必须先归档当前固定入口，避免覆盖用户刚完成的标注材料。
- 归档后将 ISAT JSON 转换为 YOLO/OBB 标签。
- 转换后必须运行标签校验和 overlay 可视化，不得直接进入训练。
- 下一轮固定入口应切换为 overlay 复查任务，只展示当前需要用户复查的 overlay 图片和填写表。

完成状态：已完成。

处理结果：

- 已确认 `local_data/review_inbox/current/to_label/` 中有 40 张 PNG 和 40 个对应 JSON。
- 已归档当前标注材料到 `local_data/review_inbox/archive/round2_annotations_20260626_annotated/`。
- 已转换 40 个 ISAT JSON 为 YOLO/OBB 标签。
- 标签输出目录：`local_data/review_inbox/current/labels/`。
- 转换结果：`converted=40`，`missing_json=0`，`errors=0`。
- 已运行标签校验：`total_samples=40`，`samples_with_labels=40`，`total_labels=40`，`error_count=0`，`warning_count=0`。
- 已生成 overlay：`overlay_written=40`，`missing_images=0`，`missing_labels=0`，`parse_errors=0`。
- 已生成固定入口 overlay 复查页面：`local_data/review_inbox/current/overlay_review/review_index.html`。
- 已生成固定入口 overlay 复查表：`local_data/review_inbox/current/overlay_review/review_form.csv`。
- 已更新 `local_data/review_inbox/current/README.md`，当前任务切换为 overlay 复查。
- 当前仍不得进入 YOLO/OBB 训练，必须等待用户复查 40 张 overlay。

第二轮 overlay 人工复查结果：

- 用户已完成 `local_data/review_inbox/current/overlay_review/review_form.csv`。
- 复查记录总数：40。
- `红框是否正确=正确`：40。
- `红框是否正确=错误`：0。
- 第二轮 40 张 overlay 质量门通过。
- 下一步必须先归档当前固定审核入口，再规划 YOLO/OBB 训练前最终数据集构建。
- 仍不得直接启动训练；训练前需要明确数据集构建策略、训练/验证划分和回滚点。

固定入口归档结果：

- 已归档第二轮 overlay 复查材料到 `local_data/review_inbox/archive/round2_overlay_review_20260626_approved/`。
- 已重置 `local_data/review_inbox/current/`。
- 当前 `current/` 只保留 `README.md`，提示当前没有待用户审核、填写或标注的文件。
- 归档目录保留 labels、overlays、overlay_review、validation、to_label、references、manifest、转换报告和复查表。

YOLO/OBB 训练前最终数据集构建需求：

- 数据来源使用已通过人工 overlay 复查的第二轮归档：`local_data/review_inbox/archive/round2_overlay_review_20260626_approved/`。
- 样本总数：40，包括 `augmented_90` 20、`augmented_90_unclear` 12、`original` 8。
- 构建数据集时必须按 `source_sample` 分组划分，避免同一张原图的原始版、90 度增强版、不清晰增强版跨 train/val/test 泄漏。
- 固定 `test` 来源样本为 `sample_001`、`sample_010`、`sample_042`，覆盖用户指出难例、底部标题栏样本和历史低置信样本。
- 固定 `val` 来源样本为 `sample_009`、`sample_020`、`sample_034`、`sample_040`，覆盖历史误判、上方标题栏、右侧标题栏和不清晰 90 度样本。
- 其余来源样本进入 `train`。
- 预期划分：train 26，val 7，test 7。
- 构建后必须检查图片/标签数量、标签字段、坐标范围和 source_sample 跨 split 泄漏。
- 该数据集用于训练链路和小样本验证，不应被表述为工业级泛化评估集。

完成状态：已完成。

新增脚本：

- `scripts/yolo_obb/build_yolo_obb_round2_dataset.py`

构建结果：

- 数据集目录：`local_data/yolo_obb_dataset_round2/`。
- 数据来源：`local_data/review_inbox/archive/round2_overlay_review_20260626_approved/`。
- 数据集策略：`round2_human_verified_grouped_by_source_sample`。
- 样本总数：40。
- train：26 张图片 / 26 个标签。
- val：7 张图片 / 7 个标签。
- test：7 张图片 / 7 个标签。
- source_sample 跨 split 泄漏：0。
- 数据来源分布：`augmented_90` 20，`augmented_90_unclear` 12，`original` 8。
- 标题栏位置分布：`left` 32，`right` 4，`bottom` 1，`top` 3。
- test 来源样本：`sample_001`、`sample_010`、`sample_042`。
- val 来源样本：`sample_009`、`sample_020`、`sample_034`、`sample_040`。

校验结果：

- 已生成 `local_data/yolo_obb_dataset_round2/data.yaml`。
- 已生成 `local_data/yolo_obb_dataset_round2/dataset_summary.json`。
- 已生成 `local_data/yolo_obb_dataset_round2/dataset_validation.json`。
- 图片/标签匹配问题：0。
- 标签字段数问题：0。
- 类别 ID 问题：0。
- 坐标范围问题：0。

说明：

- 该数据集已达到训练链路启动前的数据质量门。
- 由于样本量仍小，后续训练结果只能作为标题栏检测链路验证和小样本指标，不得直接宣称工业级泛化能力。

## 文档知识库整理需求

当前项目已经形成多类长期资料，包括调研成果、规则文件、实验计划、操作流程、RPD 和参考索引。继续将所有文档平铺在 `docs/` 下会降低可维护性。

本阶段需要：

- 记录 YOLO/OBB 训练规划依据，将外部调研、项目内路线和当前质量门整合为一份可检索文档。
- 将 `docs/` 分为：
  - `docs/research/`：调研笔记和横向学习结论。
  - `docs/plans/`：阶段计划、实验计划、实现计划。
  - `docs/workflows/`：人工操作流程和工具使用说明。
- 为 `docs/`、`references/`、`rules/`、`reports/` 增加 README 索引。
- 更新根目录 README，使用户能从入口文档找到当前项目结构和关键文件。
- 不移动 `local_data/`、`outputs/` 等本地私有或可再生产物。

完成状态：已完成。

整理结果：

- 新增 `docs/README.md` 作为公开文档总索引。
- 新增 `docs/research/`，存放调研笔记和横向学习结论。
- 新增 `docs/plans/`，存放阶段计划、实验计划和实现前规划。
- 新增 `docs/workflows/`，存放人工操作流程和工具使用说明。
- 新增 `docs/research/2026-06-26-yolo-obb-training-basis.md`，记录 YOLO/OBB 训练规划依据。
- 新增 `references/README.md`，索引外部资料样本。
- 新增 `rules/README.md`，索引长期规则。
- 新增 `reports/README.md`，索引 RPD 和阶段结果汇总。
- 更新根目录 `README.md`，加入当前文档入口、当前重点和本地私有目录约定。
- 已修正 RPD 与计划文档中的旧 `docs/*.md` 引用，避免移动后链接失效。

新的文档分层约定：

- 调研成果放入 `docs/research/`。
- 阶段规划放入 `docs/plans/`。
- 人工流程放入 `docs/workflows/`。
- 外部样本索引放入 `references/`。
- 长期项目规则放入 `rules/`。
- 需求、验收和阶段结果汇总放入 `reports/`。

YOLO/OBB 第二轮首训计划需求：

- 必须依据 `docs/research/2026-06-26-yolo-obb-training-basis.md` 和 YOLO/OBB 调试调研结论制定。
- 本轮训练只验证本地 YOLO/OBB 标题栏 detector 链路，不宣称工业级泛化能力。
- 首轮模型优先使用 nano 级 OBB 模型，降低配置压力。
- 训练产物必须输出到 ignored 的 `local_data/yolo_runs/`。
- 训练前必须检查 Ultralytics 是否安装、数据集 YAML 是否存在、数据集校验是否为 0 问题。
- 训练后必须生成预测图，并通过固定审核入口让用户复查。
- 若训练失败或预测差，必须按错误类型分层，不得直接调大模型或跳过分析。

计划文件：

- `docs/plans/018-yolo-obb-round2-training-plan.md`

YOLO/OBB 第二轮首训环境执行需求：

- 用户已同意按照 `docs/plans/018-yolo-obb-round2-training-plan.md` 继续。
- 本阶段必须先检查本机是否已安装 Ultralytics，不得直接假设环境可用。
- 若未安装 Ultralytics，需要安装训练依赖；安装后再次确认 `yolo` 命令和 Python 包可用。
- 训练前再次确认 `local_data/yolo_obb_dataset_round2/data.yaml`、`dataset_summary.json`、`dataset_validation.json` 存在且校验无问题。
- 训练产物必须写入 ignored 的 `local_data/yolo_runs/`。
- 若环境安装失败或训练命令不可用，必须停在环境问题分析，不得跳过到下一阶段。

完成状态：环境检查和依赖安装已完成。

环境处理结果：

- Python 版本：3.11.9。
- 已安装 Ultralytics：8.4.78。
- 已确认 `yolo version` 可用。
- 已确认 `local_data/yolo_obb_dataset_round2/data.yaml`、`dataset_summary.json`、`dataset_validation.json` 存在。
- 数据集校验问题数：0。

环境修复说明：

- Ultralytics 首次启动默认会写入用户目录 `C:\Users\dexterlu\AppData\Roaming\Ultralytics`，当前受限环境无法写入。
- 已改为在运行训练命令前设置 `YOLO_CONFIG_DIR=D:\project\codex\pictureAnalyse\local_data\ultralytics_config`。
- Ultralytics 实际配置目录为 `local_data/ultralytics_config/Ultralytics/`，保持在 ignored 的本地目录内，不进入公开仓库。
- Windows 控制台对 Ultralytics 包说明中的 emoji 存在 GBK 编码问题，后续训练命令统一设置 `PYTHONIOENCODING=utf-8`。

YOLO/OBB 第二轮首训结果：

- 训练模型：`yolo11n-obb.pt`。
- 训练设备：CPU。
- 训练轮数：40。
- 训练数据：`local_data/yolo_obb_dataset_round2/data.yaml`。
- 训练输出：`local_data/yolo_runs/round2_yolo11n_obb/`。
- 最后一轮 val 指标约为：precision 0.84772，recall 0.85714，mAP50 0.94389，mAP50-95 0.89811。
- 训练流程已完成，未出现数据加载、标签格式或路径错误。

产物整理说明：

- Ultralytics 将相对 `project=local_data/yolo_runs` 解释到默认 `runs/obb/` 下，已将实际训练目录移动回 `local_data/yolo_runs/round2_yolo11n_obb/`。
- 已将下载的预训练权重移动到 `local_data/models/yolo11n-obb.pt`。
- 已在 `.gitignore` 增加 `/runs/` 和常见模型权重后缀，防止训练产物误进入公开仓库。

YOLO/OBB 首训预测结果：

- 已使用 `best.pt` 对 train、val、test 分别运行 predict。
- train：26 张全部检出预测框。
- val：7 张全部检出预测框，其中 `sample_009` 出现 2 个预测框。
- test：7 张全部检出预测框，其中 `unclear90_001_from_sample_001` 出现 3 个预测框。
- 多框样本需要重点人工判断是否属于可接受冗余框、误检相似表格，或后处理应只取最高置信标题栏框。

固定审核入口：

- 当前待用户复查目录：`local_data/review_inbox/current/prediction_review/`。
- 当前复查页面：`local_data/review_inbox/current/prediction_review/review_index.html`。
- 当前填写表：`local_data/review_inbox/current/prediction_review/review_form.csv`。
- 本轮只要求复查 14 张 val/test 预测图，人工表只保留必要字段。

YOLO/OBB 首训预测人工复查结果：

- 用户已完成 `local_data/review_inbox/current/prediction_review/review_form.csv`。
- 复查记录总数：14。
- `预测框是否可接受=可以接受`：9。
- `预测框是否可接受=不可接受`：5。
- 不可接受样本：
  - `val/sample_009`：预测 2 框；多识别一个标题栏，正确标题栏框未完全覆盖，右上角识别框需要向上扩展并贴近图纸边缘。
  - `val/sample_020`：预测 1 框；识别框左边超出图纸范围过多。
  - `test/sample_001`：预测 1 框；将图纸中间零件误识别为标题栏，真实标题栏在右上方。
  - `test/sample_010`：预测 1 框；识别框向左、向上延展过多。
  - `test/unclear90_001_from_sample_001`：预测 3 框；只有左下角框完全正确，其余两个框将零件误识别为标题栏。
- 关键人工规则补充：一份图纸只有一个标题栏。后处理或训练评估不得静默接受多标题栏预测。
- 错误分层：
  - 多框误检：`val/sample_009`、`test/unclear90_001_from_sample_001`。
  - 零件误检成标题栏：`test/sample_001`、`test/unclear90_001_from_sample_001`。
  - 框范围过大或越界：`val/sample_020`、`test/sample_010`。
  - 标题栏未完全覆盖：`val/sample_009`。
- 结论：首训证明 YOLO/OBB 能学习标题栏候选，但当前预测结果未通过稳定可靠质量门；下一阶段必须先做预测错误分层与改进计划，不得直接扩大训练或进入完整 PDF 批处理。

YOLO/OBB 首训预测复查入口归档结果：

- 已归档本轮预测复查材料到 `local_data/review_inbox/archive/round2_prediction_review_20260627_reviewed/`。
- 已重置 `local_data/review_inbox/current/`。
- 当前 `current/` 只保留 `README.md`，提示当前没有待用户审核、填写或标注的文件。
- 归档目录保留 `prediction_review/` 下的 `review_index.html`、`review_form.csv` 和 14 张 val/test 预测图。
- 下一步必须先制定 YOLO/OBB 首训预测错误分层与改进计划，再决定是否进入补样本、后处理或再训练。

YOLO/OBB 首训预测错误分层与改进计划需求：

- 当前公开入口文档仍停留在训练前状态，需要更新为“训练、预测复查、归档已完成，下一步是错误分层与改进计划”。
- 必须新增一份计划文档，记录本轮 5 个不可接受样本的错误类型、可能原因、优先改进路线和质量门。
- 计划必须遵守稳定可靠优先，不得直接进入完整 PDF 批处理或盲目扩大训练。
- 计划必须区分：
  - 后处理层：一图只允许一个标题栏候选、最高置信/几何约束/NMS 或区域约束。
  - 数据层：是否需要补充负例、零件误检样本、边界过大样本和标题栏未完全覆盖样本。
  - 标注层：是否需要复查边界贴合规则，避免模型学习到过大或过窄的框。
  - 训练层：是否需要再训练、何时再训练、再训练前需要满足哪些质量门。
- 计划落地前必须先提交本 RPD/TODO 回滚点。

完成状态：已完成。

计划文件：

- `docs/plans/019-yolo-obb-prediction-error-improvement-plan.md`

同步更新：

- 已更新根目录 `README.md`，当前重点改为 YOLO/OBB 首训预测错误分层与改进。
- 已更新 `docs/README.md`，将错误分层与改进计划加入推荐阅读顺序和 plans 索引。

计划结论：

- 当前预测结果证明 detector 链路可用，但未通过稳定可靠质量门。
- 改进优先级为：后处理安全约束 -> 数据与标注复查 -> 再训练。
- 必须先处理“一页只有一个标题栏”的业务约束、多框误检、零件误检、边界过大/越界和标题栏未完整覆盖，再决定是否补样本或再训练。

YOLO/OBB 预测后处理与失败样本复查包规划需求：

- 当前 TODO 已进入 `规划 YOLO/OBB 预测后处理与失败样本复查包`。
- 本阶段不得直接实现后处理脚本、生成复查包或重新训练。
- 必须先新增计划文档，明确：
  - 预测后处理输入输出契约。
  - 一页只保留一个标题栏候选的仲裁规则。
  - 多框、零件误检、越界/过大、未完整覆盖四类问题的机器报告字段。
  - 失败样本复查包需要包含哪些图片副本、对比图和低噪声人工表。
  - 固定审核入口 `local_data/review_inbox/current/` 的发布与归档流程。
  - 后处理通过标准、失败标准和回滚点。
- 计划应优先保证人工复查便利和错误可解释，不得把模型置信度作为唯一判据。
- 计划落地前必须先提交本 RPD/TODO 回滚点。

完成状态：已完成。

计划文件：

- `docs/plans/020-yolo-obb-postprocess-review-pack-plan.md`

计划结论：

- 后处理输出必须分为 `accepted`、`needs_review`、`rejected`，模型原始预测框不得直接等同最终标题栏结果。
- 一页只允许一个最终标题栏候选；多框、冲突、疑似零件误检、越界或边界异常必须进入仲裁或人工复核。
- 失败样本复查包应优先包含 5 个不可接受样本和少量正例对照，展示原图、预测 overlay、标注 overlay、后处理候选和必要 OpenCV 参考。
- 人工填写表只保留低噪声字段，完整候选分数、坐标和 JSON 放入机器报告。
- 下一步如要实现脚本，仍必须先规划实现、更新 RPD/TODO、提交回滚点。

YOLO/OBB 预测后处理脚本实现规划需求：

- 当前 TODO 已进入 `规划 YOLO/OBB 预测后处理脚本实现`。
- 本阶段仍不得直接实现脚本。
- 必须新增实现计划，明确：
  - 脚本文件名和职责边界。
  - 是否复用 `scripts/common/obb_utils.py`、`scripts/yolo_obb/build_yolo_prediction_review_pack.py` 等既有工具。
  - 如何读取 YOLO predict 的标签、图像尺寸、人工 review CSV 和数据集标签。
  - 如何输出 `postprocess_report.json`、`postprocess_summary.csv` 和复查包 manifest。
  - 如何处理 GBK/UTF-8 人工 CSV 编码问题。
  - 如何保证不覆盖当前固定审核入口中的未归档任务。
  - 如何做最小验证，不直接进入完整 PDF 批处理。
- 计划落地前必须先提交本 RPD/TODO 回滚点。

完成状态：已完成。

计划文件：

- `docs/plans/021-yolo-obb-postprocess-implementation-plan.md`

计划结论：

- 后处理脚本建议命名为 `scripts/yolo_obb/postprocess_yolo_obb_predictions.py`。
- 第一版只处理 val/test 14 张预测结果，不发布固定审核入口，不处理完整 PDF。
- 脚本输出 `postprocess_report.json`、`postprocess_summary.csv`、`failure_case_manifest.json` 到 `local_data/yolo_postprocess/round2_first_train/`。
- 必须兼容 YOLO predict 10 字段标签和训练标签 9 字段标签。
- 必须兼容人工 review CSV 的 UTF-8 BOM 与 GBK/ANSI 编码。
- 实现后最低验证要求：14 条样本全部出现，多框样本被标记为 `multi_candidate`，人工不可接受样本不得全部进入 `accepted`。

YOLO/OBB 预测后处理脚本实现需求：

- 当前 TODO 已进入 `实现 YOLO/OBB 预测后处理脚本`。
- 实现必须严格遵守 `docs/plans/021-yolo-obb-postprocess-implementation-plan.md`。
- 本阶段只新增脚本并对 val/test 14 张首训预测结果运行最小验证。
- 本阶段不得发布固定审核入口、不得重新训练、不得处理完整 PDF。
- 输出目录为 `local_data/yolo_postprocess/round2_first_train/`，保持在 ignored 本地目录内。
- 实现前必须提交本 RPD/TODO 回滚点。

YOLO/OBB 预测后处理脚本实现结果：

- 已新增 `scripts/yolo_obb/postprocess_yolo_obb_predictions.py`。
- 已运行 `python scripts\yolo_obb\postprocess_yolo_obb_predictions.py`。
- 已生成本地报告目录 `local_data/yolo_postprocess/round2_first_train/`。
- 输出文件：
  - `postprocess_report.json`
  - `postprocess_summary.csv`
  - `failure_case_manifest.json`
- 运行摘要：
  - total：14
  - accepted：8
  - needs_review：6
  - rejected：0
  - missing_prediction_label：0
  - multi_candidate：2
  - part_false_positive：5
  - boundary_or_size_issue：2
  - manual_rejected：5
  - failure_case_manifest 记录数：9
- 质量门结果：
  - 14 张 val/test 样本全部进入后处理报告。
  - `val/sample_009` 和 `test/unclear90_001_from_sample_001` 均已标记 `multi_candidate`。
  - 用户人工判定的 5 个不可接受样本均进入 `needs_review`，没有被自动接受。
  - 额外将用户人工判定可接受的 `test/aug90_002_from_sample_010` 标记为 `needs_review/part_false_positive`；这是偏保守的误拦截，当前按稳定可靠优先保留，后续在失败样本复查包或阈值校准中处理。
- 本阶段未发布固定审核入口，未重新训练，未处理完整 PDF。

YOLO/OBB 后处理失败样本复查包实现规划需求：

- 当前 TODO 已进入 `规划 YOLO/OBB 后处理失败样本复查包实现`。
- 本阶段不得直接实现复查包脚本或发布固定审核入口。
- 必须新增计划文档，明确：
  - 复查包脚本文件名和职责边界。
  - 输入 `postprocess_report.json` 与 `failure_case_manifest.json` 的方式。
  - 固定审核入口 `local_data/review_inbox/current/` 的安全检查。
  - HTML、CSV 和机器报告的输出结构。
  - 人工表低噪声字段。
  - 失败样本和正例对照的覆盖要求。
  - 实现后的最低验证标准。
- 计划落地前必须先提交本 RPD/TODO 回滚点。

完成状态：已完成。

计划文件：

- `docs/plans/022-yolo-obb-postprocess-failure-review-pack-implementation-plan.md`

计划结论：

- 建议新增 `scripts/yolo_obb/build_yolo_postprocess_failure_review_pack.py`。
- 第一版读取 `failure_case_manifest.json`，预计发布 6 条 `needs_review` 和 3 条 positive control，共 9 条记录。
- 复查包必须发布到 `local_data/review_inbox/current/yolo_postprocess_failure_review/`，并复制图片副本到当前入口内。
- 人工 CSV 只保留问题类型确认、最终候选是否可接受、是否补标、是否修正原标注和备注等必要字段。
- `machine_report.json` 单独保留完整路径、issue_types 和分组信息，避免污染人工审核表。
- 下一步如要实现脚本，仍必须先提交本计划、RPD 和 TODO 回滚点。

YOLO/OBB 后处理失败样本复查包实现结果：

- 已新增 `scripts/yolo_obb/build_yolo_postprocess_failure_review_pack.py`。
- 已通过语法检查：`python -m py_compile scripts\yolo_obb\build_yolo_postprocess_failure_review_pack.py`。
- 已运行 `python scripts\yolo_obb\build_yolo_postprocess_failure_review_pack.py --force` 发布复查包到固定入口。
- 当前固定入口：
  - `local_data/review_inbox/current/README.md`
  - `local_data/review_inbox/current/yolo_postprocess_failure_review/review_index.html`
  - `local_data/review_inbox/current/yolo_postprocess_failure_review/review_form.csv`
  - `local_data/review_inbox/current/yolo_postprocess_failure_review/machine_report.json`
- 复查包内容：
  - 总记录数：9
  - failure：6
  - positive_control：3
  - 所有展示图片均复制到 `current/yolo_postprocess_failure_review/images/` 下。
  - 预测标签和 ground truth 标签副本复制到 `current/yolo_postprocess_failure_review/labels/` 下，供机器报告和后续归档使用。
- CSV 覆盖样本：
  - `val/sample_009`
  - `val/sample_020`
  - `test/aug90_002_from_sample_010`
  - `test/sample_001`
  - `test/sample_010`
  - `test/unclear90_001_from_sample_001`
  - `val/aug90_007_from_sample_020`
  - `val/aug90_012_from_sample_034`
  - `val/sample_040`
- 质量门结果：
  - 固定入口已从“无待审核任务”切换为本轮复查任务。
  - `review_form.csv` 记录数与 `failure_case_manifest.json` 一致。
  - 6 条 `needs_review` 样本全部出现在 CSV。
  - 3 条 positive control 出现在 CSV。
  - `git status --short` 未显示 `local_data/` 审核包文件待提交。
- 下一步等待用户填写 `review_form.csv`，完成后再归档当前入口并记录归档位置。

YOLO/OBB 后处理复查归档与贴边规则落地规划需求：

- 用户已填写 `local_data/review_inbox/current/yolo_postprocess_failure_review/review_form.csv`。
- 用户补充关键业务规律：标题栏一定会贴着图纸边缘的框线，标题栏和图纸周围的框线不会存在任何空隙。
- 本阶段必须先规划，再归档固定入口和更新长期规则。
- 本阶段不得直接重新训练、修改 YOLO/OBB 标签、调整后处理阈值或处理完整 PDF。
- 必须记录：
  - 用户复查结果统计。
  - 需要补标和不需要修正原标注的结论。
  - 当前固定入口归档位置。
  - 贴边规则对后处理的影响。
- 计划落地前必须先提交本 RPD/TODO 回滚点。

完成状态：已完成。

计划文件：

- `docs/plans/023-yolo-obb-postprocess-review-archive-and-edge-contact-rule-plan.md`

计划结论：

- 本轮复查 9 条记录，4 条最终候选可以接受，5 条不可接受。
- `val/sample_009` 需要补标；9 条均不需要修正原标注。
- `test/aug90_002_from_sample_010` 被后处理误拦截，用户确认识别没有错误，说明当前 `part_false_positive`/中心区域惩罚规则过严。
- 贴边规则应升级为长期业务规则：真正标题栏必须贴图纸外框线且无空隙；图纸主体内部与外框线有空隙的表格状零件不应作为标题栏。
- 下一步归档当前入口到 `local_data/review_inbox/archive/yolo_postprocess_failure_review_20260627_reviewed/`，重置 `current/`，并更新长期规则文档。

YOLO/OBB 后处理复查归档与贴边规则落地结果：

- 已归档当前固定审核入口到 `local_data/review_inbox/archive/yolo_postprocess_failure_review_20260627_reviewed/`。
- 已重置 `local_data/review_inbox/current/README.md`，当前没有待用户审核、填写或标注的文件。
- 已将贴边规则写入 `rules/mechanical-drawing-rotation.md`。
- 本轮复查结果：
  - 总记录数：9。
  - 最终候选可以接受：4。
  - 最终候选不可接受：5。
  - 需要补标：1，`val/sample_009`。
  - 需要修正原标注：0。
- 逐条结论：
  - `val/sample_009`：不可接受，需要补标，不需要修正原标注；备注为把左下角的零件误认为标题栏。
  - `val/sample_020`：不可接受，不需要补标，不需要修正原标注；预测框越界/范围过大。
  - `test/aug90_002_from_sample_010`：可以接受，不需要补标，不需要修正原标注；用户确认识别没有任何错误，说明当前误检规则过严。
  - `test/sample_001`：不可接受，不需要补标，不需要修正原标注；把图纸下方的零件误认为标题栏。
  - `test/sample_010`：不可接受，不需要补标，不需要修正原标注；只存在预测框范围过大问题。
  - `test/unclear90_001_from_sample_001`：不可接受，不需要补标，不需要修正原标注；多候选/零件误检。
  - `val/aug90_007_from_sample_020`：可以接受，不需要补标，不需要修正原标注；正例对照。
  - `val/aug90_012_from_sample_034`：可以接受，不需要补标，不需要修正原标注；正例对照。
  - `val/sample_040`：可以接受，不需要补标，不需要修正原标注；正例对照。
- 新业务规则：
  - 真正标题栏必须贴着图纸外框线，标题栏外边界和图纸周围框线之间不应存在空隙。
  - 仅靠近边缘但没有贴住图框线的候选，应降权或进入人工复核。
  - 位于图纸主体内部、与外框线存在明显间隔的表格状零件或局部结构，不应作为标题栏。
- 后续影响：
  - 当前 `edge_proximity_score` 只能表达“靠近边缘”，不足以表达“贴住图纸外框线”。
  - 下一步应规划并实现 `frame_contact_score` 或 `touches_frame_line`，优先用于区分零件误检和真实标题栏。
  - `test/aug90_002_from_sample_010` 应作为规则过严的回归样本，避免贴边规则升级后误伤真实标题栏。

YOLO/OBB 后处理贴边规则升级规划需求：

- 当前 TODO 已进入 `规划 YOLO/OBB 后处理贴边规则升级`。
- 用户已确认“标题栏必须贴图纸外框线且无空隙”是强业务规则。
- 当前 `edge_proximity_score` 只能表达靠近页面边缘，不能表达候选框是否真正贴住图纸外框线。
- 当前 `test/aug90_002_from_sample_010` 被误标为 `part_false_positive`，用户确认识别没有任何错误，是本轮必须保护的回归样本。
- 本阶段不得重新训练、修改标签、发布审核入口或处理完整 PDF。
- 必须新增计划文档，明确：
  - 图框线检测策略。
  - 候选框贴图框线计算字段。
  - 后处理规则如何避免误伤真实标题栏。
  - 回归样本和验证标准。
- 计划落地前必须先提交本 RPD/TODO 回滚点。

完成状态：已完成。

计划文件：

- `docs/plans/024-yolo-obb-postprocess-frame-contact-upgrade-plan.md`

计划结论：

- 第一版采用轻量 OpenCV/图像投影策略检测图纸四周外框线。
- 候选级新增 `nearest_frame_side`、`frame_line_position_normalized`、`frame_contact_gap_normalized`、`frame_contact_score`、`touches_frame_line`、`frame_contact_status`。
- 若候选贴住图框线、面积不异常且不明显越界，即使中心落入当前 `center_region`，也不应直接标记为 `part_false_positive`。
- 若候选与图框线有明显间隙，或位于图纸主体内部且不贴图框线，应保持零件误检风险并进入 `needs_review`。
- 实现后必须验证 14 条 val/test 全覆盖，`test/aug90_002_from_sample_010` 不再出现 `part_false_positive`，5 条用户确认不可接受样本不得全部自动通过。

YOLO/OBB 后处理贴边规则升级结果：

- 已更新 `scripts/yolo_obb/postprocess_yolo_obb_predictions.py`。
- 新增轻量图框线检测：
  - 使用 Pillow 读取数据集原图。
  - 转灰度后在页面四周边缘带统计暗像素投影。
  - 估计 left、right、top、bottom 四条图纸外框线位置。
- 新增候选级贴边字段：
  - `nearest_frame_side`
  - `frame_line_position_normalized`
  - `frame_contact_gap_normalized`
  - `frame_contact_score`
  - `touches_frame_line`
  - `frame_contact_status`
- 新增记录级字段：
  - `frame_detection`
- 新增配置字段：
  - `frame_search_band=0.18`
  - `frame_contact_threshold=0.025`
  - `frame_dark_threshold=190`
  - `frame_weak_threshold=0.004`
- 后处理规则调整：
  - 候选若中心落入 `center_region`，但同时 `touches_frame_line=true`，不再仅因中心区域惩罚标记为 `part_false_positive`。
  - 候选若与最近图框线存在明显间隙，仍保留 `frame_contact_gap` 证据，可用于零件误检判断。
- 验证命令：
  - `python -m py_compile scripts\yolo_obb\postprocess_yolo_obb_predictions.py`
  - `python scripts\yolo_obb\postprocess_yolo_obb_predictions.py`
- 新后处理摘要：
  - total：14
  - accepted：9
  - needs_review：5
  - rejected：0
  - missing_prediction_label：0
  - multi_candidate：2
  - part_false_positive：3
  - boundary_or_size_issue：2
  - manual_rejected：5
  - failure_case_manifest 记录数：8
- 关键回归结果：
  - `test/aug90_002_from_sample_010` 已从 `needs_review/part_false_positive` 变为 `accepted`；该候选贴住 left 图框线，`frame_contact_gap_normalized=0.004524164860239599`，`touches_frame_line=true`。
  - 用户确认不可接受的 5 条样本仍全部进入 `needs_review`，没有被自动放行。
  - `test/sample_001` 继续标记 `part_false_positive/manual_rejected`，其候选与 bottom 图框线存在明显间隙，`touches_frame_line=false`。
  - `test/sample_010` 不再标记 `part_false_positive`，但仍因 `manual_rejected/boundary_too_large` 进入 `needs_review`，符合用户复查结论“只存在预测框范围过大问题”。
  - 多候选样本 `val/sample_009` 和 `test/unclear90_001_from_sample_001` 仍进入 `needs_review`，未静默通过。
- 结论：
  - 贴图框线证据有效修正了过严的中心区域误检规则。
  - 当前后处理仍保守拦截用户确认不可接受样本。
  - 下一步应围绕 `val/sample_009` 的补标需求与多候选误检做小范围数据/标注规划，不应直接进入完整 PDF 批处理。

YOLO/OBB `sample_009` 补标与复查规划需求：

- 当前 TODO 已进入 `规划 YOLO/OBB sample_009 补标与后处理复查`。
- 用户已在后处理复查表中确认 `val/sample_009` 需要补标，但不需要修正原标注。
- `sample_009` 的主要问题是多候选框、左下角零件误检、正确标题栏候选未完整覆盖。
- 本阶段不得直接重训、批量修改数据集、发布完整 PDF 批处理或新增 YOLO 类别。
- 必须新增计划文档，明确：
  - 本轮只处理 `sample_009`。
  - 固定审核入口发布结构。
  - 人工表只保留当前判断需要的字段。
  - 零件误检区域只记录为负例说明，不混入 `title_block` 标签。
  - 用户确认后再决定是否重新标注、转标签、校验 overlay 或规划再训练。
- 计划落地前必须先提交本 RPD/TODO 回滚点。

完成状态：已完成。

计划文件：

- `docs/plans/025-yolo-obb-sample-009-supplement-review-plan.md`

计划结论：

- 下一步只发布 `sample_009` 的小复查包，不重训、不改数据集。
- 复查目标是确认当前标题栏标注是否可沿用、是否需要重新标注标题栏边界、是否作为难例补强，以及左下角误检零件是否只记录为负例说明。
- 若用户确认无需重画，则后续可把 `sample_009` 作为 hard-case 补强样本进入再训练规划。
- 若用户确认需要重新画标题栏边界，则再执行 JSON 转换、标签校验和 overlay 复查。

YOLO/OBB `sample_009` 补标复查入口发布结果：

- 已发布固定审核入口：
  - `local_data/review_inbox/current/README.md`
  - `local_data/review_inbox/current/sample_009_supplement_review/review_index.html`
  - `local_data/review_inbox/current/sample_009_supplement_review/review_form.csv`
  - `local_data/review_inbox/current/sample_009_supplement_review/machine_report.json`
- 本轮只包含 1 条样本：`sample_009`。
- 已复制到 `current/` 内的审核材料：
  - 预测结果图：`images/prediction_sample_009.jpg`
  - 当前人工标注 overlay：`images/current_label_overlay_sample_009.png`
  - 数据集原图：`images/dataset_sample_009.png`
  - 预测标签副本：`labels/prediction_sample_009.txt`
  - ground truth 标签副本：`labels/ground_truth_sample_009.txt`
  - 可选重新标注材料：`to_label/sample_009.png`、`to_label/sample_009.json`
- `review_form.csv` 只保留当前判断需要的字段：
  - 当前标题栏标注是否可沿用
  - 是否需要重新标注标题栏边界
  - 是否作为难例补强
  - 误检零件是否只记录为负例说明
  - 备注
- 已校验：
  - 固定入口发布前为空任务。
  - CSV 只有 1 条记录。
  - 审核页面引用图片均为 `current/` 内副本。
  - `git status --short` 未显示 `local_data/` 审核包文件待提交。
- 下一步等待用户填写 `review_form.csv`，然后归档当前入口并决定是否重画标注或进入 hard-case 再训练规划。

YOLO/OBB `sample_009` 复查归档与难例补强规划需求：

- 用户已填写 `local_data/review_inbox/current/sample_009_supplement_review/review_form.csv`。
- 用户复查结论：
  - 当前标题栏标注可沿用：是。
  - 是否需要重新标注标题栏边界：否。
  - 是否作为难例补强：是。
  - 误检零件是否只记录为负例说明：是。
  - 备注：左下角零件误检为标题栏，作为难例补强。
- 本阶段必须先规划，再归档固定审核入口。
- 本阶段不得重新训练、修改标签、转换新标签、生成 overlay 复查包或新增负例类别。
- 必须记录归档位置和后续 hard-case 决策。
- 计划落地前必须先提交本 RPD/TODO 回滚点。

完成状态：已完成。

计划文件：

- `docs/plans/026-yolo-obb-sample-009-review-archive-hardcase-plan.md`

计划结论：

- `sample_009` 当前人工标题栏标注可以沿用，不需要重画边界。
- 左下角误检零件只记录为负例说明，不进入 YOLO 标签。
- `sample_009` 应进入后续 hard-case 再训练准备规划，作为多候选/零件误检难例。
- 下一步归档当前入口到 `local_data/review_inbox/archive/sample_009_supplement_review_20260627_reviewed/`，并重置 `current/`。

YOLO/OBB `sample_009` 复查归档与难例补强结果：

- 已归档当前固定审核入口到 `local_data/review_inbox/archive/sample_009_supplement_review_20260627_reviewed/`。
- 已重置 `local_data/review_inbox/current/README.md`，当前没有待用户审核、填写或标注的文件。
- 已读取用户填写的 `review_form.csv`，编码为 GB18030/GBK 兼容。
- 用户最终复查结论：
  - 当前标题栏标注可沿用：是。
  - 是否需要重新标注标题栏边界：否。
  - 是否作为难例补强：是。
  - 误检零件是否只记录为负例说明：是。
  - 备注：左下角零件误检为标题栏，作为难例补强。
- 决策：
  - 不修改 `sample_009` 的现有人工标题栏标注。
  - 不重新标注标题栏边界。
  - 不为左下角误检零件新增 YOLO 标签或负框。
  - 将 `sample_009` 作为 hard-case 输入，进入后续再训练准备规划。
- 下一步：
  - 规划 YOLO/OBB hard-case 再训练准备。
  - hard-case 清单至少应包含 `sample_009`，并记录错误类型为多候选、零件误检、标题栏未完整覆盖。
  - 在重新训练前仍需先制定计划、更新 RPD/TODO 并提交回滚点。

YOLO/OBB hard-case 再训练准备规划需求：

- 用户判断：类似 `sample_009` 的图纸应整体作为“零件误检为标题栏”的难例样本处理，不应只围绕单个样本逐步尝试。
- 该判断成立：当前错误集中暴露出零件、局部框线或表格状结构误检为标题栏的系统性风险。
- 本阶段必须先规划 hard-case 组策略，再生成清单。
- 本阶段不得立即训练、修改现有数据集、批量改标签、新增负例类别或处理完整 PDF。
- 必须明确：
  - 哪些样本属于已确认零件误检/多候选失败。
  - 哪些样本属于边界/范围异常失败。
  - 哪些样本作为保护性正例，避免策略过严。
  - 误检零件只记录为负例说明，不进入 YOLO 标签。
  - 再训练前的质量门。
- 计划落地前必须先提交本 RPD/TODO 回滚点。

完成状态：已完成。

计划文件：

- `docs/plans/027-yolo-obb-hardcase-retraining-prep-plan.md`

计划结论：

- hard-case 应成组建设，而不是只修 `sample_009`。
- 第一组必须纳入 `sample_009`、`sample_001`、`unclear90_001_from_sample_001`。
- 边界异常样本 `sample_020`、`sample_010` 应作为定位质量 hard-case 纳入。
- 保护性正例至少保留 `aug90_002_from_sample_010`、`aug90_007_from_sample_020`、`sample_040`。
- 每张图仍只标一个真实 `title_block`；误检零件只写入 metadata，不画成标签。
- 下一步生成本地 hard-case 清单到 `local_data/yolo_hardcases/round3_retraining_prep/`。

YOLO/OBB hard-case 再训练准备清单生成结果：

- 已新增 `scripts/yolo_obb/build_yolo_hardcase_manifest.py`。
- 已生成本地清单到 `local_data/yolo_hardcases/round3_retraining_prep/`：
  - `hardcase_manifest.json`
  - `hardcase_manifest.csv`
  - `hardcase_summary.json`
- 清单总数：8。
- 分组统计：
  - 零件误检 + 多候选：2，`sample_009`、`unclear90_001_from_sample_001`。
  - 零件误检：1，`sample_001`。
  - 边界/范围异常：2，`sample_020`、`sample_010`。
  - 保护性正例：3，`aug90_002_from_sample_010`、`aug90_007_from_sample_020`、`sample_040`。
- 质量门结果：
  - 计划要求的 8 个样本全部覆盖。
  - 数据集图片、真实标题栏标签、预测图片和预测标签均存在。
  - 8 个样本的真实标题栏标签均为单条 `title_block`。
  - 误检零件只记录在 `negative_note` metadata 中，没有写入 YOLO 标签。
  - `quality_gate_passed=true`。
- 验证命令：
  - `python -m py_compile scripts\yolo_obb\build_yolo_hardcase_manifest.py`
  - `python scripts\yolo_obb\build_yolo_hardcase_manifest.py`
- 下一步：
  - 在规划 round3 数据集构建前，优先决定是否只把这 8 条作为最小 hard-case 补强，还是从训练集继续扩展相似误检风险样本。
  - 不建议直接跳到完整 PDF 批处理；应先构建 round3 小数据集并做 overlay/预测复查。

YOLO/OBB round3 hard-case 小数据集构建规划需求：

- 用户已同意先构建 round3 小数据集，而不是直接重训完整流程。
- 本阶段必须先规划，再提交 RPD/TODO 回滚点，然后才构建数据集和发布 overlay 复查入口。
- round3 必须独立输出到 `local_data/yolo_obb_dataset_round3/`，不得覆盖 round2。
- 数据策略：
  - 已确认失败 hard-case 进入训练集，用于补强零件误检、多候选和范围异常。
  - 保护性正例保留在验证集，用于防止 hard-case 策略过严。
  - 从 round2 train 补入少量普通正例，避免模型只学习难例而损伤正常召回。
- 标注策略：
  - 每张图仍只保留真实 `title_block` 标签。
  - 误检零件只保留在 metadata 或说明中，不进入 YOLO 标签。
- 本阶段不启动训练、不修改 round2 标签、不处理完整 PDF。

完成状态：已规划。

计划文件：

- `docs/plans/028-yolo-obb-round3-hardcase-dataset-plan.md`

计划结论：

- 下一步新增 round3 数据集构建脚本。
- 输出 `data.yaml`、`dataset_summary.json`、`round3_manifest.csv` 和 images/labels split 目录。
- 构建后必须运行标签质量校验和 overlay 复查包发布。
- 用户复查 round3 overlay 通过后，再进入 round3 小规模训练规划。

YOLO/OBB round3 hard-case 小数据集构建结果：

- 已新增 `scripts/yolo_obb/build_yolo_obb_round3_dataset.py`。
- 已增强通用校验链路：
  - `scripts/common/obb_utils.py` 支持 manifest 中的 `label_path`。
  - `scripts/yolo_obb/validate_obb_dataset.py` 支持 `--allow-source-split-overlap`，用于显式记录保护性正例同源重叠。
- 已生成本地 round3 数据集：
  - `local_data/yolo_obb_dataset_round3/data.yaml`
  - `local_data/yolo_obb_dataset_round3/dataset_summary.json`
  - `local_data/yolo_obb_dataset_round3/round3_manifest.csv`
  - `local_data/yolo_obb_dataset_round3/images/{train,val,test}/`
  - `local_data/yolo_obb_dataset_round3/labels/{train,val,test}/`
- 数据集统计：
  - 总数：24。
  - train：21。
  - val：3。
  - test：0。
  - hardcase_train：5。
  - protective_positive：3。
  - normal_positive：16。
- hard-case 覆盖：
  - `sample_009`
  - `sample_001`
  - `unclear90_001_from_sample_001`
  - `sample_020`
  - `sample_010`
  - `aug90_002_from_sample_010`
  - `aug90_007_from_sample_020`
  - `sample_040`
- 标签策略：
  - 24 个样本均为单条真实 `title_block` 标签。
  - 误检零件只保留在 `negative_note` 和复查说明中，没有进入 YOLO 标签。
- 校验结果：
  - `python -m py_compile scripts\common\obb_utils.py scripts\yolo_obb\validate_obb_dataset.py scripts\yolo_obb\build_yolo_obb_round3_dataset.py`
  - `python scripts\yolo_obb\validate_obb_dataset.py --manifest local_data\yolo_obb_dataset_round3\round3_manifest.csv --labels-dir local_data\yolo_obb_dataset_round3\labels --output-dir local_data\yolo_obb_dataset_round3\validation --allow-source-split-overlap`
  - total_samples：24。
  - samples_with_labels：24。
  - missing_labels：0。
  - total_labels：24。
  - error_count：0。
  - warning_count：0。
  - source_split_leakage_count：2，属于 `sample_020`、`sample_010` 的保护性正例同源重叠，策略为 `intentional_protective_overlap_for_val_guardrails`。
- overlay 结果：
  - 脚本内置 overlay：24 张。
  - 通用 `visualize_obb_labels.py` overlay：24 张，缺图/缺标签/空标签/解析错误均为 0。
- 固定审核入口：
  - `local_data/review_inbox/current/README.md`
  - `local_data/review_inbox/current/round3_overlay_review/review_index.html`
  - `local_data/review_inbox/current/round3_overlay_review/review_form.csv`
  - `local_data/review_inbox/current/round3_overlay_review/machine_report.json`
- 下一步：
  - 等待用户填写 `review_form.csv`，确认 round3 红框是否只框真实标题栏。
  - 用户确认通过后，再归档当前入口并规划 round3 小规模训练。

YOLO/OBB round3 overlay 复查归档与训练准备规划需求：

- 用户已完成 `local_data/review_inbox/current/round3_overlay_review/review_form.csv`。
- 用户确认：24 条 round3 overlay 全部正确，均不需要重画。
- 本阶段必须先规划，再归档当前固定审核入口。
- 本阶段不启动训练、不修改标签、不处理完整 PDF。
- 必须记录：
  - 用户审核结论。
  - 当前入口归档位置。
  - `current/` 重置状态。
  - round3 数据集是否具备进入小规模训练规划的前提。

完成状态：已规划。

计划文件：

- `docs/plans/029-yolo-obb-round3-overlay-archive-training-prep-plan.md`

计划结论：

- 下一步归档当前入口到 `local_data/review_inbox/archive/round3_overlay_review_20260628_approved/`。
- 归档后重置 `local_data/review_inbox/current/README.md` 为无待审核任务。
- round3 数据集可进入小规模训练规划，但训练仍需单独计划和回滚点。

YOLO/OBB round3 overlay 复查归档与训练准备结果：

- 已归档当前固定审核入口到 `local_data/review_inbox/archive/round3_overlay_review_20260628_approved/`。
- 已重置 `local_data/review_inbox/current/README.md`，当前没有待用户审核、填写或标注的文件。
- 用户审核结论：
  - round3 overlay 共 24 条。
  - 24 条标题栏红框全部正确。
  - 24 条均不需要重画。
- 归档内容包含：
  - `README.md`
  - `round3_overlay_review/review_index.html`
  - `round3_overlay_review/review_form.csv`
  - `round3_overlay_review/machine_report.json`
  - `round3_overlay_review/images/`
- 决策：
  - 不修改 round3 标签。
  - 不重新发布标注任务。
  - round3 数据集具备进入小规模训练规划的前提。
- 下一步：
  - 规划 YOLO/OBB round3 小规模训练。
  - 训练规划必须明确权重来源、训练参数、输出目录、训练后预测复查范围和 round2/round3 对比方式。

YOLO/OBB round3 小规模训练规划需求：

- round3 overlay 已由用户确认全部正确。
- 当前固定审核入口已重置为空任务。
- round3 数据集具备训练前提，但仍必须先规划并提交回滚点。
- 本阶段训练目标是针对 round2 暴露的零件误检、多候选和范围过大问题做小规模补强。
- 本阶段不得处理完整 PDF，不得跳过训练后预测复查。

完成状态：已规划。

计划文件：

- `docs/plans/030-yolo-obb-round3-training-plan.md`

计划结论：

- 首选从 `local_data/yolo_runs/round2_yolo11n_obb/weights/best.pt` 继续训练。
- 训练数据使用 `local_data/yolo_obb_dataset_round3/data.yaml`。
- 建议命令：
  - `yolo obb train model=local_data/yolo_runs/round2_yolo11n_obb/weights/best.pt data=local_data/yolo_obb_dataset_round3/data.yaml epochs=25 imgsz=1024 batch=2 plots=True project=local_data/yolo_runs name=round3_yolo11n_obb_hardcase`
- 训练后必须预测 round3 train、round3 val、round2 test、round2 val。
- 训练后必须发布预测复查包到固定审核入口，由用户复查后再判断 round3 是否优于 round2。

YOLO/OBB round3 小规模训练与预测复查入口发布结果：

- 已运行 round3 小规模训练。
- 训练命令：
  - `yolo obb train model=local_data/yolo_runs/round2_yolo11n_obb/weights/best.pt data=local_data/yolo_obb_dataset_round3/data.yaml epochs=25 imgsz=1024 batch=2 plots=True project=local_data/yolo_runs name=round3_yolo11n_obb_hardcase exist_ok=True`
- 实际训练环境：
  - Ultralytics：8.4.78。
  - Python：3.11.9。
  - torch：2.8.0+cu129。
  - device：CPU。
- 实际训练输出：
  - `runs/obb/local_data/yolo_runs/round3_yolo11n_obb_hardcase/`
  - 该目录位于 `.gitignore` 覆盖的 `/runs/` 下，不进入 Git。
- 最终验证摘要：
  - val images：3。
  - val instances：3。
  - Box(P)：0.981。
  - Box(R)：1.0。
  - mAP50：0.995。
  - mAP50-95：0.995。
- 已生成四组预测：
  - `local_data/yolo_predictions/round3_train/`
  - `local_data/yolo_predictions/round3_val/`
  - `local_data/yolo_predictions/round3_round2_test/`
  - `local_data/yolo_predictions/round3_round2_val/`
- 关键预测观察：
  - round3 train：21 张均生成预测；5 条 hard-case train 均为单候选。
  - round3 val：3 张均生成预测；`aug90_002_from_sample_010` 出现 2 个候选。
  - round2 test 回归：7 张均生成预测；`aug90_002_from_sample_010` 出现 2 个候选。
  - round2 val 回归：7 张均生成预测，均为单候选。
  - `sample_009`、`sample_001`、`unclear90_001_from_sample_001` 在本轮预测中均为单候选，需人工确认框位置是否可接受。
- 已新增复查包脚本：
  - `scripts/yolo_obb/build_yolo_round3_prediction_review_pack.py`
- 已发布固定审核入口：
  - `local_data/review_inbox/current/README.md`
  - `local_data/review_inbox/current/round3_prediction_review/review_index.html`
  - `local_data/review_inbox/current/round3_prediction_review/review_form.csv`
  - `local_data/review_inbox/current/round3_prediction_review/machine_report.json`
- 复查包内容：
  - 总记录数：22。
  - 预测框数量不是 1 的重点样本：2，均为 `aug90_002_from_sample_010`，分别来自 round3 protective val 和 round2 test regression。
  - 16 条普通 train 正例未放入当前人工入口，避免低价值复查噪声。
- 下一步：
  - 等待用户填写 `review_form.csv`。
  - 重点确认 `aug90_002_from_sample_010` 的两个候选是否可接受，是否属于新增多候选风险。
  - 用户复查后再归档当前入口，并决定 round3 是否优于 round2。

标题栏规范调研与 round3 预测复查归档规划需求：

- 用户已填写 round3 预测复查表。
- 用户补充：标题栏内部文字和表格结构有独有组合规则，应先调研机械制图标题栏规范。
- 本阶段必须先规划，再归档当前固定入口和开展调研。
- 调研重点：
  - 标题栏内常见规范字段。
  - 字段组合规则，而不是单词命中。
  - 标题栏内部不规则格子和大小不一单元格。
  - 标题栏与明细栏、技术要求表、零件局部表格的区别。
- 本阶段不重训、不改标签、不实现 OCR/VLM。

完成状态：已规划。

计划文件：

- `docs/plans/031-title-block-standard-research-and-round3-prediction-archive-plan.md`

计划结论：

- 归档当前入口到 `local_data/review_inbox/archive/round3_prediction_review_20260628_reviewed/`。
- 新增标题栏规范调研索引和研究笔记。
- 更新 `rules/mechanical-drawing-rotation.md`，将标题栏字段组合和表格结构作为辅助证据写入长期规则。

YOLO/OBB round3 预测复查归档与标题栏规范调研结果：

- 用户已完成 round3 预测复查表并补充标题栏规则：
  - 标题栏内部表格有大小差异，行列大概率不规则。
  - 标题栏内部应成组出现设计、校对、工艺、标准、审核、批准、制图、日期、材料、表面积等字段。
  - 单个表格出现这些词不代表它就是标题栏，必须看字段组合和结构规则。
- 已归档当前固定审核入口到 `local_data/review_inbox/archive/round3_prediction_review_20260628_reviewed/`。
- 已重置 `local_data/review_inbox/current/README.md`，当前没有待用户审核、填写或标注的文件。
- 用户复查结论：
  - round3 预测复查入口共 22 条重点记录。
  - 整体预测可接受。
  - 当时对 `aug90_002_from_sample_010` 的多候选是否属于标题栏综合表格仍存在歧义；后续诊断复查已修正为：额外候选是图纸中的普通表格，不是标题栏。
- 已新增标题栏规范调研索引：
  - `references/title-block-standard-research/README.md`
- 已新增标题栏规范调研笔记：
  - `docs/research/2026-06-28-title-block-standard-research.md`
- 已更新长期规则：
  - `rules/mechanical-drawing-rotation.md`
- 调研结论：
  - 强规则仍是贴图纸外框线和规范位置。
  - 字段组合是中强证据，应同时观察人员/流程字段簇与图纸属性字段簇。
  - 表格结构是辅助证据，标题栏常由大小不一的签字/日期小格和图名/图号/材料/比例等信息格组合而成。
  - 明细栏、技术要求表、局部说明表和零件线框可能包含表格线或少量相似文字，不能只凭单词或表格密度判定为标题栏。
- 决策：
  - 当前不重新训练、不改标签。
  - 下一步更适合设计 OCR/后处理小实验，用字段簇、贴图框线、位置和结构不均匀度解释多候选与误检样本，再决定是否需要新一轮数据或后处理升级。

标题栏 OCR 与后处理诊断实验规划需求：

- 用户同意基于上一轮调研设计实验计划。
- 本阶段目标是规划一个小型 OCR/后处理诊断实验，用于验证字段簇、贴图框线、位置和表格结构证据是否能解释历史误检和多候选样本。
- 本阶段只做计划，不实现脚本、不运行 OCR、不重新训练、不修改标签、不处理完整 PDF。
- 实验重点样本：
  - `sample_001`
  - `unclear90_001_from_sample_001`
  - `sample_009`
  - `sample_010`
  - `sample_020`
  - `aug90_002_from_sample_010`
  - `aug90_007_from_sample_020`
  - `sample_040`
- 计划输出文件：
  - `docs/plans/032-ocr-title-block-diagnostic-experiment-plan.md`
- 计划结论：
  - 实验输出应写入 `local_data/title_block_ocr_diagnostic/`，不进入 Git。
  - 输出以诊断报告为主，包括候选 crop、overlay、CSV 摘要、JSON 机器报告和 HTML 查看页。
  - OCR 字段簇只作为候选真实性确认，不直接覆盖 YOLO/OBB 或图框贴边证据。
  - 若本地 OCR 不可用，应输出 `ocr_unavailable` 并继续验证图框贴边、位置和表格结构证据。
  - 实验成功标准是解释误检和保护正例，而不是追求 OCR 准确率。

标题栏 OCR 与后处理诊断脚本实现规划需求：

- 用户同意按计划继续推进。
- 本阶段必须先规划脚本实现，再提交回滚点，最后才允许新增脚本并运行本地诊断实验。
- 计划文件：
  - `docs/plans/033-ocr-title-block-diagnostic-implementation-plan.md`
- 计划新增脚本：
  - `scripts/ocr/build_title_block_ocr_diagnostic.py`
- 默认输出目录：
  - `local_data/title_block_ocr_diagnostic/`
- 实现原则：
  - 复用现有 YOLO/OBB 预测标签格式、图框线检测和贴边评分思路。
  - crop 先用候选外接矩形，不做透视旋正，避免引入新误差。
  - OCR 只做可用性探测；若本地 OCR 不可用，输出 `ocr_unavailable`，不阻塞实验。
  - 表格结构诊断优先输出横竖线密度、单元格估算、格子面积差异和均匀网格惩罚。
  - 本脚本只输出诊断证据，不改变最终标题栏判断。

标题栏 OCR 与后处理诊断实验运行结果：

- 已新增脚本：
  - `scripts/ocr/build_title_block_ocr_diagnostic.py`
- 已执行验证：
  - `python -m py_compile scripts\ocr\build_title_block_ocr_diagnostic.py`
  - `python scripts\ocr\build_title_block_ocr_diagnostic.py`
- 本地输出目录：
  - `local_data/title_block_ocr_diagnostic/`
- 输出文件：
  - `diagnostic_report.json`
  - `diagnostic_manifest.csv`
  - `review_summary.html`
  - `crops/`
  - `overlays/`
- 运行摘要：
  - 计划目标样本：8。
  - 已覆盖目标样本：8。
  - 缺失目标样本：0。
  - 预测记录：16。
  - 候选记录：18。
  - 多候选记录：2，均为 `aug90_002_from_sample_010` 在 round3 val 和 round2 test 回归中的记录。
  - OCR 状态：18 条均为 `ocr_unavailable`，原因是当前环境未安装 `pytesseract`；脚本已按计划降级，不阻塞结构诊断。
  - 图框贴边候选：18。
  - 表格结构诊断：18 条均为 `ok`。
  - errors：空。
- 初步观察：
  - 现阶段可先使用贴边、位置、表格结构证据做诊断；字段簇 OCR 证据需要后续单独决定是否安装或接入 OCR 工具。
  - `aug90_002_from_sample_010` 的低置信第二候选被保留为单独诊断记录，并出现 `uniform_grid_like` 标记，可用于后续判断相连综合表格和均匀网格反例之间的边界。
  - 本实验没有改变 YOLO/OBB 最终预测和标签，只生成本地诊断报告。
- 决策：
  - 不立即重训。
  - 下一步应先人工查看 `review_summary.html` 与少量 crop/overlay，判断结构证据是否符合肉眼理解。
  - 若需要继续引入文字字段簇证据，应单独规划 OCR 依赖安装或其他 OCR/VLM provider，而不是把当前 `ocr_unavailable` 当作失败。

标题栏诊断 HTML 图片路径修复需求：

- 用户打开 `local_data/title_block_ocr_diagnostic/review_summary.html` 后，页面中图片未显示，只出现损坏图片占位和链接文字。
- 原因判断：HTML 中使用了从项目根开始的相对路径，浏览器按 HTML 所在目录解析后路径重复，导致 overlay/crop 图片加载失败。
- 本阶段必须先规划，再提交回滚点，然后修复脚本并重新生成 HTML。
- 计划文件：
  - `docs/plans/034-ocr-title-block-diagnostic-html-image-fix-plan.md`
- 修复目标：
  - `review_summary.html` 中 overlay 路径应类似 `overlays/round3_train__sample_001.jpg`。
  - crop 路径应类似 `crops/round3_train__sample_001__candidate_0.png`。
  - 不改变诊断算法、候选数量、OCR 状态或结构特征。

标题栏诊断 HTML 图片路径修复结果：

- 已修复 `scripts/ocr/build_title_block_ocr_diagnostic.py`。
- 修复内容：
  - 新增 HTML 相对路径 helper。
  - `review_summary.html` 中 overlay 和 crop 链接改为相对于 HTML 所在目录。
- 已重新运行：
  - `python -m py_compile scripts\ocr\build_title_block_ocr_diagnostic.py`
  - `python scripts\ocr\build_title_block_ocr_diagnostic.py`
- 重新生成结果：
  - `local_data/title_block_ocr_diagnostic/review_summary.html`
- 验证结果：
  - HTML 中 `overlays/` 引用：32。
  - HTML 中 `crops/` 引用：18。
  - HTML 中错误前缀 `local_data/title_block_ocr_diagnostic` 引用：0。
  - 诊断摘要仍保持：目标样本 8，覆盖 8，预测记录 16，候选记录 18，多候选记录 2，OCR 状态 18 条 `ocr_unavailable`，结构诊断 18 条 `ok`。
- 用户现在可重新打开 `local_data/title_block_ocr_diagnostic/review_summary.html` 查看 overlay 图片和 crop 链接。

标题栏诊断人工复查结论：

- 用户已查看修复后的诊断 HTML，并给出复查结论。
- 关键修正：
  - `round3_val / aug90_002_from_sample_010` 的额外候选是图纸中另外表格的一部分，不是标题栏。
  - `round3_round2_test / aug90_002_from_sample_010` 的额外候选同样是另外表格的一部分，不是标题栏。
  - 这两条应记录为普通表格误检导致的多候选 false positive，不应再按“标题栏综合表格的一部分”放行。
- 可接受样本：
  - `round3_train / sample_001`：没有问题。
  - `round3_train / sample_009`：没有问题。
  - `round3_train / unclear90_001_from_sample_001`：没有问题。
- 可容忍定位偏差：
  - `round3_val / aug90_007_from_sample_020`：识别框整体约逆时针 3 度，但大致没有问题，可以容忍。
  - `round3_val / sample_040`：识别框整体约逆时针 3 度，但大致没有问题，可以容忍。
- 已更新长期规则：
  - 相连表格不能默认视为标题栏综合表格，必须由人工复核或字段/结构证据确认其属于标题栏主体。
  - 约 3 度级别 OBB 角度偏差可容忍，前提是候选仍覆盖真实标题栏主体。
- 决策：
  - 当前仍不建议立即重训。
  - 下一步应规划 YOLO/OBB 多候选后处理仲裁升级：每页最终只允许一个标题栏候选，将 `aug90_002_from_sample_010` 的额外候选作为“普通表格误检为标题栏”的当前回归样本来验证拒绝逻辑。

YOLO/OBB round3 多候选后处理仲裁升级规划需求：

- 用户要求以当下情况为条件再次判断解决方法；若现有规划已足够则不浪费时间调研。
- 复核结论：
  - 既有规划已有“一页最终只允许一个标题栏候选”和“多候选必须仲裁”的方向。
  - 但现有规划缺少针对“普通表格在任意方向被误检为标题栏”的专门回归质量门，`aug90_002_from_sample_010` 只是当前代表样本。
  - 通用 NMS、`conf`、`iou`、`max_det=1` 只能做置信度过滤或重叠框压制，不能判断任意方向的普通表格是否属于标题栏主体。
- 本阶段不重训、不改标签、不接入 OCR/VLM，优先升级后处理仲裁。
- 计划文件：
  - `docs/plans/036-yolo-obb-round3-multicandidate-postprocess-plan.md`
- 计划新增脚本：
  - `scripts/yolo_obb/postprocess_yolo_obb_round3_multicandidate.py`
- 质量门：
  - 覆盖 round3 重点预测记录。
  - `aug90_002_from_sample_010` 两条多候选记录中，普通表格误检候选必须进入 rejected。
  - 每条多候选记录最终只保留一个 selected title block。
  - `sample_001`、`sample_009`、`unclear90_001_from_sample_001` 保持 accepted。
  - `aug90_007_from_sample_020`、`sample_040` 的约 3 度角度偏差保持可接受。

YOLO/OBB round3 多候选后处理仲裁升级结果：

- 已新增脚本：
  - `scripts/yolo_obb/postprocess_yolo_obb_round3_multicandidate.py`
- 已执行验证：
  - `python -m py_compile scripts\yolo_obb\postprocess_yolo_obb_round3_multicandidate.py`
  - `python scripts\yolo_obb\postprocess_yolo_obb_round3_multicandidate.py`
- 本地输出目录：
  - `local_data/yolo_postprocess/round3_multicandidate/`
- 输出文件：
  - `postprocess_report.json`
  - `postprocess_summary.csv`
  - `selected_candidates.csv`
  - `rejected_candidates.csv`
  - `review_summary.html`
  - `overlays/`
- 回归摘要：
  - records：16。
  - accepted：16。
  - needs_review：0。
  - multi_candidate_records：2。
  - rejected_candidates：2。
  - failed_expectations：0。
  - expected_false_positive_rejected：2。
- 关键回归结果：
  - `round3_val / aug90_002_from_sample_010`：选中 candidate 0，拒绝代表普通表格误检的 candidate 1。
  - `round3_round2_test / aug90_002_from_sample_010`：选中 candidate 0，拒绝代表普通表格误检的 candidate 1。
  - 两个被拒绝的 candidate 1 均记录拒绝原因为：`not_selected_by_single_title_block_rule;non_title_table_false_positive;uniform_grid_like;lower_confidence_duplicate_or_neighbor`。
  - `round3_train / sample_001`、`round3_train / sample_009`、`round3_train / unclear90_001_from_sample_001` 保持 accepted。
  - `round3_val / aug90_007_from_sample_020`、`round3_val / sample_040` 保持 accepted，并记录 `small_angle_offset_tolerated`。
- HTML 验证：
  - `review_summary.html` 中 `overlays/` 引用：32。
  - 错误路径前缀引用：0。
- 决策：
  - 当前多候选问题先由后处理仲裁解决，不需要立即重训。
  - 后续若进入完整 PDF 批处理，应先将该 round3 多候选仲裁逻辑合并或迁移到通用 YOLO/OBB 后处理链路。

非标题栏表格误检规则泛化修正需求：

- 用户指出前一轮理解有偏差：真正要拒绝的是把图纸中的普通表格错认成标题栏，而不是只拒绝某个“顶部蓝框”。
- 由于图纸可能被旋转，普通表格误检可能出现在上、下、左、右任意方向。
- 当前文档和脚本中“顶部蓝框”的表述容易导致规则过拟合到方向，必须修正为方向无关的非标题栏表格误检规则。
- 计划文件：
  - `docs/plans/037-yolo-obb-nontitle-table-generalization-fix-plan.md`
- 本阶段不重训、不改标签、不改变候选选择结果，只修正规则语义并重新跑回归。

非标题栏表格误检规则泛化修正结果：

- 已将 RPD 和计划文档中方向特化的“顶部蓝框”表述修正为“任意方向的普通表格误检为标题栏”。
- 已更新长期规则：普通表格误检与页面方向无关，不能因为候选出现在某一方向、贴近图框或与标题栏方向相似就放行。
- `aug90_002_from_sample_010` 保留为当前回归样本，但不再作为方向特化规则。
- 已重新运行：
  - `python -m py_compile scripts\yolo_obb\postprocess_yolo_obb_round3_multicandidate.py`
  - `python scripts\yolo_obb\postprocess_yolo_obb_round3_multicandidate.py`
- 回归结果保持不变：
  - records：16。
  - accepted：16。
  - needs_review：0。
  - multi_candidate_records：2。
  - rejected_candidates：2。
  - failed_expectations：0。
  - expected_false_positive_rejected：2。

YOLO/OBB 通用后处理多候选仲裁集成规划需求：

- round3 多候选仲裁已通过小范围回归，但逻辑仍在专用脚本 `scripts/yolo_obb/postprocess_yolo_obb_round3_multicandidate.py` 中。
- 通用后处理脚本 `scripts/yolo_obb/postprocess_yolo_obb_predictions.py` 仍主要面向 round2 val/test，缺少通用 `selected_title_block` / `rejected_candidates` 输出契约。
- 后续若进入更大范围预测或完整 PDF 批处理，必须先把已验证的多候选仲裁合并到通用链路。
- 本阶段仍不重训、不改标签、不接入 OCR/VLM、不处理完整 PDF、不发布新的固定审核入口。
- 普通表格误检规则必须保持方向无关，不能写死顶部、底部、左侧或右侧。
- 计划文件：
  - `docs/plans/038-yolo-obb-general-postprocess-multicandidate-integration-plan.md`
- 计划目标：
  - 通用后处理支持任意预测目录与数据集 split。
  - 输出 `selected_title_block`、`rejected_candidates`、`selected_candidates.csv` 和 `rejected_candidates.csv`。
  - 多候选记录最终只保留一个标题栏候选。
  - round2 首训 14 条不退化。
  - round3 16 条重点预测回归通过，`aug90_002_from_sample_010` 的普通表格误检候选仍被拒绝。
- 下一步必须先提交本计划、RPD 和 TODO 回滚点，再修改通用后处理脚本。

YOLO/OBB 通用后处理多候选仲裁集成结果：

- 已更新通用脚本：
  - `scripts/yolo_obb/postprocess_yolo_obb_predictions.py`
- 新增能力：
  - 支持 `--prediction-dirs` 处理显式预测目录。
  - 支持 `--diagnostic-report` 合并诊断报告中的结构证据。
  - 支持 `--diagnostic-only` 只回归诊断报告覆盖的重点预测记录。
  - 报告中新增 `selected_title_block` 和 `rejected_candidates`。
  - 输出新增 `selected_candidates.csv` 和 `rejected_candidates.csv`。
- 多候选仲裁语义：
  - 每条记录最终只保留一个 selected title block。
  - 未选候选记录拒绝原因。
  - 普通表格误检原因使用方向无关的 `non_title_table_false_positive`。
- 已运行验证：
  - `python -m py_compile scripts/yolo_obb/postprocess_yolo_obb_predictions.py`
  - `python scripts/yolo_obb/postprocess_yolo_obb_predictions.py`
  - `python scripts/yolo_obb/postprocess_yolo_obb_predictions.py --dataset-dir local_data/yolo_obb_dataset_round3 --review-form local_data/missing_review_form.csv --output-dir local_data/yolo_postprocess/general_round3_diagnostic --prediction-dirs round3_train round3_val round3_round2_test round3_round2_val --diagnostic-report local_data/title_block_ocr_diagnostic/diagnostic_report.json --diagnostic-only`
- round2 首训回归结果：
  - total：14。
  - accepted：9。
  - needs_review：5。
  - manual_rejected：5。
  - multi_candidate：2。
  - multi_candidate_resolved：2。
  - rejected_candidates：3。
  - 结论：14 条全覆盖，5 条用户人工不可接受样本仍未被静默放行。
- round3 重点预测回归结果：
  - total：16。
  - accepted：16。
  - needs_review：0。
  - multi_candidate：2。
  - multi_candidate_resolved：2。
  - rejected_candidates：2。
  - 结论：16 条重点预测全覆盖。
- 关键回归样本：
  - `round3_val / aug90_002_from_sample_010`：选中 candidate 0，拒绝 candidate 1。
  - `round3_round2_test / aug90_002_from_sample_010`：选中 candidate 0，拒绝 candidate 1。
  - 两条被拒绝候选的拒绝原因均为：`not_selected_by_single_title_block_rule;lower_score_duplicate_or_neighbor;uniform_grid_like;non_title_table_false_positive`。
- 决策：
  - 当前不需要重训。
  - 通用后处理已具备进入下一步低置信/VLM 兜底设计前的多候选安全约束。

YOLO/OBB 疑难样本分流质量门规划需求：

- 用户已同意按“先定义疑难样本分流质量门，再决定 OCR/VLM 或重训”的逻辑继续推进。
- 当前证据不支持立即重训：
  - round2 首训 14 条不退化，人工不可接受样本未被静默放行。
  - round3 16 条重点预测全覆盖。
  - 普通表格误检候选已被通用后处理拒绝。
- 本阶段目标不是直接调用 VLM，而是明确后处理后样本应进入哪些分流：
  - `auto_accept`
  - `human_review`
  - `ocr_candidate`
  - `vlm_candidate`
  - `retrain_candidate`
- 计划文件：
  - `docs/plans/039-yolo-obb-difficult-case-routing-plan.md`
- 计划新增脚本：
  - `scripts/yolo_obb/build_yolo_obb_routing_report.py`
- 本阶段不重训、不改标签、不调用 OCR/VLM、不处理完整 PDF、不发布新的固定审核入口。
- 下一步必须先提交本计划、RPD 和 TODO 回滚点，再实现只读分流报告脚本。

YOLO/OBB 疑难样本分流质量门结果：

- 已新增只读分流脚本：
  - `scripts/yolo_obb/build_yolo_obb_routing_report.py`
- 脚本职责：
  - 读取一个或多个 `postprocess_report.json`。
  - 为每条记录输出 `auto_accept`、`human_review`、`ocr_candidate`、`vlm_candidate`、`retrain_candidate` 分流标记。
  - 不调用 OCR/VLM。
  - 不修改原后处理报告。
  - 不写入固定审核入口。
- 已运行验证：
  - `python -m py_compile scripts/yolo_obb/build_yolo_obb_routing_report.py`
  - `python scripts/yolo_obb/build_yolo_obb_routing_report.py`
- 本地输出目录：
  - `local_data/yolo_postprocess/routing/`
- 输出文件：
  - `routing_report.json`
  - `route_records.csv`
  - `routing_summary.csv`
- 分流覆盖：
  - total records：30。
  - round2 首训：14。
  - round3 重点预测：16。
- 状态统计：
  - accepted：25。
  - needs_review：5。
- 分流统计：
  - auto_accept：25。
  - human_review：5。
  - ocr_candidate：16。
  - retrain_candidate：5。
  - vlm_candidate：0。
- 关键质量门：
  - round2 的 5 条 `needs_review/manual_rejected` 均进入 `human_review;retrain_candidate`，没有进入纯自动接受。
  - round3 两条 `aug90_002_from_sample_010` 多候选记录进入 `auto_accept;ocr_candidate`，保留 rejected candidate 说明，不触发 VLM。
  - 当前没有样本进入 `vlm_candidate`，说明 VLM 仍是后续疑难样本解释层，而不是默认全量流程。
- 决策：
  - 当前仍不重训。
  - 下一步可基于该路由清单选择是否设计 OCR 字段簇小实验或云端 VLM 小实验；VLM 应只面向 `vlm_candidate` 或人工指定疑难样本。

MCP/VLM teacher 复盘与蒸馏可行性规划需求：

- 用户指出：早期 MCP/VLM 识别效果很好，下一步可能不应只做 OCR 字段簇，而应先复盘 MCP/VLM 的识别方法，甚至考虑蒸馏。
- 复核历史记录后确认：
  - MCP 在严格“当前屏幕坐标”prompt 下，与人工复核样本一致。
  - `sample_009`、`sample_010` 中，MCP 与人工一致，定位出 OpenCV 高置信误判。
  - MCP 结果曾帮助形成三方候选真值，并推动后续 OpenCV/YOLO 迭代。
- 当前判断：
  - 不建议直接把 MCP/VLM 作为主流程。
  - 建议先把 MCP/VLM 作为 teacher 复盘对象，分析其纠错价值和可蒸馏信息。
  - 蒸馏方向包括规则蒸馏、数据蒸馏和轻量候选分类器蒸馏。
- 计划文件：
  - `docs/plans/040-mcp-vlm-teacher-distillation-plan.md`
- 计划新增脚本：
  - `scripts/vlm/build_mcp_vlm_teacher_review.py`
- 本阶段不调用新的 MCP/VLM，不上传图纸，不重训，不改标签，不处理完整 PDF，不发布固定审核入口。
- 下一步必须先提交本计划、RPD 和 TODO 回滚点，再实现只读 teacher 复盘报告脚本。

MCP/VLM teacher 复盘与蒸馏可行性结果：

- 已新增只读复盘脚本：
  - `scripts/vlm/build_mcp_vlm_teacher_review.py`
- 脚本读取：
  - `outputs/rotation-detection/comparison/mcp_results.json`
  - `outputs/rotation-detection/comparison/three_way_comparison.csv`
  - `outputs/rotation-detection/comparison/disagreements.csv`
  - `local_data/yolo_postprocess/routing/routing_report.json`
  - `local_data/yolo_postprocess/general_round3_diagnostic/postprocess_report.json`
- 脚本输出到：
  - `local_data/mcp_vlm_teacher_review/`
- 输出文件：
  - `teacher_review_report.json`
  - `teacher_review_summary.csv`
  - `teacher_prompt_draft.md`
  - `distillation_candidates.csv`
- 已运行验证：
  - `python -m py_compile scripts/vlm/build_mcp_vlm_teacher_review.py`
  - `python scripts/vlm/build_mcp_vlm_teacher_review.py`
- 复盘摘要：
  - MCP 结果数：63。
  - 三方比对样本数：63。
  - MCP 与人工一致：63/63，匹配率 1.0。
  - OpenCV 与人工一致：61/63，匹配率 0.968254。
  - MCP 纠偏 OpenCV：2 条，`sample_009`、`sample_010`。
  - 低置信但三方一致：1 条，`sample_042`。
  - 蒸馏候选：21 条。
- 蒸馏候选类型：
  - `mcp_corrected_opencv`：2。
  - `confidence_calibration`：1。
  - `hardcase_explanation`：16。
  - `non_title_table_false_positive`：2。
- 关键结论：
  - MCP/VLM 具备 teacher 价值，尤其适合纠偏 OpenCV 高置信误判和解释 hard-case。
  - 直接把 MCP/VLM 当主流程仍不稳妥；更适合做 teacher、小样本复盘、规则/数据/小模型蒸馏。
  - 下一步应优先设计一个小规模 teacher 调用实验，覆盖 `sample_009`、`sample_010`、`sample_042`、`aug90_002_from_sample_010` 和当前 hard-case。
  - teacher 输出必须结构化，并保留普通表格误检、贴图框线、字段簇组合、是否需人工复核等证据。

MCP/VLM teacher 小规模调用实验准备规划需求：

- 用户同意继续 teacher 路线。
- 当前不应直接全量调用 VLM，也不应立即重训；应先生成小规模 teacher 调用实验准备包。
- 计划文件：
  - `docs/plans/041-mcp-vlm-teacher-call-prep-plan.md`
- 计划新增脚本：
  - `scripts/vlm/build_mcp_vlm_teacher_call_prep.py`
- 准备包目标：
  - 选出 6 到 8 条代表性 teacher 调用任务。
  - 覆盖 MCP 纠偏、低置信校准、普通表格误检、保护性正例和 hard-case。
  - 为每条任务准备原图、overlay、候选 crop、问题和期望 JSON schema。
- 本阶段不调用 MCP/VLM、不上传图纸、不重训、不改标签、不处理完整 PDF、不发布固定审核入口。
- 下一步必须先提交本计划、RPD 和 TODO 回滚点，再实现 teacher 调用准备包脚本。

MCP/VLM teacher 小规模调用实验准备结果：

- 已新增准备包脚本：
  - `scripts/vlm/build_mcp_vlm_teacher_call_prep.py`
- 已运行验证：
  - `python -m py_compile scripts/vlm/build_mcp_vlm_teacher_call_prep.py`
  - `python scripts/vlm/build_mcp_vlm_teacher_call_prep.py`
- 本地输出目录：
  - `local_data/mcp_vlm_teacher_call_prep/`
- 输出文件：
  - `teacher_call_manifest.json`
  - `teacher_call_manifest.csv`
  - `teacher_prompt.md`
  - `teacher_response_schema.json`
  - `assets/`
- 任务数量：8。
- 缺失资产任务数：0。
- 任务覆盖：
  - `sample_009`：MCP 纠偏 OpenCV。
  - `sample_010`：MCP 纠偏 OpenCV。
  - `sample_042`：低置信但三方一致。
  - `aug90_002_from_sample_010` candidate 0：真实标题栏保护性正例。
  - `aug90_002_from_sample_010` candidate 1：普通表格误检反例。
  - `sample_001`：hard-case。
  - `unclear90_001_from_sample_001`：不清晰增强 hard-case。
  - `sample_040`：小角度偏差可容忍正例。
- 每条任务均记录：
  - task id。
  - task type。
  - teacher 问题。
  - 蒸馏方向。
  - source/overlay/candidate crop 资产路径。
  - response schema。
- 本阶段仍未调用 MCP/VLM，未上传图纸，未发布固定审核入口。
- 下一步：
  - 基于该准备包设计实际 teacher provider 调用方式。
  - 首轮应只跑这 8 条任务，并保存原始响应、解析结果和人工/规则对照。

MCP/VLM teacher provider 调用方式规划需求：

- teacher 调用准备包已包含 8 条任务、prompt、response schema 和资产。
- 下一步需要设计实际 provider 调用方式，但本阶段不应直接接云端 API 或本地模型。
- 计划文件：
  - `docs/plans/042-mcp-vlm-teacher-provider-call-plan.md`
- 计划新增脚本：
  - `scripts/vlm/build_mcp_vlm_teacher_provider_requests.py`
- 第一版只做 provider-agnostic 请求与响应协议：
  - 生成 `teacher_requests.jsonl`。
  - 生成 `teacher_response_template.jsonl`。
  - 校验响应 JSON 是否符合 schema。
  - 汇总校验错误。
- 支持后续扩展到：
  - manual。
  - mcp。
  - cloud_vlm。
  - local_vlm。
- 本阶段不调用 MCP/VLM、不上传图纸、不接入 API key、不安装依赖、不重训、不发布固定审核入口。
- 下一步必须先提交本计划、RPD 和 TODO 回滚点，再实现请求/响应脚本。

MCP/VLM teacher provider 调用方式结果：

- 已新增脚本：
  - `scripts/vlm/build_mcp_vlm_teacher_provider_requests.py`
- 已运行验证：
  - `python -m py_compile scripts/vlm/build_mcp_vlm_teacher_provider_requests.py`
  - `python scripts/vlm/build_mcp_vlm_teacher_provider_requests.py`
- 本地输出目录：
  - `local_data/mcp_vlm_teacher_provider/`
- 输出文件：
  - `teacher_requests.jsonl`
  - `teacher_response_template.jsonl`
  - `teacher_provider_summary.json`
  - `validated_responses.json`
  - `validation_errors.csv`
- 输出摘要：
  - provider_mode：`manual`。
  - task_count：8。
  - request_count：8。
  - response_template_count：8。
  - validated_response_count：8。
  - validation_error_count：16。
- 校验说明：
  - 当前校验源为生成的空响应模板。
  - 每条任务各有 `pending_response` 和 `missing_or_empty_parsed_response` 两条提示。
  - 这代表响应模板等待填写，不是流程失败。
- 本阶段仍未调用 MCP/VLM，未上传图纸，未接入 API key，未发布固定审核入口。
- 下一步：
  - 可选择 manual/MCP/cloud/local 任一 provider 填写 `teacher_response_template.jsonl`。
  - 填写后用同一脚本 `--validate-responses` 校验结构化输出，再决定是否进入规则/数据/小模型蒸馏。

MCP/VLM teacher 手动响应固定审核入口规划需求：

- 用户同意 A 方案：先做小规模、可审计的 teacher 响应获取。
- 当前 provider 请求包已经生成 8 条任务，但请求、模板、schema、prompt 和图片资产仍在业务目录中。
- 按固定审核入口规则，下一步应将本轮需要填写和参考的文件副本集中发布到：
  - `local_data/review_inbox/current/`
- 计划文件：
  - `docs/plans/043-mcp-vlm-teacher-manual-review-inbox-plan.md`
- 本阶段目标：
  - 发布 `teacher_requests.jsonl`、`teacher_response_template.jsonl`、`teacher_prompt.md`、`teacher_response_schema.json`。
  - 复制 8 条任务所需图片资产。
  - 生成低噪声 `teacher_tasks.csv` 和 README。
  - 仍不调用 MCP/VLM、不上传图纸、不重训、不改标签。
- 下一步必须先提交本计划、RPD 和 TODO 回滚点，再实现固定入口发布脚本。

MCP/VLM teacher 手动响应固定审核入口实现记录：

- 已新增脚本：
  - `scripts/vlm/publish_mcp_vlm_teacher_review_inbox.py`
- 脚本职责：
  - 检查 `local_data/review_inbox/current/` 是否为空闲入口。
  - 复制 teacher 请求、响应模板、prompt、schema 和图片资产。
  - 生成低噪声 `teacher_tasks.csv` 与 README。
  - 不调用 MCP/VLM，不上传图纸。
- 已运行验证：
  - `python -m py_compile scripts\vlm\publish_mcp_vlm_teacher_review_inbox.py`
  - `python scripts\vlm\publish_mcp_vlm_teacher_review_inbox.py`
  - `python scripts\vlm\build_mcp_vlm_teacher_provider_requests.py --validate-responses local_data\review_inbox\current\teacher_response_template.jsonl`
- 固定入口输出：
  - `local_data/review_inbox/current/README.md`
  - `local_data/review_inbox/current/teacher_tasks.csv`
  - `local_data/review_inbox/current/teacher_requests.jsonl`
  - `local_data/review_inbox/current/teacher_response_template.jsonl`
  - `local_data/review_inbox/current/teacher_prompt.md`
  - `local_data/review_inbox/current/teacher_response_schema.json`
  - `local_data/review_inbox/current/assets/`
- 发布结果：
  - task_count：8。
  - missing_asset_count：0。
  - 固定入口响应模板校验 validated_response_count：8。
  - validation_error_count：16。
- 校验说明：
  - 16 条提示均为响应模板尚未填写导致的预期状态。
  - 每条任务各有 `pending_response` 和 `missing_or_empty_parsed_response`。
  - 这不是流程失败，表示当前等待 teacher 响应填写。

项目交接与文档整理规划需求：

- 用户需要切换账号继续开发，需要在项目根目录保存一份新会话可直接读取的交接记录。
- 当前公开文档分类已经存在：
  - `docs/research/`：调研。
  - `docs/plans/`：阶段计划。
  - `docs/workflows/`：人工流程。
  - `rules/`：长期规则。
  - `reports/`：RPD 与阶段结果。
  - `references/`：外部资料索引。
- 当前缺口：
  - 根目录 README 的“当前重点”仍停留在 round2 首训预测错误分层阶段。
  - `docs/README.md` 缺少近期 MCP/VLM teacher 相关入口。
  - 根目录缺少专门的 `HANDOFF.md`。
- 计划文件：
  - `docs/plans/044-project-handoff-documentation-plan.md`
- 本阶段不重训、不调用 MCP/VLM、不上传图纸、不整理或删除本地私有数据。
- 下一步必须先提交本计划、RPD 和 TODO 回滚点，再更新文档索引与交接记录。

项目交接与文档整理实现记录：

- 已更新根目录 README：
  - 当前重点改为 MCP/VLM teacher 响应获取与校验阶段。
  - 新增 `HANDOFF.md` 作为换账号接手入口。
  - 补充 teacher 相关本地私有目录说明。
- 已重写 `docs/README.md`：
  - 保留 `research/`、`plans/`、`workflows/` 分类。
  - 新增推荐接手阅读顺序。
  - 补齐近期 MCP/VLM teacher、YOLO/OBB 通用后处理、疑难样本分流等计划入口。
- 已新增根目录交接文件：
  - `HANDOFF.md`
- `HANDOFF.md` 记录内容：
  - 当前固定审核入口。
  - 8 条 teacher 任务。
  - 关键结论和暂时不要做的事项。
  - 重要公开文档、脚本、本地目录和最近提交。
  - 接手时可运行的检查命令。
- 已运行验证：
  - `rg -n "HANDOFF|MCP/VLM teacher|当前重点|local_data/review_inbox/current|项目交接" README.md docs\README.md HANDOFF.md TODO.md reports\rpd-rotation-detection.md`
  - `git status --short`
- 验证结果：
  - 根目录 `HANDOFF.md` 已存在。
  - README 当前重点已指向 8 条 teacher 响应获取与校验。
  - `docs/README.md` 已补齐近期 teacher 相关入口。
  - `git status --short` 未显示 `local_data/`、`outputs/`、`runs/` 待提交。
- 本阶段未修改 `local_data/`，未调用 MCP/VLM，未上传图纸，未重训。

详细文件：

- `references/ocr-vlm-workflow-research/README.md`
- `docs/research/2026-06-25-ocr-vlm-workflow-research.md`
- `docs/plans/017-ocr-vlm-fallback-workflow-plan.md`
- `docs/research/2026-06-25-local-title-block-detector-and-vlm-research.md`
- `docs/plans/013-yolo-obb-title-block-experiment-plan.md`
- `docs/plans/014-yolo-obb-debugging-research-plan.md`
- `references/yolo-obb-debugging-research/README.md`
- `docs/research/2026-06-25-yolo-obb-debugging-research.md`
- `docs/plans/009-yolo-obb-label-tools-plan.md`
- `docs/plans/010-annotation-tool-selection-plan.md`
- `docs/plans/011-isat-annotation-tool-research-plan.md`
- `docs/research/2026-06-26-isat-annotation-tool-research.md`
- `docs/workflows/isat-obb-annotation-workflow.md`
- `docs/plans/012-yolo-obb-smoke-training-plan.md`
- `rules/human-review-interface.md`
- `references/annotation-tool-selection/README.md`
- `docs/research/2026-06-25-obb-annotation-tool-selection.md`
- `docs/workflows/labelme-obb-annotation-workflow.md`

MCP/VLM teacher 响应填写与校验规划需求：

- 用户已确认继续推进换账号后的当前任务。
- 当前固定审核入口：
  - `local_data/review_inbox/current/`
- 当前入口包含 8 条 teacher 小实验任务，请求、响应模板、schema、prompt 和图片资产副本均已齐备。
- 当前响应模板仍为待填写状态，校验中的 16 条提示均为预期空响应提示。
- 计划文件：
  - `docs/plans/045-mcp-vlm-teacher-response-fill-and-validation-plan.md`
- 本阶段目标：
  - 逐条分析 8 个 teacher 任务的 source、overlay 和 candidate crop。
  - 将结构化判断写入 `teacher_response_template.jsonl` 的 `parsed_response`。
  - 将已填写记录的 `parse_status` 改为 `ok`。
  - 运行既有 provider 校验脚本，目标 `validation_error_count=0`。
- 本阶段不调用云端 VLM、不上传图纸、不接入 API key、不重训、不改标签、不处理完整 PDF。
- teacher 输出只作为蒸馏证据，不直接覆盖 ground truth 或训练标签。
- 下一步必须先提交本计划、RPD 和 TODO 回滚点，再填写响应模板。

MCP/VLM teacher 响应填写与校验实现记录：

- 已提交规划回滚点：
  - `41e1bfc docs: plan mcp vlm teacher responses`
- 已填写固定审核入口响应模板：
  - `local_data/review_inbox/current/teacher_response_template.jsonl`
- 填写方式：
  - 逐条查看固定入口内的 source、overlay 和 candidate crop。
  - 按当前屏幕坐标判断标题栏位置。
  - 按 schema 写入 `parsed_response`。
  - 将 8 条记录的 `parse_status` 改为 `ok`。
- 已运行校验：
  - `python scripts\vlm\build_mcp_vlm_teacher_provider_requests.py --validate-responses local_data\review_inbox\current\teacher_response_template.jsonl`
- 校验结果：
  - `validated_response_count`：8。
  - `validation_error_count`：0。
- 本地校验输出：
  - `local_data/mcp_vlm_teacher_provider/validated_responses.json`
  - `local_data/mcp_vlm_teacher_provider/validation_errors.csv`
- 8 条 teacher 判断摘要：
  - `sample_009`：标题栏在当前图像右侧，旋转角度 270，OpenCV 曾被其他视图线条干扰。
  - `sample_010`：标题栏在当前图像底部，旋转角度 0，上方大表格是明细表。
  - `sample_042`：标题栏在当前图像右侧，旋转角度 270，线条偏淡但字段簇和贴边证据仍可接受。
  - `aug90_002_from_sample_010` candidate 0：左侧真实标题栏正例，旋转角度 90。
  - `aug90_002_from_sample_010` candidate 1：普通明细表/零件表误检反例，不是真实标题栏。
  - `sample_001` candidate 0：上方真实标题栏正例，旋转角度 180。
  - `unclear90_001_from_sample_001` candidate 0：底部真实标题栏正例，旋转角度 0，适合作为不清晰 hard-case。
  - `sample_040` candidate 0：上方真实标题栏正例，旋转角度 180，小角度 OBB 偏差可容忍。
- 当前决策：
  - teacher 响应已具备进入蒸馏分析的结构化输入条件。
  - 下一步可设计 teacher 响应蒸馏分析：规则蒸馏、hard-case 数据归档、候选 crop 小分类器或 provider 自动调用小实验。
  - 仍不应直接重训或把 teacher 输出直接覆盖为最终真值。

MCP/VLM teacher 响应蒸馏分析规划需求：

- 8 条 teacher 响应已经填写并通过 schema 校验，当前具备结构化蒸馏输入。
- 当前输入：
  - `local_data/mcp_vlm_teacher_provider/validated_responses.json`
- 计划文件：
  - `docs/plans/046-mcp-vlm-teacher-response-distillation-analysis-plan.md`
- 本阶段目标：
  - 汇总标题栏位置、候选真假、贴边证据、字段簇强度、普通表格误检风险和拒绝原因。
  - 将每条 teacher 响应归类到规则蒸馏、hard-case 数据整理、候选 crop 小分类器和 provider 自动调用实验方向。
  - 输出 JSON/CSV/Markdown 报告到 `local_data/mcp_vlm_teacher_distillation/`。
- 本阶段不调用云端 VLM、不上传图纸、不接入 API key、不重训、不改标签、不处理完整 PDF、不发布新的固定审核入口。
- 下一步必须先提交本计划、RPD 和 TODO 回滚点，再实现只读蒸馏分析脚本。

MCP/VLM teacher 响应蒸馏分析实现记录：

- 已提交规划回滚点：
  - `71b9bbe docs: plan mcp vlm teacher distillation`
- 已新增只读分析脚本：
  - `scripts/vlm/build_mcp_vlm_teacher_distillation.py`
- 脚本输入：
  - `local_data/mcp_vlm_teacher_provider/validated_responses.json`
- 脚本输出目录：
  - `local_data/mcp_vlm_teacher_distillation/`
- 输出文件：
  - `teacher_distillation_report.json`
  - `teacher_distillation_summary.csv`
  - `teacher_distillation_actions.csv`
  - `teacher_rule_candidates.md`
- 已运行验证：
  - `python -m py_compile scripts\vlm\build_mcp_vlm_teacher_distillation.py`
  - `python scripts\vlm\build_mcp_vlm_teacher_distillation.py`
- 蒸馏分析摘要：
  - validated responses：8。
  - action records：8。
  - true title block：7。
  - false title block：1。
  - needs human review：0。
  - task kind counts：
    - `mcp_corrected_opencv`：2。
    - `confidence_calibration`：1。
    - `hardcase_positive`：3。
    - `non_title_table_false_positive`：1。
    - `small_angle_offset_tolerated`：1。
  - distill target counts：
    - `rule`：8。
    - `data`：5。
    - `provider`：3。
    - `model`：1。
  - title block position counts：
    - bottom：2。
    - left：2。
    - right：2。
    - top：2。
- 规则候选：
  - 候选贴图纸外框且字段簇为 medium/strong 时，应优先于普通线条密度。
  - 缺少设计/审核/日期/材料/重量/比例字段簇的均匀零件清单，即使表格分高也应拒绝。
  - 普通表格误检必须方向无关，不能绑定 top/bottom/left/right。
  - 小角度 OBB 或边界偏差可容忍，前提是仍覆盖标题栏主体和字段簇。
  - 淡扫描样本可用贴边证据加字段簇组合作置信校准。
- 当前决策：
  - teacher 响应已经被整理为规则、数据、模型和 provider 四类后续候选。
  - 当前仍不直接重训，不把 teacher 输出直接写入 ground truth 或训练标签。
  - 下一步可优先把规则候选落入通用后处理，或设计 provider 自动调用小实验。

YOLO/OBB teacher 规则蒸馏到通用后处理规划需求：

- 用户已批准先把 teacher 蒸馏规则落到通用后处理。
- 当前依据：
  - `local_data/mcp_vlm_teacher_distillation/teacher_rule_candidates.md`
  - `local_data/mcp_vlm_teacher_distillation/teacher_distillation_actions.csv`
- 计划文件：
  - `docs/plans/047-yolo-obb-teacher-rule-postprocess-integration-plan.md`
- 当前通用后处理已具备贴边检测、多候选仲裁、`uniform_grid_like` 反证和诊断报告接入。
- 当前 OCR 字段簇仍不可用，因此本阶段不把文字字段命中作为已落地规则，只使用结构代理：
  - 贴图纸外框线。
  - 非均匀格子结构。
  - `small_large_cell_mix_score`。
  - `uniform_grid_like`。
  - `frame_contact_score`。
  - 候选是否 near edge。
- 本阶段目标：
  - 在 `scripts/yolo_obb/postprocess_yolo_obb_predictions.py` 中新增 teacher rule flags。
  - 输出 `teacher_rule_flags`、`teacher_rule_adjustment`、`teacher_rule_evidence`。
  - 让 teacher 规则成为可解释的 score adjustment，而不是不可追踪的阈值魔改。
  - 保持一张图最终只接受一个标题栏候选。
  - round2 首训与 round3 重点预测双回归不退化。
- 本阶段不调用 VLM、不接入 OCR、不上传图纸、不重训、不改标签、不处理完整 PDF、不发布新的固定审核入口。
- 下一步必须先提交本计划、RPD 和 TODO 回滚点，再实现通用后处理脚本改造。

YOLO/OBB teacher 规则蒸馏到通用后处理实现记录：

- 已提交规划回滚点：
  - `29c811e docs: plan yolo obb teacher rule postprocess`
- 已更新通用后处理脚本：
  - `scripts/yolo_obb/postprocess_yolo_obb_predictions.py`
- 新增候选字段：
  - `teacher_rule_flags`
  - `teacher_rule_adjustment`
  - `teacher_rule_evidence`
  - `axis_offset_degrees`
- 新增 teacher rule flags：
  - `teacher_frame_field_proxy_positive`：贴图纸外框且具有非均匀结构代理。
  - `teacher_uniform_table_negative`：均匀普通表格/明细表反证。
  - `teacher_small_angle_tolerated`：OBB 轴线小角度偏差且仍覆盖标题栏结构。
  - `teacher_faint_scan_confidence_proxy`：OCR 不可用或淡扫描时，以强贴边证据做置信代理。
- 实现边界：
  - 当前 OCR 字段簇仍不可用，因此没有把文字命中作为已落地规则。
  - 本阶段只使用结构代理和图框线接触证据。
  - 普通表格反例不再获得淡扫描正向代理，只保留负向 `teacher_uniform_table_negative`。
- 已运行验证：
  - `python -m py_compile scripts\yolo_obb\postprocess_yolo_obb_predictions.py`
  - `python scripts\yolo_obb\postprocess_yolo_obb_predictions.py`
  - `python scripts\yolo_obb\postprocess_yolo_obb_predictions.py --dataset-dir local_data\yolo_obb_dataset_round3 --review-form local_data\missing_review_form.csv --output-dir local_data\yolo_postprocess\general_round3_diagnostic --prediction-dirs round3_train round3_val round3_round2_test round3_round2_val --diagnostic-report local_data\title_block_ocr_diagnostic\diagnostic_report.json --diagnostic-only`
  - `python scripts\yolo_obb\build_yolo_obb_routing_report.py`
- round2 首训回归结果：
  - total：14。
  - accepted：9。
  - needs_review：5。
  - manual_rejected：5。
  - multi_candidate：2。
  - multi_candidate_resolved：2。
  - rejected_candidates：3。
  - 结论：5 条人工不可接受样本仍未被静默放行。
- round3 重点预测回归结果：
  - total：16。
  - accepted：16。
  - needs_review：0。
  - multi_candidate：2。
  - multi_candidate_resolved：2。
  - rejected_candidates：2。
  - 结论：16 条重点预测全覆盖。
- 关键样本：
  - `aug90_002_from_sample_010` candidate 0 继续被选中，带有正向 teacher flags。
  - `aug90_002_from_sample_010` candidate 1 继续被拒绝，拒绝原因包含 `teacher_uniform_table_negative` 和 `non_title_table_false_positive`。
  - `sample_040` 保留小角度 OBB 偏差可接受证据。
- routing 回归结果：
  - records：30。
  - accepted：25。
  - needs_review：5。
  - auto_accept：25。
  - human_review：5。
  - ocr_candidate：16。
  - retrain_candidate：5。
- 当前决策：
  - teacher 规则已经以可解释 flags 和 score adjustment 进入通用后处理。
  - 当前仍不重训、不调用 VLM、不把 teacher 输出写入 ground truth。
  - 下一步可考虑 provider 自动调用小实验，或继续把 OCR 字段簇真正接入 teacher rule flags。

OCR 字段簇可用性探针规划需求：

- 用户同意继续执行 OCR 字段簇小实验，但当前判断是 OCR 只应作为便宜、可解释、可审计的字段簇证据层，不作为主力路线。
- 当前本机 OCR 能力初步探测：
  - Python 包 `pytesseract`：不可用。
  - Python 包 `paddleocr`：不可用。
  - Python 包 `easyocr`：不可用。
  - Python 包 `rapidocr_onnxruntime`：不可用。
  - Python 包 `cnocr`：不可用。
  - `tesseract --version`：命令不存在或不在 PATH。
- 计划文件：
  - `docs/plans/048-ocr-field-cluster-probe-plan.md`
- 本阶段目标：
  - 增强 `scripts/ocr/build_title_block_ocr_diagnostic.py`，显式输出 OCR capability。
  - 继续只对现有 8 到 16 个重点候选 crop 做探针。
  - 如果 OCR 不可用，明确输出 `ocr_probe_decision=ocr_unavailable_locally`。
  - 如果后续 OCR 可用，再用同一报告格式输出字段簇命中。
- 本阶段不安装 OCR 依赖、不联网下载模型、不调用云端 OCR/VLM、不上传图纸、不重训、不改标签、不处理完整 PDF、不发布新的固定审核入口。
- 下一步必须先提交本计划、RPD 和 TODO 回滚点，再增强 OCR 诊断脚本。

OCR 字段簇可用性探针实现记录：

- 已提交规划回滚点：
  - `2c333b1 docs: plan ocr field cluster probe`
- 已增强脚本：
  - `scripts/ocr/build_title_block_ocr_diagnostic.py`
- 新增报告字段：
  - `ocr_capability`
  - `ocr_missing_engines`
  - `ocr_probe_decision`
  - `field_cluster_strong_candidates`
- 已运行验证：
  - `python -m py_compile scripts\ocr\build_title_block_ocr_diagnostic.py`
  - `python scripts\ocr\build_title_block_ocr_diagnostic.py`
- 输出目录：
  - `local_data/title_block_ocr_diagnostic/`
- 输出文件：
  - `diagnostic_report.json`
  - `diagnostic_manifest.csv`
  - `review_summary.html`
- 探针结果：
  - target sample count：8。
  - covered sample count：8。
  - prediction records：16。
  - candidate records：18。
  - multi candidate records：2。
  - OCR status counts：
    - `ocr_unavailable`：18。
  - field cluster strong candidates：0。
  - OCR probe decision：`ocr_unavailable_locally`。
- OCR capability：
  - available：false。
  - available engines：空。
  - missing engines：
    - `pytesseract`
    - `paddleocr`
    - `easyocr`
    - `rapidocr_onnxruntime`
    - `cnocr`
    - `tesseract`
- 当前结论：
  - OCR 字段簇路线仍有理论价值，但当前本机环境不具备继续接入条件。
  - 不应把 OCR 接入自动接受逻辑。
  - 下一步更适合设计 provider/VLM 小实验，或单独规划 OCR 安装与离线模型准备方案。

OCR 引擎选型调研规划需求：

- 用户要求调研当前有什么合适的 OCR 可以使用。
- 当前 OCR 的项目定位不是替代 YOLO/OBB 或 VLM，而是为标题栏候选 crop 提供字段簇证据：
  - 设计、制图、审核、批准、日期等流程字段。
  - 图名、图号、材料、比例、重量、单位等属性字段。
- 已知本机当前无可用 OCR 引擎，因此本轮先调研选型，不安装依赖、不下载模型、不调用云端 OCR、不上传图纸。
- 计划文件：
  - `docs/plans/049-ocr-engine-selection-research-plan.md`
- 本轮重点比较：
  - PaddleOCR / PP-OCR。
  - RapidOCR。
  - Tesseract / pytesseract。
  - EasyOCR。
  - CnOCR。
  - 云端 OCR 只作为隐私受控对照。
- 输出目标：
  - `references/ocr-engine-selection/README.md`
  - `docs/research/2026-06-28-ocr-engine-selection-research.md`
  - `docs/workflows/ocr-engine-selection-sop.md`
- 下一步必须先提交本计划、RPD 和 TODO 回滚点，再开始联网调研与文档沉淀。

OCR 引擎选型调研结果：

- 已提交调研前回滚点：
  - `8dc5db2 docs: plan ocr engine selection research`
- 已完成横向调研并沉淀：
  - `references/ocr-engine-selection/README.md`
  - `docs/research/2026-06-28-ocr-engine-selection-research.md`
  - `docs/workflows/ocr-engine-selection-sop.md`
- 调研结论：
  - 首选 RapidOCR 做下一轮本地离线小实验。
  - PaddleOCR / PP-OCR 作为能力上限和第二路线。
  - Tesseract / pytesseract 只作为 baseline。
  - CnOCR 可作为中文/竖排备选。
  - EasyOCR 可作为快速 API 对照，但 PyTorch 依赖较重。
  - 云 OCR 只在用户明确批准 provider 和外发范围后作为上限对照，不作为默认路线。
- 当前判断：
  - OCR 仍有必要，但只适合作为便宜、可解释、可审计的字段簇证据层。
  - 下一步若继续 OCR，应单独规划 RapidOCR 本地安装与字段簇小实验。
  - 在小实验通过前，不应把 OCR 接入自动接受逻辑。

RapidOCR 本地字段簇小实验规划需求：

- 用户要求先做计划，并强调必须考虑普通配置机器可运行。
- 计划文件：
  - `docs/plans/050-rapidocr-local-field-cluster-experiment-plan.md`
- 本阶段普通机器约束：
  - Windows 本地环境。
  - CPU-only，不要求 GPU、CUDA 或专用加速卡。
  - 内存按 8GB 到 16GB 档设计。
  - 只处理 8 到 16 个标题栏候选 crop。
  - 不处理完整 PDF，不做整页 OCR，不训练或微调模型。
  - 单次实验应在分钟级完成；明显超时则停止扩大范围。
- 本阶段目标：
  - 在本机确认 RapidOCR 是否可用。
  - 对重点候选 crop 生成字段簇证据。
  - 判断 RapidOCR 是否值得进入后续 `teacher_rule_flags` 接入计划。
- 本阶段不做：
  - 不调用云 OCR。
  - 不上传图纸。
  - 不启用 GPU-only 路线。
  - 不把 OCR 结果写入 ground truth。
  - 不把 OCR 结果直接用于自动接受。
- 稳定性要求：
  - OCR 不可用或失败时，现有 OpenCV、YOLO/OBB 和 teacher rule 后处理不得受影响。
  - 即使 RapidOCR 输出正常，也必须先进入诊断报告，后续是否接入后处理另行规划。
- 下一步必须先提交本计划、RPD 和 TODO 回滚点，再进入安装、脚本修改或实验执行。

RapidOCR 本地字段簇小实验实现记录：

- 已提交实现前回滚点：
  - `a7791a3 docs: plan rapidocr local field cluster experiment`
- 已完成环境检查：
  - Python：3.11.9。
  - 基线诊断脚本可运行。
  - 安装前 OCR 结果仍为 `ocr_unavailable=18`。
- 已按审批安装 RapidOCR CPU 路线：
  - `rapidocr==3.9.0`
  - `onnxruntime==1.23.2` 已存在。
  - RapidOCR 实际使用 ONNXRuntime CPU 引擎。
- 已增强脚本：
  - `scripts/ocr/build_title_block_ocr_diagnostic.py`
- 脚本新增能力：
  - OCR capability 检测包含 `rapidocr`。
  - 优先调用 RapidOCR，失败时回退 pytesseract 原路径。
  - 输出 `ocr_engine`、`ocr_status`、`ocr_rotation_angle`、`ocr_text_excerpt` 和 `ocr_engine_counts`。
  - 默认使用 `--ocr-rotation-mode auto`，按候选边侧只尝试少量阅读方向。
  - 保留 `--ocr-rotation-mode all` 作为深度诊断，不作为普通机器默认路径。
- 已运行验证：
  - `python -m py_compile scripts\ocr\build_title_block_ocr_diagnostic.py`
  - `python scripts\ocr\build_title_block_ocr_diagnostic.py`
- 输出仍位于本地忽略目录：
  - `local_data/title_block_ocr_diagnostic/diagnostic_report.json`
  - `local_data/title_block_ocr_diagnostic/diagnostic_manifest.csv`
  - `local_data/title_block_ocr_diagnostic/review_summary.html`
- 实验结果：
  - target sample count：8。
  - covered sample count：8。
  - prediction records：16。
  - candidate records：18。
  - OCR status counts：`ok=18`。
  - OCR engine counts：`rapidocr=18`。
  - structure status counts：`ok=18`。
  - field cluster strong candidates：16。
  - OCR probe decision：`ocr_field_cluster_candidate`。
  - 弱字段簇候选：2 条，均为 `aug90_002_from_sample_010` 的 candidate 1 普通明细表反例。
- 普通机器运行观察：
  - 4 方向全量尝试可得到同样 16/18 强字段簇，但耗时超过 2 分钟，不适合作为默认。
  - 默认 auto 模式约 72 秒完成 18 个候选，仍只适合 hard-case crop 级诊断，不应扩展到整页或完整 PDF OCR。
- 当前决策：
  - RapidOCR 可作为标题栏字段簇候选证据层。
  - OCR 字段簇对真实标题栏有明显召回，同时没有把已知普通明细表反例判成强字段簇。
  - 现阶段仍不把 OCR 结果直接写入 ground truth、训练标签或自动接受逻辑。
  - 后续若接入通用后处理，应另行规划，只把字段簇作为 teacher rule 证据加权，并保留人工复核质量门。

标题栏位置多证据仲裁调研与设计归档结果：

- 已提交调研前回滚点：
  - `766d4e2 docs: plan title block arbitration research`
- 已完成资料索引、横向调研和设计决策沉淀：
  - `references/title-block-position-arbitration/README.md`
  - `docs/research/2026-06-28-title-block-position-arbitration-research.md`
  - `docs/decisions/title-block-position-arbitration-design.md`
- 已标注旧设计状态：
  - `docs/plans/016-three-way-rotation-comparison-plan.md` 保留为早期三方比对、候选 ground truth 建立和误判定位方案。
  - 其中“无条件全量三方平权多数票”已废弃，不再作为最终自动决策机制。
  - `docs/plans/017-ocr-vlm-fallback-workflow-plan.md` 保留“条件并行兜底 + 证据融合”，并明确 OCR/VLM/OpenCV/YOLO 不平权。
- 外部调研支撑：
  - AEC 图纸标题栏检测与信息抽取论文支持“标题栏检测 -> 标题栏信息抽取 -> 图纸检索/分组”的处理范式。
  - 工程图纸标题栏检测与处理、工程图纸标题栏非几何信息抽取论文支持将标题栏作为图纸组织和元数据抽取核心对象。
  - ISO 7200 官方页面说明标题栏和文档头数据字段是标准化对象，但公开页不是标准全文，不能过度声称具体字段顺序或尺寸。
  - PaddleOCR 版面分析、Ultralytics OBB、OpenCV 形态学线条提取、Tesseract OCR 坐标/方向输出分别支持区域定位、旋转框检测、几何结构校验和文字字段证据。
- 当前设计结论：
  - 本项目采用“标题栏位置多证据仲裁”。
  - 标题栏位置是旋转判断的主对象，旋转角度只是标题栏位置的派生结果。
  - YOLO/OBB 负责候选框和边侧位置主证据。
  - OpenCV 负责图框、贴边、表格线和结构几何校验。
  - OCR/RapidOCR 负责字段簇真实性和后续图号抽取证据。
  - VLM 仅作为本地证据冲突、低置信或新版式时的疑难解释分支。
  - 人工只处理自动证据不足、VLM 仍不确定或图号命名风险高的异常队列。
- 证据保存要求：
  - 后续每页应保存标题栏候选、标题栏位置、旋转角度、校正角度、OCR 原文、字段簇命中、图号候选和文件名候选。
  - 机器证据进入 JSON/日志；人工审核入口仍按 `AGENTS.md` 保持低噪声。
- 下一步建议：
  - 规划并实现 `ArbitrationRecord` 只读汇总 schema。
  - 先汇总既有 YOLO/OBB 后处理、OpenCV 结果和 RapidOCR 字段簇报告，在 hard-case 与 round3 重点样本上回放。
  - 通过后再设计单页 PDF 旋正与图号重命名 dry-run，不直接覆盖原文件。

标题栏位置仲裁记录规划需求：

- 当前设计已经明确采用“标题栏位置多证据仲裁”，下一步需要先建立每页统一证据记录，避免后续 PDF 旋正和图号重命名缺少追溯依据。
- 计划文件：
  - `docs/plans/052-title-block-arbitration-record-plan.md`
- 本阶段目标：
  - 定义 `ArbitrationRecord` 结构化记录。
  - 保存每页来源、标题栏候选、YOLO/OBB 证据、OpenCV 几何证据、OCR 字段簇、仲裁结论、旋转角度、图号候选预留字段和输出 dry-run 计划。
  - 明确 `auto_accept`、`needs_vlm`、`needs_human_review` 等分流状态。
  - 后续实现只做只读汇总，不直接处理完整 PDF、不旋正、不重命名、不调用云端 VLM、不改 ground truth。
- 稳定性要求：
  - 缺失证据必须显式写入 `missing`，不得静默假设。
  - 一页最多一个最终选中标题栏候选；多候选冲突必须保留冲突原因。
  - 在 dry-run 验证通过前，所有 PDF 输出计划必须保持 `dry_run_only=true`。
  - 人工审核入口若后续生成，只显示用户判断必须看到的信息，机器证据继续保存在 JSON 或报告中。
- 下一步必须先提交本计划、RPD 和 TODO 回滚点，再实现只读汇总脚本。

标题栏位置仲裁记录只读汇总实现结果：

- 实现脚本：
  - `scripts/ocr/build_title_block_arbitration_records.py`
- 输入来源：
  - `local_data/yolo_postprocess/round2_first_train/postprocess_report.json`
  - `local_data/yolo_postprocess/general_round3_diagnostic/postprocess_report.json`
  - `local_data/title_block_ocr_diagnostic/diagnostic_report.json`
  - `outputs/rotation-detection/stage1/results.json`
  - `outputs/rotation-detection/augmented_90/results.json`
- 输出目录：
  - `local_data/title_block_arbitration/`
- 输出文件：
  - `arbitration_records.jsonl`
  - `arbitration_summary.json`
  - `arbitration_summary.csv`
  - `missing_evidence.csv`
  - `conflicts.csv`
  - `needs_review.csv`
- 关键实现修正：
  - 不再把 `nearest_frame_side` 直接当作 `title_block_position`。
  - `nearest_frame_side` 表示候选边界最贴近哪条图框线，只作为贴边证据保存为 `frame_contact_side`。
  - 标题栏位置优先按候选框长宽方向和中心位置推导：
    - 纵向长框：按中心点在左半区或右半区判断 `left/right`。
    - 横向长框：按中心点在上半区或下半区判断 `top/bottom`。
    - 近似方形框：退回 bbox 最近页面边作为弱几何代理。
  - 只有语义可比的位置来源才与 OpenCV `title_block_side` 做冲突判断；不可比来源不触发 VLM。
- 本轮运行结果：
  - `record_count=30`。
  - `decision_status_counts`: `auto_accept=25`, `needs_human_review=5`。
  - `route_counts`: `auto=25`, `human=5`。
  - `conflict_counts`: 空。
  - `missing_evidence_counts`: `ocr_selected_candidate=14`, `opencv_rotation_result=6`。
  - 30 条记录全部保持 `dry_run_only=true`。
  - 最终候选校验：每条记录最多一个 `accepted_by_source=true` 候选。
- 已知样本方向回放：
  - `sample_001 -> right -> 270`。
  - `sample_010 -> bottom -> 0`。
  - `sample_020 -> top -> 180`。
  - `aug90_002_from_sample_010 -> left -> 90`。
  - `aug90_007_from_sample_020 -> left -> 90`。
- 解释：
  - 修正前 11 条 `needs_vlm` 主要来自把贴边侧和标题栏位置混为一谈造成的假冲突。
  - 修正后未触发 VLM，说明当前重点样本内本地几何证据与 OpenCV 方向判断没有真实位置冲突。
  - 5 条 `needs_human_review` 来自 round2 历史后处理 `status != accepted`，不是本轮新增冲突。
- 边界：
  - 本轮仍只是只读 dry-run 汇总，不处理完整 PDF、不旋正 PDF、不重命名、不调用云端 VLM、不改 ground truth。
  - 图号抽取只保留 `drawing_number` 字段骨架，后续必须单独规划和验证。

标题栏仲裁准确率评估固化需求：

- 用户要求说明标题栏位置判断正确率，以及为什么可以进入下一步而不是继续打磨标题栏位置识别。
- 临时对照结果显示：
  - 当前 30 条仲裁记录均可在 ground truth 中找到对应项。
  - 标题栏位置正确：30/30。
  - 派生旋转角度正确：30/30。
  - 去重样本正确：14/14。
  - `auto_accept` 记录正确：25/25。
  - `needs_human_review` 记录位置和旋转也正确：5/5，但因历史后处理状态保守分流。
- ground truth 来源：
  - 原始人工确认集：`local_data/ground_truth/rotation_ground_truth.json`。
  - 90 度增强集：`local_data/ground_truth/rotation_ground_truth_augmented_90.json`。
  - 低清晰度增强集：`local_data/ground_truth/rotation_ground_truth_augmented_90_unclear.json`。
- 当前结论边界：
  - 可以推进到下一阶段 dry-run。
  - 不能直接推进到正式无人批量改 PDF 或重命名。
  - 30/30 是当前样本和当前仲裁记录范围内的结果，不应宣称未知图纸包泛化准确率为 100%。
- 计划文件：
  - `docs/plans/053-title-block-arbitration-accuracy-evaluation-plan.md`
- 下一步：
  - 提交本计划、RPD 和 TODO 回滚点。
  - 实现可重复评估脚本，输出 JSON/CSV 评估报告。
  - 评估通过后再规划 PDF 旋正、标题栏 OCR 和图号抽取 dry-run。

标题栏仲裁准确率评估固化实现结果：

- 实现脚本：
  - `scripts/ocr/evaluate_title_block_arbitration_records.py`
- 运行命令：
  - `python -m py_compile scripts\ocr\evaluate_title_block_arbitration_records.py`
  - `python scripts\ocr\evaluate_title_block_arbitration_records.py`
- 输出目录：
  - `local_data/title_block_arbitration/evaluation/`
- 输出文件：
  - `accuracy_summary.json`
  - `accuracy_details.csv`
  - `accuracy_errors.csv`
  - `accuracy_missing_truth.csv`
- 输入记录：
  - `local_data/title_block_arbitration/arbitration_records.jsonl`
- 输入 ground truth：
  - `local_data/ground_truth/rotation_ground_truth.json`
  - `local_data/ground_truth/rotation_ground_truth_augmented_90.json`
  - `local_data/ground_truth/rotation_ground_truth_augmented_90_unclear.json`
- 评估结果：
  - `record_count=30`
  - `records_with_truth=30`
  - `missing_truth_count=0`
  - `position_correct_records=30`
  - `position_accuracy=1.0`
  - `rotation_correct_records=30`
  - `rotation_accuracy=1.0`
  - `unique_sample_count=14`
  - `unique_samples_with_truth=14`
  - `unique_position_error_count=0`
  - `unique_rotation_error_count=0`
  - `accuracy_errors.csv` 数据行数为 0。
  - `accuracy_missing_truth.csv` 数据行数为 0。
- 分流状态：
  - `auto_accept=25`，位置和旋转准确率均为 1.0。
  - `needs_human_review=5`，位置和旋转准确率均为 1.0；这些样本仍因历史后处理状态被保守分流。
- ground truth 来源分布：
  - `manual_review_full=16`
  - `synthetic_augmented_90=8`
  - `synthetic_augmented_90_unclear=6`
- dry-run 闸门结论：
  - `ready_for_pdf_dry_run=true`
  - `not_ready_for_unattended_batch_write=true`
- 解释：
  - 标题栏位置识别在当前仲裁记录和已有 ground truth 范围内没有发现错误。
  - 继续无目标打磨标题栏位置识别容易过拟合当前样本。
  - 下一步应进入 PDF 旋正、标题栏 crop、OCR 图号抽取和命名规则的 dry-run，以暴露下游真实风险。
  - 该结论不代表未知图纸包工业级泛化准确率为 100%，也不授权正式覆盖原 PDF 或正式重命名文件。

PDF 旋正与图号抽取 dry-run 规划需求：

- 计划文件：
  - `docs/plans/054-pdf-correction-and-drawing-number-dry-run-plan.md`
- 当前依据：
  - 标题栏仲裁准确率评估已经通过当前记录范围内的 ground truth 对照。
  - 可以进入下一阶段 dry-run。
  - 仍不能直接正式覆盖 PDF 或正式按 OCR 图号重命名。
- 本阶段目标：
  - 设计单页 PDF 旋正 dry-run 输出结构。
  - 设计旋正后标题栏 crop、OCR 原文、图号候选和命名风险保存方式。
  - 明确 `auto_dry_run_ready`、`needs_human_review`、`blocked` 等分流。
  - 明确缺 PDF 路径、缺 crop、OCR 低置信、图号多候选、重名、非法字符和输出覆盖等阻断条件。
- 输出建议：
  - `local_data/pdf_correction_dry_run/dry_run_records.jsonl`
  - `local_data/pdf_correction_dry_run/dry_run_summary.json`
  - `local_data/pdf_correction_dry_run/drawing_number_candidates.csv`
  - `local_data/pdf_correction_dry_run/naming_risks.csv`
  - `local_data/pdf_correction_dry_run/needs_review.csv`
- 稳定性要求：
  - 不修改原始 PDF。
  - 不正式重命名单页 PDF。
  - 所有输出计划必须保留 `dry_run_only=true`。
  - `needs_human_review` 仲裁记录不得进入自动旋正和命名。
  - 若生成审核入口，必须统一放入 `local_data/review_inbox/current/`。

PDF 旋正与图号抽取 dry-run 实现结果：

- 实现脚本：
  - `scripts/ocr/build_pdf_correction_dry_run.py`
- 运行命令：
  - `python -m py_compile scripts\ocr\build_pdf_correction_dry_run.py`
  - `python scripts\ocr\build_pdf_correction_dry_run.py`
- 输入：
  - `local_data/title_block_arbitration/arbitration_records.jsonl`
- 输出目录：
  - `local_data/pdf_correction_dry_run/`
- 输出文件：
  - `dry_run_records.jsonl`
  - `dry_run_summary.json`
  - `dry_run_summary.csv`
  - `rotation_plan.csv`
  - `drawing_number_candidates.csv`
  - `naming_risks.csv`
  - `needs_review.csv`
  - `ocr/*.txt`
- 本轮 dry-run 汇总：
  - `record_count=30`
  - `route_counts`: `blocked=25`, `needs_human_review=5`
  - `dry_run_only=true`
  - `modified_pdf=false`
  - `renamed_pdf=false`
  - 可旋正 PDF：0
  - 可重命名 PDF：0
  - 自动 dry-run ready：0
- 旋正阻断：
  - `missing_single_page_pdf_path=30`
  - `arbitration_not_auto_accept=5`
  - 解释：当前 30 条仲裁记录来自实验图像回放，尚未接入真实单页 PDF 路径，因此全部阻断 PDF 旋正，符合计划。
- 标题栏 crop 与 OCR：
  - 有标题栏 crop 的记录：16。
  - 可引用 crop 的记录：16。
  - 写出 OCR 文本文件：16。
  - 缺 OCR 文本：14。
  - OCR 字段簇非 strong 或缺失：14。
- 图号候选：
  - `single_candidate=12`
  - `single_high_confidence_candidate=2`
  - `missing=16`
  - 风险：
    - `drawing_number_missing=16`
    - `drawing_number_low_confidence=6`
    - `duplicate_filename_candidate=14`
    - `upstream_rotation_blocked=30`
- 解释：
  - 本轮已经证明 dry-run 脚本能保存 OCR 原文、抽取图号候选、发现命名风险，并且不会在缺少单页 PDF 路径时伪造 PDF 输出。
  - 当前重复文件名风险主要来自同一图纸在 round2/round3/增强样本中重复回放，不代表真实图纸包一定重复，但说明命名去重检查必须保留。
  - 下一步若要真正验证 PDF 旋正，需要先接入已拆分的一页一个 PDF 路径，或实现从图纸包 PDF 到单页 PDF 的可追溯拆分映射。
  - 在真实单页 PDF 接入前，不应实现正式覆盖或正式重命名。

63 张全量 PDF dry-run 测试规划需求：

- 用户确认可以继续，并要求遵循项目规则执行计划。
- 当前本地资产核实：
  - 已拆分单页 PDF：`local_data/experiment_samples/all/pdf/`，63 个。
  - 原始人工确认 ground truth：`local_data/ground_truth/rotation_ground_truth.json`，63 条。
  - 渲染 PNG 目录：`local_data/experiment_samples/all/png/`，包含 63 个样本 PNG，同时还有 `.json` 标注文件和 `isat.yaml`，因此不能按目录文件总数盲跑。
  - 原始图纸包 PDF 位于 `local_data/source_pdfs/`。
- 计划文件：
  - `docs/plans/055-full-63-pdf-dry-run-test-plan.md`
- 本阶段目标：
  - 以 ground truth 的 63 个 sample 为主键，精确匹配单页 PDF 和 PNG。
  - 构建 `full_63_arbitration_records.jsonl`，填入真实 `single_page_pdf_path`。
  - 复用 `scripts/ocr/build_pdf_correction_dry_run.py` 运行 63 张全量 dry-run。
  - 验证 PDF 路径接入、旋正计划、命名阻断和风险报告。
- 预期：
  - `can_rotate_pdf` 应该达到 63，因为单页 PDF 路径和旋转角度已具备。
  - `can_rename` 不应放行，因为本轮不重新跑全量标题栏 OCR，图号候选预计缺失。
  - 仍不修改原始 PDF、不正式重命名。

63 张全量 PDF dry-run 测试实现结果：

- 实现脚本：
  - `scripts/ocr/build_full_63_pdf_dry_run_inputs.py`
- 运行命令：
  - `python -m py_compile scripts\ocr\build_full_63_pdf_dry_run_inputs.py`
  - `python scripts\ocr\build_full_63_pdf_dry_run_inputs.py`
  - `python scripts\ocr\build_pdf_correction_dry_run.py --arbitration-records local_data\full_63_pdf_dry_run\full_63_arbitration_records.jsonl --output-dir local_data\full_63_pdf_dry_run\pdf_correction_dry_run`
- 输入：
  - `local_data/ground_truth/rotation_ground_truth.json`
  - `local_data/experiment_samples/all/pdf/`
  - `local_data/experiment_samples/all/png/`
- 输出：
  - `local_data/full_63_pdf_dry_run/full_63_arbitration_records.jsonl`
  - `local_data/full_63_pdf_dry_run/full_63_input_manifest.csv`
  - `local_data/full_63_pdf_dry_run/missing_assets.csv`
  - `local_data/full_63_pdf_dry_run/full_63_input_summary.json`
  - `local_data/full_63_pdf_dry_run/pdf_correction_dry_run/`
- 输入构建结果：
  - `record_count=63`
  - `manifest_count=63`
  - `missing_asset_count=0`
  - `pdf_exists_count=63`
  - `png_exists_count=63`
- 全量 dry-run 结果：
  - `record_count=63`
  - `can_rotate_pdf=63`
  - `can_rename=0`
  - `dry_run_only=63`
  - `auto_dry_run_ready=0`
  - `blocked=63`
  - `needs_human_review=0`
  - `modified_pdf=false`
  - `renamed_pdf=false`
  - 输出目录内没有 PDF 文件，仅有 JSON/CSV/JSONL。
- 阻断与风险：
  - `rotation_blocker_counts` 为空，说明 63 张单页 PDF 路径和旋转角度均可形成旋正计划。
  - `title_block_crop_blocker_counts`: `missing_title_block_crop=63`
  - `ocr_blocker_counts`: `missing_ocr_text=63`, `ocr_field_cluster_not_strong=63`
  - `drawing_number_blocker_counts`: `drawing_number_missing=63`
  - `rename_blocker_counts`: `drawing_number_missing=63`
- 解释：
  - 63 张全量 PDF 路径接入通过，PDF 旋正计划层已经具备继续测试条件。
  - 本轮未执行全量标题栏 crop/OCR，因此命名全部被图号缺失阻断，符合预期。
  - 下一步应规划并实现“63 张全量标题栏 crop/OCR dry-run”，只对标题栏区域 OCR，不做整页 OCR。
  - 在 OCR 图号抽取和命名风险通过 dry-run 之前，仍不得正式重命名文件。

63 张全量标题栏 crop/OCR dry-run 规划需求：

- 计划文件：
  - `docs/plans/056-full-63-title-block-ocr-dry-run-plan.md`
- 当前依据：
  - 63 张全量 PDF 路径接入已通过。
  - `can_rotate_pdf=63`。
  - 当前命名全部被 `drawing_number_missing=63` 阻断。
- 本阶段目标：
  - 使用 `outputs/rotation-detection/stage1/results.json` 中的 `best_candidate.bbox` 裁剪标题栏区域。
  - 只对标题栏 crop 跑本地 OCR，不做整页 OCR。
  - 保存 crop、OCR 原文、字段簇命中和 OCR 状态。
  - 将 OCR 结果回填到全量 dry-run 输入记录。
  - 复用 `scripts/ocr/build_pdf_correction_dry_run.py` 重新输出图号候选和命名风险。
- 稳定性要求：
  - 不修改原始 PDF。
  - 不正式重命名。
  - 不调用云端 VLM。
  - 不新增人工审核入口。
  - 每页有 crop 或明确 blocker。

63 张全量标题栏 crop/OCR dry-run 实现结果：

- 实现脚本：
  - `scripts/ocr/build_full_63_title_block_ocr_dry_run.py`
- 运行命令：
  - `python -m py_compile scripts\ocr\build_full_63_title_block_ocr_dry_run.py`
  - `python scripts\ocr\build_full_63_title_block_ocr_dry_run.py`
  - `python scripts\ocr\build_pdf_correction_dry_run.py --arbitration-records local_data\full_63_title_block_ocr_dry_run\full_63_ocr_arbitration_records.jsonl --output-dir local_data\full_63_title_block_ocr_dry_run\pdf_correction_dry_run`
- 输入：
  - `local_data/full_63_pdf_dry_run/full_63_arbitration_records.jsonl`
  - `outputs/rotation-detection/stage1/results.json`
- 输出：
  - `local_data/full_63_title_block_ocr_dry_run/full_63_ocr_arbitration_records.jsonl`
  - `local_data/full_63_title_block_ocr_dry_run/ocr_summary.json`
  - `local_data/full_63_title_block_ocr_dry_run/ocr_summary.csv`
  - `local_data/full_63_title_block_ocr_dry_run/drawing_number_candidates.csv`
  - `local_data/full_63_title_block_ocr_dry_run/crops/`
  - `local_data/full_63_title_block_ocr_dry_run/ocr_text/`
  - `local_data/full_63_title_block_ocr_dry_run/pdf_correction_dry_run/`
- OCR dry-run 汇总：
  - `record_count=63`
  - `crop_count=63`
  - `ocr_text_count=63`
  - `ocr_status_counts`: `ok=63`
  - `field_cluster_level_counts`: `strong=60`, `weak=3`
  - `drawing_number_candidate_bucket_counts`: `single=43`, `multiple=10`, `none=10`
  - `ocr_capability`: `rapidocr=true`, `pytesseract=false`
  - `whole_page_ocr=false`
  - `modified_pdf=false`
  - `renamed_pdf=false`
- OCR 后 PDF dry-run 汇总：
  - `record_count=63`
  - `auto_dry_run_ready=6`
  - `blocked=53`
  - `needs_human_review=4`
  - `rotation_blocker_counts` 为空。
  - `title_block_crop_blocker_counts` 为空。
  - `ocr_blocker_counts`: `ocr_field_cluster_not_strong=3`
  - `drawing_number_blocker_counts`: `drawing_number_low_confidence=43`, `drawing_number_missing=10`, `drawing_number_ambiguous=4`
  - `rename_blocker_counts`: `drawing_number_low_confidence=43`, `drawing_number_missing=14`, `drawing_number_ambiguous=4`, `duplicate_filename_candidate=2`
  - `dry_run_only=true`
  - `modified_pdf=false`
  - `renamed_pdf=false`
- 额外核验：
  - `local_data/full_63_title_block_ocr_dry_run/crops/` 下 crop 文件数量为 63。
  - `local_data/full_63_title_block_ocr_dry_run/pdf_correction_dry_run/` 下不存在 `corrected_pdfs` 或 `renamed_pdfs` 目录。
- 解释：
  - 标题栏定位与 crop 链路在 63 张全量样本上没有路径或 bbox 阻断，说明标题栏位置识别已足以支撑下一步 OCR/图号抽取 dry-run。
  - 本地 RapidOCR 在 63 个标题栏 crop 上均返回 OCR 文本，并且 60 条达到强字段簇，说明“只对标题栏 crop 做 OCR”的路线具备继续推进价值。
  - 图号抽取与命名质量门仍不能正式放行：只有 6 条达到自动 dry-run ready，43 条低置信单候选、10 条缺失、4 条歧义。
  - 下一步应聚焦图号抽取规则、标题栏字段定位、候选置信度和命名质量门，而不是继续打磨标题栏位置识别本身。
  - 在图号抽取低置信和歧义问题解决前，不得正式重命名 PDF。

图号抽取低置信候选优化与命名质量门规划需求：

- 计划文件：
  - `docs/plans/057-drawing-number-quality-gate-plan.md`
- 当前依据：
  - 63 张全量标题栏 crop/OCR dry-run 已完成。
  - 标题栏 crop、OCR 文本均为 63/63。
  - RapidOCR 在 63 张标题栏 crop 上均返回 `ok`。
  - 字段簇强度为 `strong=60`、`weak=3`。
  - OCR 后 PDF dry-run 仅有 `auto_dry_run_ready=6`。
  - 当前主要阻断为图号候选低置信、缺失、歧义和重名风险。
- 本阶段目标：
  - 优化图号候选评分，不再只按 `near_label/global_pattern` 两档打分。
  - 加入标题栏字段上下文、图名邻近、候选模式完整度、路径噪声和明细表反证。
  - 输出候选 `reasons` 与 `penalties`，便于审计。
  - 保持命名质量门严格，只扩大 dry-run ready，不正式改 PDF、不正式重命名。
- 稳定性要求：
  - 低置信、重名、歧义、字段簇弱、缺 crop、缺 OCR、缺 PDF 路径都不得自动命名。
  - `dry_run_only=true`、`modified_pdf=false`、`renamed_pdf=false` 必须继续成立。
  - 本轮只做规则优化和 dry-run 验证，不调用云端 VLM/OCR，不修改 ground truth。
- 下一步：
  - 提交本计划、RPD 和 TODO 回滚点。
  - 修改 `scripts/ocr/build_pdf_correction_dry_run.py` 中的图号候选评分与输出。
  - 重新运行 63 张全量 dry-run，并记录自动 ready、blocked 和 needs review 的变化。

图号抽取低置信候选优化与命名质量门实现结果：

- 实现脚本：
  - `scripts/ocr/build_pdf_correction_dry_run.py`
- 关键改动：
  - 图号规则版本从 `drawing-number-regex-v0.1` 升级为 `drawing-number-regex-context-v0.2`。
  - 候选评分加入标题栏上下文证据：
    - `near_drawing_number_label`
    - `after_chinese_drawing_name`
    - `before_title_block_flow_fields`
    - `project_prefix`
    - `multi_segment_number`
  - 候选评分加入风险惩罚：
    - `cad_or_path_context`
    - `part_list_context`
    - `weak_alnum_mix`
    - `short_candidate`
  - `drawing_number_candidates.csv` 新增 `reasons` 与 `penalties`，用于解释候选升降分原因。
  - 明细表零件号、CAD/网络路径文件名候选继续降权，不允许自动命名。
  - 重名、低置信、缺失、OCR 字段簇弱等质量门保持阻断。
- 运行命令：
  - `python -m py_compile scripts\ocr\build_pdf_correction_dry_run.py`
  - `python scripts\ocr\build_pdf_correction_dry_run.py --arbitration-records local_data\full_63_title_block_ocr_dry_run\full_63_ocr_arbitration_records.jsonl --output-dir local_data\full_63_title_block_ocr_dry_run\pdf_correction_dry_run_v2`
- 输出目录：
  - `local_data/full_63_title_block_ocr_dry_run/pdf_correction_dry_run_v2/`
- 新 dry-run 汇总：
  - `record_count=63`
  - `auto_dry_run_ready=40`
  - `blocked=21`
  - `needs_human_review=2`
  - `drawing_number_selection_counts`: `single_high_confidence_candidate=42`, `single_candidate=10`, `missing=11`
  - `rotation_blocker_counts` 为空。
  - `title_block_crop_blocker_counts` 为空。
  - `ocr_blocker_counts`: `ocr_field_cluster_not_strong=3`
  - `drawing_number_blocker_counts`: `drawing_number_low_confidence=10`, `drawing_number_missing=11`
  - `rename_blocker_counts`: `drawing_number_low_confidence=10`, `drawing_number_missing=11`, `duplicate_filename_candidate=2`
  - `dry_run_only=true`
  - `modified_pdf=false`
  - `renamed_pdf=false`
- 与上一版 OCR 后 dry-run 对比：
  - 自动 dry-run ready 从 6 提升到 40。
  - blocked 从 53 降到 21。
  - needs human review 从 4 降到 2。
  - 低置信图号候选从 43 降到 10。
  - 歧义图号候选从 4 降到 0。
- 质量门保留：
  - `sample_006` 与 `sample_007` 因重复候选 `YKJ125-00-04-252` 进入 `needs_human_review`。
  - `sample_009`、`sample_041`、`sample_042` 等字段簇弱或缺失样本仍未自动放行。
  - `sample_008`、`sample_022`、`sample_032` 等 OCR 未抽到图号的样本仍保持 blocked。
  - `TT-50-40-10`、`TT-55-40-16` 等弱字母数字混合候选仍保持低置信阻断。
- 额外核验：
  - 输出目录下未生成 `corrected_pdfs` 或 `renamed_pdfs` 目录。
  - 输出目录内只有 OCR 文本子目录和 JSON/CSV/JSONL 报告。
- 解释：
  - 本轮没有通过降低全局阈值放行，而是利用标题栏行序关系把“图名 + 图号 + 标记处数/签字/日期”的候选提升为高置信。
  - 明细表中的零件号即使格式像图号，也因为 `part_list_context` 与候选竞争规则被压低。
  - CAD 文件路径和网络路径中的文件名候选被 `cad_or_path_context` 降权。
  - 当前已经可以进入下一步：设计剩余 23 条非自动放行样本的人工低噪声复核包，或继续针对 OCR 缺失/字段簇弱样本做小范围 OCR/crop 参数实验。
  - 在人工复核或进一步质量门通过前，仍不得正式重命名 PDF。

OCR 图像预处理增强调研规划需求：

- 用户提出：对不够清晰的标题栏 crop，可先像 Photoshop 一样调整明暗、对比度、锐化或其他图像增强，再进行 OCR 和图号抽取。
- 计划文件：
  - `docs/plans/058-ocr-image-preprocessing-research-plan.md`
- 本阶段目标：
  - 调研 OCR 前图像预处理成熟方案。
  - 判断亮度/对比度、CLAHE、去噪、锐化、阈值化、形态学、倾斜校正和超分辨率等方法是否适合机械图纸标题栏 crop。
  - 区分可迁移的轻量本地方法与当前不适合的重型模型方案。
  - 给出下一轮小实验建议。
- 稳定性要求：
  - 不覆盖原始 crop。
  - 不批量改写现有 OCR 结果。
  - 不调用云端增强、云 OCR 或 VLM。
  - 增强结果只作为 dry-run 派生证据，不直接写入正式文件名。
- 下一步：
  - 提交本计划、RPD 和 TODO 回滚点。
  - 调研官方文档、论文和工程实践。
  - 沉淀样本索引与取经笔记。

OCR 图像预处理增强调研结果：

- 样本索引：
  - `references/ocr-image-preprocessing/README.md`
- 横向笔记：
  - `docs/research/2026-06-29-ocr-image-preprocessing-research.md`
- 调研结论：
  - 用户提出的方向是成熟且值得验证的。
  - OCR 前图像预处理不是单一滤镜，而是“原始 crop -> 多个增强派生版本 -> 分别 OCR -> 按字段簇和图号质量门选择证据”的工作流。
  - 适合当前项目第一轮验证的轻量方法包括：
    - 灰度/反色/白边/缩放。
    - CLAHE 或局部对比度增强。
    - 轻度去噪。
    - 小强度 Unsharp Mask 锐化。
    - Otsu、自适应阈值等二值化。
    - 小 kernel 形态学微调。
    - 小角度 deskew。
  - 不建议当前优先引入深度学习超分辨率、整页 ScanTailor/unpaper 后处理或云端增强；这些可以作为后期能力上限对照。
- 项目建议：
  - 下一轮应规划 `OCR 图像预处理小实验`。
  - 样本范围控制在当前 23 条非自动放行样本。
  - 每个样本保留原始 crop，并生成有限数量增强版本，例如 `gray_clahe`、`gray_clahe_unsharp`、`denoise_otsu`、`adaptive_gaussian`、`upscale2x_clahe_unsharp`。
  - 每个增强版本分别跑 OCR，并记录 OCR 原文、字段簇、图号候选、质量门状态和是否优于原图。
  - 增强结果只能进入 dry-run 派生证据，不得覆盖原始 crop，不得直接正式重命名 PDF。
- 风险：
  - 对比度增强和锐化可能放大噪声和表格线。
  - 二值化可能导致细字断裂或线字粘连。
  - 形态学处理可能吞掉小字号图号。
  - 超分辨率或生成式增强可能生成伪细节，不能直接用于命名放行。

OCR 图像预处理小实验规划需求：

- 计划文件：
  - `docs/plans/059-ocr-image-preprocessing-small-experiment-plan.md`
- 当前依据：
  - OCR 图像预处理调研已完成。
  - 当前 63 张全量 OCR dry-run 中，40 条已自动 dry-run ready，23 条非自动放行。
  - 非自动放行样本包括图号缺失、低置信、字段簇弱和重复文件名候选。
- 本阶段目标：
  - 只针对 23 条异常样本生成有限数量增强版本。
  - 对原图和增强版本分别 OCR。
  - 比较字段簇、图号候选和命名质量门是否改善。
  - 输出机器报告和低噪声人工审核入口。
- 增强配方：
  - `original`
  - `gray_clahe`
  - `gray_clahe_unsharp`
  - `denoise_otsu`
  - `adaptive_gaussian`
  - `upscale2x_clahe_unsharp`
- 稳定性要求：
  - 不覆盖原始 crop。
  - 不处理已自动放行的 40 条样本。
  - 不正式生成或重命名 PDF。
  - 不调用云端 OCR/VLM。
  - 增强结果不得绕过命名质量门。
  - 若生成审核入口，必须放入 `local_data/review_inbox/current/`。
- 审核点：
  - 本计划需要用户审核后才能进入实现阶段。
  - 审核通过前，不生成增强图、不运行 OCR 小实验、不更新固定审核入口。

63 条图号命名人工审核包规划需求：

- 用户指出：此前 40 条 `auto_dry_run_ready` 样本并未被人工看过，不能直接视为可正式命名；23 条异常样本即使经过增强实验，也仍需要人工识别和审核。
- 结论：
  - 该质疑成立。
  - `auto_dry_run_ready` 只能表示机器质量门未发现阻断，不等于 `human_verified`，更不等于 `production_ready`。
  - 第一次形成图号命名链路时，应先生成 63 条全量命名审核包。
- 计划文件：
  - `docs/plans/060-full-63-naming-review-pack-plan.md`
- 本阶段目标：
  - 生成 63 条图号命名人工审核包。
  - 40 条自动 ready 标为“机器建议通过”。
  - 23 条非自动放行标为“异常需处理”并优先展示。
  - 固定入口统一发布到 `local_data/review_inbox/current/`。
  - 本轮只生成审核包，不回写人工结果，不正式重命名。
- 人工审核字段：
  - 样本编号。
  - 机器候选图号。
  - 机器拟文件名。
  - 人工判断。
  - 人工确认图号。
  - 备注。
- 不应在人工表中展示：
  - 机器分组。
  - `auto_dry_run_ready`、`blocked`、`needs_human_review` 等内部状态。
  - `drawing_number_low_confidence`、`duplicate_filename_candidate` 等阻断原因。
- 稳定性要求：
  - 清空旧固定审核入口，不能残留 teacher 任务。
  - 审核入口包含页面预览和标题栏 crop 副本。
  - 人工表保持低噪声，不暴露完整 JSON、内部分数、长路径、候选列表、机器分组、内部状态或阻断原因。
  - 用户完成 63 条审核前，不得继续增强 OCR 实验、回写人工结果或正式命名。

63 条图号命名人工审核包低噪声修正需求：

- 用户指出当前 `review_form.csv` 暴露了很多不需要人工知道的信息，违反 AGENTS 中人工填写表低噪声规则。
- 结论：
  - 该问题成立。
  - 当前人工 CSV 中的“机器分组 / 当前状态 / 当前阻断原因”等字段应转入机器报告，不应放在人工填写表。
- 修正要求：
  - 人工 CSV 只保留序号、样本编号、机器候选图号、机器拟文件名、人工判断、人工确认图号、备注。
  - HTML 页面只展示完成命名判断必需的信息：页面预览、标题栏 crop、样本编号、候选图号、拟文件名、OCR 摘要和简短人工提示。
  - 完整状态、阻断原因、机器分组和调试字段保留在 `review_manifest.json` 和 `local_data/full_63_naming_review_pack/` 机器报告中。
  - 重新生成 `local_data/review_inbox/current/`。

63 条图号命名人工审核包实现结果：

- 实现脚本：
  - `scripts/ocr/build_full_63_naming_review_pack.py`
- 运行命令：
  - `python -m py_compile scripts\ocr\build_full_63_naming_review_pack.py`
  - `python scripts\ocr\build_full_63_naming_review_pack.py`
- 输入：
  - `local_data/full_63_title_block_ocr_dry_run/pdf_correction_dry_run_v2/dry_run_records.jsonl`
- 固定审核入口：
  - `local_data/review_inbox/current/`
- 用户需要打开：
  - `local_data/review_inbox/current/README.md`
  - `local_data/review_inbox/current/naming_review/review_index.html`
  - `local_data/review_inbox/current/naming_review/review_form.csv`
- 机器报告：
  - `local_data/full_63_naming_review_pack/review_summary.json`
  - `local_data/full_63_naming_review_pack/review_manifest.json`
- 生成结果：
  - `review_record_count=63`
  - `machine_suggested_count=40`
  - `exception_count=23`
  - `missing_asset_count=0`
  - 页面预览副本：63。
  - 标题栏 crop 副本：63。
  - `modified_pdf=false`
  - `renamed_pdf=false`
- 审核入口状态：
  - `local_data/review_inbox/current/` 已替换为本轮命名审核入口。
  - 旧 teacher 审核入口不再作为当前入口展示。
  - 初版人工填写表暴露了机器分组、当前状态和阻断原因，已按低噪声规则修正。
- 下一步：
  - 用户审核 63 条图号命名人工审核包。
  - 审核完成前，不得继续 OCR 图像预处理小实验、不得回写人工结果、不得正式生成或重命名 PDF。

63 条图号命名人工审核包低噪声修正结果：

- 修正脚本：
  - `scripts/ocr/build_full_63_naming_review_pack.py`
- 重新运行：
  - `python -m py_compile scripts\ocr\build_full_63_naming_review_pack.py`
  - `python scripts\ocr\build_full_63_naming_review_pack.py`
- 修正后的人工 CSV 字段：
  - `序号`
  - `样本编号`
  - `机器候选图号`
  - `机器拟文件名`
  - `人工判断`
  - `人工确认图号`
  - `备注`
- 验证结果：
  - `review_record_count=63`
  - `machine_suggested_count=40`
  - `exception_count=23`
  - `missing_asset_count=0`
  - 页面预览副本：63。
  - 标题栏 crop 副本：63。
  - 人工 HTML/CSV 中不再出现 `auto_dry_run_ready`、`blocked`、`needs_human_review`、`drawing_number_low_confidence`、`duplicate_filename_candidate`、机器分组、当前状态或阻断原因。
  - 完整机器字段仍保存在 `review_manifest.json` 和 `local_data/full_63_naming_review_pack/review_manifest.json`。

63 条图号命名人工审核包校正视图修正需求：

- 用户指出：`review_index.html` 中展示未旋转到正确方向的图片，审核图号时很难阅读；应旋转后展示，并顺便让用户审核旋转是否正确。
- 结论：
  - 该问题成立。
  - 命名审核入口应默认展示按 `correction_degrees` 生成的校正后 PNG 派生图。
  - 这只是审核视图，不等于正式旋正 PDF。
- 修正要求：
  - 页面预览图按校正角度旋转后复制到固定入口。
  - 标题栏 crop 也生成校正后视图，方便阅读 OCR 图号。
  - HTML 文案改为“校正后页面预览”和“校正后标题栏 crop”。
  - review manifest 继续保留原始页面/crop 路径和校正后资产路径。
  - 仍不得生成正式 PDF 或重命名 PDF。
- 执行结果：
  - 已重新生成固定入口：`local_data/review_inbox/current/`。
  - `review_index.html` 默认引用 `assets/pages_corrected/` 和 `assets/crops_corrected/`。
  - 页面校正后 PNG：63 张。
  - 标题栏 crop 校正后 PNG：63 张。
  - `review_form.csv` 新增低噪声人工字段 `旋转判断`，用于记录旋转是否正确；未加入内部状态或调试字段。
  - `review_manifest.json` 中 63 条均保留 `corrected_page_asset`、`corrected_crop_asset`、`source_page_path`、`source_crop_path`。
  - 抽样视觉检查覆盖 `correction_degrees=90/180/0`：`sample_001`、`sample_003`、`sample_010` 页面方向正常。
  - 校验未生成 `corrected_pdfs` 或 `renamed_pdfs`。
  - HTML/CSV 未出现内部状态码、阻断原因或机器分组字段。

63 条图号命名审核暂停与标题栏 crop 质量修复决策：

- 用户只填写了部分 `review_form.csv`，但明确反馈：所有已看图片旋转方向正确，不必继续填完；大量标题栏 crop 存在右侧区域缺失，少数标题栏右半边未识别，另有图像未后处理导致字迹不清。
- 已读取用户备注并抽样核对校正后图片：
  - `sample_008`、`sample_022`、`sample_032`：crop 只覆盖标题栏左半部分，图名/图号栏未进入 crop。
  - `sample_009`：crop 混入图纸主体和标题栏左侧，真实右下图号栏未进入 crop。
  - `sample_016`：标题栏主体基本完整，但右侧少截，导致机器候选 `YKJ125-10-13A-25` 少尾部。
  - `sample_006`：抽样发现右侧也存在截断风险，机器候选疑似少尾部字符。
  - `sample_035`、`sample_039`、`sample_042`：crop 基本完整，但图像浅、短横线不清，OCR 易把 `-` 漏读或读成空格。
- 结论：
  - 当前 63 条命名审核包不能作为最终命名依据。
  - 当前审核不要求用户继续填写，应先归档已填备注。
  - 问题根因不是旋转，而是标题栏 crop 完整性质量门不足，以及浅字样本缺少图像预处理。
  - 旧流程只验证“像不像标题栏/方向是否正确”不够，后续必须增加“完整覆盖图名和图号栏，尤其右侧边界”的人工复核和自动质量门。
- 后续计划：
  - 见 `docs/plans/061-title-block-crop-quality-recovery-plan.md`。
  - 先保全当前用户反馈，再生成标题栏完整性专项审核包。
  - 修复 crop 生成策略后，再对浅字样本执行图像预处理小实验。
  - 最后重新生成 63 条图号命名审核包，所有样本重新进入人工复核，不沿用旧自动放行结论。
- 额外风险：
  - 用户保存后的 CSV 变为 GBK/ANSI 编码；导入脚本必须兼容 UTF-8-BOM 和 GBK/ANSI，避免人工备注丢失或乱码。

标题栏 crop 完整性专项审核包执行结果：

- 已新增脚本：`scripts/ocr/build_title_block_crop_quality_review_pack.py`。
- 已归档上一轮命名审核部分反馈：
  - 归档目录：`local_data/review_inbox/archive/naming_review_partial_20260629_202825`。
  - 原 `review_form.csv` 编码识别为 `gb18030`。
  - 原表 63 行，已填写 14 行。
  - 已填写行中旋转判断正确 14 行，人工判断错误 9 行。
  - 有备注样本：`sample_008`、`sample_009`、`sample_016`、`sample_022`、`sample_032`、`sample_035`、`sample_039`、`sample_042`。
- 已重新生成固定入口：`local_data/review_inbox/current/`。
- 当前入口文件：
  - `title_block_crop_review/review_index.html`
  - `title_block_crop_review/review_form.csv`
  - `title_block_crop_review/review_manifest.json`
- 审核资产：
  - 校正后整页：63 张。
  - 当前标题栏 crop：63 张。
  - 当前 crop 位置 overlay：63 张。
- 人工 CSV 字段保持低噪声：`序号`、`样本编号`、`当前crop判断`、`问题类型`、`备注`。
- HTML/CSV 未出现内部状态码、阻断原因、机器分组、bbox、score、candidate 或 JSON 字段。
- 抽样视觉检查：
  - `sample_008` overlay 能显示旧 crop 只覆盖左下区域并遗漏右侧图名/图号。
  - `sample_009` overlay 能显示旧 crop 混入底部主体视图并遗漏右下标题栏。
  - `sample_016` overlay 能显示旧 crop 右侧贴近图号尾部，适合审核尾部截断。
- 未生成 `corrected_pdfs` 或 `renamed_pdfs`。

docs/plans 编号命名整理需求：

- 用户指出：`docs/plans` 中计划文档无法从文件名看出生成顺序，不利于追溯。
- 现状：
  - `docs/plans/` 编号规划前共有 61 个计划文件；新增编号整理计划后，执行编号重命名时共有 62 个计划文件。
  - 计划文件被 `reports/rpd-rotation-detection.md`、`docs/README.md`、`HANDOFF.md`、`docs/decisions/`、`docs/research/`、`references/` 和部分计划正文交叉引用。
- 决策：
  - 给所有计划文件增加三位数字编号前缀。
  - 编号排序优先依据 Git 首次加入文件的提交时间。
  - 同一提交内缺少精确编辑顺序的早期文件，使用现有时间和文件名做稳定排序补充。
  - 使用 `git mv` 执行重命名，并同步修正仓库内引用。
- 计划：
  - 见 `docs/plans/062-docs-plan-numbering-plan.md`。
- 风险：
  - 编号用于追溯辅助，不声称能完全还原同一提交内的编辑时序。
  - 必须搜索旧文件名残留，避免文档链接失效。
- 执行结果：
  - 已通过 `git mv` 将 62 个计划文件重命名为三位数字前缀格式。
  - 已同步修正仓库内计划文档引用。
  - 排序依据为 Git 首次加入时间、文件修改时间、文件名的稳定组合。

标题栏 crop 完整性审核结果归档与分层需求：

- 用户已完成当前标题栏 crop 完整性专项审核表。
- 当前阶段必须先保全用户填写结果，再进入 crop 修复策略实现。
- 初步读取结果：
  - 总样本数：63。
  - `已完整识别`：27。
  - `未完整识别`：36。
  - 问题类型集中为 `标题栏右侧未全被识别`。
  - 典型备注包括“图号未完整”“一半未识别”“标题栏位置判断错误，识别位置90%为零件图”。
- 必须归档当前固定审核入口：
  - `local_data/review_inbox/current/title_block_crop_review/`
- 归档后重置：
  - `local_data/review_inbox/current/`
- 输出要求：
  - 保留用户原始 `review_form.csv`。
  - 生成机器可读统计摘要。
  - 生成人工可读低噪声摘要。
  - 抽样视觉核对右侧缺失、半截标题栏、错框/混入主体和浅字问题。
- 计划：
  - 见 `docs/plans/063-title-block-crop-review-result-archive-plan.md`。
- 下一步约束：
  - 当前阶段不修复 crop 算法。
  - 不运行 OCR 图像预处理小实验。
  - 不重新生成命名审核包。
  - 不生成正式 PDF，不重命名 PDF。

标题栏 crop 完整性审核结果归档与分层执行结果：

- 新增归档脚本：
  - `scripts/ocr/archive_title_block_crop_review_results.py`
- 已归档当前固定审核入口：
  - `local_data/review_inbox/archive/title_block_crop_review_20260629_reviewed/`
- 已重置固定审核入口：
  - `local_data/review_inbox/current/README.md`
  - 当前没有待用户审核、填写或标注的文件。
- 已生成业务摘要：
  - `local_data/title_block_crop_quality_review/filled_review_summary.json`
  - `local_data/title_block_crop_quality_review/filled_review_summary.csv`
  - `local_data/title_block_crop_quality_review/human_summary.md`
- 审核表读取：
  - 编码识别为 `gb18030`。
  - 原始用户填写表已保留在归档目录。
  - 归档后的 `review_manifest.json` 已将资产路径改写到归档目录，不再指向 `review_inbox/current`。
- 统计结果：
  - 总样本数：63。
  - 完整：27。
  - 未完整：36。
  - 主要问题类型：标题栏右侧未全部覆盖 36 条。
- 完整样本：
  - `sample_002`、`sample_035`、`sample_038`、`sample_039`、`sample_041`、`sample_042`、`sample_051`、`sample_055`、`sample_056`、`sample_057`、`sample_062`、`sample_001`、`sample_011`、`sample_034`、`sample_036`、`sample_037`、`sample_040`、`sample_044`、`sample_046`、`sample_047`、`sample_049`、`sample_050`、`sample_052`、`sample_053`、`sample_054`、`sample_059`、`sample_061`。
- 未完整样本：
  - `sample_006`、`sample_007`、`sample_008`、`sample_009`、`sample_016`、`sample_022`、`sample_032`、`sample_043`、`sample_045`、`sample_048`、`sample_060`、`sample_063`、`sample_003`、`sample_004`、`sample_005`、`sample_010`、`sample_012`、`sample_013`、`sample_014`、`sample_015`、`sample_017`、`sample_018`、`sample_019`、`sample_020`、`sample_021`、`sample_023`、`sample_024`、`sample_025`、`sample_026`、`sample_027`、`sample_028`、`sample_029`、`sample_030`、`sample_031`、`sample_033`、`sample_058`。
- 抽样视觉核对结论：
  - `sample_006`：右侧少量截断，图号/比例栏贴近或越出旧框。
  - `sample_008`：旧框只覆盖左下技术要求和签字区，右侧图名/图号栏缺失。
  - `sample_009`：旧框混入底部零件视图，真实右下标题栏未完整进入。
  - `sample_016`：右侧标题栏外框和图号尾部存在截断风险。
  - `sample_035`：crop 基本完整，但图号区域偏浅，短横线容易漏读。
  - `sample_042`：crop 基本完整，但图号区域浅且有叠影。
- 下一步：
  - 进入标题栏 crop 生成策略修复规划与实现。
  - 优先解决右侧/图号尾部缺失、半截标题栏、错框或混入主体三类完整性问题。
  - 浅字和短横线不清问题保留到 OCR 图像预处理小实验阶段处理。

标题栏 crop 生成策略修复需求：

- 当前 crop 生成源头是 `scripts/ocr/build_full_63_title_block_ocr_dry_run.py`。
- 当前策略直接使用 stage1 `best_candidate.bbox` 加 `CROP_PADDING_RATIO=0.03`：
  - 这会让局部候选框错误传递到 OCR、图号抽取和命名审核。
  - 对 `sample_008`、`sample_022`、`sample_032` 等样本，会只截左半标题栏。
  - 对 `sample_009`，会混入主体零件视图并遗漏右下标题栏。
- 修复方向：
  - 使用人工确认的旋转方向先生成校正后页面。
  - 在校正坐标系中生成标题栏 crop。
  - 将 stage1 bbox 仅作为弱提示，不再作为最终 crop 边界。
  - 对底部标题栏强制向右侧图名/图号栏和图框右边界扩展。
  - 对半截标题栏和错框样本使用保守底部整带候选。
- 修复后必须生成新的 crop 复核固定入口，由用户人工审核。
- 计划：
  - 见 `docs/plans/064-title-block-crop-generation-fix-plan.md`。
- 约束：
  - 人工审核修复后 crop 前，不重建图号命名审核包。
  - 不生成正式 PDF，不重命名 PDF。
  - 浅字问题留到 OCR 图像预处理小实验，不在本阶段混合处理。

标题栏 crop 生成策略修复执行结果：

- 已修改 `scripts/ocr/build_full_63_title_block_ocr_dry_run.py`：
  - 读取人工确认的旋转角度后生成校正后页面。
  - 将旧 stage1 bbox 仅作为修复前参考位置，不再直接作为最终 crop。
  - 竖版和常规底部标题栏使用校正后底部全宽保守候选，避免右侧图名/图号栏再次截断。
  - 横版且旧提示框明显偏左或不贴右侧时，使用右下表格线证据收缩到右下标题栏区域。
  - 右下策略增加下半部表格线列投影左边界收紧，减少主体零件视图混入。
- 已新增 `scripts/ocr/build_title_block_crop_recovery_review_pack.py`：
  - 从修复 dry-run 记录生成固定审核入口。
  - 人工 CSV 仅保留 `序号`、`样本编号`、`修复后crop判断`、`问题类型`、`备注`。
  - HTML 展示校正后整页、修复后 crop、修复后位置示意，不暴露 bbox、score、JSON、长路径或候选列表。
- 已重新运行 63 条标题栏 crop/OCR dry-run：
  - 输出目录：`local_data/full_63_title_block_ocr_dry_run/crop_recovery_v1/`
  - 记录数：63。
  - crop：63/63。
  - 校正后页面：63/63。
  - overlay：63/63。
  - OCR 状态：63/63 ok。
  - 字段簇：strong 61，weak 2。
  - crop 策略：底部全宽 62，右下表格线证据 1。
  - `modified_pdf=false`，`renamed_pdf=false`。
- 典型样本验证：
  - `sample_006`、`sample_016`：右侧图号/比例栏不再被旧框截断。
  - `sample_008`、`sample_022`、`sample_032`、`sample_045`、`sample_048`：使用底部全宽候选，不再只覆盖左半标题栏。
  - `sample_009`：触发右下表格线证据策略，红框从底部整带收缩到右下标题栏区域；OCR 可抽到图号候选，但仍存在 `10` 被识别为 `1Q` 的 OCR 风险，必须留待后续人工命名审核或图像预处理处理。
  - `sample_035`、`sample_042`：未误触发右下收缩，浅字/叠影问题仍保留到 OCR 图像预处理小实验。
- 已发布修复后标题栏 crop 复核固定入口：
  - `local_data/review_inbox/current/title_block_crop_recovery_review/review_index.html`
  - `local_data/review_inbox/current/title_block_crop_recovery_review/review_form.csv`
  - 三类图片资产各 63 张，缺失数 0。
- 当前暂停点：
  - 等待用户审核修复后 crop 完整性。
  - 在该审核完成前，不重建图号命名审核包，不执行 OCR 图像预处理小实验，不生成正式 PDF，不重命名 PDF。

标题栏粗 crop 对图号 OCR 影响调研需求：

- 用户已完成修复后标题栏 crop 复核表。
- 人工审核结论：
  - 总数：63。
  - `修复后crop判断=正确`：63。
  - `问题类型=范围太大`：31。
  - 典型备注：`左半边不是标题栏，而是图纸`。
- 需求判断：
  - 当前 crop 方案在完整性上有效，但有明显粗裁剪倾向。
  - 粗 crop 简洁稳定，适合作为完整性复核对象。
  - 粗 crop 可能把图纸下部主体、尺寸、技术要求或印章送入 OCR，增加图号识别复杂度。
  - 当前不能直接进入图号命名审核，也不能简单收窄 crop 后覆盖掉完整性成果。
- 本轮必须先归档当前已填写审核入口并重置 `local_data/review_inbox/current/`，再调研成熟方案。
- 调研重点：
  - 粗定位后字段级细定位。
  - 表格结构识别与单元格定位。
  - OCR 文本检测后按位置/规则过滤。
  - 关键词或字段锚点定位图号区域。
  - 完整性 crop 与 OCR 用细 ROI 双轨策略。
- 计划：
  - 见 `docs/plans/065-title-block-coarse-crop-ocr-downstream-research-plan.md`。
- 约束：
  - 本轮不修改 crop 生成脚本。
  - 不生成命名审核包。
  - 不运行 OCR 图像预处理实验。
  - 不生成正式 PDF，不重命名 PDF。

标题栏粗 crop 对图号 OCR 影响调研执行结果：

- 已归档修复后标题栏 crop 复核入口：
  - `local_data/review_inbox/archive/title_block_crop_recovery_review_20260630_150339_reviewed/`
- 已重置固定审核入口：
  - `local_data/review_inbox/current/README.md`
  - 当前没有待用户审核、填写或标注的文件。
- 已生成复核摘要：
  - `local_data/title_block_crop_recovery_review/filled_review_summary.json`
  - `local_data/title_block_crop_recovery_review/filled_review_summary.csv`
  - `local_data/title_block_crop_recovery_review/human_summary.md`
- 摘要结果：
  - 记录数：63。
  - `修复后crop判断=正确`：63。
  - `问题类型=范围太大`：31。
  - `modified_pdf=false`。
  - `renamed_pdf=false`。
- 已沉淀调研资料：
  - `references/title-block-coarse-crop-ocr-downstream/README.md`
  - `docs/research/2026-06-30-title-block-coarse-crop-ocr-downstream-research.md`
  - `docs/decisions/title-block-crop-and-ocr-roi-strategy.md`
- 调研结论：
  - 用户关于粗 crop 增加下游图号 OCR 复杂性的担心成立。
  - 当前粗 crop 不应回退或整体收窄，因为它已经解决标题栏完整性和右侧图号栏漏裁问题。
  - 当前粗 crop 应保留为完整性 crop、人工审核图和回溯证据。
  - 图号 OCR 不应直接把粗 crop 作为唯一主输入，应新增 OCR 用细 ROI 或图号字段 ROI。
  - 细 ROI 可由表格线/图框线、OCR 文本框、关键词锚点和图号格式质量门共同生成。
  - `范围太大` 的 31 条样本应作为下一轮细 ROI 小实验重点样本，而不是视为 crop 完整性失败。
- 下一步：
  - 先规划 OCR 用细 ROI 小实验。
  - 小实验通过前，不重新生成 63 条图号命名人工审核包。
  - 浅字标题栏 OCR 图像预处理仍作为互补实验，不能替代细 ROI 设计。

OCR 用细 ROI 小实验规划需求：

- 用户已同意下一步计划，进入 OCR 用细 ROI 小实验规划。
- 本轮目的：
  - 不推翻当前 63/63 完整性 crop 结论。
  - 在图号 OCR 前新增更小、更低噪声的细 ROI。
  - 对比粗 crop OCR 与细 ROI OCR 的图号候选质量。
  - 为后续是否重建 63 条图号命名审核包提供依据。
- 样本范围：
  - 31 条 `范围太大` 样本。
  - 加入 `sample_009` 作为旧流程图号易错补充样本。
  - `sample_035`、`sample_042` 已在 31 条内，继续作为浅字/叠影风险样本观察。
- 计划：
  - 见 `docs/plans/066-ocr-fine-roi-small-experiment-plan.md`。
- 约束：
  - 本轮不修改当前粗 crop 生成策略。
  - 不运行 OCR 图像预处理增强实验。
  - 不生成正式旋正 PDF。
  - 不正式重命名单页 PDF。
  - 不调用云端 OCR/VLM。
  - 实验完成并生成固定审核入口后，必须等待用户审核细 ROI 与图号候选，不能直接重建 63 条命名审核包。

OCR 用细 ROI 小实验执行结果：

- 新增脚本：
  - `scripts/ocr/build_ocr_fine_roi_experiment.py`
- 已运行命令：
  - `python -m py_compile scripts\ocr\build_ocr_fine_roi_experiment.py`
  - `python scripts\ocr\build_ocr_fine_roi_experiment.py`
- 输入：
  - `local_data/full_63_title_block_ocr_dry_run/crop_recovery_v1/full_63_ocr_arbitration_records.jsonl`
  - `local_data/title_block_crop_recovery_review/filled_review_summary.json`
- 本地输出：
  - `local_data/ocr_fine_roi_experiment/experiment_summary.json`
  - `local_data/ocr_fine_roi_experiment/fine_roi_records.jsonl`
  - `local_data/ocr_fine_roi_experiment/fine_roi_ocr_results.jsonl`
  - `local_data/ocr_fine_roi_experiment/drawing_number_comparison.csv`
  - `local_data/ocr_fine_roi_experiment/needs_review.csv`
  - `local_data/ocr_fine_roi_experiment/fine_rois/`
  - `local_data/ocr_fine_roi_experiment/overlays/`
- 固定审核入口：
  - `local_data/review_inbox/current/fine_roi_review/review_index.html`
  - `local_data/review_inbox/current/fine_roi_review/review_form.csv`
- 实验统计：
  - 样本数：32。
  - ROI 记录数：96。
  - 细 ROI 机器候选通过质量门：24。
  - 仍需人工复核：8。
  - 最佳 ROI 类型：`table_line_right_roi` 22，`bottom_right_band_roi` 8，`right_band_roi` 2。
  - 审核入口资产缺失数：0。
  - `modified_pdf=false`。
  - `renamed_pdf=false`。
- 需人工复核原因：
  - 粗 crop 与细 ROI 候选不一致：4。
  - 细 ROI 未识别出图号：3。
  - 细 ROI 候选置信度偏低：1。
- 观察：
  - `sample_009` 细 ROI 将粗 crop 中疑似 `YEJ125-1Q-00-2525` 的候选改为 `YEJ125-10-00-2525`，说明缩小 ROI 对 `10/1Q` 噪声有帮助；但因粗细候选冲突，仍按质量门进入人工复核。
  - 多 ROI OCR 当前耗时为分钟级，后续若全量化应增加缓存或减少候选 ROI 数量。
- 审核界面：
  - 人工 CSV 仅保留序号、样本编号、细 ROI 判断、图号判断、人工确认图号、备注。
  - HTML 仅展示校正后整页、完整性 crop、细 ROI、位置示意、粗/细 OCR 摘要和候选图号。
  - 人工 HTML/CSV 未暴露 bbox、score、长路径、JSON、完整 OCR 或候选列表。
- 当前暂停点：
  - 等待用户审核细 ROI 与图号候选。
  - 用户审核完成前，不执行 OCR 图像预处理实验，不重建 63 条命名审核包，不生成正式 PDF，不重命名 PDF。

细 ROI 审核入口说明修复需求：

- 用户指出当前 `review_form.csv` 不清楚每个字段应该填写什么，`review_index.html` 中不同颜色框也没有说明。
- 该问题成立：
  - 当前审核入口字段足够低噪声，但缺少必要填写指南。
  - 当前位置示意图使用红、蓝、绿三种框，且较粗框表示机器选中的细 ROI，但 HTML 中没有图例。
- 修复范围：
  - 补充 `README.md` 中的字段填写规则。
  - 补充 `review_index.html` 中的颜色图例和填写提示。
  - 保持 `review_form.csv` 字段不变，避免增加人工填写负担。
- 计划：
  - 见 `docs/plans/067-fine-roi-review-instruction-fix-plan.md`。
- 约束：
  - 不修改细 ROI 生成算法。
  - 不重新跑 OCR。
  - 不改变机器候选结论。
  - 不生成正式 PDF，不重命名 PDF。

细 ROI 审核入口说明修复执行结果：

- 已修改脚本：
  - `scripts/ocr/build_ocr_fine_roi_experiment.py`
- 已重新生成当前审核入口：
  - `local_data/review_inbox/current/README.md`
  - `local_data/review_inbox/current/fine_roi_review/review_index.html`
  - `local_data/review_inbox/current/fine_roi_review/review_form.csv`
- 修复内容：
  - 在 `README.md` 中补充 CSV 字段填写规则。
  - 在 `review_index.html` 顶部补充填写说明。
  - 在 `review_index.html` 顶部补充颜色图例：红框为右侧区域候选，蓝框为右下区域候选，绿框为表格线右侧区域候选，较粗框为当前机器选中的细 ROI。
- 验证结果：
  - `review_form.csv` 字段保持不变。
  - 人工 HTML/CSV 未出现 bbox、score、长路径、JSON、完整 OCR、候选列表或内部技术码。
  - 未重新跑 OCR。
  - `modified_pdf=false`。
  - `renamed_pdf=false`。

账号切换交接更新需求：

- 用户准备切换账号后继续对话，需要当前项目状态可被新会话快速接手。
- 现有 `HANDOFF.md` 仍停留在 2026-06-28 的 MCP/VLM teacher 阶段，已不符合当前状态。
- 当前真实状态：
  - 细 ROI 与图号候选复核入口已发布。
  - 当前等待用户审核 `local_data/review_inbox/current/fine_roi_review/review_form.csv`。
- 计划：
  - 见 `docs/plans/068-account-switch-handoff-update-plan.md`。
- 约束：
  - 本轮只更新交接文档和状态记录。
  - 不修改算法，不重新跑 OCR，不归档当前审核入口，不生成或重命名 PDF。

账号切换交接更新执行结果：

- 已更新 `HANDOFF.md`。
- 交接记录已指向当前固定审核入口：
  - `local_data/review_inbox/current/README.md`
  - `local_data/review_inbox/current/fine_roi_review/review_index.html`
  - `local_data/review_inbox/current/fine_roi_review/review_form.csv`
- 交接记录已明确：
  - 当前等待用户审核 32 条细 ROI 与图号候选。
  - CSV 字段填写规则和颜色图例。
  - 最近关键提交。
  - 审核完成前不要重建 63 条命名审核包，不要执行 OCR 图像预处理实验，不要生成或重命名 PDF。
- 本轮未修改算法，未重新跑 OCR，未归档当前审核入口。

图号人工校正记忆系统需求：

- 用户已完成当前细 ROI 与图号候选复核。
- 用户提出需要建立记忆系统，用于沉淀每次人工校准图号识别时发现的规律，方便后续迁移。
- 当前审核入口：
  - `local_data/review_inbox/current/fine_roi_review/review_form.csv`
  - `local_data/review_inbox/current/fine_roi_review/review_index.html`
  - `local_data/review_inbox/current/fine_roi_review/review_manifest.json`
- 当前机器候选记录：
  - `local_data/ocr_fine_roi_experiment/fine_roi_records.jsonl`
- 计划：
  - 见 `docs/plans/069-drawing-number-calibration-memory-plan.md`。
- 目标：
  - 归档当前已填写审核入口。
  - 建立本地私有图号校正记忆库。
  - 记录人工校准事实、机器候选与人工确认差异、OCR 易错规律和 ROI 裁剪建议。
  - 生成可迁移 JSON/Markdown 导出包。
- 约束：
  - 不自动修改图号识别算法。
  - 不重新跑 OCR。
  - 不重建 63 条命名审核包。
  - 不执行浅字标题栏图像预处理实验。
  - 不生成正式 PDF，不重命名 PDF。
  - 不把 `local_data/` 中的私有图号、图片或审核结果加入 Git。

图号人工校正记忆系统执行结果：

- 新增脚本：
  - `scripts/ocr/archive_fine_roi_review_and_build_memory.py`
- 已执行命令：
  - `python -m py_compile scripts\ocr\archive_fine_roi_review_and_build_memory.py`
  - `python scripts\ocr\archive_fine_roi_review_and_build_memory.py`
- 已归档当前审核入口：
  - `local_data/review_inbox/archive/fine_roi_review_20260701_104716_reviewed/`
- 已重置固定审核入口：
  - `local_data/review_inbox/current/README.md`
  - 当前没有待用户审核、填写或标注的文件。
- 审核表读取：
  - 编码识别为 `gb18030`。
  - 审核记录：32 条。
  - manifest：32 条。
  - 机器记录缺失：0。
- 已生成本地图号人工校正记忆库：
  - `local_data/drawing_number_calibration_memory/memory_events.jsonl`
  - `local_data/drawing_number_calibration_memory/memory_patterns.json`
  - `local_data/drawing_number_calibration_memory/memory_patterns.md`
  - `local_data/drawing_number_calibration_memory/current_session_events.csv`
- 已生成可移植导出：
  - `local_data/drawing_number_calibration_memory/portable_export/drawing_number_calibration_memory_v1.json`
  - `local_data/drawing_number_calibration_memory/portable_export/drawing_number_calibration_rules.md`
- 本轮记忆统计：
  - 记忆事件：32 条。
  - 机器候选人工确认可用：24 条。
  - 人工修正机器候选：4 条。
  - OCR 未识别但人工补充：3 条。
  - 仍需人工兜底：1 条，`sample_009`。
  - 细 ROI 判断：32 条均为 `范围太大`。
- 当前可迁移规律：
  - 当细 ROI 虽能识别图号但被人工反复标记范围太大时，不应只按图号命中自动放行，应继续收窄 ROI 或保留人工复核。
  - 高频 ROI 建议为上侧减少约 20%，以及左侧向右减少约 25%。
  - 已记录 OCR 候选差异示例，包括 `1 -> 0A`、`K -> X`、`C -> 0`。
  - 图号模糊或人工无法确认的样本不得自动命名，应保留人工识别或 VLM 兜底。
- 验证结果：
  - `modified_pdf=false`。
  - `renamed_pdf=false`。
  - `current` 目录只剩说明文件。
  - `local_data/` 私有记忆库未进入 Git。

基于人工记忆的细 ROI 收窄实验需求：

- 用户同意下一步集中处理 ROI 收窄，暂时不考虑图号识别正确性问题。
- 该判断成立：
  - 当前 32 条人工审核样本全部标记为 `范围太大`。
  - 若此时先修图号识别规则，容易把 ROI 噪声、明细表干扰和主体图纸混入误当成图号规则问题。
  - 图号识别正确性本轮只作为机器侧护栏，不作为优化目标。
- 计划：
  - 见 `docs/plans/070-memory-based-fine-roi-tightening-plan.md`。
- 本轮目标：
  - 基于人工记忆生成新版收窄细 ROI。
  - 生成人工可审的新旧 ROI 对比入口。
  - 人工填写表只围绕 ROI 是否更好，不要求用户判断图号对错。
- 约束：
  - 不修正图号识别规则。
  - 不重新生成 63 条图号命名审核包。
  - 不执行浅字标题栏 OCR 图像预处理实验。
  - 不生成正式 PDF，不重命名 PDF。
  - 不把 `local_data/` 私有输出加入 Git。

基于人工记忆的细 ROI 收窄实验执行结果：

- 新增脚本：
  - `scripts/ocr/build_memory_based_fine_roi_tightening.py`
- 已执行命令：
  - `python -m py_compile scripts\ocr\build_memory_based_fine_roi_tightening.py`
  - `python scripts\ocr\build_memory_based_fine_roi_tightening.py`
- 输入：
  - `local_data/drawing_number_calibration_memory/current_session_events.csv`
  - `local_data/ocr_fine_roi_experiment/fine_roi_records.jsonl`
  - `local_data/ocr_fine_roi_experiment/fine_roi_ocr_results.jsonl`
- 本地输出：
  - `local_data/ocr_fine_roi_tightening_experiment/tightening_summary.json`
  - `local_data/ocr_fine_roi_tightening_experiment/tightening_summary.csv`
  - `local_data/ocr_fine_roi_tightening_experiment/tightening_records.jsonl`
  - `local_data/ocr_fine_roi_tightening_experiment/tightening_records.csv`
  - `local_data/ocr_fine_roi_tightening_experiment/old_fine_rois/`
  - `local_data/ocr_fine_roi_tightening_experiment/new_fine_rois/`
  - `local_data/ocr_fine_roi_tightening_experiment/overlays/`
- 固定审核入口：
  - `local_data/review_inbox/current/fine_roi_tightening_review/review_index.html`
  - `local_data/review_inbox/current/fine_roi_tightening_review/review_form.csv`
  - `local_data/review_inbox/current/fine_roi_tightening_review/review_manifest.json`
- 实验统计：
  - 样本数：32。
  - 平均面积减少：0.238073。
  - 最小面积减少：0.199105。
  - 最大面积减少：0.5。
  - 基础 ROI 类型：`table_line_right_roi` 22，`bottom_right_band_roi` 9，`right_band_roi` 1。
  - 审核入口资产缺失数：0。
  - 收窄被安全阈值拒绝：0。
  - OCR 机器护栏：新版 ROI 仍有候选 27，丢失旧候选 2，前后均无候选 3。
  - `modified_pdf=false`。
  - `renamed_pdf=false`。
- 审核界面：
  - 人工 CSV 仅保留 `序号`、`样本编号`、`新版ROI判断`、`相对旧ROI是否更好`、`问题类型`、`备注`。
  - HTML 展示完整性 crop、旧细 ROI、新版 ROI、新旧位置对比图。
  - 新旧位置对比图中红框为旧细 ROI，绿框为新版 ROI。
  - 人工 HTML/CSV 未暴露 OCR 候选、bbox、score、长路径、JSON、完整 OCR 或图号判断字段。
- 抽样视觉核对：
  - `sample_001`：新版绿框明显去掉旧红框左侧主体和上侧明细区域的一部分，仍覆盖标题栏。
  - `sample_043`：左侧按 50% 强收窄后，右侧标题栏保留，左侧技术要求和明细表显著减少，适合人工判断是否过窄。
- 当前暂停点：
  - 等待用户审核细 ROI 收窄复核入口。
  - 审核完成前，不修正图号识别规则，不重建 63 条命名审核包，不执行浅字 OCR 图像预处理实验，不生成正式 PDF，不重命名 PDF。

细 ROI 收窄复核结果归档与分层需求：

- 用户已完成当前细 ROI 收窄复核表。
- 初步读取结果：
  - 审核记录：32 条。
  - `新版ROI判断=正确`：31 条。
  - `相对旧ROI是否更好=更好`：31 条。
  - `sample_001` 标记为 `范围太小`、`更差`、`裁掉标题栏`。
  - `sample_001` 备注为：旧 ROI 的高度更好，新 ROI 的左右范围合适。
- 判断：
  - 当前收窄策略整体有效。
  - `sample_001` 暴露出上侧/高度收窄过激风险。
  - 后续固化策略时应把左右收窄和高度收窄拆开，不能无条件对所有样本执行上侧减少。
- 计划：
  - 见 `docs/plans/071-fine-roi-tightening-review-archive-plan.md`。
- 本轮目标：
  - 归档当前已填写审核入口。
  - 重置固定审核入口。
  - 生成机器摘要、人工摘要和规则分层结论。
- 约束：
  - 不修改 ROI 生成算法。
  - 不重新跑 OCR。
  - 不重建 63 条图号命名审核包。
  - 不执行浅字标题栏 OCR 图像预处理实验。
  - 不生成正式 PDF，不重命名 PDF。

细 ROI 收窄复核结果归档与分层执行结果：

- 新增脚本：
  - `scripts/ocr/archive_fine_roi_tightening_review_results.py`
- 已执行命令：
  - `python -m py_compile scripts\ocr\archive_fine_roi_tightening_review_results.py`
  - `python scripts\ocr\archive_fine_roi_tightening_review_results.py`
- 已归档当前审核入口：
  - `local_data/review_inbox/archive/fine_roi_tightening_review_20260701_141941_reviewed/`
- 已重置固定审核入口：
  - `local_data/review_inbox/current/README.md`
  - 当前没有待用户审核、填写或标注的文件。
- 已生成业务摘要：
  - `local_data/fine_roi_tightening_review/filled_review_summary.json`
  - `local_data/fine_roi_tightening_review/filled_review_summary.csv`
  - `local_data/fine_roi_tightening_review/human_summary.md`
- 审核表读取：
  - 编码识别为 `gb18030`。
  - 审核记录：32 条。
  - manifest：32 条。
  - 收窄实验记录：32 条。
- 统计结果：
  - 新版 ROI 正确且更好：31 条。
  - 需要调整：1 条，`sample_001`。
  - `modified_pdf=false`。
  - `renamed_pdf=false`。
- 规则分层结论：
  - 当前收窄策略整体有效，大多数样本可以采用本轮新版 ROI。
  - `sample_001` 需要保留旧 ROI 高度，采用新版左右范围。
  - 后续固化策略时应把高度收窄与左右收窄拆开，不能无条件套用上侧减少。
- 当前暂停点：
  - 当前没有待审核文件。
  - 下一步应规划并实现“细 ROI 收窄策略固化”，先处理 `sample_001` 例外规则，再考虑重建 63 条命名审核包。

## JS2207 泛化测试需求

用户新增测试 PDF：

- `local_data/source_pdfs/JS2207-00-00升降平台.pdf`

这套图纸用于检验现有旋转方向识别与标题栏检测流程的通用性。用户明确要求：

- 严禁对 `JS2207` 做针对性优化。
- 图纸旋转方向是随机的。
- 必须使用之前完成的工具和工作流执行旋转识别与标题栏识别。
- 完成后发布固定审核入口，等待用户审核。

本轮判断：

- 该任务应作为泛化验收，而不是算法调参任务。
- 如果既有流程在 `JS2207` 上失败，应记录失败样本、置信度、标题栏 crop 和位置示意图，交由用户审核后再决定是否进入通用策略改进。
- 不得根据 `JS2207` 的文件名、页码、图幅或特定标题栏样式写规则。

计划：

- 见 `docs/plans/072-js2207-generalization-test-plan.md`。

目标：

- 拆分 `JS2207` 原 PDF 为单页 PDF。
- 渲染单页 PNG。
- 复用 `scripts/rotation/detect_rotation_stage1.py` 生成旋转和标题栏所在侧检测结果。
- 复用既有标题栏 crop recovery 逻辑生成校正后整页、标题栏 crop 和位置示意图。
- 发布低噪声人工审核包到 `local_data/review_inbox/current/`。

约束：

- 不修改标题栏检测算法、阈值或仲裁规则。
- 不修正图号识别正确性。
- 不生成正式旋正 PDF。
- 不重命名单页 PDF。
- 不重建 63 条图号命名审核包。
- 不把 `local_data/` 私有输出加入 Git。

JS2207 泛化测试执行结果：

- 新增脚本：
  - `scripts/experiments/build_js2207_generalization_review_pack.py`
- 已执行命令：
  - `python -m py_compile scripts\experiments\build_js2207_generalization_review_pack.py`
  - `python scripts\experiments\build_js2207_generalization_review_pack.py`
- 输入：
  - `local_data/source_pdfs/JS2207-00-00升降平台.pdf`
- 本地输出：
  - `local_data/js2207_generalization_test/single_page_pdfs/`
  - `local_data/js2207_generalization_test/rendered_png/`
  - `local_data/js2207_generalization_test/stage1/results.json`
  - `local_data/js2207_generalization_test/title_block_crop_recovery/`
  - `local_data/js2207_generalization_test/js2207_generalization_records.jsonl`
  - `local_data/js2207_generalization_test/js2207_generalization_summary.json`
  - `local_data/js2207_generalization_test/js2207_generalization_summary.csv`
- 固定审核入口：
  - `local_data/review_inbox/current/README.md`
  - `local_data/review_inbox/current/js2207_generalization_review/review_index.html`
  - `local_data/review_inbox/current/js2207_generalization_review/review_form.csv`
  - `local_data/review_inbox/current/js2207_generalization_review/review_manifest.json`
- 运行统计：
  - PDF 页数：29。
  - OpenCV stage1 结果：29。
  - stage1 低置信复核标记：0。
  - 标题栏 crop recovery 成功：29。
  - 审核入口资产缺失数：0。
  - 审核入口图片资产：116 张，原始渲染图、校正后整页、标题栏 crop、位置示意图各 29 张。
  - `algorithm_changes=false`。
  - `js2207_specific_optimization=false`。
  - `modified_pdf=false`。
  - `renamed_pdf=false`。
- 审核界面：
  - HTML 展示原始渲染图、机器校正后整页、标题栏 crop 和标题栏位置示意图。
  - 人工 CSV 仅保留页码、样本编号、机器标题栏位置、机器旋转角度、旋转是否正确、标题栏位置是否正确、正确标题栏位置、正确旋转角度和备注。
  - 人工 HTML/CSV 未暴露 bbox、score、confidence、debug 路径、长 JSON 或机器候选列表。
- 当前暂停点：
  - 等待用户审核 `local_data/review_inbox/current/js2207_generalization_review/review_form.csv`。
  - 用户审核完成前，不基于 JS2207 调参，不修改标题栏检测策略，不生成正式 PDF，不重命名 PDF。

## 阿里云 VLM 旋正与图号读取 MVP 需求

用户已审核 JS2207 泛化测试的一部分，并指出当前问题已经明显：

- 既有流程没有先稳定判断标题栏在上下左右的位置，再由标题栏位置推导页面应如何旋转。
- 一部分页面因此发生旋转判断失误。
- 当前继续围绕本地小模型或本地标题栏检测细节调试，可能偏离用户真正目标。
- 用户当前目标是尽快拿到 MVP：把图片旋转到正确方向，然后读取图号。
- 若本地模型短期调试困难，应优先尝试 VLM；用户可以提供相关 Key。

本轮判断：

- 用户的纠偏成立。当前阶段不应继续把主要精力放在本地小模型局部优化上。
- JS2207 的失败现象说明本地策略存在泛化风险，继续用该策略承载旋正和图号读取主链路，会把局部假设带入后续 OCR/命名。
- VLM 适合先作为 MVP 主线的视觉判断器，快速验证端到端链路。
- 但 VLM 输出不能直接执行不可逆动作。正式旋正 PDF、正式重命名 PDF 仍必须等待 dry-run、人工审核和质量门稳定。

阿里云百炼 VLM 接入调研：

- 使用“他山”方式先调研官方文档，不调用模型，不上传图纸。
- 官方文档显示百炼支持 OpenAI 兼容接口和 DashScope 原生接口。
- API Key 环境变量为 `DASHSCOPE_API_KEY`。
- OpenAI 兼容北京地域 base URL 示例为：
  - `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`
- chat completions endpoint 示例为：
  - `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions`
- 视觉输入可使用 `image_url`。
- 本地图片可转为 Base64 data URL，例如：
  - `data:image/png;base64,{base64_image}`
  - `data:image/jpeg;base64,{base64_image}`
  - `data:image/webp;base64,{base64_image}`
- DashScope 原生接口可使用 `MultiModalConversation` 或 HTTP multimodal-generation endpoint。
- 模型名不应硬编码，应由环境变量配置。

调研沉淀：

- 资料索引：`references/aliyun-vlm-integration/README.md`
- 调研笔记：`docs/research/2026-07-01-aliyun-vlm-integration-research.md`
- MVP 计划：`docs/plans/073-aliyun-vlm-rotation-drawing-number-mvp-plan.md`

MVP 计划边界：

- 第一版优先 provider：`aliyun_openai_compatible`。
- 必需环境变量：
  - `DASHSCOPE_API_KEY`
  - `DASHSCOPE_BASE_URL`
  - `ALIYUN_VLM_MODEL`
- 输入：
  - PDF 拆页渲染图，或已有 PNG 页面。
- 输出：
  - `vlm_requests.jsonl`
  - `vlm_raw_responses.jsonl`
  - `vlm_decisions.jsonl`
  - `vlm_decisions.csv`
  - `needs_review.csv`
  - 固定审核入口 `local_data/review_inbox/current/`
- VLM 结构化判断字段：
  - 当前页面旋转角度。
  - 应顺时针校正角度。
  - 标题栏位置。
  - 图号候选。
  - 选中的图号。
  - 置信度。
  - 是否需要人工审核。
  - 证据和原因。

质量门：

- API 调用失败、JSON 解析失败、schema 校验失败必须进入人工审核。
- 旋转角度不在 `0/90/180/270` 必须进入人工审核。
- 图号为空、候选冲突或模型低置信必须进入人工审核。
- VLM 与本地检测结果冲突时必须进入人工审核。
- VLM 结果先进入 dry-run，不直接覆盖 PDF，不直接重命名 PDF。

当前暂停点：

- 已完成调研和计划。
- 下一步应在用户确认后实现阿里 VLM MVP 请求包生成脚本。
- 联网调用前需要用户确认 `DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`、`ALIYUN_VLM_MODEL` 和图纸可外发范围。

## 项目结构整理与阿里云 VLM MVP 请求包实现需求

用户同意继续推进阿里云 VLM MVP，并要求顺便整理项目，把文件分门别类放好。

当前真实状态：

- 固定审核入口 `local_data/review_inbox/current/` 仍包含 JS2207 泛化测试审核包。
- JS2207 审核表共 29 页，已填写 6 页，未填写 23 页。
- 已填写反馈中，第 3 页和第 6 页明确指出机器旋转/标题栏位置判断错误。
- 这些人工反馈必须保留，不得在发布新审核入口时被覆盖。
- 公开脚本目前集中在 `scripts/` 根目录，领域边界不清晰。

本轮目标：

- 先规划、更新 RPD/TODO 并提交回滚点。
- 将公开脚本按领域整理到 `scripts/common/`、`scripts/rotation/`、`scripts/ocr/`、`scripts/yolo_obb/`、`scripts/vlm/`、`scripts/experiments/`。
- 补充 `scripts/README.md`，说明脚本分类和常用模块命令。
- 将脚本调用方式逐步统一为 `python -m scripts.<category>.<module>`。
- 更新 README、HANDOFF、docs 索引和关键计划/RPD 中的脚本路径。
- 实现阿里云 VLM MVP 离线请求包生成脚本。

约束：

- 不移动、删除或覆盖 `local_data/` 私有资料。
- 不覆盖当前 JS2207 已填写审核反馈。
- 不正式旋正 PDF。
- 不重命名 PDF。
- 不联网调用阿里云。
- 不写入或打印 API Key。
- 不对 JS2207 写特判。

计划：

- 见 `docs/plans/074-project-organization-and-aliyun-vlm-mvp-implementation-plan.md`。

项目结构整理与阿里云 VLM MVP 请求包实现结果：

- 已提交实现前回滚点：
  - `e9775df docs: plan project organization and aliyun vlm mvp`
- 已将公开脚本按领域整理：
  - `scripts/common/`
  - `scripts/rotation/`
  - `scripts/ocr/`
  - `scripts/yolo_obb/`
  - `scripts/vlm/`
  - `scripts/experiments/`
- 已新增脚本索引：
  - `scripts/README.md`
- 已新增阿里云 VLM MVP dry-run 请求包脚本：
  - `scripts/vlm/build_aliyun_vlm_mvp_requests.py`
- 已更新 README、HANDOFF、docs 索引和公开文档中的关键脚本路径。
- 已验证：
  - `python -m py_compile` 覆盖关键整理后脚本。
  - `python -m scripts.experiments.build_js2207_generalization_review_pack --help` 可运行。
  - `python -m scripts.vlm.build_aliyun_vlm_mvp_requests --input-image-dir local_data\js2207_generalization_test\rendered_png --limit-pages 2` 成功生成请求包。
- dry-run 输出：
  - `local_data/aliyun_vlm_mvp/vlm_requests.jsonl`
  - `local_data/aliyun_vlm_mvp/vlm_request_manifest.json`
  - `local_data/aliyun_vlm_mvp/vlm_request_manifest.csv`
  - `local_data/aliyun_vlm_mvp/vlm_prompt.md`
  - `local_data/aliyun_vlm_mvp/vlm_response_schema.json`
  - `local_data/aliyun_vlm_mvp/vlm_mvp_summary.json`
- dry-run 结果：
  - 请求数：2。
  - `network_call_executed=false`。
  - `modified_pdf=false`。
  - `renamed_pdf=false`。
  - 环境变量状态只记录是否存在，不打印 Key。
- 当前仍需用户确认：
  - `DASHSCOPE_API_KEY`
  - `DASHSCOPE_BASE_URL`
  - `ALIYUN_VLM_MODEL`
  - 图纸可外发范围。

## 阿里云 VLM 接入方式复核需求

用户希望重新调研阿里的 VLM 如何接入。

本轮判断：

- 项目已有阿里云 VLM dry-run 请求包生成脚本，但还没有联网调用。
- 在进入小批量联网调用前，应再次核对官方接入文档，避免 base URL、模型名、视觉输入格式或结构化输出假设过期。
- 本轮只更新调研和项目接入判断，不调用模型、不上传图纸。

计划：

- 见 `docs/plans/075-aliyun-vlm-integration-refresh-research-plan.md`。

阿里云 VLM 接入方式复核结果：

- 已复核官方“图像与视频理解”“首次调用千问 API”“模型列表”文档。
- 当前仍推荐第一版使用 OpenAI 兼容接口：
  - `DASHSCOPE_API_KEY`
  - `DASHSCOPE_BASE_URL`
  - `ALIYUN_VLM_MODEL`
- OpenAI 兼容视觉输入使用 `messages[].content[]` 中的 `image_url.url`。
- 本地图纸页可压缩为 JPEG 后传入：
  - `data:image/jpeg;base64,{base64_image}`
- DashScope 原生接口保留为备选路线：
  - `dashscope.MultiModalConversation`
  - `/api/v1/services/aigc/multimodal-generation/generation`
- 官方图像限制要求继续在客户端控制图片尺寸和请求体大小，尤其 Base64 编码后不超过 `10MB`。
- 当前 dry-run 请求包脚本与复核结果一致，下一步若联网调用，需要新增原始响应落盘、JSON/schema 校验、错误分层和固定审核入口发布。
- 仍不得在用户确认前上传图纸或联网调用模型。

## 阿里云 VLM 双模型小批量烟测需求

用户已将阿里云百炼访问配置放入本地 `.env/.env`，并希望同时测试 `Qwen3-VL-Flash` 和 `Qwen3-VL-Plus`。

当前本地状态：

- `.env/.env` 存在。
- 已确认变量名：
  - `DASHSCOPE_API_KEY`
  - `DASHSCOPE_BASE_URL`
- 不读取、不打印、不提交 API Key 值。
- `.env/` 必须加入 `.gitignore`，防止密钥误入版本库。

本轮目标：

- 新增阿里云 VLM 联网烟测脚本。
- 从 `.env/.env` 安全加载环境变量。
- 对同一批 2 到 3 页图纸分别调用：
  - `qwen3-vl-flash`
  - `qwen3-vl-plus`
- 保存原始响应、解析结果、schema 校验结果和双模型对比结果。
- 生成 `needs_review.csv`，将调用失败、解析失败、schema 不合格、角度非法、图号为空和双模型冲突全部列入人工复核。

约束：

- 不覆盖当前 `local_data/review_inbox/current/` 中已有 JS2207 审核材料。
- 不发布新的固定审核入口。
- 不生成正式旋正 PDF。
- 不重命名单页 PDF。
- 不把 VLM 结果直接写回 ground truth。
- 不为 JS2207 写特判。
- 不把 API Key 写入命令行、日志、JSON、CSV 或提交记录。

计划：

- 见 `docs/plans/076-aliyun-vlm-dual-model-smoke-test-plan.md`。

质量门：

- HTTP 请求失败或超时必须进入人工复核。
- 阿里云响应非 JSON、缺失 `choices[0].message.content` 或模型内容非 JSON 必须进入人工复核。
- 业务 schema 缺字段、类型错误或角度不在 `0/90/180/270` 必须进入人工复核。
- 图号为空、模型自报需要复核或两个模型之间存在旋转/标题栏位置/图号冲突必须进入人工复核。

回滚准备：

- 实现前提交本轮计划、RPD、TODO 和 `.gitignore`，作为双模型联网烟测脚本实现前的回滚点。

执行结果：

- 已提交实现前回滚点：
  - `0ed0e1d docs: plan aliyun vlm dual model smoke test`
- 新增联网烟测脚本：
  - `scripts/vlm/run_aliyun_vlm_mvp_smoke.py`
- 已增强阿里云 VLM prompt，要求模型按固定 JSON 字段返回。
- `.env/` 已加入 `.gitignore`，`.env/.env` 未进入 Git 跟踪。
- `.env/.env` 中当前 `DASHSCOPE_BASE_URL` 为 `/api/v1` 路线；脚本已兼容该形态，自动转换到 OpenAI 兼容 endpoint：
  - `/compatible-mode/v1/chat/completions`
- 已执行 dry-run：
  - 命令：`python -m scripts.vlm.run_aliyun_vlm_mvp_smoke --dry-run --limit-pages 2`
  - 请求数：4。
  - `network_call_executed=false`。
- 已执行联网烟测：
  - 命令：`python -m scripts.vlm.run_aliyun_vlm_mvp_smoke --limit-pages 2 --timeout-seconds 120 --retries 0`
  - 页数：2。
  - 模型：`qwen3-vl-flash`、`qwen3-vl-plus`。
  - 请求数：4。
  - 原始响应数：4。
  - HTTP 200：4。
  - 模型内容 JSON 解析通过：4。
  - 业务 schema 校验通过：4。
  - 模型级 `needs_review`：0。
  - 双模型对比 `needs_review`：2。
  - `modified_pdf=false`。
  - `renamed_pdf=false`。
- 输出位于：
  - `local_data/aliyun_vlm_mvp/vlm_raw_responses.jsonl`
  - `local_data/aliyun_vlm_mvp/vlm_decisions.jsonl`
  - `local_data/aliyun_vlm_mvp/vlm_decisions.csv`
  - `local_data/aliyun_vlm_mvp/dual_model_comparison.json`
  - `local_data/aliyun_vlm_mvp/dual_model_comparison.csv`
  - `local_data/aliyun_vlm_mvp/needs_review.csv`
  - `local_data/aliyun_vlm_mvp/vlm_call_summary.json`

烟测观察：

- 两个模型对前 2 页的旋转角度判断一致：
  - 当前顺时针旋转角度：均为 `0`。
  - 建议顺时针校正角度：均为 `0`。
- 两个模型对标题栏位置存在冲突：
  - `qwen3-vl-flash`：两页均返回 `bottom_right`。
  - `qwen3-vl-plus`：两页均返回 `top_right`。
- 第 1 页图号存在冲突：
  - `qwen3-vl-flash`：`JS22207 00-10`。
  - `qwen3-vl-plus`：`JS2207 00-10`。
- 第 2 页图号一致：
  - 两个模型均返回 `JS2207-00-00`。

当前判断：

- 阿里云百炼 OpenAI 兼容 VLM 接入已经打通。
- `qwen3-vl-flash` 与 `qwen3-vl-plus` 都能返回可解析、可校验的结构化结果。
- 图号读取上 `qwen3-vl-plus` 在第 1 页更稳，`qwen3-vl-flash` 出现多读字符风险。
- 标题栏位置字段需要进一步收紧定义：当前两个模型对“原始屏幕坐标下的标题栏位置”理解不一致，但不影响本轮两页旋转角度一致性。
- 下一步不应直接发布审核入口，而应先优化 prompt 中“标题栏位置必须按当前图片屏幕坐标判断”的定义，再扩大到 3 到 5 页复测。

## 阿里云 VLM 标题栏不同位置复测需求

用户核对首轮双模型烟测后反馈：

- `js2207_page_001` 的图号两个模型都识别正确。
- `js2207_page_001` 的标题栏位置应为 `top_right`。
- 需要再次测试标题栏处于不同位置时，`qwen3-vl-flash` 与 `qwen3-vl-plus` 的差异。
- 用户关注压缩后的图片是否导致图片模糊。

本轮判断：

- 首轮 API 接入和 schema 校验已通过，下一步重点不是继续证明接口可用，而是验证标题栏位置字段是否稳定。
- 直接从 JS2207 中抽页会混入本地旧算法误判和未完成审核的不确定性。
- 更稳妥的复测方式是以用户已确认的 `js2207_page_001.png` 为基准，生成四张受控旋转图，覆盖 `top_right`、`bottom_right`、`bottom_left`、`top_left`。
- 压缩 JPEG 是为了控制 Base64 请求体大小、网络稳定性和官方图片限制，但图号读取确实可能受压缩影响；本轮应提高图片质量参数复测。

计划：

- 见 `docs/plans/077-aliyun-vlm-title-block-position-probe-plan.md`。

目标：

- 生成受控多位置标题栏图片。
- 使用 `--max-image-long-side 3200` 与 `--jpeg-quality 95` 复测。
- 分别调用 `qwen3-vl-flash` 和 `qwen3-vl-plus`。
- 对比模型输出与预期标题栏屏幕位置。
- 记录图号读取是否受高质量输入影响。

约束：

- 不覆盖当前固定审核入口。
- 不发布新的固定审核入口。
- 不生成正式旋正 PDF。
- 不重命名 PDF。
- 不把 `local_data/` 输出纳入 Git。

回滚准备：

- 实现前提交本轮计划、RPD 和 TODO，作为多位置复测实现前的回滚点。

执行结果：

- 已提交复测前回滚点：
  - `988dc7d docs: plan aliyun vlm title block position probe`
- 新增受控图片生成脚本：
  - `scripts/experiments/build_aliyun_vlm_position_probe_images.py`
- 已以用户确认的 `js2207_page_001.png` 为基准生成四张受控位置图片：
  - `top_right`
  - `bottom_right`
  - `bottom_left`
  - `top_left`
- 已使用高质量参数联网复测：
  - `--max-image-long-side 3200`
  - `--jpeg-quality 95`
  - 页数：4。
  - 模型：`qwen3-vl-flash`、`qwen3-vl-plus`。
  - 请求数：8。
  - HTTP 200：8。
  - 模型内容 JSON 解析通过：8。
  - 业务 schema 校验通过：8。
  - 模型级 `needs_review`：0。
  - 双模型对比 `needs_review`：4。
- 输出位于：
  - `local_data/aliyun_vlm_position_probe/position_probe_images/`
  - `local_data/aliyun_vlm_position_probe/position_probe_manifest.csv`
  - `local_data/aliyun_vlm_position_probe/vlm_decisions.csv`
  - `local_data/aliyun_vlm_position_probe/dual_model_comparison.csv`
  - `local_data/aliyun_vlm_position_probe/needs_review.csv`
  - `local_data/aliyun_vlm_position_probe/vlm_call_summary.json`

复测观察：

| 受控位置 | `qwen3-vl-flash` 标题栏位置 | `qwen3-vl-plus` 标题栏位置 | 标题栏位置结论 | 旋转字段结论 | 图号结论 |
| --- | --- | --- | --- | --- | --- |
| `top_right` | `bottom_right` | `bottom_right` | 两模型均误判 | 两模型均不符合项目规则 | 两模型均读到 `JS2207 00-10` |
| `bottom_right` | `bottom_right` | `bottom_right` | 两模型均正确 | 两模型均正确 | 仅分隔符差异 |
| `bottom_left` | `bottom_left` | `bottom_left` | 两模型均正确 | Flash 正确，Plus 错误 | 两模型一致 |
| `top_left` | `top_left` | `top_left` | 两模型均正确 | 两模型均错误 | 仅分隔符差异 |

图片质量观察：

- 高质量复测中，上传 JPEG 未发生缩放：
  - 原始长边约 `1754` 像素。
  - 准备后尺寸仍为原始尺寸。
  - `jpeg_quality=95`。
  - 单张 JPEG 约 `241KB` 到 `243KB`。
  - Base64 data URL 约 `321KB` 到 `323KB`。
- 用户指出首轮第 1 页图号两个模型都算正确；高质量复测中也未出现首轮 Flash 多读 `2` 的问题。
- 当前不稳定的主要来源不是图片压缩，而是模型对“标题栏位置”和“当前旋转角度”任务定义的理解：
  - `top_right` 容易被两个模型解释成正确阅读语义下的 `bottom_right`。
  - `current_clockwise_degrees` 容易被模型理解为“是否已经可阅读”，而不是项目定义的屏幕坐标推导角度。

当前判断：

- VLM 不宜直接决定 `current_clockwise_degrees` 和 `correction_clockwise_degrees`。
- 更稳定的策略是让 VLM 只判断“当前屏幕坐标下标题栏位置”，并由程序按项目规则推导角度：
  - `bottom_right` / `bottom` -> `0`
  - `bottom_left` / `left` -> `90`
  - `top_left` / `top` -> `180`
  - `top_right` / `right` -> `270`
- 对图号读取，应保留高质量局部图策略：
  - 整页图用于标题栏位置判断。
  - 标题栏 crop 或高质量局部图用于图号读取。
- 后续 prompt 需要明确禁止模型按“正确阅读方向”重解释位置，必须按原始图片屏幕坐标判断。

## VLM 只判断标题栏当前位置设计决策

用户确认旋转判断应拆解为两个步骤：

1. 判断标题栏当前位置。
2. 根据标题栏当前位置推断图纸被旋转的角度。

设计依据：

- 机械制图规则中，标题栏在正确阅读方向下位于图纸右下角。
- 因此标题栏当前位置一旦确定，图纸旋转角度就是确定性结果。
- VLM 直接输出旋转角度容易混淆“当前屏幕坐标”“正确阅读方向”和“是否可阅读”等语义。
- 项目后续只需要准确得到标题栏当前位置；角度由程序推导。

计划：

- 见 `docs/plans/078-vlm-title-block-position-only-plan.md`。

本轮目标：

- 修改阿里云 VLM prompt/schema，不再要求模型输出角度。
- 程序根据 `title_block_position` 派生：
  - `derived_current_clockwise_degrees`
  - `derived_correction_clockwise_degrees`
- 双模型对比以标题栏位置和图号为主，不再比较模型自由生成的旋转角度。

位置到角度规则：

| 标题栏当前位置 | 当前图纸已顺时针旋转角度 | 建议顺时针校正角度 |
| --- | --- | --- |
| `bottom_right` / `bottom` | 0 | 0 |
| `bottom_left` / `left` | 90 | 270 |
| `top_left` / `top` | 180 | 180 |
| `top_right` / `right` | 270 | 90 |
| `unknown` | 空 | 空 |

回滚准备：

- 实现前提交本轮计划、RPD 和 TODO，作为标题栏位置优先重构前回滚点。

执行结果：

- 已提交重构前回滚点：
  - `5aa30e2 docs: plan vlm title block position only flow`
- 已修改阿里云 VLM prompt/schema：
  - 不再要求模型输出 `current_clockwise_degrees`。
  - 不再要求模型输出 `correction_clockwise_degrees`。
  - 明确要求标题栏位置必须按当前原始图片屏幕坐标判断。
  - 明确禁止模型把图片想象旋转到正确阅读方向后再判断位置。
- 已修改联网烟测脚本：
  - 模型输出只校验 `title_block_position`、图号和质量门字段。
  - 程序根据 `title_block_position` 派生 `derived_current_clockwise_degrees` 和 `derived_correction_clockwise_degrees`。
  - 双模型对比不再比较模型自由生成的旋转角度，只比较标题栏位置和图号。
- 已执行 dry-run：
  - 命令：`python -m scripts.vlm.run_aliyun_vlm_mvp_smoke --dry-run --input-image-dir local_data\aliyun_vlm_position_probe\position_probe_images --limit-pages 1 --output-dir local_data\aliyun_vlm_position_only_dry_run`
  - 请求数：2。
  - `network_call_executed=false`。
- 已执行受控多位置联网复测：
  - 命令：`python -m scripts.vlm.run_aliyun_vlm_mvp_smoke --input-image-dir local_data\aliyun_vlm_position_probe\position_probe_images --output-dir local_data\aliyun_vlm_position_only_probe --limit-pages 4 --max-image-long-side 3200 --jpeg-quality 95 --timeout-seconds 120 --retries 0`
  - 页数：4。
  - 模型：`qwen3-vl-flash`、`qwen3-vl-plus`。
  - 请求数：8。
  - HTTP 200：8。
  - 模型内容 JSON 解析通过：8。
  - 业务 schema 校验通过：8。
  - 模型级 `needs_review`：0。
  - 双模型对比 `needs_review`：1。

位置优先复测观察：

| 受控位置 | Flash 位置 | Plus 位置 | 派生当前旋转角 | 派生校正角 | 结论 |
| --- | --- | --- | --- | --- | --- |
| `top_right` | `top_right` | `top_right` | 270 | 90 | 正确 |
| `bottom_right` | `bottom_right` | `bottom_right` | 0 | 0 | 正确 |
| `bottom_left` | `bottom_left` | `bottom_left` | 90 | 270 | 正确 |
| `top_left` | `top_left` | `top_left` | 180 | 180 | 正确 |

唯一双模型复核项：

- `bottom_right` 样本图号分隔符不同：
  - Flash：`JS2207-00-10`
  - Plus：`JS2207 00-10`
- 该复核项不影响标题栏位置和旋转角度。

当前判断：

- 用户提出的“两步法”成立，并且受控验证显著优于让 VLM 直接输出角度。
- 后续主链路应固定为：
  1. VLM 判断标题栏当前位置。
  2. 程序按机械制图规则派生旋转角度。
  3. 图号读取单独走规范化和人工复核质量门。
- 后续扩大样本时，评价指标应优先看 `title_block_position` 是否正确，而不是模型自然语言或自由角度字段。

## JS2207 真实 PDF 原向 VLM 标题栏位置审核需求

用户要求对真实图纸包执行测试：

```text
local_data/source_pdfs/JS2207-00-00升降平台.pdf
```

明确要求：

- 不准自行旋转图纸。
- 先将 PDF 拆成一张张单独图纸。
- 直接测试原始方向图纸。
- 不压缩图片。
- 只判断标题栏当前位置。
- 用 Excel 表格提交模型判断结果供审核。
- 生成单个 HTML 文件，按图片排列顺序展示，方便对照审查。

计划：

- 见 `docs/plans/079-js2207-real-pdf-vlm-title-block-review-plan.md`。

本轮目标：

- 从源 PDF 重新拆分 29 个单页 PDF。
- 原向渲染 PNG，不旋转、不压缩、不裁切。
- 使用 PNG 原图 Base64 data URL 直接调用阿里云 VLM。
- VLM 只判断当前屏幕坐标下标题栏位置。
- 程序保留派生角度，但审核表重点展示标题栏位置。
- 生成 Excel、CSV 和单页 HTML 审核入口。
- 审核入口统一发布到 `local_data/review_inbox/current/`。

约束：

- 不生成正式旋正 PDF。
- 不重命名单页 PDF。
- 不使用受控旋转样本。
- 不把 `local_data/` 输出纳入 Git。
- 若 PNG 原图请求体过大或超时，应记录失败并进入审核，不得自动改用压缩图替代本轮结论。

回滚准备：

- 实现前提交本轮计划、RPD 和 TODO，作为真实 PDF VLM 批量测试实现前回滚点。

执行结果：

- 已提交实现前回滚点：
  - `a991ea8 docs: plan js2207 real pdf vlm review`
- 新增真实 PDF VLM 标题栏位置审核脚本：
  - `scripts/experiments/build_js2207_real_vlm_title_block_review.py`
- 已从源 PDF 重新拆分单页图纸：
  - 源 PDF：`local_data/source_pdfs/JS2207-00-00升降平台.pdf`
  - 单页 PDF：29 个。
- 已原向渲染 PNG：
  - PNG：29 张。
  - 渲染 DPI：150。
  - 不旋转。
  - 不压缩。
  - 不裁切。
- 已使用 PNG 原图 Base64 data URL 联网调用阿里云 VLM：
  - 模型：`qwen3-vl-flash`、`qwen3-vl-plus`。
  - 请求数：58。
  - 原始响应数：58。
  - 模型级 `needs_review`：0。
  - 双模型对比 `needs_review`：10。
  - `compressed=false`。
  - `no_resize=true`。
  - `modified_pdf=false`。
  - `renamed_pdf=false`。
- 已归档旧固定审核入口：
  - `local_data/review_inbox/archive/current_archived_before_js2207_real_vlm_20260702_151138`
- 已发布新固定审核入口：
  - `local_data/review_inbox/current/README.md`
  - `local_data/review_inbox/current/js2207_real_vlm_title_block_review/review_index.html`
  - `local_data/review_inbox/current/js2207_real_vlm_title_block_review/vlm_title_block_review.xlsx`
  - `local_data/review_inbox/current/js2207_real_vlm_title_block_review/vlm_title_block_review.csv`
  - `local_data/review_inbox/current/js2207_real_vlm_title_block_review/review_manifest.json`
  - `local_data/review_inbox/current/js2207_real_vlm_title_block_review/images/`
- 审核入口内容：
  - HTML 单文件按页码顺序展示 29 张原向 PNG。
  - 每页下方展示两个模型的标题栏位置和程序派生角度。
  - Excel/CSV 每页每模型一行，共 58 行，按页码和模型顺序排列。
  - 人工填写字段只保留 `位置是否正确`、`正确标题栏位置` 和 `备注`。

当前待用户审核：

- 打开 `local_data/review_inbox/current/js2207_real_vlm_title_block_review/review_index.html` 对照图片。
- 在 `local_data/review_inbox/current/js2207_real_vlm_title_block_review/vlm_title_block_review.xlsx` 中填写审核结果。

## JS2207 真实 VLM Excel 审核结果归档需求

用户已完成 JS2207 真实 PDF 原向 VLM 标题栏位置审核，并说明：

- 已填写 Excel 表格。
- CSV 表格没有填写。

本轮判断：

- Excel 是唯一人工审核结果来源。
- CSV 只能作为机器生成参考，不得读取为人工填写结果。
- 归档时必须保留用户填写的 Excel 原件。

计划：

- 见 `docs/plans/080-js2207-real-vlm-excel-review-archive-plan.md`。

本轮目标：

- 读取 `local_data/review_inbox/current/js2207_real_vlm_title_block_review/vlm_title_block_review.xlsx`。
- 解析人工填写字段：
  - `位置是否正确`
  - `正确标题栏位置`
  - `备注`
- 生成机器摘要、人工摘要和可追溯 JSON/CSV。
- 归档当前审核入口。
- 重置 `local_data/review_inbox/current/` 为无待审核任务。

约束：

- 不读取 CSV 作为人工审核结果。
- 不修改用户填写的 Excel。
- 不生成正式旋正 PDF。
- 不重命名 PDF。
- 不把 `local_data/` 输出纳入 Git。

回滚准备：

- 实现前提交本轮计划、RPD 和 TODO，作为 Excel 审核归档实现前回滚点。
- 已提交回滚点：`e0d4823 docs: plan js2207 vlm excel review archive`。

JS2207 真实 VLM Excel 审核结果归档执行结果：

- 新增归档脚本：
  - `scripts/experiments/archive_js2207_real_vlm_excel_review.py`
- 输入来源：
  - 仅读取用户填写的 Excel：`vlm_title_block_review.xlsx`。
  - CSV 未作为人工审核来源。
- 脚本防护：
  - 默认要求解析到 58 行审核记录。
  - 默认要求至少存在人工填写内容，避免空表误归档。
  - 不修改用户填写的 Excel。
  - 不生成正式旋正 PDF。
  - 不重命名 PDF。
- 已归档当前固定审核入口：
  - `local_data/review_inbox/archive/js2207_real_vlm_title_block_review_20260702_154249_reviewed`
- 用户填写的 Excel 原件归档位置：
  - `local_data/review_inbox/archive/js2207_real_vlm_title_block_review_20260702_154249_reviewed/js2207_real_vlm_title_block_review/vlm_title_block_review.xlsx`
- 已重置固定审核入口：
  - `local_data/review_inbox/current/README.md`
  - 当前没有待用户审核、填写或标注的文件。
- 本地摘要输出：
  - `local_data/js2207_real_vlm_title_block_review/excel_review_rows.json`
  - `local_data/js2207_real_vlm_title_block_review/excel_review_rows.csv`
  - `local_data/js2207_real_vlm_title_block_review/excel_review_summary.json`
  - `local_data/js2207_real_vlm_title_block_review/excel_review_summary.csv`
  - `local_data/js2207_real_vlm_title_block_review/human_summary.md`
- 审核统计：
  - Excel 记录数：58。
  - 已填写记录数：58。
  - 空白记录数：0。
  - 人工判断分布：正确 24，错误 34。
  - 需关注页数：18。
  - 不确定记录数：0。

本轮关键发现：

- `qwen3-vl-flash` 和 `qwen3-vl-plus` 在 JS2207 真实图纸包上仍存在大量标题栏位置误判，不能直接进入正式旋正或正式重命名。
- 真实图纸里存在“只有零件表格、没有标题栏”的页，VLM 会把零件表格误判为标题栏，后续 schema 需要支持 `no_title_block` 或等价异常状态。
- 四角枚举不足以表达本轮人工反馈，用户多次填写正确标题栏位置为 `上方`、`下方`、`左下方`。后续标题栏位置 schema 需要从四角分类扩展为边/区域分类，并保留由位置推导旋转角度的确定性规则。
- 部分人工备注显示“模型位置字段错，但程序派生旋转角度仍正确”，说明下一轮分析应区分“标题栏精确位置正确性”和“由该位置推导出的旋转角度正确性”，不能只看单一位置枚举准确率。

## 竖向图纸底边满宽标题栏规则固化需求

用户补充说明：部分图纸是按纸张竖向绘制，标题栏在下方刚好占满图纸宽度，因此在 JS2207 Excel 审核中多处填写为 `下方`。

本轮判断：

- `下方` 是合法标题栏位置，不是人工填写噪声。
- 对竖向图纸，标题栏可能横跨底边，而不是集中在右下角。
- 后续 VLM prompt/schema 和本地位置映射都不应强制使用四角枚举。

计划：

- 见 `docs/plans/081-vertical-sheet-bottom-edge-title-block-rule-plan.md`。

约束：

- 本轮只固化规则和文档。
- 不重新调用 VLM。
- 不修改已归档审核结果。
- 不生成正式旋正 PDF。
- 不重命名 PDF。

回滚准备：

- 实现前提交本轮计划、RPD 和 TODO，作为规则固化前回滚点。
- 已提交回滚点：`35120c9 docs: plan vertical sheet title block rule`。

竖向图纸底边满宽标题栏规则固化结果：

- 已更新长期规则：
  - `rules/mechanical-drawing-rotation.md`
- 规则明确：
  - 正确方向下标题栏可以位于页面下方、底边满宽区域或右下方。
  - 竖向纸张绘制的机械图纸中，标题栏可能位于下方并刚好占满图纸宽度。
  - 这类标题栏应判为下方或底边标题栏，不应强行归入 `bottom_left` 或 `bottom_right`。
  - 后续自动化输出应支持边位置，例如 `bottom_edge`、`top_edge`、`left_edge`、`right_edge`。
  - 对没有可确认标题栏的页面，应支持 `no_title_block`。
- 本轮仍只修改规则和文档：
  - 未重新调用 VLM。
  - 未修改已归档 Excel 或本地审核结果。
  - 未生成正式旋正 PDF。
  - 未重命名 PDF。

## JS2207 VLM 提示词调整复测需求

用户要求：根据已填写的 Excel 表格和刚补充的竖向图纸底边满宽标题栏信息，调整提示词后再做一次实验，争取提高正确率。

输入依据：

- 已归档 Excel 审核结果：
  - `local_data/js2207_real_vlm_title_block_review/excel_review_rows.json`
  - `local_data/js2207_real_vlm_title_block_review/excel_review_summary.json`
- 用户补充：
  - 部分图纸按纸张竖向绘制。
  - 标题栏在下方并刚好占满图纸宽度。
  - Excel 中填写的 `下方` 是合法位置。
- 长期规则：
  - `rules/mechanical-drawing-rotation.md`

计划：

- 见 `docs/plans/082-js2207-vlm-prompt-retest-plan.md`。

本轮目标：

- 调整 prompt/schema，支持边位置和 `no_title_block`。
- 明确零件表格、明细表、技术要求表不得误判为标题栏。
- 使用同一份 JS2207 原向 PNG，不旋转、不压缩，重跑 `qwen3-vl-flash` 与 `qwen3-vl-plus`。
- 用已填写 Excel 自动评估新版结果，并与旧结果 24/58 正确作比较。

约束：

- 不修改已归档 Excel。
- 不读取 CSV 作为人工真值。
- 不生成正式旋正 PDF。
- 不重命名 PDF。
- 不对 JS2207 页码写特判。

回滚准备：

- 实现前提交本轮计划、RPD 和 TODO，作为 prompt 复测实现前回滚点。
- 已提交回滚点：`006a0dd docs: plan js2207 vlm prompt retest`。

JS2207 VLM 提示词调整复测执行结果：

- 已调整 VLM prompt/schema：
  - 新增边位置：`bottom_edge`、`top_edge`、`left_edge`、`right_edge`。
  - 新增无标题栏状态：`no_title_block`。
  - 明确竖向图纸底边满宽标题栏应输出 `bottom_edge`。
  - 明确零件表格、明细表、技术要求表、局部说明表不能作为标题栏。
- 已扩展本地解析与派生映射：
  - `bottom_edge` -> 当前旋转 0 度。
  - `top_edge` -> 当前旋转 180 度。
  - `left_edge` -> 当前旋转 90 度。
  - `right_edge` -> 当前旋转 270 度。
  - `no_title_block` 不派生旋转角度，进入复核/异常状态。
- 已新增自动评估脚本：
  - `scripts/experiments/evaluate_js2207_vlm_prompt_retest.py`
  - 使用已归档 Excel 审核结果作为真值。
  - 不读取 CSV 作为人工真值。
- 复测输入：
  - 源 PDF：`local_data/source_pdfs/JS2207-00-00升降平台.pdf`
  - 图片：重新拆分并原向渲染 PNG。
  - 图片策略：PNG 原图，不旋转、不压缩、不 resize。
  - 模型：`qwen3-vl-flash`、`qwen3-vl-plus`。
- 复测输出目录：
  - `local_data/js2207_real_pdf_vlm_title_block_prompt_retest/`
- 复测运行结果：
  - 页数：29。
  - 请求数：58。
  - 原始响应数：58。
  - 模型级 `needs_review`：2。
  - 双模型对比 `needs_review`：18。
  - `compressed=false`。
  - `no_resize=true`。
  - `modified_pdf=false`。
  - `renamed_pdf=false`。
- 自动评估输出：
  - `local_data/js2207_real_pdf_vlm_title_block_prompt_retest/evaluation/prompt_retest_evaluation_rows.json`
  - `local_data/js2207_real_pdf_vlm_title_block_prompt_retest/evaluation/prompt_retest_evaluation_rows.csv`
  - `local_data/js2207_real_pdf_vlm_title_block_prompt_retest/evaluation/prompt_retest_truth_by_page.json`
  - `local_data/js2207_real_pdf_vlm_title_block_prompt_retest/evaluation/prompt_retest_evaluation_summary.json`
  - `local_data/js2207_real_pdf_vlm_title_block_prompt_retest/evaluation/prompt_retest_evaluation_summary.md`
- 新旧对比：
  - 旧版精确位置正确：24/58，正确率 0.4138。
  - 新版精确位置正确：38/58，正确率 0.6552。
  - 精确正确数增加：14。
  - 新版旋转分组正确：49/58，正确率 0.8448。
- 分模型结果：
  - `qwen3-vl-flash`：精确位置 16/29，旋转分组 25/29。
  - `qwen3-vl-plus`：精确位置 22/29，旋转分组 24/29。

本轮结论：

- 调整 prompt/schema 后正确率明显提高，主要收益来自将竖向图纸底边满宽标题栏识别为 `bottom_edge`。
- `qwen3-vl-plus` 当前更适合作为标题栏位置主判断模型；`qwen3-vl-flash` 仍倾向将 `top_edge` 误报为 `top_left`。
- 仍未稳定解决“无标题栏页”：第 3 页两模型仍输出 `bottom_edge`，其中 Plus 虽然在原因中指出未识别到标准标题栏，但结构化位置字段没有返回 `no_title_block`。
- 后续若继续提升，应重点强化两类约束：
  - 当证据判断“未识别到标准标题栏”时，结构化 `title_block_position` 必须为 `no_title_block`。
  - 顶边横向标题栏应返回 `top_edge`，不要按左端位置误报为 `top_left`。
- 本轮未发布新的固定审核入口，未修改已归档 Excel，未生成正式旋正 PDF，未重命名 PDF。

## JS2207 VLM Prompt 复测人工审核包发布需求

用户要求对 JS2207 VLM prompt 复测结果进行人工审核。

计划：

- 见 `docs/plans/083-js2207-vlm-prompt-retest-review-pack-plan.md`。

目标：

- 基于已有复测结果发布人工审核包到固定入口：
  - `local_data/review_inbox/current/`
- 审核内容只让用户判断新版模型标题栏位置是否正确。
- HTML 按页码顺序展示原向图纸，并在同一页展示两个模型判断，方便对照。
- Excel 按页码和模型顺序排列，共 58 行。

约束：

- 不重新调用 VLM。
- 不修改 prompt/schema。
- 不修改已归档 Excel。
- 不生成正式旋正 PDF。
- 不重命名 PDF。
- 不提交 `local_data/` 输出。

回滚准备：

- 实现前提交本轮计划、RPD 和 TODO，作为审核包发布前回滚点。
- 已提交回滚点：`d4d63f5 docs: plan js2207 prompt retest review pack`。

JS2207 VLM Prompt 复测人工审核包发布结果：

- 新增发布脚本：
  - `scripts/experiments/publish_js2207_vlm_prompt_retest_review.py`
- 已发布固定审核入口：
  - `local_data/review_inbox/current/README.md`
  - `local_data/review_inbox/current/js2207_vlm_prompt_retest_review/review_index.html`
  - `local_data/review_inbox/current/js2207_vlm_prompt_retest_review/vlm_prompt_retest_review.xlsx`
  - `local_data/review_inbox/current/js2207_vlm_prompt_retest_review/vlm_prompt_retest_review.csv`
  - `local_data/review_inbox/current/js2207_vlm_prompt_retest_review/review_manifest.json`
  - `local_data/review_inbox/current/js2207_vlm_prompt_retest_review/images/`
- 发布内容：
  - 页数：29。
  - Excel 记录数：58。
  - 图片副本数：29。
  - HTML 按页码顺序展示原向 PNG，并并列展示两个模型新版标题栏位置。
  - Excel 人工填写字段只保留 `位置是否正确`、`正确标题栏位置` 和 `备注`。
- 发布前固定入口仅有无待审核任务 README，因此未产生额外归档：
  - `archived_previous_current=null`
- 验证结果：
  - HTML、Excel、CSV、manifest 已生成。
  - 图片副本均在 `current` 内。
  - 未重新联网。
  - 未生成正式旋正 PDF。
  - 未重命名 PDF。

当前待用户审核：

- 打开 `local_data/review_inbox/current/js2207_vlm_prompt_retest_review/review_index.html` 对照图片。
- 在 `local_data/review_inbox/current/js2207_vlm_prompt_retest_review/vlm_prompt_retest_review.xlsx` 中填写审核结果。

## VLM 标题栏提示词泛化盲测需求

用户质疑当前 VLM prompt 是否对 JS2207 图片做了特化处理，是否忽略通用性。该质疑成立，因此下一步需要使用非 JS2207 PDF 做盲测，而不是继续只在 JS2207 上调 prompt。

计划：

- 见 `docs/plans/084-vlm-title-block-generalization-blind-test-plan.md`。

本轮输入：

- `local_data/source_pdfs/YKJ125-00-00-2525铁屑压块机生产图（250911章）解密.pdf`

本轮目标：

- 不修改当前 prompt/schema。
- 不对 YKJ125 页码、图号样式或模板写特判。
- 按 PDF 顺序拆分并原向渲染 PNG。
- 使用 `qwen3-vl-flash` 与 `qwen3-vl-plus` 判断标题栏当前位置。
- 图片不旋转、不 resize、不做有损 JPEG 压缩。
- 程序只根据标题栏当前位置本地派生旋转角度。
- 发布低噪声 HTML/Excel 审核包到固定入口，等待人工审核。

盲测边界：

- YKJ125 是非 JS2207 图纸包，但属于项目早期样本来源，不能代表跨企业、跨模板、跨行业全面泛化。
- 本轮只验证当前 prompt 是否明显依赖 JS2207 局部特征。
- 本轮不根据模型输出继续改 prompt，必须先人工审核。

约束：

- 当前固定入口中仍有 JS2207 prompt 复测审核包，发布 YKJ125 入口前必须先归档并记录归档位置。
- 不读取或打印 `.env/.env` 中的 API Key。
- 不生成正式旋正 PDF。
- 不重命名 PDF。
- 不提交 `local_data/` 输出。

回滚准备：

- 实现前提交本轮计划、RPD 和 TODO，作为盲测执行前回滚点。
- 已提交回滚点：`d7bdd73 docs: plan vlm title block blind test`。

通用盲测脚本实现：

- 新增脚本：
  - `scripts/experiments/build_vlm_title_block_blind_review.py`
- 脚本行为：
  - 支持任意源 PDF、输出目录、审核入口和样本前缀参数。
  - 拆分 PDF 为单页 PDF，并用 Ghostscript 原向渲染 PNG。
  - 使用当前 VLM prompt/schema，不在脚本内改写规则。
  - 以 PNG data URL 直接调用 `qwen3-vl-flash` 和 `qwen3-vl-plus`。
  - 输出请求、响应、结构化决策、双模型对比、HTML 和 Excel 审核包。
  - 发布前自动归档 `local_data/review_inbox/current/` 中已有审核入口。
  - 不生成正式旋正 PDF，不重命名 PDF。

YKJ125 VLM 标题栏泛化盲测运行结果：

- 输入：
  - `local_data/source_pdfs/YKJ125-00-00-2525铁屑压块机生产图（250911章）解密.pdf`
- 页数：63。
- 模型：
  - `qwen3-vl-flash`
  - `qwen3-vl-plus`
- 请求数：126。
- 图片策略：
  - 原向 PNG。
  - 不旋转。
  - 不 resize。
  - 不做有损 JPEG 压缩。
- 输出目录：
  - `local_data/vlm_title_block_generalization_blind_ykj125/`
- 当前运行状态：
  - API 成功：124/126。
  - 超时：2/126。
  - 需要补跑：
    - 第 26 页 `qwen3-vl-plus`
    - 第 36 页 `qwen3-vl-flash`
  - 有效结构化解析：124/126。
  - 模型位置分布显示双模型分歧较多，尤其 `qwen3-vl-flash` 倾向输出角位置，`qwen3-vl-plus` 更常输出边位置。
- 当前审核入口已生成但暂不交付为最终审核包，原因是 Excel 中仍有 2 条超时空结果。

补跑要求：

- 只补跑超时的模型-页码组合。
- 不修改 prompt/schema。
- 不重跑全部 126 条。
- 补跑成功后重建决策、双模型对比和审核包。
- 不生成正式旋正 PDF，不重命名 PDF。

YKJ125 VLM 标题栏泛化盲测补跑和发布结果：

- 新增补跑脚本：
  - `scripts/experiments/retry_vlm_title_block_blind_failures.py`
- 已只补跑失败项：
  - 第 26 页 `qwen3-vl-plus`
  - 第 36 页 `qwen3-vl-flash`
- 补跑后结果：
  - API 成功：126/126。
  - 结构化解析成功：126/126。
  - schema 校验成功：126/126。
  - 模型级 `needs_review`：1/126。
  - 双模型对比 `needs_review`：61/63。
  - 标题栏位置分歧：50/63 页。
- 标题栏位置分布：
  - `top_right`：34。
  - `top_edge`：30。
  - `top_left`：27。
  - `bottom_right`：18。
  - `right_edge`：14。
  - `bottom_edge`：3。
- 分模型位置倾向：
  - `qwen3-vl-flash`：`top_left` 27、`bottom_right` 17、`top_right` 17、`bottom_edge` 1、`right_edge` 1。
  - `qwen3-vl-plus`：`top_edge` 30、`top_right` 17、`right_edge` 13、`bottom_edge` 2、`bottom_right` 1。
- 固定审核入口：
  - `local_data/review_inbox/current/README.md`
  - `local_data/review_inbox/current/ykj125_vlm_title_block_blind_review/review_index.html`
  - `local_data/review_inbox/current/ykj125_vlm_title_block_blind_review/vlm_title_block_blind_review.xlsx`
  - `local_data/review_inbox/current/ykj125_vlm_title_block_blind_review/vlm_title_block_blind_review.csv`
  - `local_data/review_inbox/current/ykj125_vlm_title_block_blind_review/review_manifest.json`
  - `local_data/review_inbox/current/ykj125_vlm_title_block_blind_review/images/`
- 审核包验证：
  - 页数：63。
  - Excel 数据行：126。
  - 图片副本：63。
  - HTML、Excel、CSV、manifest 均已生成。
  - 图片副本均位于 `current` 内。
  - 未生成正式旋正 PDF。
  - 未重命名 PDF。
- 固定入口归档记录：
  - 本轮最终发布前归档上一版 YKJ125 入口到 `local_data/review_inbox/archive/current_archived_before_ykj125_vlm_title_block_blind_review_20260702_183937`
  - 早前发布 YKJ125 入口前已归档 JS2207 prompt 复测入口到 `local_data/review_inbox/archive/current_archived_before_ykj125_vlm_title_block_blind_review_20260702_180142`

当前待用户审核：

- 打开 `local_data/review_inbox/current/ykj125_vlm_title_block_blind_review/review_index.html` 对照图片。
- 在 `local_data/review_inbox/current/ykj125_vlm_title_block_blind_review/vlm_title_block_blind_review.xlsx` 中填写 `位置是否正确`、必要时填写 `正确标题栏位置` 和 `备注`。

## 阿里模型参数与准确性调研需求

用户补充：`qwen3-vl-flash` 将在 9 月下线，因此后续没有必要继续作为常规模型使用。当前 `qwen3-vl-plus` 的设计应保留下来。

用户希望先调研以下模型和参数，再决定下一轮测试：

- `qwen3.7-max`
- `qwen3.5-OCR`
- `qwenVL-OCR-Latest`
- `qwen3-vl-plus` 的 `thinking_budget`
- `temperature`
- `top_p`

计划：

- 见 `docs/plans/085-aliyun-model-parameter-accuracy-research-plan.md`。

本轮目标：

- 核对阿里官方文档，确认模型名、接口形态和是否支持图像输入。
- 调研 `temperature`、`top_p`、`thinking_budget` 的可配置性和准确性建议。
- 区分标题栏位置判断模型与图号 OCR 模型。
- 给出下一轮小样本测试的模型和参数建议。

约束：

- 本轮只调研，不批量调用模型。
- 不修改 prompt/schema。
- 不上传图纸。
- 不读取或打印 `.env/.env` 中的 API Key。
- 不生成正式旋正 PDF。
- 不重命名 PDF。

回滚准备：

- 调研前提交本轮计划、RPD 和 TODO，作为后续文档和脚本修改前回滚点。

调研结论：

- 资料索引：
  - `references/aliyun-model-parameter-accuracy/README.md`
- 调研笔记：
  - `docs/research/2026-07-02-aliyun-model-parameter-accuracy-research.md`
- `qwen3-vl-flash` 不再进入常规测试设计；保留当前 `qwen3-vl-plus` 主线。
- `qwen3.7-max` 的官方视觉模型 ID 为 `qwen3.7-max-2026-06-08`，支持文本、图像和视频输入，但具体表格中结构化输出列为 `--`。它可以作为强推理探索模型测试，但不应直接替代当前 JSON/schema 主流程。
- 若目标是增强标题栏位置判断且保持结构化输出，官方更推荐从 `qwen3.7-plus` 开始；`qwen3.7-plus` 更适合作为下一轮对照候选。
- 官方 Qwen-OCR 文档已确认 `qwen3.5-ocr`；用户写法 `qwenVL-OCR-Latest` 应按官方模型 ID 写为 `qwen-vl-ocr-latest`。
- `qwen3.5-ocr` 和 `qwen-vl-ocr-latest` 适合作为标题栏 crop 或图号区域 crop 的 OCR 候选，不应混入整页标题栏位置主判断。
- Qwen-OCR 不支持自定义 System Message；所有 OCR 指令必须放入 User Message。OpenAI 兼容模式不能直接使用图像旋转矫正和内置 OCR 任务等高级参数，若需要完整 OCR 高级能力，应另评估 DashScope SDK 路线。
- 参数推荐：
  - 确定性分类和 OCR 字段提取默认 `temperature=0`。
  - 不额外设置 `top_p`，因为官方建议 `temperature` 与 `top_p` 通常只设置一个。
  - 当前主线继续使用 `qwen3-vl-plus` 非思考模式，`enable_thinking=false`。
  - `thinking_budget` 只能作为受控消融实验，与 `enable_thinking=true` 配合使用；通过 OpenAI SDK 调用时放入 `extra_body`。它可能提高复杂推理，也可能增加延迟、费用和 JSON 不稳定风险。
- 下一轮标题栏位置测试建议：
  - `qwen3-vl-plus`：`temperature=0`，`enable_thinking=false`，不设 `top_p`。
  - `qwen3-vl-plus` 思考预算消融：`temperature=0`，`enable_thinking=true`，`thinking_budget=512`，必要时再加 `1024`。
  - `qwen3.7-plus`：`temperature=0`，`enable_thinking=false`，不设 `top_p`。
  - `qwen3.7-max-2026-06-08`：作为用户指定探索对照，同样记录 JSON 解析和 schema 成功率。
- 下一轮 OCR 测试应另开任务：
  - `qwen3.5-ocr` vs `qwen-vl-ocr-latest`。
  - 输入为标题栏 crop 或图号 crop，不使用整页位置判断 prompt。
  - 输出进入人工审核，不直接重命名 PDF。

## VLM 标题栏错题集优先模型测试需求

用户提出下一步测试节奏：

1. 先测试上一轮中识别出错的部分。
2. 发布实际效果给用户人工审核。
3. 如果效果不错，再扩大测试，把所有图纸都识别一次。

该策略成立，并应作为下一轮执行边界。原因：

- 直接全量调用会增加费用和审核负担，也会把错误定位变得不清楚。
- 错题集能优先验证新模型/新参数是否解决真实失败模式。
- 人工审核通过前，不应把新模型输出作为全量处理依据。

计划：

- 见 `docs/plans/086-vlm-title-block-error-first-model-test-plan.md`。

本轮目标：

- 从上一轮 YKJ125 人工审核完成的 `vlm_title_block_blind_review.xlsx` 中读取 `qwen3-vl-plus` 错误页和存疑页。
- 构建最多 12 到 20 页的错题集优先测试集。
- 使用以下标题栏位置候选重新测试：
  - `qwen3-vl-plus`：`temperature=0`，`enable_thinking=false`。
  - `qwen3-vl-plus`：`temperature=0`，`enable_thinking=true`，`thinking_budget=512`。
  - `qwen3.7-plus`：`temperature=0`，`enable_thinking=false`。
  - `qwen3.7-max-2026-06-08`：`temperature=0`，`enable_thinking=false`。
- 不设置 `top_p`。
- 不纳入 `qwen3-vl-flash`。
- 发布 HTML/Excel 审核包到固定入口，等待用户审核。

约束：

- 不直接跑全量 63 页。
- 不测试 `qwen3.5-ocr` 或 `qwen-vl-ocr-latest`；OCR 后续另开 crop/图号任务。
- 不旋转图纸，不生成正式旋正 PDF，不重命名 PDF。
- 不读取或打印 `.env/.env` 中的 API Key。
- 不把本轮错题集结果直接写入 ground truth。
- 不根据 YKJ125 错题集写特化 prompt。

回滚准备：

- 实现前提交本轮计划、RPD 和 TODO，作为后续脚本修改和模型调用前回滚点。
- 已提交回滚点：`17bbe43 docs: plan vlm error-first model test`。

VLM 标题栏错题集优先模型测试执行结果：

- 新增脚本：
  - `scripts/experiments/build_vlm_title_block_error_first_review.py`
- 输入人工审核表：
  - `local_data/review_inbox/archive/current_archived_before_ykj125_vlm_title_block_error_first_review_20260702_201728/ykj125_vlm_title_block_blind_review/vlm_title_block_blind_review.xlsx`
- 选择规则：
  - 读取上一轮 `qwen3-vl-plus` 人工标记为 `错误` 的页。
  - 不补充其他页，不扩大到全量。
- 选中页码：
  - `1, 2, 11, 34, 36, 38, 40, 42, 44, 49, 50, 51, 53, 54, 59`
- 样本数：
  - 15 页。
  - 60 条模型请求。
- 图片策略：
  - 复用上一轮 YKJ125 原向 PNG。
  - 不旋转、不 resize、不做有损压缩。
- 模型参数：
  - `qwen3-vl-plus / 非思考`：`temperature=0`，`enable_thinking=false`，不设 `top_p`。
  - `qwen3-vl-plus / thinking_budget=512`：`temperature=0`，`enable_thinking=true`，`thinking_budget=512`，不设 `top_p`。
  - `qwen3.7-plus / 非思考`：`temperature=0`，`enable_thinking=false`，不设 `top_p`。
  - `qwen3.7-max-2026-06-08 / 非思考`：`temperature=0`，`enable_thinking=false`，不设 `top_p`。
- 请求结果：
  - API 成功：56/60。
  - JSON 解析成功：56/60。
  - schema 成功：56/60。
  - 失败 4 条均为 `qwen3-vl-plus / thinking_budget=512`，HTTP 500，且均已保留失败记录。
- 自动对照上一轮人工正确位置：
  - 总命中：5/60。
  - `qwen3-vl-plus / 非思考`：3/15。
  - `qwen3-vl-plus / thinking_budget=512`：1/15。
  - `qwen3.7-plus / 非思考`：1/15。
  - `qwen3.7-max-2026-06-08 / 非思考`：0/15。
- 关键观察：
  - 新模型和 thinking 变体没有稳定解决上一轮错题集。
  - 多数输出仍倾向 `right_edge`，而上一轮人工正确位置均为 `右上方`。
  - `thinking_budget=512` 在未压缩整页 PNG 上出现延迟和 HTTP 500 风险，不适合作为当前全量默认方案。
  - 第 1 页 thinking 变体输出 `top_right`，但该改善没有稳定扩展到其他相似页。
- 固定审核入口：
  - `local_data/review_inbox/current/README.md`
  - `local_data/review_inbox/current/ykj125_vlm_title_block_error_first_review/review_index.html`
  - `local_data/review_inbox/current/ykj125_vlm_title_block_error_first_review/vlm_error_first_review.xlsx`
  - `local_data/review_inbox/current/ykj125_vlm_title_block_error_first_review/vlm_error_first_review.csv`
  - `local_data/review_inbox/current/ykj125_vlm_title_block_error_first_review/review_manifest.json`
  - `local_data/review_inbox/current/ykj125_vlm_title_block_error_first_review/images/`
- 审核包验证：
  - HTML、Excel、CSV、manifest 已生成。
  - 图片副本数：15。
  - Excel 数据行：60。
  - 人工表不暴露长 JSON、候选列表或自动对照摘要。
  - 未生成正式旋正 PDF。
  - 未重命名 PDF。

当前待用户审核：

- 打开 `local_data/review_inbox/current/ykj125_vlm_title_block_error_first_review/review_index.html` 对照图片。
- 在 `local_data/review_inbox/current/ykj125_vlm_title_block_error_first_review/vlm_error_first_review.xlsx` 中填写 `位置是否正确`、必要时填写 `正确标题栏位置` 和 `备注`。
- 用户审核前不进入全量测试。

## VLM 错题集旋转分组放宽评估需求

用户指出：当前实际目标是判断图纸旋转角度，因此标题栏位于上下左右哪个方向是重点；标题栏在同一方向内偏上、偏下，或被枚举为边位置还是角位置，不应作为主门限。

该判断成立。对于旋转判断而言，`right_edge` 与 `top_right` 都代表标题栏在当前图片右侧方向，均对应当前顺时针旋转 270 度。上一轮错题集小测按精确位置计算命中率，会低估对旋转角度判断实际可用的结果。

计划：

- 见 `docs/plans/087-vlm-error-first-rotation-group-threshold-plan.md`。

本轮目标：

- 保留精确标题栏位置作为诊断字段。
- 新增旋转分组评估口径。
- 使用已有错题集 VLM 响应重算，不重新调用 API。
- 重建当前审核包，使人工主判断变为派生当前旋转角度是否正确。

约束：

- 不重新联网。
- 不修改 prompt/schema。
- 不生成正式旋正 PDF。
- 不重命名 PDF。
- 用户审核前不进入全量测试。

回滚准备：

- 已提交回滚点：`1f024f9 docs: plan vlm rotation group threshold`。

VLM 错题集旋转分组放宽评估执行结果：

- 已复用本地既有响应重算：
  - `local_data/vlm_title_block_error_first_ykj125/vlm_raw_responses.jsonl`
  - 未重新调用 API。
- 已更新脚本：
  - `scripts/experiments/build_vlm_title_block_error_first_review.py`
- 审核口径调整：
  - 精确标题栏位置继续保留为参考字段。
  - 人工主审核字段改为 `旋转角度是否正确`、`正确旋转角度`、`备注`。
  - HTML 增加模型派生当前旋转角度。
- 旋转分组机器摘要：
  - 有效旋转结果：56/60。
  - 缺失旋转结果：4/60，均来自 `qwen3-vl-plus / thinking_budget=512` 的 HTTP 500。
  - 总旋转分组命中：54/56 有效结果。
- 分模型旋转分组命中：
  - `qwen3-vl-plus / 非思考`：13/15。
  - `qwen3-vl-plus / thinking_budget=512`：11/11 有效结果，另有 4 条失败。
  - `qwen3.7-plus / 非思考`：15/15。
  - `qwen3.7-max-2026-06-08 / 非思考`：15/15。
- 与精确位置口径的差异：
  - 精确位置总命中仍为 5/60。
  - 旋转分组口径显示多数 `right_edge` 与 `top_right` 的差异不影响旋转角度。
  - 用户提出的放宽门限符合当前任务目标。
- 固定审核入口已重建：
  - `local_data/review_inbox/current/ykj125_vlm_title_block_error_first_review/review_index.html`
  - `local_data/review_inbox/current/ykj125_vlm_title_block_error_first_review/vlm_error_first_review.xlsx`
  - `local_data/review_inbox/current/ykj125_vlm_title_block_error_first_review/vlm_error_first_review.csv`
  - `local_data/review_inbox/current/ykj125_vlm_title_block_error_first_review/review_manifest.json`
  - `local_data/review_inbox/current/ykj125_vlm_title_block_error_first_review/images/`
- 验证结果：
  - Excel 数据行：60。
  - 图片副本：15。
  - 未联网。
  - 未生成正式旋正 PDF。
  - 未重命名 PDF。

当前结论：

- 若仅以旋转角度为目标，`qwen3.7-plus / 非思考` 和 `qwen3.7-max-2026-06-08 / 非思考` 在本轮错题集上均表现为 15/15。
- `qwen3-vl-plus / thinking_budget=512` 虽然有效结果全对，但存在 HTTP 500 和延迟风险，不适合作为当前全量默认。
- 仍需用户审核当前旋转分组审核包后，再决定是否扩大到全量图纸。

## VLM 错题集审核表降噪需求

用户指出当前人工填写表暴露了不需要用户填写和判断的字段。该问题成立，并违反 `AGENTS.md` 中“人工填写表只显示用户完成当前判断必须看到的信息”的规则。

计划：

- 见 `docs/plans/088-vlm-error-first-review-form-simplification-plan.md`。

本轮目标：

- 将 `vlm_error_first_review.xlsx` 收敛为低噪声人工表。
- 只保留 `页码`、`模型`、`模型派生当前旋转角度`、`旋转角度是否正确`、`正确旋转角度`、`备注`。
- 将样本编号、位置代码、上一轮人工正确位置、上一轮 Plus 误判位置等追溯字段移入机器报告或 manifest。

约束：

- 不重新调用 API。
- 不修改模型结果。
- 不生成正式旋正 PDF。
- 不重命名 PDF。
- 不扩大到全量测试。

回滚准备：

- 已提交回滚点：`73c8894 docs: plan vlm review form simplification`。

VLM 错题集审核表降噪执行结果：

- 已更新脚本：
  - `scripts/experiments/build_vlm_title_block_error_first_review.py`
- 已复用已有响应重建当前审核包：
  - `local_data/vlm_title_block_error_first_ykj125/vlm_raw_responses.jsonl`
  - 未重新调用 API。
- 人工填写表已收敛为 6 列：
  - `页码`
  - `模型`
  - `模型派生当前旋转角度`
  - `旋转角度是否正确`
  - `正确旋转角度`
  - `备注`
- 已移出人工表的追溯字段：
  - 样本编号。
  - 标题栏位置与位置代码。
  - 上一轮人工正确位置。
  - 上一轮 Plus 误判位置。
- 追溯字段保留位置：
  - `local_data/review_inbox/current/ykj125_vlm_title_block_error_first_review/review_manifest.json`
  - `local_data/vlm_title_block_error_first_ykj125/run_summary.json`
  - `local_data/vlm_title_block_error_first_ykj125/vlm_decisions.jsonl`
  - `local_data/vlm_title_block_error_first_ykj125/vlm_decisions.csv`
- 验证结果：
  - Excel 数据行：60。
  - 图片副本：15。
  - `review_manifest.json` 包含 `human_review_fields` 与 `machine_review_rows`。
  - 未联网。
  - 未生成正式旋正 PDF。
  - 未重命名 PDF。

## VLM 错题集审核结果分析与全量测试决策需求

用户已完成低噪声 Excel 审核表填写，并要求总结哪些方案组合最好。用户认为下一步可以根据最佳方案进行全量测试。

计划：

- 见 `docs/plans/089-vlm-error-first-review-analysis-and-full-test-decision-plan.md`。

本轮目标：

- 读取当前固定审核入口中已填写的 `vlm_error_first_review.xlsx`。
- 按人工填写的 `旋转角度是否正确` 统计各模型/参数组合表现。
- 综合 API 稳定性、schema 稳定性和人工正确率，给出推荐方案。
- 只做总结和决策建议，不直接执行全量测试。

约束：

- 不重新调用模型。
- 不修改 prompt/schema。
- 不生成正式旋正 PDF。
- 不重命名 PDF。
- 不覆盖人工填写 Excel。

回滚准备：

- 已提交回滚点：`77641d0 docs: plan vlm error-first review analysis`。

VLM 错题集审核结果分析执行结果：

- 新增分析脚本：
  - `scripts/experiments/analyze_vlm_error_first_review.py`
- 读取人工审核表：
  - `local_data/review_inbox/current/ykj125_vlm_title_block_error_first_review/vlm_error_first_review.xlsx`
- 输出本地分析结果：
  - `local_data/vlm_title_block_error_first_ykj125/manual_review_analysis/manual_review_analysis_summary.json`
  - `local_data/vlm_title_block_error_first_ykj125/manual_review_analysis/manual_review_analysis_summary.md`
  - `local_data/vlm_title_block_error_first_ykj125/manual_review_analysis/manual_review_analysis_rows.json`
  - `local_data/vlm_title_block_error_first_ykj125/manual_review_analysis/manual_review_analysis_rows.csv`
- 人工审核记录：
  - 总记录：60。
  - 已填写：60。
- 分模型人工审核结果：
  - `qwen3.7-max-2026-06-08 / 非思考`：15/15，正确率 1.0，API 成功 15/15，schema 成功 15/15。
  - `qwen3.7-plus / 非思考`：15/15，正确率 1.0，API 成功 15/15，schema 成功 15/15。
  - `qwen3-vl-plus / 非思考`：13/15，错误页 1、49，API 成功 15/15，schema 成功 15/15。
  - `qwen3-vl-plus / thinking_budget=512`：11/15，错误页 40、44、49、59，均为模型未输出旋转角度；API 成功 11/15，schema 成功 11/15。
- 归档与入口重置：
  - 已归档当前审核入口到 `local_data/review_inbox/archive/ykj125_vlm_title_block_error_first_review_20260702_212658_reviewed`
  - 已重置 `local_data/review_inbox/current/README.md`
  - 当前没有待用户审核、填写或标注的文件。

当前推荐：

- 推荐全量主测方案：`qwen3.7-plus / 非思考`。
- 推荐理由：
  - 本轮错题集人工审核 15/15。
  - API 和 schema 均 15/15。
  - 与 `qwen3.7-max-2026-06-08` 同分，但更适合作为结构化输出主流程候选，风险更低。
- 可选全量对照方案：`qwen3.7-max-2026-06-08 / 非思考`。
  - 本轮同样 15/15，可作为能力上限对照。
  - 不建议作为默认主流程，原因是模型强但长期结构化和成本/延迟风险更高。
- 不推荐全量方案：
  - `qwen3-vl-plus / thinking_budget=512`：虽然有效结果全对，但 4 条失败，稳定性不达标。
  - `qwen3-vl-plus / 非思考`：稳定但错题集中仍有 2/15 错误，适合作为既有基线，不适合作为本轮改进主方案。

下一步：

- 若进入全量测试，应另起全量测试计划。
- 全量测试建议优先跑 `qwen3.7-plus / 非思考`。
- 可同时加入 `qwen3.7-max-2026-06-08 / 非思考` 作为对照，但不建议直接把 max 作为默认生产方案。
- 全量结果仍需发布低噪声人工审核包，不直接生成正式旋正 PDF。

## PDF 拆分与 JS2207 VLM 全量方向测试需求

用户要求将 `local_data/source_pdfs/` 下两个 PDF 图纸文件全部拆分出来，分别放入两个文件夹，并优先测试 `JS2207-00-00升降平台.pdf` 中全部图纸方向。

本轮模型组合：

- `qwen3.7-plus / 非思考`
- `qwen3.7-max-2026-06-08 / 非思考`

模型参数：

- `temperature=0`
- `enable_thinking=false`
- 不设置 `top_p`
- `response_format={"type":"json_object"}`

本轮只让模型判断标题栏当前位置，由程序按 `rules/mechanical-drawing-rotation.md` 派生当前顺时针旋转角度。人工审核主目标是判断派生旋转角度是否正确，而不是精确审查标题栏角位置。

人工审核表必须保持低噪声，只保留：

- `页码`
- `模型`
- `模型派生当前旋转角度`
- `旋转角度是否正确`
- `正确旋转角度`
- `备注`

标题栏位置代码、raw response、置信度、错误原因、prompt、schema、图片路径和候选字段只进入机器报告或 manifest，不出现在人工填写表中。

约束：

- 不读取或打印 `.env/.env` 中的 API Key。
- 不旋转输入图纸。
- 不 resize 输入图片。
- 不使用 JPEG 或有损压缩。
- 不生成正式旋正 PDF。
- 不重命名 PDF。
- 不把 `local_data/`、`.env/` 或图纸资料纳入 Git。
- 用户审核前不把本轮结果写入 ground truth 或进入正式批处理。

详细计划见 `docs/plans/090-pdf-split-and-js2207-vlm-full-rotation-test-plan.md`。

执行结果：

- 新增脚本：
  - `scripts/experiments/build_pdf_split_and_js2207_vlm_rotation_review.py`
- 拆分和渲染输出：
  - `local_data/split_source_pdfs/js2207_lifting_platform/`
  - `local_data/split_source_pdfs/ykj125_briquetting_machine/`
- 拆分结果：
  - JS2207：29 页单页 PDF，29 张原向 PNG。
  - YKJ125：63 页单页 PDF，63 张原向 PNG。
- JS2207 VLM 全量测试输出：
  - `local_data/vlm_js2207_full_rotation_test/`
- 固定审核入口：
  - `local_data/review_inbox/current/js2207_vlm_full_rotation_review/review_index.html`
  - `local_data/review_inbox/current/js2207_vlm_full_rotation_review/js2207_vlm_full_rotation_review.xlsx`
- API 与解析结果：
  - 请求数：58。
  - API 成功：58/58。
  - JSON 解析成功：58/58。
  - schema 成功：58/58。
- 分模型结果：
  - `qwen3.7-plus / 非思考`：29/29 API、解析、schema 成功。
  - `qwen3.7-max-2026-06-08 / 非思考`：29/29 API、解析、schema 成功。
- 两个模型的派生旋转角度分布一致：
  - 270 度：4 页。
  - 180 度：9 页。
  - 90 度：7 页。
  - 0 度：8 页。
  - 无可派生角度：1 页。
- 需要重点人工审核：
  - 第 3 页两个模型均返回 `no_title_block`，因此人工表中该页两个模型的派生当前旋转角度为空。
- 审核包验证：
  - HTML 按第 1 页到第 29 页顺序展示原向图片。
  - 当前审核入口图片副本：29 张。
  - Excel 数据行：58。
  - Excel 只保留 `页码`、`模型`、`模型派生当前旋转角度`、`旋转角度是否正确`、`正确旋转角度`、`备注`。
  - HTML 不暴露 raw response、位置代码、调试原因或候选字段。
  - 未生成正式旋正 PDF。
  - 未重命名 PDF。
  - `local_data/` 未纳入 Git。
- 过程备注：
  - 首次在普通沙箱网络下运行时 58 个请求均被 socket 权限拦截；已在脚本中增加“全请求失败不发布审核包”的质量门。
  - 随后使用已批准的联网前缀重跑成功，并归档首次无效入口到 `local_data/review_inbox/archive/current_archived_before_js2207_vlm_full_rotation_review_20260702_220506`。

人工审核统计：

- 用户已完成 JS2207 VLM 双模型全量方向审核。
- 总记录：58 行，覆盖 29 页。
- 两个模型结果完全一致，无模型间分歧。
- `qwen3.7-plus / 非思考`：
  - 正确：27。
  - 错误：2。
  - 总数：29。
  - 正确率：93.10%。
- `qwen3.7-max-2026-06-08 / 非思考`：
  - 正确：27。
  - 错误：2。
  - 总数：29。
  - 正确率：93.10%。
- 排除第 3 页“不是图纸，没有标题栏”的特殊页后：
  - 两个模型均为 26/28，正确率 92.86%。
- 错误页：
  - 第 15 页：模型判断 `0` 度，人工正确角度为 `90` 度。
  - 第 22 页：模型判断 `0` 度，人工正确角度为 `90` 度。
- 结论：
  - `qwen3.7-max-2026-06-08 / 非思考` 没有体现出优于 `qwen3.7-plus / 非思考` 的效果。
  - MVP 阶段暂用 `qwen3.7-plus / 非思考`。

## PDF 拆分、VLM 方向识别与旋正 MVP 脚本需求

用户要求当前只完成 MVP，将前面的图纸拆分脚本和图纸旋转方向识别流程合并为一个 Python 脚本。该脚本读取它所在目录中的 `input/` 目录里的 PDF 图纸，把拆分好的图纸保存为若干 PDF 文件，输出到 `output/` 文件夹中，并根据图纸旋转信息把图纸摆正。

本轮 MVP 主方案：

- `qwen3.7-plus / 非思考`
- `temperature=0`
- `enable_thinking=false`
- 不设置 `top_p`

工程边界：

- 脚本从自身所在目录解析 `input/`、`output/` 和 `work/`。
- 旋正 PDF 优先使用 PDF 页面旋转能力，不把图纸栅格化后重新生成 PDF。
- 渲染 PNG 只用于 VLM 标题栏位置判断和必要视觉检查。
- 对 VLM/API/解析失败、`no_title_block`、`unknown` 或无法派生校正角度的页面，不强行旋正；输出未旋转副本并标记人工复核。
- 当前 MVP 不做图号 OCR、不按图号重命名、不合并多页 PDF。

批判性风险：

- 当前 JS2207 人工审核显示该模型仍有方向误判，不能作为无人值守正式批处理。
- 第 15 页和第 22 页这类错误说明底部/左侧边界场景仍需人工复核兜底。
- MVP 输出必须保留 manifest、summary 和 needs_review 清单，避免误把模型输出当确定真值。

详细计划见 `docs/plans/091-mvp-pdf-split-vlm-rotation-correction-script-plan.md`。

执行结果：

- 新增 MVP 工具目录：
  - `tools/pdf_rotation_mvp/`
- 新增脚本：
  - `tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py`
- 新增说明：
  - `tools/pdf_rotation_mvp/README.md`
- 固定目录：
  - `tools/pdf_rotation_mvp/input/`
  - `tools/pdf_rotation_mvp/output/`
  - `tools/pdf_rotation_mvp/work/`
- `.gitignore` 已忽略 MVP 工具的 `input/*`、`output/*`、`work/*`，仅保留 `.gitkeep`。

脚本能力：

- 从脚本所在目录的 `input/` 读取 PDF。
- 使用 `pypdf` 拆分为单页 PDF。
- 使用 Ghostscript 将单页 PDF 渲染为 PNG，供 VLM 判断方向。
- 使用 `qwen3.7-plus`、`temperature=0`、`enable_thinking=false`、不设置 `top_p`。
- 程序根据标题栏位置派生当前顺时针旋转角度和校正角度。
- 对明确可校正页使用 PDF 页面旋转能力输出旋正单页 PDF。
- 对 dry-run、API 失败、解析失败、schema 失败或无可派生校正角度的页，复制未旋转单页 PDF 并标记 `copied_needs_review`。
- 输出：
  - `output/report.csv`
  - `output/needs_review.csv`
  - `output/summary.json`
  - `work/vlm_raw_responses.jsonl`
  - `work/vlm_decisions.jsonl`
  - `work/output_records.jsonl`

验证结果：

- `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
- 使用 JS2207 源 PDF 做 `--dry-run --limit-pages 1`：
  - 页面数：1。
  - corrected：0。
  - copied_needs_review：1。
  - 符合 dry-run 不联网、不假装成功的质量门。
- 使用 JS2207 源 PDF 做联网 `--limit-pages 1` smoke：
  - API 成功：1/1。
  - JSON 解析成功：1/1。
  - schema 成功：1/1。
  - corrected：1。
  - 标题栏位置：`right_edge`。
  - 当前旋转角度：270。
  - 校正角度：90。
  - PDF 原始 `/Rotate`：0。
  - 应用 PDF 顺时针旋转：90。

注意：

- 本次 smoke 的输入 PDF、输出 PDF 和中间文件均位于 `.gitignore` 覆盖目录，不进入 Git。
- 该 MVP 仍不是无人值守正式批处理工具，后续全量使用前仍需检查 `needs_review.csv` 和抽样视觉核对输出 PDF。

## JS2207 MVP PDF 旋正全量测试需求

用户要求使用 `local_data/source_pdfs/JS2207-00-00升降平台.pdf` 测试 MVP PDF 旋正脚本，并保留输出文件夹中的内容供审核。

本轮边界：

- 只处理 JS2207 源 PDF。
- 使用既有 MVP 脚本，不调整识别逻辑。
- 使用 `qwen3.7-plus / 非思考`。
- 输出保留在 `tools/pdf_rotation_mvp/output/`。
- 中间文件保留在 `tools/pdf_rotation_mvp/work/`。
- 用户审核入口发布到 `local_data/review_inbox/current/`。

详细计划见 `docs/plans/092-js2207-mvp-pdf-rotation-correction-run-plan.md`。

执行结果：

- MVP 输入：
  - `tools/pdf_rotation_mvp/input/JS2207-00-00升降平台.pdf`
- MVP 输出：
  - `tools/pdf_rotation_mvp/output/JS2207-00-00升降平台/`
  - `tools/pdf_rotation_mvp/output/report.csv`
  - `tools/pdf_rotation_mvp/output/needs_review.csv`
  - `tools/pdf_rotation_mvp/output/summary.json`
- MVP 中间文件：
  - `tools/pdf_rotation_mvp/work/`
- 固定审核入口：
  - `local_data/review_inbox/current/js2207_mvp_pdf_rotation_review/review_index.html`
  - `local_data/review_inbox/current/js2207_mvp_pdf_rotation_review/pdfs/`
  - `local_data/review_inbox/current/js2207_mvp_pdf_rotation_review/reports/report.csv`
  - `local_data/review_inbox/current/js2207_mvp_pdf_rotation_review/reports/needs_review.csv`

运行摘要：

- 源 PDF：1 个。
- 页数：29。
- API 成功：29/29。
- JSON 解析成功：29/29。
- schema 成功：29/29。
- corrected：28。
- copied_needs_review：1。
- 输出单页 PDF：29。
- report 行数：29。
- needs_review 行数：1。

复核重点：

- 第 3 页：模型返回 `no_title_block`，输出状态为 `copied_needs_review`。
- 第 15 页：上一轮人工审核曾发现方向风险，本轮报告为 `bottom_left`，当前旋转 90，校正 270。
- 第 22 页：上一轮人工审核曾发现方向风险，本轮报告为 `bottom_edge`，当前旋转 0，校正 0，需要用户重点审核。

固定审核入口已归档上一轮入口，并发布本轮审核包。MVP 输入、输出、中间文件和 `local_data/` 均在 `.gitignore` 覆盖范围内，未进入 Git。

## JS2207 标题栏图号 OCR 四模型测试需求

用户确认第 22 页旋正仍然错误，但当前暂不处理该问题。下一步希望使用 `tools/pdf_rotation_mvp/output/JS2207-00-00升降平台/` 中的单页 PDF 测试 OCR 效果，目标是提取标题栏图号。

用户指定测试模型：

- `qwen3.7-plus`
- `qwen3.7-max`
- `qwen3.5-ocr`
- `qwen-VL-ocr`

按前期调研规范化为：

- `qwen3.7-plus`
- `qwen3.7-max-2026-06-08`
- `qwen3.5-ocr`
- `qwen-vl-ocr-latest`

提示词需要结合标题栏规范：

- 真正标题栏应包含图号/图样代号、图名/名称、材料、比例、单位、设计、制图、校对、审核、批准、日期等字段组合。
- 明细表、零件表、技术要求表和局部说明表不是标题栏。
- 不得把明细表中的零件号、材料号或单个字段误当作图纸图号。
- 看不清或没有标题栏时应返回空图号并标记人工复核。

本轮输入策略：

- 使用 MVP 输出 PDF。
- 渲染为 PNG。
- 优先裁切底部标题栏候选区域作为 OCR 输入。
- 第 22 页方向错误作为已知风险记录，不在本轮修正。

人工审核表只保留：

- `页码`
- `模型`
- `模型提取图号`
- `图号是否正确`
- `正确图号`
- `备注`

详细计划见 `docs/plans/093-js2207-title-block-drawing-number-ocr-model-test-plan.md`。

执行结果：

- 新增脚本：
  - `scripts/experiments/build_js2207_title_block_drawing_number_ocr_review.py`
- 输入目录：
  - `tools/pdf_rotation_mvp/output/JS2207-00-00升降平台/`
- 输出目录：
  - `local_data/js2207_title_block_drawing_number_ocr_test/`
- 固定审核入口：
  - `local_data/review_inbox/current/js2207_title_block_drawing_number_ocr_review/review_index.html`
  - `local_data/review_inbox/current/js2207_title_block_drawing_number_ocr_review/js2207_title_block_drawing_number_ocr_review.xlsx`
  - `local_data/review_inbox/current/js2207_title_block_drawing_number_ocr_review/crops/`
  - `local_data/review_inbox/current/js2207_title_block_drawing_number_ocr_review/pages/`

脚本策略：

- 将 MVP 单页 PDF 渲染为 PNG。
- 按横向底部 30%、竖向底部 35% 裁切标题栏候选区域。
- 使用标题栏规范提示词提取整张图纸的图号或图样代号。
- 明确要求不得把明细表、零件表、技术要求表、局部说明表中的编号误当图号。
- `temperature=0`，不设置 `top_p`。
- `qwen3.7-plus`、`qwen3.7-max-2026-06-08`、`qwen-vl-ocr-latest` 优先使用结构化 JSON 请求。
- `qwen3.5-ocr` 初始结构化请求返回空内容，因此调整为优先 `minimal_text` 请求；脚本仍保留空内容和参数不兼容时的模式回退。

最终运行摘要：

- 页数：29。
- 模型数：4。
- 预期请求：116。
- API 成功：116/116。
- JSON 解析成功：114/116。
- schema 成功：114/116。
- 非空图号：68/116。
- crop 图片：29。
- 整页参考图：29。
- Excel 行数：117 行，即 1 行表头 + 116 条审核记录。

按模型机器统计：

| 模型 | API 成功 | JSON 解析成功 | schema 成功 | 非空图号 |
| --- | ---: | ---: | ---: | ---: |
| `qwen3.7-plus` | 29/29 | 29/29 | 29/29 | 28/29 |
| `qwen3.7-max-2026-06-08` | 29/29 | 29/29 | 29/29 | 28/29 |
| `qwen3.5-ocr` | 29/29 | 28/29 | 28/29 | 1/29 |
| `qwen-vl-ocr-latest` | 29/29 | 28/29 | 28/29 | 11/29 |

复核重点：

- 第 3 页：上一轮已知无标题栏/非图纸；本轮多数模型返回空图号，`qwen-vl-ocr-latest` 返回内容不是合法 JSON。
- 第 22 页：方向存在已知错误，本轮暂不修正；三个模型仍提取到 `JS2207-30-00`，需要人工核对是否可信。
- 两个 `qwen3.7` 模型在机器层面的结构化稳定性明显高于两个 OCR 模型；是否准确必须等待人工审核表结果，不能只看非空率。

固定审核入口已归档上一版入口，并发布最终二次重跑结果。私有产物、图纸、图片和模型响应均位于 `.gitignore` 覆盖目录，未进入 Git。

## 阿里云模型联网沙箱规则固化需求

用户已完成 JS2207 标题栏图号 OCR 四模型审核表填写，并指出每次调用阿里云模型测试脚本时，普通沙箱都会先拦截联网请求，随后才提权重跑，浪费时间。

已确认现象：

- 普通沙箱调用阿里云百炼 / DashScope / OpenAI-compatible endpoint 时，可能出现 Windows socket 权限错误。
- 该错误属于执行环境网络权限问题，不代表模型、API key、endpoint、prompt 或输入图片有误。
- 后续同类真实联网调用应直接使用提权执行或已批准命令前缀，避免制造一轮已知失败日志。

本轮目标：

- 将规则写入 `AGENTS.md`。
- 不修改模型脚本。
- 不重新运行模型测试。
- 不读取或暴露 `.env/.env` 中的密钥。

详细计划见 `docs/plans/094-aliyun-model-network-sandbox-rule-plan.md`。

执行结果：

- 已在 `AGENTS.md` 新增“阿里云模型联网执行规则”。
- 后续涉及阿里云百炼、DashScope、OpenAI-compatible endpoint 的真实模型调用、OCR/VLM 测试、smoke test 或批量实验时，应直接使用已批准命令前缀或 `sandbox_permissions=require_escalated` 联网执行。
- 明确禁止先在普通沙箱中试跑已知会被拦截的联网请求。
- 规则同时保留 dry-run、少量 smoke test、日志脱敏、质量门、错误分层、人工审核入口、回滚准备和密钥保护要求。

## JS2207 标题栏图号 OCR 审核结果统计需求

用户已完成 `local_data/review_inbox/current/js2207_title_block_drawing_number_ocr_review/js2207_title_block_drawing_number_ocr_review.xlsx` 的人工审核填写。

本轮目标：

- 读取人工审核表。
- 统计 `qwen3.7-plus`、`qwen3.7-max-2026-06-08`、`qwen3.5-ocr`、`qwen-vl-ocr-latest` 的图号提取表现。
- 单独观察第 3 页无标题栏和第 22 页方向错误风险页。
- 生成机器统计报告和人工摘要。
- 归档当前审核入口并重置 `local_data/review_inbox/current/`。

本轮不重新调用模型、不修改用户填写表格、不修正第 22 页方向。

详细计划见 `docs/plans/095-js2207-title-block-drawing-number-ocr-review-analysis-plan.md`。

执行结果：

- 新增分析脚本：
  - `scripts/experiments/analyze_js2207_title_block_drawing_number_ocr_review.py`
- 输入人工审核表：
  - `local_data/review_inbox/current/js2207_title_block_drawing_number_ocr_review/js2207_title_block_drawing_number_ocr_review.xlsx`
- 统计输出目录：
  - `local_data/js2207_title_block_drawing_number_ocr_test/review_analysis/`
- 当前审核入口已归档：
  - `local_data/review_inbox/archive/current_archived_after_js2207_title_block_drawing_number_ocr_review_20260703_003122/`
- `local_data/review_inbox/current/` 已重置为无待审核任务。

审核统计摘要：

- 审核记录：116 条。
- 已明确审核：116 条。
- 总正确：72 条。
- 总错误：44 条。
- 未识别审核值：0 条。

按模型统计：

| 模型 | 已审核 | 正确 | 错误 | 正确率 | 空预测 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `qwen3.7-plus` | 29 | 29 | 0 | 100.00% | 1 |
| `qwen3.7-max-2026-06-08` | 29 | 29 | 0 | 100.00% | 1 |
| `qwen3.5-ocr` | 29 | 2 | 27 | 6.90% | 28 |
| `qwen-vl-ocr-latest` | 29 | 12 | 17 | 41.38% | 18 |

去除第 3 页和第 22 页风险页后：

| 模型 | 已审核 | 正确 | 错误 | 正确率 | 空预测 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `qwen3.7-plus` | 27 | 27 | 0 | 100.00% | 0 |
| `qwen3.7-max-2026-06-08` | 27 | 27 | 0 | 100.00% | 0 |
| `qwen3.5-ocr` | 27 | 0 | 27 | 0.00% | 27 |
| `qwen-vl-ocr-latest` | 27 | 10 | 17 | 37.04% | 17 |

结论：

- 在当前 MVP 图纸旋正输出、底部标题栏 crop、标题栏规范 prompt 和人工审核口径下，`qwen3.7-plus` 与 `qwen3.7-max-2026-06-08` 均达到 100% 正确率。
- `qwen3.5-ocr` 和 `qwen-vl-ocr-latest` 不适合作为当前图号提取主链路；它们更可能需要专门的 OCR 区域检测、原生 OCR 调用或二阶段解析实验。
- MVP 阶段若优先稳定交付，应继续沿用 `qwen3.7-plus` 作为默认图号提取模型；`qwen3.7-max-2026-06-08` 可作为对照或兜底候选，但需要结合成本、延迟和后续样本泛化再决定是否引入。

## PDF 旋正 MVP 增加图号命名工序需求

用户同意当前图号 OCR 审核结论，并要求修改此前的拆分、旋转图纸脚本：

```text
tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py
```

新增最后一道读取图号的工序。最终输出的若干单个图纸 PDF 文件名必须是图纸图号。

本轮设计原则：

- 继续使用 `qwen3.7-plus` 作为 MVP 默认模型。
- 方向识别仍先判断标题栏位置，再由程序推导旋转角度。
- 图号读取发生在旋正之后，基于旋正页面的底部标题栏候选区域。
- 主输出目录只放已旋正且成功读取唯一图号的 PDF，文件名为 `<图号>.pdf`。
- 读不到图号、图号重复、图号不适合作为文件名、方向识别失败、无标题栏或模型要求人工复核时，页面进入 `needs_review/`，不得使用页码伪装成最终图号文件名。
- 不重新调用 OCR 模型作为主链路，不跳过人工复核质量门。

详细计划见 `docs/plans/096-mvp-pdf-rotation-drawing-number-filename-plan.md`。

执行结果：

- 已修改 `tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py`。
- 保留既有 PDF 拆分、渲染、标题栏位置识别和 PDF 页面旋正流程。
- 新增旋正后标题栏候选区域裁切和图号读取流程，默认继续使用 `qwen3.7-plus`、`temperature=0`、`enable_thinking=false`、不设置 `top_p`。
- 最终发布阶段只将方向可靠、图号可靠、图号可作为文件名且同一源 PDF 分组内唯一的页面输出为 `output/<源PDF名>/<图号>.pdf`。
- 方向失败、图号读取失败、图号重复、文件名非法、模型要求复核或 dry-run 页面进入 `output/<源PDF名>/needs_review/`。
- 只有已明确旋正的页面才进入图号读取，避免对方向失败页继续消耗模型请求。
- `output/report.csv` 已加入 `final_pdf_path`、`final_status`、`drawing_number`、`final_filename_stem`、`drawing_number_*`、`final_blockers` 等字段。
- `work/` 中方向识别与图号识别分别写入 `orientation_*.jsonl` 和 `drawing_number_*.jsonl`。
- 已更新 `tools/pdf_rotation_mvp/README.md` 说明新输出结构和报告字段。

验证结果：

- `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
- `python tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py --dry-run --limit-pages 1` 通过：
  - `published_count=0`。
  - `final_needs_review_count=1`。
  - 未生成看似成功的图号命名 PDF。
- `python tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py --limit-pages 1` 联网 smoke 通过：
  - 方向识别 API、JSON 解析、schema 均为 1/1。
  - 图号识别 API、JSON 解析、schema 均为 1/1。
  - `corrected_count=1`。
  - `published_count=1`。
  - `final_needs_review_count=0`。
  - 第 1 页最终输出为 `tools/pdf_rotation_mvp/output/JS2207-00-00升降平台/JS2207-00-10.pdf`。

注意：

- 本轮只做 1 页 smoke 验证，没有重新跑 JS2207 全量 29 页。
- 该 MVP 仍不修正此前已知的第 22 页方向问题；全量处理后仍需要查看 `report.csv` 和 `needs_review.csv`，并进行人工抽查。

## JS2207 MVP 图号命名全流程测试需求

用户要求清空 `tools/pdf_rotation_mvp/output/`，并再次使用 `local_data/source_pdfs/JS2207-00-00升降平台.pdf` 进行全流程测试。

本轮目标：

- 清空上一轮 smoke 输出，保留 `output/.gitkeep`。
- 使用 JS2207 源 PDF 作为 MVP 输入。
- 运行完整流程：拆分、渲染、方向识别、旋正、图号读取、按图号命名发布。
- 保留 `tools/pdf_rotation_mvp/output/` 和 `tools/pdf_rotation_mvp/work/` 供后续审核。
- 汇总 `summary.json`、`report.csv`、`needs_review.csv` 和主输出目录 PDF 文件名。

质量要求：

- 不读取或暴露 `.env/.env` 中的 API Key。
- 真实阿里云模型调用直接使用已批准的 MVP 脚本命令或提权执行。
- 不提交图纸、输出 PDF、模型响应或 `local_data/` 本地产物。
- 方向失败、图号失败、重复图号或文件名非法页面必须进入 `needs_review/`。

详细计划见 `docs/plans/097-js2207-mvp-drawing-number-full-flow-run-plan.md`。

执行结果：

- 已清空 `tools/pdf_rotation_mvp/output/`，仅保留 `.gitkeep`。
- 已确认 MVP 输入存在：`tools/pdf_rotation_mvp/input/JS2207-00-00升降平台.pdf`。
- 已运行 `python tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 完整流程。
- 输出保留在：
  - `tools/pdf_rotation_mvp/output/`
  - `tools/pdf_rotation_mvp/work/`
- 固定审核入口已发布：
  - `local_data/review_inbox/current/js2207_mvp_drawing_number_full_flow_review/review_index.html`
  - `local_data/review_inbox/current/js2207_mvp_drawing_number_full_flow_review/review_form.csv`
  - `local_data/review_inbox/current/js2207_mvp_drawing_number_full_flow_review/pdfs/`
  - `local_data/review_inbox/current/js2207_mvp_drawing_number_full_flow_review/reports/`

运行摘要：

- 源 PDF：1 个。
- 页数：29。
- 方向识别 API 成功：29/29。
- 方向 JSON 解析成功：29/29。
- 方向 schema 成功：29/29。
- 图号识别 API 成功：28/28。
- 图号 JSON 解析成功：28/28。
- 图号 schema 成功：28/28。
- 图号非空：28/28。
- corrected：28。
- copied_needs_review：1。
- published：28。
- final_needs_review：1。
- `report.csv` 行数：29。
- `needs_review.csv` 行数：1。
- 主输出目录正式 PDF：28 个。
- 主输出目录 PDF 文件名均与 `report.csv` 中 `drawing_number` 一致。
- 未发现重复图号。

复核重点：

- 第 3 页：模型判断 `no_title_block`，进入 `needs_review/`。
- 第 22 页：本轮发布为 `JS2207-30-00.pdf`，模型判断标题栏位置 `bottom_edge`、当前旋转 `0` 度；但该页是历史已知方向风险页，已在审核表中标注“历史已知方向风险，请重点核查”。

注意：

- 本轮没有修改识别逻辑，只执行已提交的 MVP 全流程。
- `local_data/`、MVP `input/output/work`、模型响应和图纸 PDF 均为本地产物，不纳入 Git。

## JS2207 MVP 图号命名审核结果归档需求

用户已完成 `local_data/review_inbox/current/js2207_mvp_drawing_number_full_flow_review/review_form.csv` 人工审核填写。

本轮目标：

- 读取用户填写后的审核表。
- 统计人工判断分布和备注。
- 归档当前固定审核入口。
- 重置 `local_data/review_inbox/current/`。
- 记录用户对无标题栏/无图号页面的处理建议。

用户新增规则建议：

- 对于无图号或无标题栏但需要保留的页面，后续输出文件名可使用 `人工复核_XX`。
- `XX` 使用数字，避免文件名重复。

本轮不重新调用模型，不修改用户填写表，不重命名当前输出 PDF。

详细计划见 `docs/plans/098-js2207-mvp-review-result-archive-plan.md`。

执行结果：

- 已读取用户填写后的审核表。
- 审核表编码为 Excel/ANSI 风格，读取时使用 GB18030 兜底。
- 审核记录：29 条。
- 人工判断分布：
  - 正确：28。
  - 错误：1。
- 输出状态分布：
  - 已发布：28。
  - 需复核：1。
- 当前审核入口已归档：
  - `local_data/review_inbox/archive/current_archived_after_js2207_mvp_drawing_number_full_flow_review_20260703_013348/`
- `local_data/review_inbox/current/` 已重置为无待审核任务。
- 统计输出：
  - `local_data/js2207_mvp_drawing_number_full_flow_review/review_analysis/summary.json`
  - `local_data/js2207_mvp_drawing_number_full_flow_review/review_analysis/issues.csv`
  - `local_data/js2207_mvp_drawing_number_full_flow_review/review_analysis/notes.csv`

人工审核结论：

- 第 3 页：人工判断为错误/删除类处理。该页不存在标题栏，用户备注要求后续无标题栏/无图号但需要保留时，文件名直接写 `待人工复核_XX`，其中 `XX` 为数字，防止文件名重复。
- 第 22 页：人工判断为正确，但备注指出图纸仍是顺时针 90 度旋转，没有被转回正确位置。该页说明当前 MVP 图号识别可正确，但方向旋正仍存在已知缺陷，需要作为后续修正重点。

后续需求：

- 将无图号/无标题栏页的占位命名规则从当前 `needs_review/<task_id>.pdf` 调整为更符合人工使用的 `待人工复核_XX.pdf`。
- 单独分析第 22 页方向未摆正问题，决定是改 prompt、加人工复核质量门，还是增加确定性规则。

## YOLO 标题栏识别展示案例需求

用户需要生成一张此前使用本地 YOLO/OBB 模型识别标题栏的案例，用于对外展示，形式类似此前人工审核 HTML 文件。

本轮目标：

- 从历史 YOLO/OBB 预测复查归档中挑选一张清晰样例。
- 生成单案例 HTML。
- 将 HTML 和图片副本发布到固定入口。

候选来源：

- `local_data/review_inbox/archive/round3_prediction_review_20260628_reviewed/round3_prediction_review/`

初步选择：

- `round2_val_regression_sample_020.jpg`

选择原因：

- 蓝色预测框完整覆盖标题栏。
- 标签 `title_block 0.88` 清晰。
- 图纸主体和标题栏都能在一张图中看到，适合说明本地 YOLO/OBB 模型的识别效果。

详细计划见 `docs/plans/099-yolo-title-block-demo-case-plan.md`。

执行结果：

- 已从历史归档中选择样例：
  - `local_data/review_inbox/archive/round3_prediction_review_20260628_reviewed/round3_prediction_review/images/round2_val_regression_sample_020.jpg`
- 已发布展示入口：
  - `local_data/review_inbox/current/yolo_title_block_demo/review_index.html`
  - `local_data/review_inbox/current/yolo_title_block_demo/images/round2_val_regression_sample_020.jpg`
  - `local_data/review_inbox/current/yolo_title_block_demo/metadata.json`
- 已更新固定入口说明：
  - `local_data/review_inbox/current/README.md`
- 校验结果：
  - HTML 中引用的图片副本存在。
  - 页面包含 `title_block 0.88` 标签说明。
  - 图片已视觉检查，蓝色框完整覆盖标题栏，适合对外展示。
- 本轮只生成展示材料，没有重新训练或重新推理 YOLO。
- 展示材料位于 `local_data/`，不纳入 Git。

## ROI 收敛多框展示案例需求

用户指出上一轮单框 YOLO 展示形式不对。真正需要的是当时收敛、调整 ROI 时用于人工审核的页面形态：同一张图上有多个彩色框，分别代表不同策略下的识别结果；案例数量至少 10 张，并尽量包含识别出错或高风险案例。

本轮目标：

- 使用历史 ROI 实验 overlay，不重新训练、不重新推理。
- 选择不少于 10 张样本。
- 优先包含 `needs_review`、候选冲突、图号缺失、低置信度等风险样本。
- 同时提供三策略 ROI overlay 和收窄前后 ROI overlay。
- 发布到固定入口 `local_data/review_inbox/current/roi_convergence_demo/`。

候选来源：

- `local_data/ocr_fine_roi_experiment/overlays/*__fine_roi_overlay.png`
- `local_data/ocr_fine_roi_tightening_experiment/overlays/*__old_new_roi_overlay.png`
- `local_data/ocr_fine_roi_experiment/review_manifest.json`
- `local_data/ocr_fine_roi_tightening_experiment/review_manifest.json`

拟选样本：

- 风险/错误样本：`sample_035`、`sample_041`、`sample_044`、`sample_047`、`sample_049`、`sample_055`、`sample_062`、`sample_009`。
- 正常对照样本：`sample_001`、`sample_002`、`sample_019`。

详细计划见 `docs/plans/100-roi-convergence-demo-cases-plan.md`。

执行结果：

- 已将上一轮形式不对的单框展示入口归档：
  - `local_data/review_inbox/archive/yolo_title_block_demo_wrong_form_20260703_121539/`
- 已发布新的固定入口：
  - `local_data/review_inbox/current/roi_convergence_demo/review_index.html`
  - `local_data/review_inbox/current/roi_convergence_demo/metadata.json`
  - `local_data/review_inbox/current/roi_convergence_demo/assets/fine_roi_overlays/`
  - `local_data/review_inbox/current/roi_convergence_demo/assets/tightening_overlays/`
- 已更新入口说明：
  - `local_data/review_inbox/current/README.md`
- 展示案例数量：11。
- 风险/错误案例数量：8。
- 正常对照案例数量：3。
- 三策略 ROI overlay 数量：11。
- 收窄前后 ROI overlay 数量：11。
- HTML 图片引用数量：22，缺失引用：0。
- 抽查样本：
  - `sample_035`：风险样本，三策略图中红、蓝、绿候选框可见。
  - `sample_001`：正常对照，三策略图中红、蓝、绿候选框可见。
  - `sample_009`：收窄对照图中旧 ROI 红框和新版 ROI 绿框可见。
- 本轮没有重新训练 YOLO/OBB，没有重新调用 OCR/VLM，只整理历史 ROI 实验展示证据。

## 账号切换当前状态交接需求

用户准备切换账号，需要记录当前所有应保存状态，做好新账号或新会话的接手准备。

本轮目标：

- 更新根目录 `HANDOFF.md`。
- 记录当前 Git 状态、固定审核入口、MVP 主线、模型/API 约束、本地产物位置、已知问题、下一步和禁止事项。
- 只记录 `.env/.env` 作为 API key 位置，不读取、不打印、不提交密钥。
- 不重新调用阿里云模型，不重新处理 PDF，不修改 MVP 脚本逻辑。
- 不覆盖当前固定入口 `local_data/review_inbox/current/`。

当前关键状态：

- 最新公开提交：
  - `6738d99 docs: record roi convergence demo output`
  - `accfc7a docs: plan roi convergence demo cases`
- 当前固定入口：
  - `local_data/review_inbox/current/README.md`
  - `local_data/review_inbox/current/roi_convergence_demo/review_index.html`
- 当前主线：
  - PDF 拆分、VLM 方向识别、旋正、标题栏图号 OCR、按图号命名 PDF 的 MVP 已完成 JS2207 全流程测试。
  - MVP 阶段暂用 `qwen3.7-plus / 非思考`。
- 已知后续任务：
  - 落实无标题栏/无图号页 `待人工复核_XX` 命名规则。
  - 单独分析第 22 页方向仍未摆正问题。
  - 对浅字标题栏样本执行 OCR 图像预处理小实验。

详细计划见 `docs/plans/101-account-switch-current-state-handoff-plan.md`。

执行结果：

- 已更新根目录交接入口：
  - `HANDOFF.md`
- 已更新文档索引：
  - `docs/README.md`
- `HANDOFF.md` 已记录：
  - 新会话先读顺序。
  - 当前固定入口 `local_data/review_inbox/current/roi_convergence_demo/review_index.html`。
  - 当前 ROI 收敛展示包数量：11 张案例，其中 8 张风险/错误案例、3 张正常对照。
  - 当前 MVP 工具入口、输入目录、输出目录和工作目录。
  - JS2207 最新 MVP 摘要：29 页，发布 28 个正式 PDF，最终需复核 1 个。
  - 当前模型选择：`qwen3.7-plus / 非思考`，`temperature=0`，`top_p=not_set`。
  - API key 只记录位置 `.env/.env`，未读取、未打印、未提交。
  - 第 3 页无标题栏/无图号处理结论。
  - 第 22 页方向仍未摆正的已知缺陷。
  - 下一步优先事项和暂时不要做的事项。
- 已校验：
  - `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
  - `HANDOFF.md` 存在。
  - `local_data/review_inbox/current/README.md` 存在。
  - `local_data/review_inbox/current/roi_convergence_demo/review_index.html` 存在。
  - `tools/pdf_rotation_mvp/output/summary.json` 存在。
  - `tools/pdf_rotation_mvp/output/report.csv` 存在。
  - `tools/pdf_rotation_mvp/output/needs_review.csv` 存在。
- 已在 TODO 中关闭两个被后续流程覆盖的旧等待项：
  - JS2207 双模型全量方向结果审核等待项。
  - JS2207 标题栏图号 OCR 四模型审核等待项。

## 项目目录整理需求

当前项目中存在历史输出、临时目录、重复样本和无关课程草稿，影响后续开发判断。

整理要求：

- 保留公开仓库的源码、规划、规则、RPD、参考资料。
- 保留本地私有原 PDF 和前 20 张实验样本。
- 删除可再生输出、旧临时目录、重复的前 5 张样本和无关草稿。
- 具体计划见 `docs/plans/001-project-structure-cleanup-plan.md`。

## 风险

- 图纸中存在明细表、技术要求表等非标题栏表格，可能干扰表格密度判断。
- 扫描噪声、倾斜、裁切会影响线条检测。
- 不同图幅和标题栏布局可能需要调整区域阈值。

## 回滚准备

实现前必须提交当前规划、RPD 和 todo。若后续实现不可用，可回退到该提交，保留已确认的需求和计划。

## 项目目录、命名、配置与 EXE 发布综合整理需求

用户要求重新整理项目目录，按照更符合一般 Python 软件工程的方式区分源码、测试、文档、配置和发布产物；同时指出当前 `tools/` 目录承载 MVP 主程序会误导使用者，以为它只是辅助工具。

补充需求：

- 项目英文名 `pictureAnalyse` 不够贴切，需要更符合机械图纸处理目标的新名称。
- 最终目标是编译成 Windows `.exe`。
- 配置文件和程序应放在同一个应用目录内，接近 Linux/便携式程序设计习惯，不强制依赖系统级环境变量，避免影响其他项目。
- 千问/阿里云大模型 API key 应由用户写入本项目或发布目录内的真实配置文件；公开仓库只提交配置模板，不提交真实 key。
- 整理前必须先形成综合规划文件，等待用户审核后再执行源码迁移和程序改造。

当前确认方案：

- 产品名：`BlueprintNormalizer`。
- Python 包名：`blueprint_normalizer`。
- CLI 命令：`blueprint-normalizer`。
- GitHub 仓库名：`blueprint-normalizer`。
- Windows 程序名：`BlueprintNormalizer.exe`。
- Linux 程序名：`blueprint-normalizer`。
- 本地顶层目录建议由 `pictureAnalyse` 手动改名为 `BlueprintNormalizer`。
- 正式源码迁入 `src/blueprint_normalizer/`。
- 测试放入 `tests/`。
- 文档统一归入 `docs/`，其中保留 `plans/research/workflows/decisions/reports/rules/references` 分层。
- 配置模板放入 `etc/blueprint-normalizer.example.toml`。
- 真实配置文件名为 `blueprint-normalizer.toml`，与 `BlueprintNormalizer.exe` 同级或位于开发态仓库根目录，并加入 `.gitignore`。
- Windows 最终发布目录包含 `BlueprintNormalizer.exe`、`blueprint-normalizer.toml`、`input/`、`output/`、`work/`、`logs/`。
- Linux 最终发布目录包含 `blueprint-normalizer`、`blueprint-normalizer.toml`、`input/`、`output/`、`work/`、`logs/`。
- README 需要同时服务人类和 AI，根 README 顶部应包含稳定的 `AI Quick Context`。
- GitHub 可直接重命名仓库，也可在确认本地历史完整后删除旧仓库并新建 `blueprint-normalizer`。

目录调整会影响源码，后续必须同步修改：

- `scripts.*` 导入路径。
- 项目根目录解析逻辑。
- MVP 默认输入、输出、工作目录。
- 配置加载顺序。
- 当前 README、HANDOFF、docs 索引和运行命令。
- 阿里云联网执行命令前缀。
- GitHub remote URL。

详细计划见 `docs/plans/102-project-layout-naming-config-exe-plan.md`。

本轮只修订规划、RPD 和 TODO，不移动源码、不修改程序逻辑、不读取或写入真实 API key。

## GitHub 新仓库单快照发布需求

用户希望删除旧 GitHub 仓库 `pictureAnalyse`，按照新项目名上传到 `blueprint-normalizer`，并且新 Git 仓库只保留当前最近版本，不保留过去 269 个本地历史提交。

经检查，当前本地状态适合做单快照新仓库：

- 当前路径已为 `D:\project\codex\BlueprintNormalizer`。
- 当前工作区干净。
- 当前 remote 仍为 `https://github.com/dexterlu-coder/pictureAnalyse.git`。
- 当前本地历史 269 个提交。
- 当前 tracked 文件 218 个。
- 当前 tracked 文件未包含 `local_data/`、`.env/`、`outputs/`、`runs/` 或 MVP 真实 `input/output/work` 产物。
- 当前只有 `master` 与 `origin/master`，没有 tag，历史结构不复杂。

用户修正了执行顺序：不应先删除旧仓库，而应先创建并提交新项目，确认新仓库没有问题后，再删除旧仓库。

当前确认方案：

- 先创建新 GitHub 仓库 `dexterlu-coder/blueprint-normalizer`。
- 新仓库不要初始化 README、LICENSE 或 `.gitignore`。
- 优先使用旁路发布快照工作区生成单提交，而不是直接删除当前主工作区 `.git`。
- 将当前公开文件快照推送为新仓库唯一初始提交。
- 验收新仓库页面、文件清单、clone 结果和非联网编译检查。
- 新仓库确认无误后，再由用户单独确认删除旧仓库 `dexterlu-coder/pictureAnalyse`。

详细计划见 `docs/plans/103-github-new-repo-single-snapshot-plan.md`。

本轮只修订计划、RPD、TODO 和忽略规则，不删除旧仓库、不创建新仓库、不重写本地历史、不读取或提交真实 API key。

执行结果：

- 已提交规划回滚点：
  - `a5fa70a docs: plan single snapshot GitHub migration`
  - `cd50402 docs: mark GitHub migration plan checkpoint`
- 已在 `local_data/github_single_snapshot_20260706_001/` 创建旁路发布快照工作区。
- 发布快照工作区初始提交：
  - `54acba8 Initial snapshot for BlueprintNormalizer`
- 已创建并推送新 GitHub 仓库：
  - `https://github.com/dexterlu-coder/blueprint-normalizer`
- 新仓库默认分支：
  - `master`
- 已从新仓库重新 clone 到：
  - `local_data/github_single_snapshot_clone_20260706_001/`
- 远端 clone 验收结果：
  - `git rev-list --count HEAD` 为 `1`。
  - `git log --oneline -3` 只显示 `54acba8 Initial snapshot for BlueprintNormalizer`。
  - `git ls-files local_data .env outputs runs blueprint-normalizer.toml` 无输出。
  - `AGENTS.md`、`HANDOFF.md`、`TODO.md`、`docs/plans/103-github-new-repo-single-snapshot-plan.md`、`tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py` 均存在。
  - `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
- 已确认旧 GitHub 仓库仍存在：
  - `https://github.com/dexterlu-coder/pictureAnalyse`

补充执行结果：

- 已在记录执行结果后重新生成单提交快照，并用 `--force-with-lease` 覆盖推送新仓库。
- 新仓库仍保持单提交历史。
- 最终 clone 验收显示提交数为 `1`，关键文件存在，禁区路径无跟踪文件，MVP 脚本编译检查通过。
- 旧仓库删除必须等待用户单独确认。

## 旧 GitHub 仓库删除确认

用户已确认新仓库 `https://github.com/dexterlu-coder/blueprint-normalizer` 可用，可以删除旧仓库：

```text
https://github.com/dexterlu-coder/pictureAnalyse
```

删除前条件已满足：

- 新仓库已创建。
- 新仓库保持单提交历史。
- 新仓库 clone 验收通过。
- 新仓库未跟踪 `local_data/`、`.env/`、`outputs/`、`runs/`、`blueprint-normalizer.toml`。
- 旧仓库删除风险已记录：GitHub 侧 issue、star、watcher、settings、权限配置和旧远端历史会丢失。

本轮将先提交此确认记录，再执行 GitHub 删除命令。删除完成后需要再次确认旧仓库不可访问、新仓库仍可访问，并更新 TODO/RPD/HANDOFF。

执行结果：

- 首次执行删除时，GitHub 返回 403，原因是当前 `gh` token 缺少 `delete_repo` scope。
- 已按 GitHub CLI 提示执行 `gh auth refresh -h github.com -s delete_repo`，用户通过设备码完成授权。
- 已执行删除命令：

```powershell
gh repo delete dexterlu-coder/pictureAnalyse --yes
```

- 删除命令返回成功。
- 旧仓库验收：
  - `gh repo view dexterlu-coder/pictureAnalyse` 返回无法解析仓库，符合已删除预期。
- 新仓库验收：
  - `gh repo view dexterlu-coder/blueprint-normalizer` 返回成功。
  - 新仓库 URL 仍为 `https://github.com/dexterlu-coder/blueprint-normalizer`。
  - 默认分支仍为 `master`。

后续仍需处理本地主工作区 remote：当前主工作区 `origin` 仍指向旧 URL，不能直接向新仓库普通 push，避免把 269+ 历史推入新仓库。若要保持新仓库单提交历史，优先从新仓库重新 clone 作为主工作区，或继续使用旁路快照方式覆盖推送。

## 本地干净工作区切换需求

旧 GitHub 仓库已删除，新仓库已保持单提交历史。当前打开的本地目录仍是旧历史工作区，`origin` 仍指向已删除的旧仓库 URL。用户确认继续按既定计划执行本地收口。

当前决策：

- 不直接把旧历史工作区 `origin` 改到新仓库后普通 push。
- 不直接删除当前工作区 `.git`。
- 保留当前 `D:\project\codex\BlueprintNormalizer` 作为旧历史备份。
- 在同级目录创建干净 clone：

```text
D:\project\codex\BlueprintNormalizer_clean
```

- 干净 clone 来自：

```text
https://github.com/dexterlu-coder/blueprint-normalizer.git
```

- 验收通过后，后续开发应从干净工作区重新打开 Codex/终端。

详细计划见 `docs/plans/104-local-clean-worktree-switch-plan.md`。

本轮先提交计划、RPD、TODO、HANDOFF 回滚点，再执行联网 clone 和本地非联网验收。

执行结果：

- 已提交本地干净工作区切换执行前回滚点：
  - `b2e02b6 docs: plan local clean worktree switch`
- 已从新仓库 clone 干净工作区：

```text
D:\project\codex\BlueprintNormalizer_clean
```

- 干净工作区验收结果：
  - `git rev-list --count HEAD` 输出 `1`。
  - `git log --oneline -1` 输出 `6eb6b87 Initial snapshot for BlueprintNormalizer`。
  - `git remote -v` 指向 `https://github.com/dexterlu-coder/blueprint-normalizer.git`。
  - `git ls-files local_data .env outputs runs blueprint-normalizer.toml` 无输出。
  - `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。

注意：本轮记录执行结果后仍会覆盖推送新仓库单提交快照，因此需要在覆盖推送后刷新或复验 `D:\project\codex\BlueprintNormalizer_clean`，确保它跟上最终远端提交。

## 当前目录原地重建 Git 历史纠偏需求

用户明确指出上一轮创建 `D:\project\codex\BlueprintNormalizer_clean` 不符合要求。用户原意是：直接在当前 `D:\project\codex\BlueprintNormalizer` 中删除旧 Git 历史，只保留当前最近版本。

问题复盘：

- 为避免误推旧历史，曾采用旁路干净 clone 方案。
- 该方案技术上安全，但改变了用户本地目录结构。
- 这一步应该在执行前询问用户，不应自作主张。

用户已明确授权执行纠偏：

- 删除误创建的 `D:\project\codex\BlueprintNormalizer_clean`。
- 在当前 `D:\project\codex\BlueprintNormalizer` 中删除旧 `.git` 并重新 `git init`。
- 将当前公开快照提交为单个初始提交。
- 设置 `origin` 到 `https://github.com/dexterlu-coder/blueprint-normalizer.git`。
- 验收当前目录提交数、remote、禁区路径和非联网编译检查。
- 覆盖推送到新仓库，保持 GitHub 远端也只有当前单提交。

详细计划见 `docs/plans/105-in-place-single-history-reset-plan.md`。

本轮先提交此纠偏计划作为旧历史删除前最后回滚点，再执行破坏性删除和历史重建。

执行结果：

- 已删除误创建的同级目录：

```text
D:\project\codex\BlueprintNormalizer_clean
```

- 已删除当前目录旧 `.git` 并重新初始化 Git。
- 已将当前公开快照提交为单个初始提交：

```text
Initial snapshot for BlueprintNormalizer
```

- 已设置当前目录 remote：

```text
origin  https://github.com/dexterlu-coder/blueprint-normalizer.git
```

- 本地验收结果：
  - `git rev-list --count HEAD` 输出 `1`。
  - `git remote -v` 指向 `blueprint-normalizer`。
  - `git ls-files local_data .env outputs runs blueprint-normalizer.toml` 无输出。
  - `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
  - `Test-Path D:\project\codex\BlueprintNormalizer_clean` 输出 `False`。
- 已覆盖推送当前目录单提交到新 GitHub 仓库。

当前状态符合用户要求：不再使用额外项目文件夹，当前 `BlueprintNormalizer` 目录自身已是单提交 Git 仓库。

## 本地磁盘数据清理方案需求

用户询问为什么项目文件夹仍超过 5 GB。经只读盘点确认：

- `.git` 已约 1.6 MB，不再是体积来源。
- `local_data/` 约 5.16 GB，是主要体积来源。
- `tools/pdf_rotation_mvp/` 约 387 MB。
- `outputs/` 约 193 MB。
- `runs/` 约 13 MB。

主要大目录：

- `local_data/review_inbox/archive/` 约 2.46 GB。
- `local_data/split_source_pdfs/` 约 372 MB。
- `local_data/experiment_samples/` 约 343 MB。
- `local_data/full_63_title_block_ocr_dry_run/` 约 293 MB。
- `local_data/vlm_title_block_generalization_blind_ykj125/` 约 277 MB。
- `local_data/source_pdfs/` 约 226 MB，默认应保留。
- `tools/pdf_rotation_mvp/work/` 约 202 MB。
- `tools/pdf_rotation_mvp/output/` 约 123 MB。

当前结论：Git 历史已经清理，磁盘占用来自被 `.gitignore` 忽略的本地私有数据、审核包、渲染图、拆分页、模型响应和实验输出。

详细清理方案见 `docs/plans/106-local-data-disk-cleanup-plan.md`。

本轮只制定方案，不删除任何本地数据。后续必须由用户先确认清理档位和具体待删除清单。

## 工程化整理 TODO 展开需求

用户要求不要忘记把后续文件迁移、删除、调整计划写入 TODO。经核对，详细计划已经存在于 `docs/plans/102-project-layout-naming-config-exe-plan.md`，其中包含：

- 目标源码目录。
- 当前路径到目标路径的目录映射。
- 对源码导入、路径解析、MVP 默认目录、配置加载和文档命令的影响。
- 阶段 1 到阶段 6 的实施安排。

因此本轮不新增新的工程化总计划，而是将 `102` 计划中的迁移、删除、调整、测试、打包事项细化写入 `TODO.md`。同时用户已决定跳过本地磁盘数据清理执行，继续工程化整理。

新增 TODO 覆盖范围：

- 阶段 1：`pyproject.toml`、`src/blueprint_normalizer/`、`etc/`、`tests/`、`packaging/` 基础结构。
- 阶段 2：`scripts/*`、`tools/pdf_rotation_mvp/` 到 `src/blueprint_normalizer/` 的迁移。
- 阶段 3：CLI、配置加载、运行目录和 dry-run。
- 阶段 4：`reports/`、`rules/`、`references/` 迁入 `docs/`，README/HANDOFF/索引/命令更新。
- 阶段 5：包导入、配置解析、路径解析、文件名规则、dry-run 非联网测试。
- 阶段 6：PyInstaller spec、发布目录模板和真实配置排除。
- 清理项：废弃或删除旧正式入口、空目录、旧命令说明和过期 TODO。

本轮只更新 TODO/RPD，不执行源码迁移、不删除文件、不调用阿里云。

## TODO 历史完成项压缩需求

用户指出 `TODO.md` 前面已完成的部分应该合并、压缩。经核对，当前 `TODO.md` 已包含大量已完成流水账，继续逐条保留会干扰后续工程化整理执行。

本轮处理原则：

- 不改变真实任务完成状态。
- 不删除可追溯依据，历史细节继续以本 RPD 和 `docs/plans/` 为依据。
- 将已完成任务压缩为阶段摘要。
- 保留当前未完成的工程化整理、MVP 质量修正、审核包、批处理等待办事项。
- 不执行源码迁移、不删除本地数据、不调用阿里云。

详细计划见 `docs/plans/107-todo-compression-plan.md`。

## 阶段 1 项目元信息、配置模板和 CLI 骨架需求

用户确认继续执行下一步计划。按项目工作流，本轮先补阶段 1 细计划、RPD 和 TODO，再提交执行前回滚点，最后才实现工程骨架。

阶段 1 边界：

- 新增 `pyproject.toml`、`src/blueprint_normalizer/`、`etc/`、`tests/`、`packaging/pyinstaller/`。
- 只建立 CLI、配置解析、路径解析和测试骨架。
- 不迁移 `scripts/`、不迁移 `tools/pdf_rotation_mvp/`。
- 不读取真实配置、不读取 `.env/.env`、不打印 API key。
- 不调用阿里云、不处理真实 PDF、不改动固定审核入口。

验收口径：

- 新包文件可编译。
- `python -m blueprint_normalizer --help` 可在开发态通过 `PYTHONPATH=src` 运行。
- 配置模板可解析，`config check` 不泄露密钥。
- 单元测试非联网通过。

阶段 1 细节已统一并入 `docs/plans/102-project-layout-naming-config-exe-plan.md`。

执行结果：

- 已新增 `pyproject.toml`，采用 `src/` 布局，并暴露 `blueprint-normalizer = "blueprint_normalizer.cli:main"`。
- 已新增 `src/blueprint_normalizer/` 基础包：
  - `__init__.py`
  - `__main__.py`
  - `cli.py`
  - `config.py`
  - `paths.py`
- 已新增公开配置模板：
  - `etc/blueprint-normalizer.example.toml`
  - `etc/README.md`
- 已新增测试骨架和 7 个非联网单元测试。
- 已新增 `packaging/pyinstaller/BlueprintNormalizer.spec` 作为 EXE 打包占位。
- 已补充 `.gitignore`，忽略 Python 包元数据和覆盖率产物。

非联网验证结果：

- `python -m compileall src tests` 通过。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer --help` 通过。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer config check --config etc\blueprint-normalizer.example.toml` 通过，仅提示真实运行需要凭据，不打印 API key。
- `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v` 通过，7 个测试全部成功。

本阶段未迁移旧源码、未调用阿里云、未读取真实配置、未改动固定审核入口。

## 阶段 2 计划批判性审核与收窄需求

用户要求用批判性思维、软件工程师思维补充详细计划。经对抗性审核，原阶段 2 TODO 中“一次性迁移 `scripts/*` 和 `tools/pdf_rotation_mvp/`”的范围过大，风险不可控。

主要问题：

- `scripts/*` 覆盖历史实验、YOLO/OBB、OCR、VLM、审核包脚本和联网脚本；一次性迁移会造成导入路径、文档命令、批准命令前缀和本地数据路径同时变化。
- 旧 MVP 仍从 `DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL` 环境变量读取凭据，新目标要求优先读取应用同目录 `blueprint-normalizer.toml`。
- 旧 MVP 默认路径绑定 `tools/pdf_rotation_mvp/input/output/work`，新目标要求应用目录语义。
- 阶段 1 的 PyInstaller spec 只是占位，不能被当成可用打包方案。
- 阶段 5 的集中测试太靠后；阶段 2 每个小步都必须带非联网验收。

修正决策：

- 阶段 2 收窄为“只迁移当前正式 MVP 主线”。
- 暂不迁移 `scripts/*` 历史实验脚本。
- 暂不删除旧 `tools/pdf_rotation_mvp/` 入口。
- 先做只读审计、配置适配、CLI dry-run，再做最小主线迁移。
- 明确阻断条件：可能联网、可能泄露 API key、可能写入固定审核入口、旧入口不可编译、禁区路径进入 Git 时立即停止。

阶段 2 收窄计划已统一并入 `docs/plans/102-project-layout-naming-config-exe-plan.md`。

## 工程化阶段计划统一管理需求

用户要求将所有阶段内容整合，不要把计划分散到不同文件内，后续要能够统一管理。

本轮修正：

- 将阶段 1 细计划从独立文件并入 `docs/plans/102-project-layout-naming-config-exe-plan.md`。
- 将阶段 2 收窄版 MVP 主线迁移计划并入同一个 102 总计划。
- 删除分散阶段计划文件：
  - `docs/plans/108-stage1-project-metadata-config-cli-skeleton-plan.md`
  - `docs/plans/109-stage2-narrow-mvp-migration-plan.md`
- 102 号计划新增“统一实施计划”章节，作为阶段 0 到阶段 7 的唯一管理入口。
- TODO 继续作为当前任务板，RPD 继续作为事实记录，不再为每个工程化阶段新增独立计划文件。

后续规则：

- 工程化阶段范围、风险、验收和阻断条件统一维护在 102 号计划。
- 若阶段计划需要修正，直接修订 102，并同步 RPD/TODO。
- 历史 RPD 记录允许保留旧文件名引用的上下文，但当前有效计划入口以 102 为准。

## 阶段 2 只读审计启动需求

用户确认执行统一计划。按 AGENTS 工作流，阶段 2 不直接迁移源码，先记录执行前边界并建立文档回滚点，然后只读审计旧 MVP 主程序：

```text
tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py
```

当前执行前基线：

- 当前目录：`D:\project\codex\BlueprintNormalizer`。
- 当前唯一提交：`68e863f Initial snapshot for BlueprintNormalizer`。
- 当前有效工程化计划入口：`docs/plans/102-project-layout-naming-config-exe-plan.md`。
- 阶段 2 范围：只处理当前正式 MVP 主线，不迁移 `scripts/*` 历史实验脚本。

只读审计需要输出：

- 函数边界。
- 全局变量和路径默认值。
- 凭据读取点。
- 联网函数。
- Ghostscript 或其他外部命令调用。
- 需要参数化的对象。
- 可优先迁移为纯函数或数据结构的部分。

本小步明确不做：

- 不修改旧 MVP 源码。
- 不新增包内 MVP 实现文件。
- 不调用阿里云、DashScope 或 OpenAI-compatible endpoint。
- 不读取 `.env/.env` 中的真实密钥。
- 不处理真实 PDF。
- 不写入 `local_data/review_inbox/current/`。
- 不删除、覆盖或清理任何本地数据。

执行前文档回滚点：

- 已将阶段 2 启动边界写入 RPD/TODO。
- 已通过 `git commit --amend --no-edit` 保持单提交历史。
- 已通过 `git push --force-with-lease` 推送到新仓库。
- 后续审计记录继续以单提交 amend 方式收口，最终哈希以 `git log -1` 为准。

执行结果：

- 已执行只读审计，目标文件 `tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py` 共 1274 行。
- 旧入口 `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
- 本轮未调用阿里云、未处理真实 PDF、未读取 `.env/.env`、未写入 `local_data/review_inbox/current/`。

只读审计结论：

- 全局默认路径绑定旧工具目录：`SCRIPT_DIR / "input"`、`SCRIPT_DIR / "output"`、`SCRIPT_DIR / "work"`。
- 默认凭据文件为 `REPO_ROOT / ".env" / ".env"`，不符合新目标的同目录 `blueprint-normalizer.toml` 优先策略。
- `load_env()` 会把 env 文件值写入 `os.environ`，`call_vlm_for_records()` 再读取 `DASHSCOPE_API_KEY` 和 `DASHSCOPE_BASE_URL`。
- `post_chat_completion()` 使用 `urllib.request.urlopen()` 发起真实联网 POST 请求；所有联网调用由 `call_vlm_for_records()` 触发。
- Ghostscript 依赖集中在 `find_ghostscript()`、`run_command()`、`render_pdf_page()`，查找 `gswin64c`、`gswin32c` 或 `gs`。
- `run()` 会执行 `safe_reset_child_dir(work_dir, SCRIPT_DIR)` 并清空每个输入 PDF 对应的输出子目录；迁移时必须把清空行为变成显式、可审计、限制在应用工作目录内的动作。
- 旧脚本 `--dry-run` 仍会读取输入 PDF、拆分页、渲染 PNG、写 work/output 报告和复制 needs-review PDF；不能把它直接当作阶段 2 新 CLI dry-run。
- 可优先迁移为纯函数的对象包括：`safe_name()`、`normalize_drawing_number()`、`drawing_number_filename_status()`、位置映射、响应 JSON 解析、响应校验、决策构建和报告行构建。
- 需要参数化或隔离的对象包括：`SCRIPT_DIR`、`REPO_ROOT`、默认 `input/output/work`、默认 env 文件、模型参数、联网 endpoint、Ghostscript 查找与执行、路径清空策略、输入 PDF 收集、最终发布目录。

## 阶段 2 包内 MVP dry-run 实施边界

旧 MVP 只读审计完成后，下一小步是创建包内 MVP 目录，并提供真正无副作用的 `pdf-rotation-mvp dry-run`。

实施范围：

- 新增 `src/blueprint_normalizer/pdf_rotation_mvp/` 包目录。
- 新增包内 `cli.py`、`pipeline.py`、`legacy_adapter.py` 和基础占位目录。
- 将主 CLI 挂载 `blueprint-normalizer pdf-rotation-mvp dry-run`。
- dry-run 只解析配置、计算输入/输出/工作/日志目录、返回脱敏状态和检查结果。
- dry-run 不读取 `.env/.env`，不读取真实 API key 内容，不调用阿里云，不处理真实 PDF，不调用 Ghostscript，不创建输出目录，不写 `local_data/review_inbox/current/`。

验收：

- 新包文件可编译。
- CLI help 可显示 `pdf-rotation-mvp`。
- `pdf-rotation-mvp dry-run --config etc/blueprint-normalizer.example.toml` 可运行并返回非联网结构检查结果。
- 测试覆盖 dry-run 不写文件、不泄露假 key、显式 `--config` 优先。
- 禁区路径未进入 Git。

执行结果：

- 已新增 `src/blueprint_normalizer/pdf_rotation_mvp/` 包目录。
- 已新增 `cli.py`、`pipeline.py`、`legacy_adapter.py`、`prompts/.gitkeep`、`schemas/.gitkeep`。
- 已在主 CLI 中挂载 `pdf-rotation-mvp dry-run`。
- dry-run 当前只读取指定 TOML 配置，输出脱敏配置、模型状态、路径解析结果和 side-effect 标记。
- `legacy_adapter.py` 只记录旧入口边界，不导入也不执行旧脚本。

验证结果：

- `python -m compileall src tests` 通过。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer --help` 通过，显示 `pdf-rotation-mvp`。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer pdf-rotation-mvp --help` 通过。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer pdf-rotation-mvp dry-run --config etc\blueprint-normalizer.example.toml` 通过。
- `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v` 通过，9 个测试全部成功。
- 测试确认假 key 不出现在 stdout，显式 `--config` 被使用，dry-run 不创建 `input/output/work/logs` 目录。
- 本轮未调用阿里云、未处理真实 PDF、未读取 `.env/.env`、未写入 `local_data/review_inbox/current/`。

## 阶段 2 第一批纯逻辑迁移边界

用户要求继续推进计划。下一小步迁移旧 MVP 中最小、可测试、无副作用的纯逻辑，为后续主线迁移打底。

实施范围：

- 从 `tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py` 迁移文件名清洗和图号规范化逻辑。
- 迁移标题栏位置常量、别名、位置到旋转角度映射。
- 迁移模型响应内容提取、JSON 解析、方向响应校验、方向决策构建。
- 迁移图号响应校验和图号决策构建。
- 为上述逻辑新增单元测试，覆盖成功、非法字段、缺失图号、非法文件名、Markdown JSON 包裹等关键分支。

明确不做：

- 不迁移 PDF 拆分、PDF 旋转、Ghostscript 渲染、图片 crop、VLM 联网、目录清空、最终 PDF 发布。
- 不读取 `.env/.env` 或真实 `blueprint-normalizer.toml`。
- 不调用阿里云、DashScope 或 OpenAI-compatible endpoint。
- 不处理真实 PDF。
- 不写入 `local_data/review_inbox/current/`。

验收：

- 新纯逻辑模块可编译。
- 新增单元测试通过。
- 现有 dry-run 行为保持无副作用。
- 旧入口仍可 `py_compile`。
- 禁区路径未进入 Git。

执行结果：

- 已新增 `src/blueprint_normalizer/pdf_rotation_mvp/domain.py`。
- 已迁移第一批纯函数和常量：`safe_name()`、`normalize_drawing_number()`、`drawing_number_filename_status()`、位置映射、`extract_message_content()`、`parse_json_content()`、方向决策构建、图号决策构建。
- 已新增 `tests/unit/test_pdf_rotation_mvp_domain.py`，覆盖旧脚本关键行为。
- 本轮仍未迁移 PDF 拆分、PDF 旋转、Ghostscript、VLM 联网、目录清空、最终发布等副作用逻辑。

验证结果：

- `python -m compileall src tests` 通过。
- `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v` 通过，17 个测试全部成功。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer pdf-rotation-mvp dry-run --config etc\blueprint-normalizer.example.toml` 通过，side-effect 标记仍全部为 `false`。
- `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
- `git ls-files local_data .env outputs runs blueprint-normalizer.toml` 无输出。
- 本轮未调用阿里云、未处理真实 PDF、未读取 `.env/.env`、未写入 `local_data/review_inbox/current/`。

## 阶段 2 运行配置适配边界

用户要求继续执行计划。下一小步将路径参数和 MVP 运行配置对象从 `pipeline.py` 的临时 dry-run 逻辑中抽离出来，使后续主线迁移可以依赖统一配置结构。

实施范围：

- 新增包内运行配置适配模块。
- 将 TOML 中的 `[qwen]`、`[paths]`、`[runtime]` 转换为明确的数据结构。
- 路径字段只做解析和存在性检查，不创建目录。
- API key 只记录是否存在，不在运行配置报告中暴露真实值。
- `build_dry_run_report()` 复用运行配置对象，保持当前 JSON 输出兼容。
- 新增单元测试覆盖显式配置、相对路径解析、缺失配置、脱敏和 dry-run 无副作用。

明确不做：

- 不读取 `.env/.env`。
- 不调用阿里云、DashScope 或 OpenAI-compatible endpoint。
- 不处理真实 PDF。
- 不调用 Ghostscript。
- 不创建、清空或删除任何 input/output/work/logs 目录。
- 不写入 `local_data/review_inbox/current/`。

验收：

- 新配置适配模块可编译。
- dry-run 输出仍显示 side-effect 全部为 `false`。
- 单元测试通过。
- 旧入口仍可 `py_compile`。
- 禁区路径未进入 Git。

执行结果：

- 已新增 `src/blueprint_normalizer/pdf_rotation_mvp/runtime_config.py`。
- 已新增运行配置数据结构：`PathSetting`、`QwenRuntimeConfig`、`RuntimeOptions`、`MvpRunConfig`。
- 已新增 `load_mvp_run_config()`，将 TOML 转换为包内运行配置对象。
- 已将 `build_dry_run_report()` 改为复用运行配置对象，不再在 `pipeline.py` 中散落解析 TOML。
- 运行配置对象不保存 API key 原文，只记录 `api_key_present`，报告中继续使用脱敏配置。
- 路径字段只解析为绝对路径并检查存在性，不创建目录。
- 已新增 `tests/unit/test_pdf_rotation_mvp_runtime_config.py`，覆盖显式配置、相对路径、缺失配置和脱敏。

验证结果：

- `python -m compileall src tests` 通过。
- `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v` 通过，19 个测试全部成功。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer pdf-rotation-mvp dry-run --config etc\blueprint-normalizer.example.toml` 通过，side-effect 标记仍全部为 `false`。
- `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
- 本轮未调用阿里云、未处理真实 PDF、未读取 `.env/.env`、未调用 Ghostscript、未创建运行目录、未写入 `local_data/review_inbox/current/`。

## 阶段 2 副作用边界对象实施边界

用户已剪切带走临时资料包，要求回到主线继续执行原定计划。下一小步将为未来真实 `run` 建立执行计划对象，把旧 MVP 中会产生副作用的步骤先建模出来，但不执行任何副作用。

实施范围：

- 新增包内执行计划模块。
- 将未来 MVP 主线拆成显式步骤：
  - 配置加载。
  - 输入 PDF 收集。
  - 工作目录准备。
  - PDF 拆分。
  - Ghostscript 渲染。
  - 方向 VLM 请求。
  - PDF 旋正或复制。
  - 标题栏 crop。
  - 图号 VLM 请求。
  - 最终 PDF 发布。
  - 报告输出。
- 每个步骤记录是否会读取 PDF、写文件、调用外部命令、联网、触碰审核入口。
- dry-run 可输出执行计划摘要，帮助后续审查真实 `run` 的副作用边界。

明确不做：

- 不读取真实 PDF。
- 不创建、清空或删除 input/output/work/logs 目录。
- 不调用 Ghostscript。
- 不调用阿里云、DashScope 或 OpenAI-compatible endpoint。
- 不读取 `.env/.env`。
- 不写入 `local_data/review_inbox/current/`。
- 不迁移旧 MVP 的 PDF 处理函数。

验收：

- 新执行计划模块可编译。
- dry-run side-effect 顶层标记仍全部为 `false`。
- dry-run 输出计划步骤，但每个步骤只是描述，不执行。
- 单元测试覆盖步骤顺序和副作用标记。
- 旧入口仍可 `py_compile`。
- 禁区路径未进入 Git。

执行结果：

- 已新增 `src/blueprint_normalizer/pdf_rotation_mvp/execution_plan.py`。
- 已新增 `ExecutionStep` 和 `MvpExecutionPlan` 数据结构。
- 已新增 `build_execution_plan()`，将未来真实 `run` 拆成 11 个显式步骤。
- 执行计划步骤覆盖配置加载、输入 PDF 收集、工作目录准备、PDF 拆分、Ghostscript 渲染、方向 VLM 请求、PDF 旋正或复制、标题栏 crop、图号 VLM 请求、最终 PDF 发布和报告输出。
- 每个步骤均记录 `reads_pdf`、`writes_files`、`calls_external_command`、`calls_model_endpoint`、`touches_review_inbox` 和 `enabled_for_dry_run`。
- `build_dry_run_report()` 已输出 `execution_plan` 摘要；该摘要只描述未来真实运行的副作用，不代表 dry-run 已执行这些步骤。
- 为避免 Windows 控制台编码导致 JSON 步骤标题乱码，执行计划中的机器可读 `title` 使用 ASCII 英文；中文步骤说明保留在 RPD/TODO 中。
- 已新增 `tests/unit/test_pdf_rotation_mvp_execution_plan.py`，覆盖步骤顺序、Ghostscript/VLM/PDF 发布关键标记，以及 dry-run 不创建目录。

验证结果：

- `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v` 通过，21 个测试全部成功。
- `python -m compileall src tests` 通过。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer pdf-rotation-mvp dry-run --config etc\blueprint-normalizer.example.toml` 通过，顶层 `side_effects` 仍全部为 `false`，且输出 `execution_plan`。
- 本轮未调用阿里云、未处理真实 PDF、未读取 `.env/.env`、未调用 Ghostscript、未创建运行目录、未写入 `local_data/review_inbox/current/`。

## 阶段 2 最小 MVP 主线数据骨架迁移边界

下一小步继续迁移旧 `tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py` 中的主线结构，但只迁移无副作用的数据骨架和报告组装逻辑。该步骤为后续真实 `run` 铺垫，不接入 PDF 读取、Ghostscript、阿里云模型调用或文件发布。

实施范围：

- 新增包内主线数据骨架模块。
- 迁移 `PageRecord` 和 `ImageRecord` 记录结构。
- 迁移 `image_records_from_pages()`，用于从拆页记录派生 VLM 图片任务记录。
- 迁移 `build_report_rows()`，用于合并方向决策、旋转输出、图号决策和最终发布结果。
- 单元测试覆盖：
  - 图片记录派生字段保持旧脚本语义。
  - 报告行按 `task_id` 合并多个阶段结果。
  - 缺失阶段结果时输出空值而不是异常。

明确不做：

- 不读取真实 PDF。
- 不枚举输入目录。
- 不创建、清空或删除 input/output/work/logs 目录。
- 不调用 Ghostscript。
- 不调用阿里云、DashScope 或 OpenAI-compatible endpoint。
- 不读取 `.env/.env`。
- 不旋转、复制或发布 PDF。
- 不写入报告文件或 `local_data/review_inbox/current/`。
- 不改旧 MVP 入口行为，旧脚本继续作为回归对照。

验收：

- 新主线数据骨架模块可编译。
- dry-run 顶层 side-effect 标记仍全部为 `false`。
- 单元测试覆盖主线数据骨架和报告行组装。
- 旧入口仍可 `py_compile`。
- 禁区路径未进入 Git。

执行结果：

- 已新增 `src/blueprint_normalizer/pdf_rotation_mvp/workflow.py`。
- 已迁移 `PageRecord`、`ImageRecord` 数据结构。
- 已迁移 `as_posix()` 路径展示辅助；包内版本支持注入 root，便于测试和后续封装。
- 已迁移 `image_records_from_pages()`，用于从页面记录派生 VLM 图片记录。
- 已迁移 `build_report_rows()`，用于按 `task_id` 合并方向决策、旋转输出、图号决策和最终发布结果。
- 已新增 `tests/unit/test_pdf_rotation_mvp_workflow.py`，覆盖图片记录派生、报告字段合并和缺失阶段结果兜底。

验证结果：

- `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v` 通过，24 个测试全部成功。
- `python -m compileall src tests` 通过。
- `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer pdf-rotation-mvp dry-run --config etc\blueprint-normalizer.example.toml` 通过，顶层 `side_effects` 仍全部为 `false`。
- `git ls-files local_data .env outputs runs blueprint-normalizer.toml` 无输出。
- 本轮未调用阿里云、未处理真实 PDF、未读取 `.env/.env`、未调用 Ghostscript、未创建运行目录、未写入 `local_data/review_inbox/current/`。

## 阶段 2 输入收集和目录安全守门迁移边界

下一小步继续接入最小 MVP 主线，但只迁移输入收集和受控目录安全守门能力。该步骤仍不处理 PDF 内容、不调用 Ghostscript、不调用模型、不发布文件，目标是先把真实 `run` 前的路径边界建立清楚。

实施范围：

- 迁移 `collect_input_pdfs()` 到包内模块，只枚举输入目录下一层 `.pdf` 文件。
- PDF 收集逻辑只检查路径、文件类型和排序，不打开或解析 PDF 内容。
- 新增受控目录安全 helper：
  - 判断候选路径是否位于允许根目录下。
  - 拒绝把允许根目录自身作为可创建或可重置目标。
  - 可创建受控子目录，但不清空、不删除已有内容。
- 单元测试覆盖：
  - 缺失输入目录报错。
  - 空输入目录报错。
  - `.pdf` 后缀大小写兼容，非 PDF 文件被忽略。
  - 结果排序稳定。
  - 越界路径和根目录自身被拒绝。

明确不做：

- 不读取真实 PDF 内容。
- 不递归扫描输入目录。
- 不清空、删除或移动任何目录。
- 不迁移旧脚本 `safe_reset_child_dir()` 的删除逻辑。
- 不调用 Ghostscript。
- 不调用阿里云、DashScope 或 OpenAI-compatible endpoint。
- 不读取 `.env/.env`。
- 不写入报告文件或 `local_data/review_inbox/current/`。
- 不改旧 MVP 入口行为，旧脚本继续作为回归对照。

验收：

- 新输入收集和目录安全 helper 可编译。
- dry-run 顶层 side-effect 标记仍全部为 `false`。
- 单元测试覆盖输入收集和路径守门。
- 旧入口仍可 `py_compile`。
- 禁区路径未进入 Git。

执行结果：

- 已新增 `src/blueprint_normalizer/pdf_rotation_mvp/io_boundary.py`。
- 已迁移 `collect_input_pdfs()` 到包内模块，只枚举输入目录下一层 `.pdf` 文件，并按路径稳定排序。
- 已新增 `ensure_path_under_root()`，用于解析并校验候选路径必须位于允许根目录下。
- 已新增 `ensure_child_dir()`，用于创建受控子目录；该 helper 不清空、不删除已有内容。
- 旧脚本 `safe_reset_child_dir()` 的删除逻辑本轮未迁移，后续若需要必须单独规划和复核。
- 已新增 `tests/unit/test_pdf_rotation_mvp_io_boundary.py`，覆盖缺失目录、空目录、大小写 PDF 后缀、非递归枚举、越界路径拒绝和根目录自身拒绝。

验证结果：

- `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v` 通过，28 个测试全部成功。
- `python -m compileall src tests` 通过。
- `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer pdf-rotation-mvp dry-run --config etc\blueprint-normalizer.example.toml` 通过，顶层 `side_effects` 仍全部为 `false`。
- `git ls-files local_data .env outputs runs blueprint-normalizer.toml` 无输出。
- 本轮未调用阿里云、未处理真实 PDF、未读取 `.env/.env`、未调用 Ghostscript、未清空/删除目录、未写入 `local_data/review_inbox/current/`。

## 阶段 2 报告写出工具迁移边界

下一小步迁移旧 MVP 中的报告写出工具，为后续真实 `run` 输出机器报告做准备。该步骤只迁移 JSON、JSONL、CSV 的序列化函数，并只在单元测试临时目录中验证写出行为；不会接入 dry-run，也不会写入项目运行目录、真实输出目录或审核入口。

实施范围：

- 新增包内报告写出模块。
- 迁移 `write_json()`：
  - 自动创建父目录。
  - 使用 UTF-8。
  - `ensure_ascii=False`。
  - 缩进 2 空格并以换行结尾。
- 迁移 `write_jsonl()`：
  - 自动创建父目录。
  - 每行一个 JSON 对象。
  - 使用 UTF-8 和 `ensure_ascii=False`。
- 迁移 `write_csv()`：
  - 自动创建父目录。
  - 使用 UTF-8-SIG，兼容 Excel。
  - `extrasaction="ignore"`，忽略多余字段。
  - 空 rows 时仍按传入 fieldnames 写表头。
- 单元测试只在 `tempfile.TemporaryDirectory()` 内写入测试文件。

明确不做：

- 不接入 `pipeline.build_dry_run_report()`。
- 不写入真实 `output_dir`、`work_dir`、`log_dir`。
- 不写入 `local_data/review_inbox/current/`。
- 不读取真实 PDF。
- 不调用 Ghostscript。
- 不调用阿里云、DashScope 或 OpenAI-compatible endpoint。
- 不读取 `.env/.env`。
- 不改旧 MVP 入口行为，旧脚本继续作为回归对照。

验收：

- 新报告写出模块可编译。
- 单元测试覆盖 JSON、JSONL、CSV 写出行为。
- dry-run 顶层 side-effect 标记仍全部为 `false`。
- 旧入口仍可 `py_compile`。
- 禁区路径未进入 Git。

执行结果：

- 已新增 `src/blueprint_normalizer/pdf_rotation_mvp/report_writer.py`。
- 已迁移 `write_json()`，保持 UTF-8、`ensure_ascii=False`、2 空格缩进和末尾换行。
- 已迁移 `write_jsonl()`，保持每行一个 JSON 对象、UTF-8 和 `ensure_ascii=False`。
- 已迁移 `write_csv()`，保持 UTF-8-SIG、`extrasaction="ignore"` 和空 rows 写表头行为。
- 已新增 `tests/unit/test_pdf_rotation_mvp_report_writer.py`，覆盖 JSON 中文内容、JSONL 行格式、CSV BOM、忽略多余字段和空表头写出。
- 报告写出工具本轮只在单元测试临时目录中执行，未接入 dry-run 或真实运行目录。

验证结果：

- `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v` 通过，32 个测试全部成功。
- `python -m compileall src tests` 通过。
- `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer pdf-rotation-mvp dry-run --config etc\blueprint-normalizer.example.toml` 通过，顶层 `side_effects` 仍全部为 `false`。
- `git ls-files local_data .env outputs runs blueprint-normalizer.toml` 无输出。
- 本轮未调用阿里云、未处理真实 PDF、未读取 `.env/.env`、未调用 Ghostscript、未写入真实输出目录、未写入 `local_data/review_inbox/current/`。

## 阶段 2 MVP prompt 资产迁移边界

下一小步迁移旧 MVP 中的两段模型提示词资产。目标是把旧 `tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py` 中的 `TITLE_BLOCK_ONLY_PROMPT` 和 `DRAWING_NUMBER_PROMPT` 从脚本常量迁到包内资源文件，并提供稳定读取 helper，为后续真实 `run` 接入模型调用做准备。

实施范围：

- 新增包内 prompt 资源文件：
  - `src/blueprint_normalizer/pdf_rotation_mvp/prompts/title_block_only.md`
  - `src/blueprint_normalizer/pdf_rotation_mvp/prompts/drawing_number.md`
- 新增 prompt 读取 helper。
- 更新打包配置，确保 prompt 资源进入 wheel/EXE 构建输入。
- 单元测试覆盖：
  - prompt 资源可读取。
  - prompt 保留中文说明。
  - prompt 包含关键 JSON 字段约束。
  - 未知 prompt 名称会失败，而不是静默返回空文本。

明确不做：

- 不调用阿里云、DashScope 或 OpenAI-compatible endpoint。
- 不读取 `.env/.env`。
- 不读取或处理真实 PDF。
- 不调用 Ghostscript。
- 不接入 `pipeline.build_dry_run_report()` 的真实模型请求。
- 不写入真实输出目录或 `local_data/review_inbox/current/`。
- 不改旧 MVP 入口行为，旧脚本继续作为回归对照。

验收：

- 新 prompt 资源和读取 helper 可编译。
- 单元测试覆盖 prompt 资源读取。
- dry-run 顶层 side-effect 标记仍全部为 `false`。
- 旧入口仍可 `py_compile`。
- 禁区路径未进入 Git。

执行结果：

- 已新增 `src/blueprint_normalizer/pdf_rotation_mvp/prompts/title_block_only.md`。
- 已新增 `src/blueprint_normalizer/pdf_rotation_mvp/prompts/drawing_number.md`。
- 已新增 `src/blueprint_normalizer/pdf_rotation_mvp/prompts.py`，提供 `load_prompt()` 和 prompt 名称映射。
- 已更新 `pyproject.toml`，将 `blueprint_normalizer.pdf_rotation_mvp` 的 `prompts/*.md` 纳入 package data。
- 已新增 `tests/unit/test_pdf_rotation_mvp_prompts.py`，覆盖 prompt 资源读取、中文内容、关键 JSON 字段和未知名称错误。
- 本轮只迁移 prompt 资产，未将 prompt 接入真实模型调用。

验证结果：

- `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v` 通过，34 个测试全部成功。
- `python -m compileall src tests` 通过。
- `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer pdf-rotation-mvp dry-run --config etc\blueprint-normalizer.example.toml` 通过，顶层 `side_effects` 仍全部为 `false`。
- `git ls-files local_data .env outputs runs blueprint-normalizer.toml` 无输出。
- 本轮未调用阿里云、未处理真实 PDF、未读取 `.env/.env`、未调用 Ghostscript、未写入真实输出目录、未写入 `local_data/review_inbox/current/`。

## 阶段 2 VLM 请求构造迁移边界

下一小步迁移旧 MVP 中的 VLM 请求构造逻辑，为后续真实 `run` 接入模型调用做准备。该步骤只迁移 endpoint 归一化、图片 data URL、请求 body 和公开日志脱敏逻辑；不迁移 HTTP 调用，不触发任何阿里云、DashScope 或 OpenAI-compatible endpoint 请求。

实施范围：

- 新增包内 VLM 请求构造模块。
- 迁移 `endpoint_from_base_url()`：
  - 兼容 `/compatible-mode/v1`。
  - 兼容 `/api/v1`。
  - 兼容已包含 `/chat/completions` 的完整 endpoint。
  - 空 base URL 显式失败。
- 迁移 `data_url_for()`：
  - 读取传入图片文件。
  - 生成 `data:<mime>;base64,<payload>` 格式。
  - 单元测试只使用临时小文件，不读取真实图纸。
- 迁移 `build_request_body()`：
  - 保留 OpenAI-compatible chat completions body 结构。
  - 保留 `temperature=0`。
  - 保留 JSON object 响应格式约束。
  - 保留 `enable_thinking=False`。
- 迁移 `redacted_request_row()` 和 `public_raw_row()`：
  - 保持请求记录中的图片 data URL 脱敏。
  - 保持公开 raw response 行不暴露大体量或不必要响应文本。

明确不做：

- 不迁移 `post_chat_completion()`。
- 不调用阿里云、DashScope 或 OpenAI-compatible endpoint。
- 不读取 `.env/.env`。
- 不读取或处理真实图纸、真实图片或 PDF。
- 不调用 Ghostscript。
- 不写入真实输出目录。
- 不写入 `local_data/review_inbox/current/`。
- 不改旧 MVP 入口行为，旧脚本继续作为回归对照。

验收：

- 新 VLM 请求构造模块可编译。
- 单元测试覆盖 endpoint 兼容路径、base64 data URL、请求体结构和脱敏输出。
- dry-run 顶层 side-effect 标记仍全部为 `false`。
- 旧入口仍可 `py_compile`。
- 禁区路径未进入 Git。

执行结果：

- 已新增 `src/blueprint_normalizer/pdf_rotation_mvp/vlm_request.py`。
- 已迁移 `endpoint_from_base_url()`，保持 `/compatible-mode/v1`、`/api/v1`、完整 `/chat/completions` 和空 base URL 失败逻辑。
- 已迁移 `data_url_for()`，保持 `data:<mime>;base64,<payload>` 输出格式。
- 已迁移 `build_request_body()`，保持 OpenAI-compatible chat completions 请求体结构、`temperature=0`、JSON object 响应格式和 `enable_thinking=False`。
- 已迁移 `redacted_request_row()`，复用包内 `build_request_body()` 并保持图片 data URL 脱敏为 `<omitted_png_data_url:...>`。
- 已迁移 `public_raw_row()`，保持公开 raw response 行包含 `record_version`，且 response JSON 存在时不输出冗余 `response_text`。
- 已新增 `tests/unit/test_pdf_rotation_mvp_vlm_request.py`，覆盖 endpoint 归一化、base64 data URL、请求体结构、脱敏请求行和公开 raw row。
- 本轮只迁移请求构造和脱敏逻辑，未迁移 `post_chat_completion()`，未发起真实模型请求。

验证结果：

- `$env:PYTHONPATH='src'; python -m unittest tests.unit.test_pdf_rotation_mvp_vlm_request -v` 通过，7 个测试全部成功。
- `python -m py_compile src\blueprint_normalizer\pdf_rotation_mvp\vlm_request.py tests\unit\test_pdf_rotation_mvp_vlm_request.py` 通过。
- `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v` 通过，41 个测试全部成功。
- `python -m compileall src tests` 通过。
- `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer pdf-rotation-mvp dry-run --config etc\blueprint-normalizer.example.toml` 通过，顶层 `side_effects` 仍全部为 `false`。
- `git ls-files local_data .env outputs runs blueprint-normalizer.toml` 无输出。
- 本轮未调用阿里云、未处理真实 PDF、未读取 `.env/.env`、未调用 Ghostscript、未写入真实输出目录、未写入 `local_data/review_inbox/current/`。

## 阶段 2 MVP run summary 主线骨架迁移边界

下一小步迁移旧 MVP `run()` 末尾的 summary 聚合逻辑。该步骤只把已完成各阶段的记录聚合成最终 summary 字典，并构造输出文件清单；不接入目录准备、拆页、Ghostscript、HTTP 调用、PDF 旋转、标题栏裁剪、报告写出或 CLI `run` 命令。

实施范围：

- 新增包内 run summary 模块。
- 迁移旧 `run()` 中 summary 字段的纯聚合逻辑：
  - `record_version`
  - 输入、输出、工作目录
  - 模型与固定推理参数
  - dry-run 标记
  - source/page 计数
  - 方向判断 API/parse/schema 成功计数
  - 图号识别 API/parse/schema 成功计数
  - 图号非空计数
  - PDF 校正、复制复核、发布和最终复核计数
  - env 状态
  - 输出文件清单
- 单元测试使用构造出的内存记录和临时路径，不读取真实 PDF、不写真实报告。

明确不做：

- 不迁移 `split_and_render_pdfs()`。
- 不迁移 `call_vlm_for_records()` 或 `post_chat_completion()`。
- 不迁移 `rotate_or_copy_pdf()`、`build_corrected_crop_records()` 或 `publish_final_pdfs()`。
- 不调用阿里云、DashScope 或 OpenAI-compatible endpoint。
- 不读取 `.env/.env`。
- 不读取或处理真实图纸、真实图片或 PDF。
- 不调用 Ghostscript。
- 不写入真实输出目录。
- 不写入 `local_data/review_inbox/current/`。
- 不新增 CLI `run` 命令。
- 不改旧 MVP 入口行为，旧脚本继续作为回归对照。

验收：

- 新 run summary 模块可编译。
- 单元测试覆盖关键计数和输出路径清单。
- dry-run 顶层 side-effect 标记仍全部为 `false`。
- 旧入口仍可 `py_compile`。
- 禁区路径未进入 Git。

执行结果：

- 已新增 `src/blueprint_normalizer/pdf_rotation_mvp/run_summary.py`。
- 已迁移 `build_run_summary()`，聚合输入/输出/工作目录、模型、固定推理参数、dry-run 标记、source/page 计数、方向判断计数、图号识别计数、输出状态计数、env 状态和输出文件清单。
- 已新增 `tests/unit/test_pdf_rotation_mvp_run_summary.py`，覆盖关键计数、非 published 结果复核计数、输出路径清单和 root 相对路径。
- 本轮只迁移旧 `run()` 末尾 summary 聚合逻辑，未接入目录准备、拆页渲染、模型请求、PDF 旋转、标题栏裁剪、报告写出或 CLI `run` 命令。

验证结果：

- `$env:PYTHONPATH='src'; python -m unittest tests.unit.test_pdf_rotation_mvp_run_summary -v` 通过，2 个测试全部成功。
- `python -m py_compile src\blueprint_normalizer\pdf_rotation_mvp\run_summary.py tests\unit\test_pdf_rotation_mvp_run_summary.py` 通过。
- `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v` 通过，43 个测试全部成功。
- `python -m compileall src tests` 通过。
- `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer pdf-rotation-mvp dry-run --config etc\blueprint-normalizer.example.toml` 通过，顶层 `side_effects` 仍全部为 `false`。
- `git ls-files local_data .env outputs runs blueprint-normalizer.toml` 无输出。
- 本轮未调用阿里云、未处理真实 PDF、未读取 `.env/.env`、未调用 Ghostscript、未写入真实输出目录、未写入 `local_data/review_inbox/current/`。

## 阶段 2 MVP run orchestrator 守门骨架迁移边界

下一小步新增包内真实运行入口的守门骨架。目标是让未来 CLI `run` 有一个明确的包内落点，但当前默认只返回“真实运行尚未启用”的报告，不执行任何旧 MVP 副作用步骤。

实施范围：

- 在包内 pipeline 增加真实运行禁用报告函数。
- 复用 `load_mvp_run_config()` 加载配置。
- 复用 `build_execution_plan()` 列出未来真实运行步骤。
- 报告中显式标记：
  - 真实 run 未启用。
  - 本次未读取 `.env/.env`。
  - 本次未读取 PDF。
  - 本次未调用模型 endpoint。
  - 本次未调用 Ghostscript。
  - 本次未创建目录或写输出。
  - 本次未写入 `local_data/review_inbox/current/`。
- 单元测试只调用守门函数，不接 CLI `run` 命令。

明确不做：

- 不新增 CLI `pdf-rotation-mvp run` 命令。
- 不迁移 `split_and_render_pdfs()`。
- 不迁移 `call_vlm_for_records()` 或 `post_chat_completion()`。
- 不迁移 PDF 旋转、标题栏裁剪、最终发布或真实报告写出。
- 不调用阿里云、DashScope 或 OpenAI-compatible endpoint。
- 不读取 `.env/.env`。
- 不读取或处理真实图纸、真实图片或 PDF。
- 不调用 Ghostscript。
- 不写入真实输出目录。
- 不写入 `local_data/review_inbox/current/`。
- 不改旧 MVP 入口行为，旧脚本继续作为回归对照。

验收：

- 守门函数可编译。
- 单元测试覆盖默认不执行副作用、配置错误透传和未来步骤清单。
- dry-run 顶层 side-effect 标记仍全部为 `false`。
- 旧入口仍可 `py_compile`。
- 禁区路径未进入 Git。

执行结果：

- 已在 `src/blueprint_normalizer/pdf_rotation_mvp/pipeline.py` 新增 `no_side_effects()`，统一 dry-run 与 run-disabled 报告的顶层副作用标记。
- 已新增 `build_run_disabled_report()`，复用 `load_mvp_run_config()` 和 `build_execution_plan()`，返回 `pdf_rotation_mvp_run_disabled` 报告。
- `build_run_disabled_report()` 当前始终 `ok=false`、`run_enabled=false`，并通过 `blockers` 明确标记 `run_not_enabled`；配置失败时额外标记 `config_not_ok`。
- 已新增 `tests/unit/test_pdf_rotation_mvp_run_orchestrator.py`，覆盖默认不执行副作用、不创建运行目录、配置错误透传和未来步骤清单。
- 本轮只新增包内真实 run 的禁用守门骨架，未新增 CLI `run` 命令，未接入任何真实副作用步骤。

验证结果：

- `$env:PYTHONPATH='src'; python -m unittest tests.unit.test_pdf_rotation_mvp_run_orchestrator -v` 通过，2 个测试全部成功。
- `python -m py_compile src\blueprint_normalizer\pdf_rotation_mvp\pipeline.py tests\unit\test_pdf_rotation_mvp_run_orchestrator.py` 通过。
- `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v` 通过，45 个测试全部成功。
- `python -m compileall src tests` 通过。
- `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer pdf-rotation-mvp dry-run --config etc\blueprint-normalizer.example.toml` 通过，顶层 `side_effects` 仍全部为 `false`。
- `git ls-files local_data .env outputs runs blueprint-normalizer.toml` 无输出。
- 本轮未调用阿里云、未处理真实 PDF、未读取 `.env/.env`、未调用 Ghostscript、未写入真实输出目录、未写入 `local_data/review_inbox/current/`。

## 阶段 2 收尾非联网检查记录

本轮对阶段 2 中已完成的非联网收尾项做集中确认。该检查只验证入口、编译、dry-run 和 Git 禁区状态；未接入真实 MVP `run`，也未迁移 `scripts/*` 历史实验脚本。

执行结果：

- 旧入口 `tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py` 继续保留，作为回归对照；本轮未改为薄 wrapper。
- `scripts/*` 历史实验脚本继续后置到单独阶段，不作为阶段 2 当前执行项。
- 阶段 2 的“迁移最小 MVP 主线到包内模块”仍未标记完成，因为真实拆页渲染、模型请求、旋转发布和报告写出尚未接入包内执行。

验证结果：

- `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
- `python -m py_compile src\blueprint_normalizer\pdf_rotation_mvp\__init__.py src\blueprint_normalizer\pdf_rotation_mvp\cli.py src\blueprint_normalizer\pdf_rotation_mvp\domain.py src\blueprint_normalizer\pdf_rotation_mvp\execution_plan.py src\blueprint_normalizer\pdf_rotation_mvp\io_boundary.py src\blueprint_normalizer\pdf_rotation_mvp\legacy_adapter.py src\blueprint_normalizer\pdf_rotation_mvp\pipeline.py src\blueprint_normalizer\pdf_rotation_mvp\prompts.py src\blueprint_normalizer\pdf_rotation_mvp\report_writer.py src\blueprint_normalizer\pdf_rotation_mvp\run_summary.py src\blueprint_normalizer\pdf_rotation_mvp\runtime_config.py src\blueprint_normalizer\pdf_rotation_mvp\vlm_request.py src\blueprint_normalizer\pdf_rotation_mvp\workflow.py` 通过。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer --help` 通过。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer config check --config etc\blueprint-normalizer.example.toml` 通过，未打印 API key，只提示示例配置缺少真实 Qwen 凭据。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer pdf-rotation-mvp dry-run --config etc\blueprint-normalizer.example.toml` 已在本轮 run orchestrator 验证中通过，顶层 `side_effects` 全部为 `false`。
- `git ls-files local_data .env outputs runs blueprint-normalizer.toml` 无输出。
- 本轮未调用阿里云、未处理真实 PDF、未读取 `.env/.env`、未调用 Ghostscript、未写入真实输出目录、未写入 `local_data/review_inbox/current/`。

## 阶段 2 PDF 旋转/复制输出迁移边界

下一小步迁移旧 MVP 中的 `rotate_or_copy_pdf()`。该步骤是最小 MVP 主线中“模型方向判断之后生成校正页”的输出环节，只处理传入的单页临时 PDF 记录；单元测试使用临时目录中合成的一页空白 PDF，不读取真实图纸或业务 PDF。

实施范围：

- 新增包内 PDF 输出模块。
- 迁移 `rotate_or_copy_pdf()`：
  - 当方向决策 API、parse、schema 均成功且角度为 `0/90/180/270` 时，写出 corrected PDF。
  - 当 dry-run 或决策不满足质量门时，复制 split PDF 到输出路径，并标记 `copied_needs_review`。
  - 保留 `original_pdf_rotate`、`applied_pdf_rotate_clockwise`、`needs_review`、`output_blockers` 和路径报告字段。
- 单元测试只构造临时一页 PDF 和内存决策，不使用真实样本。

明确不做：

- 不接入包内 `build_run_disabled_report()` 或 CLI `run`。
- 不迁移 `split_and_render_pdfs()`。
- 不迁移 `call_vlm_for_records()` 或 `post_chat_completion()`。
- 不迁移标题栏裁剪、最终发布或报告写出。
- 不调用阿里云、DashScope 或 OpenAI-compatible endpoint。
- 不读取 `.env/.env`。
- 不读取或处理真实图纸、真实图片或业务 PDF。
- 不调用 Ghostscript。
- 不写入真实输出目录。
- 不写入 `local_data/review_inbox/current/`。
- 不改旧 MVP 入口行为，旧脚本继续作为回归对照。

验收：

- 新 PDF 输出模块可编译。
- 单元测试覆盖 corrected、copied_needs_review、dry-run blocker 和路径报告。
- dry-run 顶层 side-effect 标记仍全部为 `false`。
- 旧入口仍可 `py_compile`。
- 禁区路径未进入 Git。

执行结果：

- 已新增 `src/blueprint_normalizer/pdf_rotation_mvp/pdf_output.py`。
- 已迁移 `rotate_or_copy_pdf()`，保持旧 MVP 的质量门 blocker、`corrected`、`copied_needs_review`、PDF `/Rotate` 读取/写入和路径报告行为。
- 已新增 `tests/unit/test_pdf_rotation_mvp_pdf_output.py`，使用临时目录中的合成一页 PDF 覆盖成功旋转、0 度校正、dry-run 复制、质量门失败复制和 root 相对路径报告。
- 本轮只迁移单页 PDF 旋转/复制输出环节，未接入包内真实 run、拆页渲染、模型调用、标题栏裁剪、最终发布或报告写出。

验证结果：

- `$env:PYTHONPATH='src'; python -m unittest tests.unit.test_pdf_rotation_mvp_pdf_output -v` 通过，4 个测试全部成功。
- `python -m py_compile src\blueprint_normalizer\pdf_rotation_mvp\pdf_output.py tests\unit\test_pdf_rotation_mvp_pdf_output.py` 通过。
- `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v` 通过，49 个测试全部成功。
- `python -m compileall src tests` 通过。
- `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer pdf-rotation-mvp dry-run --config etc\blueprint-normalizer.example.toml` 通过，顶层 `side_effects` 仍全部为 `false`。
- `git ls-files local_data .env outputs runs blueprint-normalizer.toml` 无输出。
- 本轮未调用阿里云、未读取真实图纸或业务 PDF、未读取 `.env/.env`、未调用 Ghostscript、未写入真实输出目录、未写入 `local_data/review_inbox/current/`。

## 阶段 2 最终 PDF 发布迁移边界

下一小步迁移旧 MVP 中的 `publish_final_pdfs()`。该步骤是最小 MVP 主线中“已校正页面按图号发布到最终输出目录”的环节，只处理传入的临时 PDF 和内存决策；单元测试使用临时目录中合成的一页 PDF，不读取真实图纸或业务 PDF。

实施范围：

- 在包内 PDF 输出模块中迁移 `publish_final_pdfs()`。
- 保留旧 MVP 的质量门：
  - dry-run 阻断。
  - rotation output 必须为 `corrected`。
  - rotation decision 不得要求复核。
  - drawing number decision 必须 API/parse/schema 成功。
  - drawing number decision 不得要求复核。
  - `final_filename_stem` 必须存在且不能在同一源 PDF 内重复。
  - corrected PDF 必须存在。
- 保留最终输出路径：
  - 成功发布到 `output_dir/source_stem/final_filename_stem.pdf`。
  - 阻断项复制到 `output_dir/source_stem/needs_review/task_id.pdf`。
- 保留 `final_status`、`needs_review`、`final_blockers` 和路径报告字段。

明确不做：

- 不接入包内 `build_run_disabled_report()` 或 CLI `run`。
- 不迁移 `split_and_render_pdfs()`。
- 不迁移 `call_vlm_for_records()` 或 `post_chat_completion()`。
- 不迁移标题栏裁剪或报告写出。
- 不调用阿里云、DashScope 或 OpenAI-compatible endpoint。
- 不读取 `.env/.env`。
- 不读取或处理真实图纸、真实图片或业务 PDF。
- 不调用 Ghostscript。
- 不写入真实输出目录。
- 不写入 `local_data/review_inbox/current/`。
- 不改旧 MVP 入口行为，旧脚本继续作为回归对照。

验收：

- 最终发布函数可编译。
- 单元测试覆盖 published、needs_review、dry-run blocker、重复图号、缺失图号和路径报告。
- dry-run 顶层 side-effect 标记仍全部为 `false`。
- 旧入口仍可 `py_compile`。
- 禁区路径未进入 Git。

执行结果：

- 已在 `src/blueprint_normalizer/pdf_rotation_mvp/pdf_output.py` 中迁移 `publish_final_pdfs()`。
- 保留旧 MVP 的发布质量门、`published`/`needs_review` 分流、重复图号阻断、缺失图号阻断、缺失 corrected PDF 阻断和最终路径报告行为。
- 已扩展 `tests/unit/test_pdf_rotation_mvp_pdf_output.py`，使用临时目录中的合成一页 PDF 覆盖成功发布、dry-run 阻断、重复图号、缺失图号、失败旋转输出和 root 相对路径报告。
- 本轮只迁移最终 PDF 发布环节，未接入包内真实 run、拆页渲染、模型调用、标题栏裁剪或报告写出。

验证结果：

- `$env:PYTHONPATH='src'; python -m unittest tests.unit.test_pdf_rotation_mvp_pdf_output -v` 通过，8 个测试全部成功。
- `python -m py_compile src\blueprint_normalizer\pdf_rotation_mvp\pdf_output.py tests\unit\test_pdf_rotation_mvp_pdf_output.py` 通过。
- `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v` 通过，53 个测试全部成功。
- `python -m compileall src tests` 通过。
- `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer pdf-rotation-mvp dry-run --config etc\blueprint-normalizer.example.toml` 通过，顶层 `side_effects` 仍全部为 `false`。
- `git ls-files local_data .env outputs runs blueprint-normalizer.toml` 无输出。
- 本轮未调用阿里云、未读取真实图纸或业务 PDF、未读取 `.env/.env`、未调用 Ghostscript、未写入真实输出目录、未写入 `local_data/review_inbox/current/`。

## 阶段 2 标题栏裁剪候选图迁移边界

下一小步迁移旧 MVP 中的 `crop_title_block_candidate()`。该步骤只从已存在的渲染图片中裁出底部标题栏候选图，并输出裁剪元数据；单元测试使用临时目录中合成的 PNG，不读取真实图纸或业务图片。

实施范围：

- 新增包内标题栏裁剪模块。
- 迁移 `crop_title_block_candidate()`：
  - 横向图片裁底部 30%。
  - 竖向图片裁底部 35%。
  - 输出 RGB PNG。
  - 返回 `crop_path`、`crop_strategy`、`crop_ratio`、`crop_box`、`rendered_width`、`rendered_height`。
- 单元测试只构造临时 PNG 图片，不使用真实样本。

明确不做：

- 不迁移 `build_corrected_crop_records()`。
- 不调用 Ghostscript 重新渲染 corrected PDF。
- 不接入包内 `build_run_disabled_report()` 或 CLI `run`。
- 不迁移 `call_vlm_for_records()` 或 `post_chat_completion()`。
- 不迁移最终报告写出。
- 不调用阿里云、DashScope 或 OpenAI-compatible endpoint。
- 不读取 `.env/.env`。
- 不读取或处理真实图纸、真实图片或业务 PDF。
- 不写入真实输出目录。
- 不写入 `local_data/review_inbox/current/`。
- 不改旧 MVP 入口行为，旧脚本继续作为回归对照。

验收：

- 新标题栏裁剪模块可编译。
- 单元测试覆盖横图、竖图、输出尺寸、crop_box 和路径报告。
- dry-run 顶层 side-effect 标记仍全部为 `false`。
- 旧入口仍可 `py_compile`。
- 禁区路径未进入 Git。

执行结果：

- 已新增 `src/blueprint_normalizer/pdf_rotation_mvp/title_block_crop.py`。
- 已迁移 `crop_title_block_candidate()`，保留旧 MVP 横向 30%、竖向 35% 的底部全宽裁剪策略。
- 已保留返回字段：`crop_path`、`crop_strategy`、`crop_ratio`、`crop_box`、`rendered_width`、`rendered_height`。
- 包内实现额外支持 `root` 参数，仅用于测试和报告路径相对化；默认行为仍使用项目根目录相对路径。
- 已新增 `tests/unit/test_pdf_rotation_mvp_title_block_crop.py`，使用临时合成 PNG 覆盖横向图、竖向图、输出尺寸、`crop_box` 和路径报告。
- 本轮未迁移 `build_corrected_crop_records()`，未调用 Ghostscript，未读取真实图纸，未调用阿里云或任何模型接口，未写入 `local_data/review_inbox/current/`。

验证结果：

- `$env:PYTHONPATH='src'; python -m unittest tests.unit.test_pdf_rotation_mvp_title_block_crop -v` 通过，2 个测试通过。
- `python -m py_compile src\blueprint_normalizer\pdf_rotation_mvp\title_block_crop.py tests\unit\test_pdf_rotation_mvp_title_block_crop.py` 通过。
- `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v` 通过，55 个测试通过。
- `python -m compileall src tests` 通过。
- `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
- `$env:PYTHONPATH='src'; python -m blueprint_normalizer pdf-rotation-mvp dry-run --config etc\blueprint-normalizer.example.toml` 通过，side-effect 标记仍显示不读 PDF、不调用模型、不调用 Ghostscript、不写审核入口。
- `git ls-files local_data .env outputs runs blueprint-normalizer.toml` 无输出。

## 账号切换交接文档刷新计划

用户准备切换账号继续后续工作。本轮只刷新根目录 `HANDOFF.md`，让新账号从当前真实状态接手；不迁移目录、不移动文档、不执行真实模型调用、不处理真实图纸。

实施范围：

- 将 `HANDOFF.md` 从 2026-07-06 改名前旧状态刷新为 2026-07-08 当前状态。
- 明确当前路径、远端仓库、单提交快照、最近提交、TODO 进度和下一步。
- 明确已完成的阶段 2 子模块迁移：配置、dry-run、domain、workflow、VLM 请求构造、summary、orchestrator、PDF 输出、最终发布、标题栏裁剪。
- 明确保留未完成项：阶段 2 最小 MVP 主线尚未完整接通，阶段 3 尚未开始。
- 写清非联网接手检查命令和禁区规则。

明确不做：

- 不读取 `.env/.env`。
- 不读取或处理真实 PDF、真实图片或业务数据。
- 不调用阿里云、DashScope 或 OpenAI-compatible endpoint。
- 不写入 `local_data/review_inbox/current/`。
- 不迁移 `reports/`、`rules/`、`references/` 目录。
- 不执行阶段 3 CLI 实现。

验收：

- 根目录 `HANDOFF.md` 与当前 `TODO.md`、git 状态和远端状态一致。
- 新账号可按 `HANDOFF.md` 中的“接手先读”和“接手检查命令”继续工作。
- `TODO.md` 标记本轮交接文档刷新完成。
- 禁区路径未进入 Git。

执行结果：

- 已将根目录 `HANDOFF.md` 从 2026-07-06 改名前旧交接刷新为 2026-07-08 当前账号切换交接文档。
- 已写明当前路径 `D:\project\codex\BlueprintNormalizer`、远端 `blueprint-normalizer`、单提交历史、最近提交和接手检查命令。
- 已写明阶段 2 已完成子模块、仍未完成的最小 MVP 主线父任务、阶段 3 尚未开始。
- 已写明非联网验证命令、禁区路径、阿里云联网规则和固定审核入口规则。
- 已在 `TODO.md` 标记本轮根目录交接文档刷新完成。

验证结果：

- 本轮只修改文档和 TODO/RPD，不读取真实 PDF、不读取 `.env/.env`、不调用阿里云、不写入 `local_data/review_inbox/current/`。
- `git ls-files local_data .env outputs runs blueprint-normalizer.toml` 无输出。
