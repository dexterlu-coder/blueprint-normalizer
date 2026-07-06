# 阿里模型参数与准确性调研计划

日期：2026-07-02

## 背景

用户补充：`qwen3-vl-flash` 将在 9 月下线，因此后续没有必要继续作为常规模型使用。当前 `qwen3-vl-plus` 的设计应保留，并作为主判断模型基础。

用户希望进一步调研并准备测试：

- `qwen3.7-max`
- `qwen3.5-OCR`
- `qwenVL-OCR-Latest`
- `qwen3-vl-plus` 的 `thinking_budget`
- `temperature` 和 `top_p` 参数在可配置时如何设置，以提升机械图纸标题栏位置识别准确性。

## 目标

1. 核对阿里云百炼官方文档，确认上述模型是否存在、模型名是否准确、是否支持图像输入和当前 OpenAI 兼容接口。
2. 确认各模型的参数能力：
   - `temperature`
   - `top_p`
   - `thinking_budget`
   - OCR 模型是否有专用输入/输出或结构化限制。
3. 从准确性目标出发，形成推荐参数：
   - 标题栏位置判断优先稳定、可复现、低随机性。
   - OCR 图号读取优先忠实、少幻觉、必要时返回空和人工复核。
4. 明确哪些模型适合做标题栏位置判断，哪些只适合做 OCR 辅助。
5. 保留 `qwen3-vl-plus` 主线设计，停止把 `qwen3-vl-flash` 作为常规对照模型。

## 非目标

- 本轮不批量调用模型。
- 本轮不修改 prompt/schema。
- 本轮不上传图纸。
- 本轮不改正式 PDF，不重命名 PDF。
- 不读取或打印 `.env/.env` 中的 API Key。
- 不把未核验的模型名写入正式默认配置。

## 调研输出

资料索引：

```text
references/aliyun-model-parameter-accuracy/README.md
```

调研笔记：

```text
docs/research/2026-07-02-aliyun-model-parameter-accuracy-research.md
```

RPD 记录：

```text
reports/rpd-rotation-detection.md
```

## 初步判断原则

1. 若任务要求确定性分类，`temperature` 应尽量低，优先 `0` 或官方允许的最低值。
2. 若 `temperature=0` 可用，通常不再提高 `top_p` 的探索性；保守设置应降低随机采样影响。
3. OCR 任务不应鼓励创作性输出；模型看不清时必须返回空值并触发人工复核。
4. `thinking_budget` 若可配置，应只在复杂视觉推理模型上验证，不能假设越大越好；需要平衡准确性、延迟、费用和结构化输出稳定性。
5. 对机械图纸任务，标题栏位置判断和图号 OCR 可以拆成两个模型层：位置模型不一定等于最佳 OCR 模型。

## 验证方向

调研完成后再决定是否进行小样本测试。若测试，应优先选取人工已审核、覆盖错误类型的页：

- YKJ125 中 Plus 错误页，例如第 1、49 页。
- YKJ125 中 `right_edge` vs `top_right` 灰区页。
- JS2207 中 `bottom_edge`、`top_edge`、`no_title_block` 难例。

## 回滚准备

调研前提交本计划、RPD 和 TODO，作为后续文档和脚本修改前回滚点。
