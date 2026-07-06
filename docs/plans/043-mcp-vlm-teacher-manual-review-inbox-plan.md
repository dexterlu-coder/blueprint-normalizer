# MCP/VLM teacher 手动响应审核入口计划

## 背景

teacher provider 请求包已经生成 8 条任务和空响应模板。用户同意 A 方案：先进行小规模、可审计的 teacher 响应获取，不直接重训，也不全量接入云端 VLM。

当前缺口是：请求、模板、schema 和图片资产分散在业务目录中，不符合固定审核入口规则，也不方便人工或交互式 MCP/VLM 逐条填写。

## 目标

1. 将 8 条 teacher 请求发布到 `local_data/review_inbox/current/`。
2. 在固定入口内提供简短说明、请求 JSONL、响应模板 JSONL、schema、prompt 和图片资产副本。
3. 生成低噪声任务清单，便于逐条填写结构化响应。
4. 保持 provider-agnostic，不实际调用 MCP/VLM，不上传图纸。
5. 后续用户或 provider 填写完成后，可用现有 provider 校验脚本验证响应。

## 非目标

本阶段不做：

- 不调用 MCP/VLM。
- 不接入云端 API。
- 不安装新依赖。
- 不重训。
- 不改标签。
- 不把 teacher 输出直接写成最终真值。

## 输入

```text
local_data/mcp_vlm_teacher_provider/teacher_requests.jsonl
local_data/mcp_vlm_teacher_provider/teacher_response_template.jsonl
local_data/mcp_vlm_teacher_call_prep/teacher_call_manifest.json
local_data/mcp_vlm_teacher_call_prep/teacher_prompt.md
local_data/mcp_vlm_teacher_call_prep/teacher_response_schema.json
local_data/mcp_vlm_teacher_call_prep/assets/
```

## 输出

固定审核入口：

```text
local_data/review_inbox/current/
```

包含：

```text
README.md
teacher_tasks.csv
teacher_requests.jsonl
teacher_response_template.jsonl
teacher_prompt.md
teacher_response_schema.json
assets/
```

## 验证

运行：

```text
python -m py_compile scripts/vlm/publish_mcp_vlm_teacher_review_inbox.py
python scripts/vlm/publish_mcp_vlm_teacher_review_inbox.py
python scripts/vlm/build_mcp_vlm_teacher_provider_requests.py --validate-responses local_data/review_inbox/current/teacher_response_template.jsonl
```

期望：

- 固定入口存在 8 条任务。
- 8 条任务资产副本完整。
- 空响应模板校验只产生待填写提示，不崩溃。
- 不触发外部调用。

## 回滚点

本计划、RPD 和 TODO 提交后作为发布 teacher 手动响应审核入口前回滚点。

