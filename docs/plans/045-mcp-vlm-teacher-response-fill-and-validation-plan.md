# MCP/VLM teacher 响应填写与校验计划

## 背景

当前固定审核入口已经发布 8 条 MCP/VLM teacher 小实验任务，包含请求、响应模板、schema、prompt 和图片资产副本。响应模板仍处于待填写状态，校验结果中的 16 条提示均为预期的空响应提示。

用户已确认继续推进。本阶段需要在不重训、不调用云端、不上传图纸的前提下，基于固定入口内的任务资产填写结构化 teacher 响应，并用既有 schema 校验。

## 目标

1. 保持当前固定审核入口 `local_data/review_inbox/current/` 作为唯一操作入口。
2. 逐条分析 8 个 teacher 任务的 source、overlay 和 candidate crop。
3. 将判断结果写入 `teacher_response_template.jsonl` 的 `parsed_response` 字段。
4. 将已填写记录的 `parse_status` 改为 `ok`。
5. 运行 provider 校验脚本，确认结构化响应通过 schema 校验。
6. 保留 teacher 响应作为蒸馏证据，不直接覆盖 ground truth 或训练标签。

## 非目标

本阶段不做：

- 不调用云端 VLM。
- 不上传图纸。
- 不接入 API key。
- 不重训 YOLO/OBB。
- 不改训练标签。
- 不处理完整 PDF。
- 不把 teacher 输出直接当最终真值。

## 输入

```text
local_data/review_inbox/current/teacher_tasks.csv
local_data/review_inbox/current/teacher_requests.jsonl
local_data/review_inbox/current/teacher_response_template.jsonl
local_data/review_inbox/current/teacher_response_schema.json
local_data/review_inbox/current/assets/
```

## 输出

```text
local_data/review_inbox/current/teacher_response_template.jsonl
local_data/mcp_vlm_teacher_provider/validated_responses.json
local_data/mcp_vlm_teacher_provider/validation_errors.csv
```

## 判断原则

- 只按当前屏幕坐标判断标题栏位置，不按零件自然方向猜测。
- 标题栏应贴住图纸外框线，标题栏与外框线之间不应有空隙。
- 判断字段证据时看字段簇组合，不把单个词命中当作强证据。
- 普通表格误检与图纸方向无关，不能写死某个方向。
- 小角度 OBB 偏差可以接受，前提是候选仍覆盖真实标题栏主体。
- 对图片证据不足的记录，应保守标记需要人工复核。

## 验证

运行：

```text
python scripts/vlm/build_mcp_vlm_teacher_provider_requests.py --validate-responses local_data/review_inbox/current/teacher_response_template.jsonl
```

期望：

- `validated_response_count` 为 8。
- `validation_error_count` 为 0。
- 生成的 `validated_responses.json` 可用于后续规则蒸馏、hard-case 数据整理或候选 crop 小分类器设计。

## 回滚点

本计划、RPD 和 TODO 提交后作为填写 teacher 响应模板前回滚点。

