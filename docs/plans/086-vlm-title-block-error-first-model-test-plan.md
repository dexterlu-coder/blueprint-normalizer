# VLM 标题栏错题集优先模型测试计划

日期：2026-07-02

## 背景

用户提出下一步测试策略：

1. 先测试上一轮中识别出错的部分。
2. 将实际效果发布给用户人工审核。
3. 如果效果不错，再扩大测试，把所有图纸都识别一次。

该策略符合项目稳定可靠优先原则。上一轮 YKJ125 盲测中，`qwen3-vl-plus` 明显优于 `qwen3-vl-flash`，且 `qwen3-vl-flash` 将下线；因此下一轮不再纳入 Flash。

上一轮参数调研结论见：

- `docs/research/2026-07-02-aliyun-model-parameter-accuracy-research.md`
- `references/aliyun-model-parameter-accuracy/README.md`

## 目标

1. 从上一轮人工审核完成的 YKJ125 盲测表中读取错误页和存疑页。
2. 构建一个“错题集优先”的标题栏位置测试集。
3. 使用新候选模型/参数重新判断标题栏当前位置。
4. 生成低噪声 Excel 和单页 HTML 审核包到固定入口：

```text
local_data/review_inbox/current/
```

5. 等待用户人工审核，不自动进入全量测试。

## 测试模型与参数

标题栏位置小测候选：

| 模型 | 参数 | 目的 |
| --- | --- | --- |
| `qwen3-vl-plus` | `temperature=0`, `enable_thinking=false`, 不设 `top_p` | 当前主线基准 |
| `qwen3-vl-plus` | `temperature=0`, `enable_thinking=true`, `thinking_budget=512`, 不设 `top_p` | 思考预算消融 |
| `qwen3.7-plus` | `temperature=0`, `enable_thinking=false`, 不设 `top_p` | 更推荐的强视觉结构化候选 |
| `qwen3.7-max-2026-06-08` | `temperature=0`, `enable_thinking=false`, 不设 `top_p` | 用户指定强推理探索候选 |

说明：

- `qwen3.7-plus` 是否在当前账号/地域可用，需要运行时由 API 返回确认。
- `qwen3.7-max-2026-06-08` 结构化输出存在风险，必须记录 JSON 解析率和 schema 成功率。
- `thinking_budget` 不作为默认增强，只作为受控对照。
- 本轮不测试 `qwen3.5-ocr` 和 `qwen-vl-ocr-latest`；OCR 应另开 crop/图号测试任务。

## 样本选择

优先来源：

```text
local_data/review_inbox/current/ykj125_vlm_title_block_blind_review/vlm_title_block_blind_review.xlsx
```

若当前入口被归档，则从归档目录读取等价文件。

样本选择规则：

1. 必选：上一轮 `qwen3-vl-plus` 被人工标记为错误的页。
2. 必选：上一轮 `qwen3-vl-plus` 被人工标记为不确定/存疑的页。
3. 可选补充：Flash 错误但 Plus 正确、且代表边界类型的页，用于确认新模型不会退化。
4. 可选补充：人工备注中提到 `right_edge`、`top_right`、`bottom_edge`、`top_edge`、`no_title_block` 灰区的页。
5. 若样本不足 12 页，则从人工备注和双模型分歧页中补到最多 20 页。
6. 若样本超过 20 页，则按错误优先、存疑次之、边位置覆盖优先排序取前 20 页。

所有样本必须保持 PDF 原向渲染，不允许为了模型测试旋转图纸。

## 非目标

- 不直接跑全量 63 页。
- 不生成正式旋正 PDF。
- 不重命名 PDF。
- 不测试图号 OCR。
- 不读取或打印 `.env/.env` 中的 API Key。
- 不把本轮结果直接写入 ground truth。
- 不根据 YKJ125 错题集继续做图纸特化 prompt。

## 实现计划

1. 新增审核表读取工具：
   - 支持无 `openpyxl` 环境时读取 xlsx 底层 XML。
   - 只提取页码、模型、模型位置、人工判断、正确位置、备注。
2. 新增错题集测试脚本：
   - 读取上一轮 YKJ125 审核结果。
   - 生成错题集页码清单。
   - 复用上一轮已渲染的原向 PNG，避免重复拆 PDF。
   - 构造新模型请求。
   - 支持 per-model 参数：`enable_thinking`、`thinking_budget`。
   - 保存原始响应、解析结果、决策 CSV/JSON。
3. 发布审核包：
   - HTML 按页码顺序展示图纸和各模型判断。
   - Excel 只保留人工本轮审核必须字段。
   - 图片副本必须放入 `current` 内。
4. 记录机器摘要：
   - 请求数、成功数、解析成功数、schema 成功数。
   - 各模型输出分布。
   - 与上一轮人工真值的自动对比，仅作为机器摘要，不替代人工审核。

## 人工审核入口要求

固定入口必须包含：

```text
local_data/review_inbox/current/README.md
local_data/review_inbox/current/<review_slug>/review_index.html
local_data/review_inbox/current/<review_slug>/vlm_error_first_review.xlsx
local_data/review_inbox/current/<review_slug>/vlm_error_first_review.csv
local_data/review_inbox/current/<review_slug>/review_manifest.json
local_data/review_inbox/current/<review_slug>/images/
```

Excel 人工字段只保留：

- `位置是否正确`
- `正确标题栏位置`
- `备注`

机器字段和长 JSON 放入 `review_manifest.json` 或输出目录机器报告，不进入人工填写表。

## 验收标准

1. 错题集样本来源可追溯到上一轮人工审核表。
2. 审核包中的图片、HTML、Excel、CSV、manifest 都位于 `local_data/review_inbox/current/`。
3. HTML 和 Excel 顺序与页码顺序一致。
4. 请求结果包含每个模型的 API 状态、解析状态和 schema 状态。
5. 本轮不修改正式 PDF，不重命名 PDF。
6. 用户审核前不进入全量 63 页测试。

## 扩大测试门槛

只有用户完成本轮审核后，才决定是否进入全量测试。

建议扩大测试门槛：

- `qwen3-vl-plus` 新参数或新模型在错题集上明显减少错误。
- JSON/schema 成功率接近 100%。
- 没有出现大量 `no_title_block`、角/边位置混淆或解释正确但枚举错误。
- 用户认可 HTML/Excel 审核体验。

## 回滚准备

实现前提交本计划、RPD 和 TODO，作为错题集优先测试脚本与批处理运行前回滚点。
