# 阿里模型参数与准确性调研

日期：2026-07-02

## 一、调研目标

用户补充：`qwen3-vl-flash` 将在 2026 年 9 月下线，因此后续不再作为常规对照模型。当前已验证较好的 `qwen3-vl-plus` 设计继续保留。

本轮目标是确认以下模型和参数是否适合机械图纸标题栏位置判断、图号 OCR，以及如何配置以提高准确性和可复现性：

- `qwen3.7-max`
- `qwen3.5-OCR`
- `qwenVL-OCR-Latest`
- `temperature`
- `top_p`
- `qwen3-vl-plus` 的 `thinking_budget`

本轮不调用模型、不上传图纸、不修改 prompt/schema、不读取 `.env/.env`。

## 二、官方资料索引

| 资料 | 来源 | 用途 |
| --- | --- | --- |
| 视觉理解模型列表 | https://help.aliyun.com/zh/model-studio/vision-model/ | 确认视觉模型、OCR 模型、结构化输出支持情况 |
| 图像与视频理解 | https://help.aliyun.com/zh/model-studio/vision | 确认 OpenAI 兼容、DashScope、图片输入、思考模式和图像限制 |
| OpenAI 兼容 Chat API | https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions | 确认 `temperature`、`top_p`、`response_format`、`enable_thinking`、`thinking_budget` 参数 |
| 文字提取 Qwen-OCR | https://help.aliyun.com/zh/model-studio/qwen-vl-ocr | 确认 `qwen3.5-ocr`、`qwen-vl-ocr-latest` 用法和 OCR 限制 |

## 三、模型判断

### 1. qwen3.7-max

官方视觉模型页中明确出现的视觉模型 ID 是：

```text
qwen3.7-max-2026-06-08
```

该模型支持文本、图像、视频输入，输出文本，具备 1M 上下文、64k 最大输出、Function Calling 和内置工具。它可以作为强视觉推理候选。

但对本项目最关键的问题是结构化输出：官方页面一方面说明 Qwen3.7、Qwen3.6、Qwen3.5、Qwen3-VL 系列在非思考模式下支持视觉结构化输出；另一方面，具体模型表中 `qwen3.7-max-2026-06-08` 的结构化输出列为 `--`，而 `qwen3.7-plus` 为支持。项目应以具体模型行作为质量门依据。

结论：

- 可以测试 `qwen3.7-max-2026-06-08` 的标题栏位置判断能力。
- 不建议直接把它替换为主流程模型，因为当前流程依赖稳定 JSON/schema。
- 若测试，需要把它作为“强推理但结构化风险较高”的探索对照，并记录 JSON 解析失败率。
- 若目标是替换或增强当前 JSON 主线，`qwen3.7-plus` 反而比 `qwen3.7-max` 更值得优先测试。

### 2. qwen3.5-OCR

官方 Qwen-OCR 文档已确认精确模型名：

```text
qwen3.5-ocr
```

它属于 Qwen3.5-OCR，面向文档解析、文字定位、关键信息提取、多轮对话和 PDF 文档解析。

OpenAI 兼容调用形态与当前项目一致：

```json
{
  "model": "qwen3.5-ocr",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/png;base64,{base64_image}"
          },
          "min_pixels": 3072,
          "max_pixels": 8388608
        },
        {
          "type": "text",
          "text": "请只提取标题栏中的图号、名称、比例等字段；看不清返回空字符串。"
        }
      ]
    }
  ],
  "temperature": 0
}
```

关键限制：

- Qwen-OCR 不支持自定义 System Message，所有指令必须通过 User Message 传入。
- OpenAI 兼容 SDK 可快速迁移，但图像旋转矫正、内置 OCR 任务等高级功能不能直接通过参数调用，需要 prompt 模拟并自行解析。
- DashScope SDK 支持完整高级功能，更适合后续专门 OCR 链路。
- `qwen3.5-ocr` 使用 URL 或本地路径时单张图像不超过 20MB；Base64 编码后字符串不超过 10MB。
- 图中文字过小或分辨率低时仍有幻觉风险。

结论：

- `qwen3.5-ocr` 不适合作为整页标题栏位置判断主模型。
- 它适合作为标题栏 crop、图号区域 crop 的 OCR 候选。
- 如果后续要读取图号，应该单独做 crop OCR 实验，而不是和标题栏位置判断混在同一次评估里。

### 3. qwenVL-OCR-Latest

用户写法 `qwenVL-OCR-Latest` 对应官方模型 ID 应按文档写为：

```text
qwen-vl-ocr-latest
```

它属于 Qwen-VL-OCR 最新版。官方说明 Qwen-VL-OCR 基于 Qwen3-VL 架构，支持文档解析、文字定位、高精识别、信息抽取、表格解析、公式识别、通用文字识别、多语言识别和图像旋转矫正。

结论：

- 它适合与 `qwen3.5-ocr` 做 OCR 对照。
- `latest` 有供应商漂移风险，不适合作为生产默认模型；若实验结果好，应再选择稳定版或具体快照。
- 它不应接管“标题栏在整页哪个位置”的主判断，最多作为 crop 后的文字证据层。

## 四、采样参数建议

### temperature

官方说明 `temperature` 控制生成文本多样性，越高越多样，越低越确定，取值范围为 `[0, 2)`。

本项目任务不是创作，而是确定性分类和字段提取，因此推荐：

```json
{
  "temperature": 0
}
```

这适用于：

- 标题栏位置枚举分类。
- JSON-only 输出。
- OCR 字段提取。

### top_p

官方说明 `top_p` 控制核采样概率阈值，取值范围为 `(0, 1.0]`；并建议 `temperature` 和 `top_p` 通常只设置一个。

本项目推荐：

```text
设置 temperature=0，不额外设置 top_p。
```

原因：

- 低随机性优先级高于语言多样性。
- 同时调低两个采样参数会增加不同模型间行为差异，反而不好归因。
- 如果某个模型拒绝 `temperature=0`，再退而使用很低的 `top_p` 做单独兼容实验。

### enable_thinking 与 thinking_budget

官方视觉文档说明：

- `qwen3.7`、`qwen3.6`、`qwen3.5`、`qwen3-vl-plus`、`qwen3-vl-flash` 属于混合思考模型。
- `qwen3.7`、`qwen3.6`、`qwen3.5` 默认开启思考模式。
- `qwen3-vl-plus` 和 `qwen3-vl-flash` 默认关闭思考模式。
- `thinking_budget` 可限制思考过程最大 Token 数。
- `enable_thinking` 和 `thinking_budget` 都不是 OpenAI 标准参数；通过 OpenAI Python SDK 调用时应放入 `extra_body`。
- 开启思考模式时，思考过程也可能计入输出 Token，延迟和费用会上升。
- 官方视觉模型页强调结构化输出在非思考模式下支持。

因此，当前主线推荐继续使用非思考模式：

```json
{
  "model": "qwen3-vl-plus",
  "temperature": 0,
  "response_format": {
    "type": "json_object"
  },
  "extra_body": {
    "enable_thinking": false
  }
}
```

若要测试 `thinking_budget`，必须作为受控实验变量，而不是默认开启：

```python
completion = client.chat.completions.create(
    model="qwen3-vl-plus",
    messages=messages,
    temperature=0,
    stream=True,
    stream_options={"include_usage": True},
    extra_body={
        "enable_thinking": True,
        "thinking_budget": 512,
    },
)
```

推荐实验只比较：

- `qwen3-vl-plus` 非思考：`enable_thinking=false`
- `qwen3-vl-plus` 思考受限：`enable_thinking=true, thinking_budget=512`
- 需要时再加一档：`thinking_budget=1024`

评估指标必须包括：

- 标题栏位置准确率。
- JSON 解析成功率。
- schema 校验成功率。
- 延迟。
- Token 成本。
- 是否出现解释正确但枚举输出错误的情况。

## 五、下一轮测试建议

不要再把 `qwen3-vl-flash` 纳入常规测试。

标题栏位置判断建议测试：

| 优先级 | 模型 | 参数 | 角色 |
| --- | --- | --- | --- |
| P0 | `qwen3-vl-plus` | `temperature=0`, `enable_thinking=false`, 不设 `top_p` | 当前主线基准 |
| P1 | `qwen3-vl-plus` | `temperature=0`, `enable_thinking=true`, `thinking_budget=512` | 思考预算消融 |
| P2 | `qwen3.7-plus` | `temperature=0`, `enable_thinking=false`, 不设 `top_p` | 更推荐的强视觉结构化候选 |
| P3 | `qwen3.7-max-2026-06-08` | `temperature=0`, `enable_thinking=false`, 不设 `top_p` | 按用户要求测试的强推理探索候选 |

OCR 建议另开任务测试：

| 优先级 | 模型 | 输入 | 角色 |
| --- | --- | --- | --- |
| P0 | `qwen3.5-ocr` | 标题栏 crop 或图号 crop | 图号/标题栏字段提取 |
| P1 | `qwen-vl-ocr-latest` | 同一批 crop | 最新 OCR 能力上限对照 |

抽样建议：

- 不用全量先烧钱；先选 12 到 20 页。
- 样本必须覆盖 `top_right`、`right_edge`、`bottom_edge`、`top_edge`、`no_title_block`、竖向图纸底边满宽标题栏。
- 必须使用人工已审核真值，输出固定入口审核包。
- 测试后不要只看整体准确率，还要看失败类别是否可解释。

## 六、批判性结论

当前最容易犯的错误是把“模型更强”误解成“主流程更稳”。对机械图纸标题栏位置判断来说，主流程真正需要的是低随机性、结构化稳定、枚举可控、失败可复核。

因此：

1. `qwen3-vl-plus` 仍应保留为当前主线。
2. `temperature=0`、不设置 `top_p` 是当前最稳的默认参数。
3. `thinking_budget` 可能提升复杂图纸推理，但也可能破坏 JSON 稳定性、增加延迟和成本；只能做消融实验。
4. `qwen3.7-max` 值得按用户要求测试，但不应因为名字是 max 就默认替代 Plus。
5. `qwen3.5-ocr` 和 `qwen-vl-ocr-latest` 应被放到 OCR 子任务，而不是整页标题栏位置判断主任务。
