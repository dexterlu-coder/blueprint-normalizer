# 阿里云百炼 VLM 接入调研

日期：2026-07-01

复核日期：2026-07-02

## 一、学习目标

- 我们真正要解决的问题：尽快构建机械图纸 MVP，把页面旋转到正确方向，并读取图号候选。
- 本轮不做的事情：不调用阿里模型，不上传图纸，不配置 API Key，不实现批处理脚本。
- 最终沉淀物：阿里 VLM 接入资料索引、项目级接入判断、后续 MVP 计划依据。

## 二、样本索引

| 样本 | 类型 | 来源 | 本地路径 | 一句话价值 | 不适合照搬 |
| --- | --- | --- | --- | --- | --- |
| 百炼视觉理解 | 官方文档 | https://help.aliyun.com/zh/model-studio/vision | `%TEMP%/aliyun_vision.html` | 明确视觉输入、OpenAI 兼容和 DashScope 原生调用方式 | 示例不是工程图纸旋正任务 |
| 首次 API 调用 | 官方文档 | https://help.aliyun.com/zh/model-studio/getting-started/first-api-call-to-qwen | `%TEMP%/aliyun_first_api.html` | 明确 `DASHSCOPE_API_KEY` 和 `compatible-mode/v1` 接入 | 主要是通用 API 入门 |
| 模型列表 | 官方文档 | https://help.aliyun.com/zh/model-studio/models | `%TEMP%/aliyun_models.html` | 确认百炼覆盖图像与视频等模态 | 模型可用性需接入前再次确认 |
| DashScope SDK/原生接口 | 官方文档 | https://help.aliyun.com/zh/model-studio/developer-reference/use-dashscope-sdk | `%TEMP%/aliyun_dashscope.html` | 提供原生 SDK/HTTP 路线 | MVP 第一版不宜强依赖 SDK |
| Qwen-VL API 参考 | 官方文档 | https://help.aliyun.com/zh/model-studio/qwen-vl-api-reference | `%TEMP%/aliyun_qwen_vl_api.html` | 后续确认模型参数、图片限制和计费 | 当前计划不把某个模型名写死 |

## 三、接入方式

阿里云百炼有两条接入路线。

第一条是 OpenAI 兼容接口。Python 侧可使用 `openai.OpenAI`，也可以直接 HTTP POST。认证读取：

```text
DASHSCOPE_API_KEY
```

北京地域示例 base URL：

```text
https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
```

对应 chat completions endpoint：

```text
https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions
```

视觉消息使用 `image_url`：

```json
{
  "role": "user",
  "content": [
    {
      "type": "image_url",
      "image_url": {
        "url": "data:image/png;base64,{base64_image}"
      }
    },
    {
      "type": "text",
      "text": "请只返回 JSON。"
    }
  ]
}
```

第二条是 DashScope 原生接口。Python 侧可使用 `dashscope.MultiModalConversation.call`，HTTP 侧可 POST：

```text
https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
```

原生消息里的本地图片同样可用 data URL：

```json
{"image": "data:image/png;base64,{base64_image}"}
```

## 四、对象模型

这个接入不应被建模为“调用一个 VLM 得到答案”，而应拆成以下对象：

- `VlmProviderConfig`：provider、base URL、模型名、超时、重试、图片尺寸限制。
- `RenderedPageAsset`：从 PDF 页渲染出的图片，以及传给模型的压缩版本。
- `VlmRequestRecord`：模型输入、提示词版本、图片摘要、dry-run 标记。
- `VlmPageDecision`：当前旋转、校正角度、标题栏位置、图号候选、置信度、是否需人工复核。
- `VlmRawResponse`：原始模型响应、解析状态、错误信息。
- `ReviewRoute`：哪些结果可进入 dry-run ready，哪些必须进固定审核入口。

## 五、工作协议

1. 输入阶段：PDF 仍先拆页、渲染，生成可追溯的页面图片。
2. 调用阶段：默认只发低分辨率但可读的整页预览，必要时第二轮再发标题栏 crop。
3. 约束阶段：提示词要求 JSON-only，字段固定，候选必须带证据。
4. 校验阶段：本地解析 JSON 并做枚举值、角度、图号格式和置信字段校验。
5. 决策阶段：高置信只进入 dry-run，不直接改 PDF；低置信或冲突进入人工审核。
6. 审核阶段：固定入口仍是 `local_data/review_inbox/current/`，人工表只显示当前判断所需字段。
7. 进化阶段：人工修正结果沉淀为样本和规则，但不得为某一套图纸写特判。

## 六、横向判断

| 路线 | 强项 | 弱项 | 本项目选择 |
| --- | --- | --- | --- |
| OpenAI 兼容接口 | 依赖少、接口通用、适合直接 HTTP、易接 provider 抽象 | 仍需处理地域和 Workspace 差异 | MVP 首选 |
| DashScope SDK/原生接口 | 阿里原生能力覆盖完整，可能支持更多平台参数 | 引入 SDK 依赖，迁移成本稍高 | 作为备选 |
| 公网图片 URL | 请求体小 | 图纸需要外传到存储服务，隐私和清理复杂 | 不作为首选 |
| Base64 data URL | 本地文件可直接传入，不需要公网托管 | 请求体更大，需控制图片尺寸 | MVP 首选 |
| 全量 VLM 自动处理 | 启动快，绕开本地模型调试 | 成本、稳定性、幻觉和供应商漂移 | 只做 dry-run 与审核门控 |

## 七、批判性结论

用户指出“不要陷入本地小模型局部优化”，这个判断成立。当前项目的目标不是证明本地标题栏检测技术路线优雅，而是尽快得到可验证的端到端 MVP。JS2207 暴露的问题也说明：若标题栏位置判断本身不稳，继续收窄 ROI 或微调本地规则会放大局部假设。

但这不意味着可以让 VLM 直接接管正式文件操作。VLM 应该先接管“判断与解释”，不接管“不可逆动作”。本轮 MVP 的正确边界是：

- VLM 主动判断页面应如何旋正。
- VLM 尝试读取图号候选。
- 程序生成 dry-run 记录、预览和审核包。
- 人工审核低置信与冲突样本。
- 后续再决定是否正式旋正 PDF 和命名。

## 八、MVP 推荐

优先接入：

```text
provider = aliyun_openai_compatible
api_key = env:DASHSCOPE_API_KEY
base_url = env:DASHSCOPE_BASE_URL
model = env:ALIYUN_VLM_MODEL
input_image = local rendered page as base64 data URL
output = JSON-only VlmPageDecision
```

模型名暂不硬编码。计划中允许默认候选为用户账户可用的视觉模型，例如官方文档中出现的 `qwen3.7-plus`、`qwen-vl-plus`、`qwen-vl-max`、`qwen2.5-vl` 系列之一。真正调用前应由用户确认可用模型、地域、Workspace 和费用。

## 九、风险清单

- 费用风险：全量 PDF 每页调用 VLM 会产生成本，需要先小批量。
- 隐私风险：图纸会发送到云端，必须由用户显式提供 Key 并确认可外发。
- 网络风险：运行环境需要联网，失败要可重试、可恢复。
- JSON 风险：模型可能输出非 JSON 或字段不完整，必须 schema 校验。
- 幻觉风险：模型可能编造图号，图号候选必须有原图证据和人工审核门。
- 图片限制风险：整页工程图过大，必须做压缩、尺寸限制和必要时二阶段 crop。
- 版本漂移风险：模型能力会变化，需要记录 provider、模型名、时间和提示词版本。

## 十、2026-07-02 官方文档复核

本次复核目标是回答“阿里的 VLM 如何接入”，并检查当前项目的 dry-run 请求包脚本是否仍符合官方接入形态。

复核来源：

- 阿里云百炼图像与视频理解官方文档。
- 阿里云百炼首次调用千问 API 官方文档。
- 阿里云百炼模型列表官方文档。

复核结论：

1. 阿里云百炼仍提供 OpenAI 兼容接口和 DashScope 原生接口两条路线。
2. OpenAI 兼容接口仍适合本项目第一版 MVP：
   - 可以直接 HTTP POST `/chat/completions`。
   - 认证使用 `Authorization: Bearer $DASHSCOPE_API_KEY`。
   - base URL 中需要按地域和业务空间填入 `WorkspaceId`。
   - 视觉输入使用 `image_url.url`。
3. DashScope 原生接口适合作为第二路线：
   - Python 可用 `dashscope.MultiModalConversation`。
   - HTTP endpoint 为 `/api/v1/services/aigc/multimodal-generation/generation`。
   - 视觉输入字段为 `{"image": "..."}`。
4. 本地图像可以转为 Base64 data URL：
   - OpenAI 兼容：`{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,{base64_image}"}}`
   - DashScope 原生：`{"image":"data:image/jpeg;base64,{base64_image}"}`
5. 官方图像限制要求关注：
   - 宽高均需大于 10 像素。
   - 长短边比例不得超过 200:1。
   - 推荐把分辨率控制在 8K 以内，过大图像可能导致网络传输耗时或超时。
   - Base64 编码后的字符串不超过 10MB。
6. 模型列表显示百炼覆盖文本、图像、音频、视频等多模态；图像与视频理解当前示例包括 `qwen3.7-plus`、`qwen3.5-omni-plus` 等，但模型名和账号可用性会变化，不应写死。

对当前项目的更新判断：

- `scripts/vlm/build_aliyun_vlm_mvp_requests.py` 的方向正确：先把本地页面图片压缩为 JPEG，再生成 Base64 data URL 请求包。
- `ALIYUN_VLM_MODEL` 必须继续由用户确认，不在代码中固定为某个示例模型。
- 当前脚本只生成请求包，下一步联网调用脚本需要新增：
  - `DASHSCOPE_BASE_URL` 校验。
  - HTTP 请求超时和重试。
  - `vlm_raw_responses.jsonl` 原始响应落盘。
  - JSON 解析和 schema 校验。
  - `needs_review.csv` 与固定审核入口发布。
- 发图纸到云端前，仍必须由用户明确确认图纸可外发范围。

最小调用形态建议：

```json
{
  "model": "${ALIYUN_VLM_MODEL}",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "请判断图纸方向并只返回 JSON。"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/jpeg;base64,{base64_image}"
          }
        }
      ]
    }
  ],
  "temperature": 0,
  "response_format": {
    "type": "json_object"
  }
}
```

注意：结构化输出不能只靠 `response_format`。仍需要提示词约束、后置 JSON 解析、schema 校验和人工审核质量门。
