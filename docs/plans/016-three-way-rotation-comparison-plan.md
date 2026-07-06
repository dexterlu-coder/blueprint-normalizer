# 三方旋转识别比对计划

## 设计状态

状态更新时间：2026-06-28。

本计划保留为历史方案，用于追溯早期全量 63 张图纸的 OpenCV、图像识别 MCP 和人工复核三方比对，以及由此建立候选 ground truth、定位 OpenCV 误判样本的过程。

当前已废弃的部分：

- 无条件全量三方平权多数票。
- 用简单多数票直接决定最终旋转角度、PDF 校正或文件命名。

当前仍保留的部分：

- 多源证据互相校验。
- 分歧样本进入错误分层和复核。
- 人工结果可作为 ground truth 来源等级升级依据。

当前主设计已升级为“标题栏位置多证据仲裁”，详见 `docs/decisions/title-block-position-arbitration-design.md`。投票不再是最终决策机制，而是历史阶段用于建立评估基准和发现误判的实验方法。

## 目标

对全量 63 张机械图纸建立三方识别结果：

1. OpenCV 自动识别结果。
2. 图像识别 MCP 视觉判断结果。
3. 人工复核判断结果。

通过三方比对，形成更可信的候选标准答案，并定位 OpenCV 的误判和低置信度样本。

## 输入

- 全量 PNG 样本：`local_data/experiment_samples/all/png/*.png`
- OpenCV 输出：`outputs/rotation-detection/stage1/results.json`

## 输出

输出目录：

- `outputs/rotation-detection/comparison/`

建议文件：

- `mcp_results.json`：图像识别 MCP 全量结果。
- `manual_results.json`：人工复核结果。
- `three_way_comparison.csv`：OpenCV、MCP、人工三方比对表。
- `disagreements.csv`：三方不一致样本。

这些输出都属于本地实验产物，不进入 Git。

## 判断规则

仍依据 `rules/mechanical-drawing-rotation.md`：

| 当前标题栏位置 | 已顺时针旋转角度 |
| --- | --- |
| 下方或右下方 | 0 度 |
| 左侧 | 90 度 |
| 上方或左上方 | 180 度 |
| 右侧或右上方 | 270 度 |

## MCP 识别要求

对每张 PNG 调用图像识别 MCP，要求只判断：

- 标题栏实际位置。
- 已顺时针旋转角度。
- 是否需要人工复核。
- 简短依据。

MCP 输出不直接作为最终真值，只作为第二意见。

## 人工复核要求

人工复核优先看标题栏位置，不依赖零件视图方向。

人工复核输出：

- 文件名。
- 标题栏位置。
- 已顺时针旋转角度。
- 依据。
- 复核置信度。

## 三方比对规则

- 三方一致：作为高可信候选真值。
- OpenCV 与 MCP 一致，但人工不同：人工优先，并记录原因。
- MCP 与人工一致，但 OpenCV 不同：标记 OpenCV 可能误判。
- OpenCV 与人工一致，但 MCP 不同：标记 MCP 可能误判。
- 三方都不同：必须人工二次复核。

## 审核点

执行前需要确认本计划。
