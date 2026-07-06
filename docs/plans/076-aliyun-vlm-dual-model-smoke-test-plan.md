# 阿里云 VLM 双模型小批量烟测计划

日期：2026-07-02

## 背景

用户已将阿里云百炼访问配置放入本地 `.env/.env`，并希望同时测试 `Qwen3-VL-Flash` 和 `Qwen3-VL-Plus`。本轮目标是在不覆盖现有 JS2207 审核入口、不生成正式 PDF、不重命名 PDF 的前提下，完成 2 个模型的最小联网烟测，观察它们对机械图纸方向和图号读取任务的稳定性。

## 当前输入

- 本地环境文件：`.env/.env`
- 已确认变量名：
  - `DASHSCOPE_API_KEY`
  - `DASHSCOPE_BASE_URL`
- 待测试模型：
  - `qwen3-vl-flash`
  - `qwen3-vl-plus`
- 默认测试图片目录：
  - `local_data/js2207_generalization_test/rendered_png/`

## 官方接入依据

- 百炼支持 OpenAI 兼容接口。
- 认证使用 `Authorization: Bearer $DASHSCOPE_API_KEY`。
- 北京地域 OpenAI 兼容 base URL 形态为 `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`。
- Chat Completions endpoint 为 `/chat/completions`。
- 视觉输入使用 `messages[].content[]` 中的 `image_url.url`。
- 本地图像可转换为 `data:image/jpeg;base64,{base64_image}`。
- Base64 编码后的图像字符串不得超过 `10MB`，客户端应控制长边、JPEG 质量和测试页数。

## 目标

1. 保护 `.env/.env` 不进入 Git。
2. 新增安全读取 `.env/.env` 的联网调用脚本，不打印、不落盘 API Key。
3. 对同一批 2 到 3 页图纸分别调用 `qwen3-vl-flash` 和 `qwen3-vl-plus`。
4. 保存每次调用的原始响应、解析结果、schema 校验结果和错误分层。
5. 生成双模型对比报告，重点比较当前旋转角度、校正角度、标题栏位置、选中图号和是否需要人工复核。
6. 只产出本地 dry-run 结果，不发布新的固定审核入口。

## 非目标

- 不覆盖 `local_data/review_inbox/current/` 中已有 JS2207 审核材料。
- 不归档当前 JS2207 审核入口。
- 不生成正式旋正 PDF。
- 不重命名单页 PDF。
- 不把 VLM 结果直接写回 ground truth。
- 不为 JS2207 写特判。
- 不把 API Key 写入命令行、日志、JSON、CSV 或提交记录。

## 实现方案

新增脚本：

```text
scripts/vlm/run_aliyun_vlm_mvp_smoke.py
```

脚本职责：

- 从 `.env/.env` 加载 `DASHSCOPE_API_KEY` 和 `DASHSCOPE_BASE_URL`。
- 支持 `--models qwen3-vl-flash,qwen3-vl-plus`。
- 复用现有请求包生成逻辑压缩图片并构造 OpenAI 兼容请求体。
- 逐模型、逐页调用 `{DASHSCOPE_BASE_URL.rstrip("/")}/chat/completions`。
- 对 HTTP 状态、响应 JSON、模型内容 JSON 和业务 schema 分层校验。
- 每条结果独立落盘，失败时保留错误原因但不丢失原始响应。

## 输出

输出目录：

```text
local_data/aliyun_vlm_mvp/
```

本轮新增或更新：

- `vlm_raw_responses.jsonl`
- `vlm_decisions.jsonl`
- `vlm_decisions.csv`
- `needs_review.csv`
- `dual_model_comparison.json`
- `dual_model_comparison.csv`
- `vlm_call_summary.json`

## 质量门

任一情况必须进入 `needs_review`：

- HTTP 请求失败或超时。
- 阿里云返回非 JSON 或错误对象。
- `choices[0].message.content` 缺失。
- 模型内容不是可解析 JSON。
- 业务 schema 字段缺失或类型不合法。
- 旋转角度不在 `0/90/180/270`。
- 图号为空或明显不可读。
- 模型自报 `needs_human_review=true`。
- `qwen3-vl-flash` 与 `qwen3-vl-plus` 对同一页的旋转角度、标题栏位置或选中图号冲突。

## 验证步骤

1. 编译新脚本。
2. dry-run 生成 2 页请求包，确认不联网时仍可生成请求和清单。
3. 联网调用 2 到 3 页、2 个模型。
4. 检查输出文件存在且不包含 API Key。
5. 检查 `.env/.env` 未被 Git 跟踪。
6. 记录结果到 RPD 和 TODO。

## 回滚准备

实现前提交本计划、RPD、TODO 和 `.gitignore`，作为联网调用脚本实现前的回滚点。若调用脚本不可用，可回退实现提交，保留安全忽略规则和本轮计划。
