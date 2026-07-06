# 阿里云百炼 VLM 接入资料索引

日期：2026-07-01

最近复核：2026-07-02

## 学习目标

- 了解阿里云百炼视觉理解模型如何接入本项目。
- 重点确认图片输入、认证、接口形态、本地文件传入和结构化输出约束。
- 本轮只调研和规划，不调用模型，不上传图纸，不配置 API Key。

## 样本索引

| 样本 | 类型 | 来源 | 本地缓存 | 一句话价值 | 不适合照搬 |
| --- | --- | --- | --- | --- | --- |
| 百炼视觉理解文档 | 官方文档 | https://help.aliyun.com/zh/model-studio/vision | `%TEMP%/aliyun_vision.html` | 给出视觉理解、单图/多图、OpenAI 兼容和 DashScope 原生调用示例 | 示例偏通用 VQA，不能直接当图纸旋正质量门 |
| 首次 API 调用 | 官方文档 | https://help.aliyun.com/zh/model-studio/getting-started/first-api-call-to-qwen | `%TEMP%/aliyun_first_api.html` | 明确 `DASHSCOPE_API_KEY`、OpenAI SDK、HTTP 调用和 `compatible-mode/v1` | 示例主要面向文本模型，视觉输入仍需结合视觉文档 |
| 模型列表 | 官方文档 | https://help.aliyun.com/zh/model-studio/models | `%TEMP%/aliyun_models.html` | 用于确认百炼覆盖文本、图像、音频、视频等模态 | 模型命名和可用地域可能变化，不能硬编码为长期事实 |
| DashScope 文档 | 官方文档 | https://help.aliyun.com/zh/model-studio/developer-reference/use-dashscope-sdk | `%TEMP%/aliyun_dashscope.html` | 了解 DashScope SDK/原生接口路线 | 第一版 MVP 不宜为了 SDK 增加依赖和适配面 |
| Qwen-VL API 参考 | 官方文档 | https://help.aliyun.com/zh/model-studio/qwen-vl-api-reference | `%TEMP%/aliyun_qwen_vl_api.html` | 作为后续模型参数、限制和计费信息复核入口 | 接口细节需在真正接入前再次按当前文档核对 |

## 2026-07-02 复核索引

| 样本 | 类型 | 来源 | 一句话价值 | 对本项目结论 |
| --- | --- | --- | --- | --- |
| 图像与视频理解 | 官方文档 | https://help.aliyun.com/zh/model-studio/vision | 官方明确视觉理解支持单图/多图，OpenAI 兼容和 DashScope 两种调用示例 | 第一版继续优先 OpenAI 兼容接口 |
| 首次调用千问 API | 官方文档 | https://help.aliyun.com/zh/model-studio/first-api-call-to-qwen | 官方说明获取 API Key、配置 `DASHSCOPE_API_KEY`、获取 WorkspaceId | API Key 只放环境变量，base URL 由用户按地域/WorkspaceId 确认 |
| 模型列表 | 官方文档 | https://help.aliyun.com/zh/model-studio/models | 官方模型列表显示图像与视频理解模型覆盖 `qwen3.7-plus`、`qwen3.5-omni-plus` 等 | 模型名不能硬编码，继续使用 `ALIYUN_VLM_MODEL` |

## 接入事实摘录

官方文档显示，百炼可通过 OpenAI 兼容接口和 DashScope 原生接口调用视觉理解能力。

OpenAI 兼容接口的关键形态：

```text
base_url = https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
endpoint = https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions
auth = Authorization: Bearer $DASHSCOPE_API_KEY
```

视觉输入在 `messages[].content[]` 中使用：

```json
{"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}
```

本地图片可转为 Base64 data URL：

```text
data:image/png;base64,{base64_image}
data:image/jpeg;base64,{base64_image}
data:image/webp;base64,{base64_image}
```

DashScope 原生接口的关键形态：

```text
base_http_api_url = https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1
service endpoint = /api/v1/services/aigc/multimodal-generation/generation
auth = Authorization: Bearer $DASHSCOPE_API_KEY
```

DashScope 原生消息中，图片字段形态为：

```json
{"image": "data:image/png;base64,{base64_image}"}
```

## 对本项目的可迁移原则

1. 第一版 MVP 优先使用 OpenAI 兼容接口，少引入 SDK 依赖。
2. 本地图纸页渲染为 PNG/JPEG 后用 Base64 data URL 传入，不要求公网图片 URL。
3. API Key 只从环境变量读取，不写入代码、文档、`local_data` 或日志。
4. `base_url`、模型名、地域和 Workspace 必须可配置。
5. VLM 输出必须要求 JSON-only，并用本地 schema 校验，不把模型自然语言解释直接进入后续自动化。
6. 图号读取结果只能进入 dry-run 和审核包，不能直接重命名 PDF。
7. 低置信、JSON 解析失败、候选冲突、模型无法判断时必须进入固定审核入口。

## 当前建议

本项目当前目标是尽快做出“旋转到正确方向 + 读取图号”的 MVP。因此阿里 VLM 应先作为主线 MVP 的云端视觉判断器，而不是继续作为 YOLO/OBB teacher 蒸馏工具。

推荐默认 provider：

```text
provider = aliyun_openai_compatible
api_key_env = DASHSCOPE_API_KEY
base_url_env = DASHSCOPE_BASE_URL
model_env = ALIYUN_VLM_MODEL
```

模型名不在代码中写死。默认值可在计划中暂定，真正调用前由用户按账户可用模型确认。

## 2026-07-02 接入复核结论

当前官方文档仍支持两条路线：

1. OpenAI 兼容接口：
   - `base_url` 形态：`https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`
   - chat completions endpoint：`/chat/completions`
   - 认证：`Authorization: Bearer $DASHSCOPE_API_KEY`
   - 图片输入：`messages[].content[]` 中使用 `{"type":"image_url","image_url":{"url":"..."}}`
2. DashScope 原生接口：
   - `base_http_api_url` 形态：`https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1`
   - HTTP endpoint：`/api/v1/services/aigc/multimodal-generation/generation`
   - 图片输入：`content` 中使用 `{"image":"..."}`

本地图纸页推荐转换为 JPEG 后以 Base64 data URL 输入：

```text
data:image/jpeg;base64,{base64_image}
```

官方图像限制中，Base64 编码后的字符串不超过 `10MB`；因此项目脚本应继续在客户端控制长边、JPEG 质量和请求页数。

当前项目实现 `scripts/vlm/build_aliyun_vlm_mvp_requests.py` 与复核结论一致：

- provider：`aliyun_openai_compatible`
- Key：`DASHSCOPE_API_KEY`
- base URL：`DASHSCOPE_BASE_URL`
- 模型：`ALIYUN_VLM_MODEL`
- 输入图片：本地渲染页压缩为 JPEG，再转 Base64 data URL
- 当前只 dry-run 生成请求包，不联网调用
