# 阿里模型参数与准确性资料索引

日期：2026-07-02

本目录记录阿里云百炼模型选择、视觉/OCR 用法和采样参数调研资料。调研目标是服务机械图纸标题栏位置判断和图号 OCR，不是追新模型名。

## 样本索引

| 样本 | 类型 | 来源 | 一句话价值 | 不适合照搬 |
| --- | --- | --- | --- | --- |
| 模型大全功能规格与计费 | 官方文档 | https://help.aliyun.com/zh/model-studio/models | 确认百炼覆盖文本、图像、音频、视频等模态 | 总览页不提供每个模型的完整参数细节 |
| 视觉理解模型列表 | 官方文档 | https://help.aliyun.com/zh/model-studio/vision-model/ | 确认视觉理解推荐模型、Qwen3.7/Qwen3.5/Qwen3-VL/Qwen-OCR 列表、结构化输出支持情况 | 模型广场中的可用性仍需按账号和地域确认 |
| 图像与视频理解用法 | 官方文档 | https://help.aliyun.com/zh/model-studio/vision | 确认 OpenAI 兼容、DashScope、`enable_thinking`、`thinking_budget`、高分辨率图像和文件限制 | 示例偏通用图片/视频，不能直接作为机械图纸 prompt |
| OpenAI 兼容 Chat API | 官方文档 | https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions | 确认 `temperature`、`top_p`、`response_format`、`enable_thinking`、`thinking_budget` 参数说明 | 参数需要结合具体视觉/OCR模型支持表判断 |
| 文字提取 Qwen-OCR | 官方文档 | https://help.aliyun.com/zh/model-studio/qwen-vl-ocr | 确认 `qwen3.5-ocr`、`qwen-vl-ocr-latest`、OpenAI 兼容和 DashScope OCR 用法 | OCR 模型不应直接替代整页标题栏位置判断模型 |

## 关键结论

1. `qwen3-vl-flash` 将不再作为常规模型使用；项目主线保留 `qwen3-vl-plus`。
2. 官方视觉模型表中，`qwen3.7-max-2026-06-08` 支持文本、图像和视频输入；具体表格中结构化输出列为 `--`，不适合直接替代当前 JSON 质量门主线。
3. 官方推荐视觉理解从 `qwen3.7-plus` 开始；`qwen3.7-plus` 支持结构化输出，更适合与本项目的 JSON schema 配合。
4. 官方 Qwen-OCR 文档已确认 `qwen3.5-ocr` 这个精确模型名；它属于 Qwen3.5-OCR，适合文档解析、文字定位和关键信息提取。
5. 用户写法 `qwenVL-OCR-Latest` 应按官方模型 ID 写为 `qwen-vl-ocr-latest`；它适合做标题栏 crop 或图号区域 OCR，不应作为标题栏位置判断主模型。
6. Qwen-OCR 不支持自定义 System Message，所有 OCR 指令应放在 User Message；OpenAI 兼容模式不能直接使用图像旋转矫正和内置 OCR 任务等高级参数。
7. `temperature` 和 `top_p` 都控制输出多样性，官方建议二者只设置一个；本项目确定性分类优先设置 `temperature=0`，不额外设置 `top_p`。
8. `qwen3-vl-plus` 默认关闭思考模式；若要使用 `thinking_budget`，必须配合 `enable_thinking=true`，并把参数放入 OpenAI SDK 的 `extra_body` 或 HTTP 请求体。
9. 结构化输出以非思考模式为主；`thinking_budget` 只能作为受控消融实验，不作为当前默认准确性参数。
