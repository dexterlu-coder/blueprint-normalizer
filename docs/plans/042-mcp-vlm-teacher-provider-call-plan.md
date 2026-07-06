# MCP/VLM teacher provider 调用方式计划

## 背景

teacher 调用准备包已经生成 8 条代表任务，包含：

- 原图、overlay、候选 crop。
- teacher prompt。
- response schema。
- teacher call manifest。

下一步需要设计实际调用方式。但直接把云端 VLM、MCP、本地 VLM 调用写死进流程风险较高：不同 provider 的图片输入、认证、返回格式、错误处理和隐私要求都不同。

因此第一阶段先实现 provider-agnostic 的请求/响应协议：

- 生成统一请求 JSONL。
- 生成空响应模板。
- 校验 teacher 响应是否符合 schema。
- 汇总响应与蒸馏候选。

本阶段不实际调用外部模型。

## 目标

1. 明确 teacher provider 调用的统一输入输出协议。
2. 新增脚本，读取 teacher call manifest 并生成 provider 请求包。
3. 新增响应模板，供人工/MCP/云端 VLM/本地 VLM 填写或适配。
4. 新增响应校验逻辑，确保返回 JSON 可解析且字段完整。
5. 为后续实际 provider 接入保留扩展点。

## 非目标

本阶段不做：

- 不调用 MCP/VLM。
- 不上传图纸。
- 不接入 API key。
- 不安装新依赖。
- 不重新训练。
- 不修改标签。
- 不发布固定审核入口。

## 输入

```text
local_data/mcp_vlm_teacher_call_prep/teacher_call_manifest.json
local_data/mcp_vlm_teacher_call_prep/teacher_prompt.md
local_data/mcp_vlm_teacher_call_prep/teacher_response_schema.json
```

## 输出

输出到 ignored 本地目录：

```text
local_data/mcp_vlm_teacher_provider/
```

输出文件：

```text
teacher_requests.jsonl
teacher_response_template.jsonl
teacher_provider_summary.json
validated_responses.json
validation_errors.csv
```

## provider 类型

### manual

人工或交互式 MCP 手动读取请求，逐条填入响应模板。

### mcp

后续可接入已有图像识别 MCP 工具。第一版只生成请求，不自动调用。

### cloud_vlm

后续可接入智谱、阿里或其他云端 VLM。必须显式配置 provider 和凭证，不得默认上传图纸。

### local_vlm

后续可接入本地模型服务。第一版不下载模型、不启动服务。

## 请求协议

每条请求包含：

```json
{
  "task_id": "",
  "provider_mode": "manual",
  "prompt": "",
  "question": "",
  "assets": {
    "source_image": "",
    "overlay_image": "",
    "candidate_crop": ""
  },
  "response_schema_path": "",
  "expected_output": "json_only"
}
```

## 响应协议

每条响应必须包含：

```json
{
  "task_id": "",
  "provider": "",
  "raw_response": {},
  "parsed_response": {},
  "parse_status": "ok|error",
  "notes": ""
}
```

其中 `parsed_response` 必须符合 `teacher_response_schema.json`。

## 验证

运行：

```text
python -m py_compile scripts/vlm/build_mcp_vlm_teacher_provider_requests.py
python scripts/vlm/build_mcp_vlm_teacher_provider_requests.py
python scripts/vlm/build_mcp_vlm_teacher_provider_requests.py --validate-responses local_data/mcp_vlm_teacher_provider/teacher_response_template.jsonl
```

期望：

- 请求数等于 teacher call manifest 的 8 条任务。
- 响应模板数为 8。
- 空模板校验应输出 8 条待填写/缺失响应，不应崩溃。
- 不触发外部调用。

## 回滚点

本计划、RPD 和 TODO 提交后作为 provider 请求/响应脚本实现前回滚点。

