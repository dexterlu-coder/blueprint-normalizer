# 阿里云 VLM 旋正与图号读取 MVP 计划

## 背景

JS2207 泛化测试暴露出一个关键问题：继续围绕本地标题栏检测策略做局部优化，可能无法最快回答用户真正关心的问题。

用户当前目标是尽快得到一个 MVP：

1. 将 PDF/图片页面旋转到正确方向。
2. 从图纸标题栏读取图号候选。
3. 形成可审核、可回滚、可迁移的批处理流程。

因此本阶段将阿里云百炼 VLM 作为主线 MVP 的视觉判断器。本地 OpenCV/YOLO/OCR 不废弃，但暂时退为辅助证据、回归对照或后续降本方案。

相关调研见：

- `references/aliyun-vlm-integration/README.md`
- `docs/research/2026-07-01-aliyun-vlm-integration-research.md`

## 目标

1. 设计阿里云百炼 VLM 接入配置，不把 API Key 写入仓库。
2. 设计 PDF 页渲染、图片压缩和 Base64 data URL 输入流程。
3. 设计 VLM 结构化输出 schema，用于旋转判断和图号候选读取。
4. 设计 dry-run 输出，不正式改写 PDF，不正式重命名文件。
5. 设计固定审核入口，让用户审核低置信、冲突和异常样本。
6. 保留 provider 抽象，后续可切换 DashScope 原生接口、本地 VLM 或其他云 VLM。

## 非目标

本阶段不做：

- 不继续优化 JS2207 特定样式。
- 不为 `JS2207-00-00升降平台.pdf` 写特判。
- 不训练或微调本地标题栏模型。
- 不把 VLM 输出直接用于正式覆盖 PDF。
- 不把 VLM 图号直接用于正式重命名。
- 不把 API Key 写入代码、配置文件、日志或 `local_data`。
- 不把 `local_data/` 私有输入输出加入 Git。

## 接入选择

第一版 provider：

```text
aliyun_openai_compatible
```

原因：

- 官方支持 OpenAI 兼容接口。
- 可以直接 HTTP 调用，减少 SDK 依赖。
- 输入可使用 Base64 data URL，不需要把图纸上传到公网对象存储。
- 与已有 provider-agnostic 思路兼容。

备选 provider：

```text
aliyun_dashscope_native
```

DashScope 原生接口保留为第二选择，用于 OpenAI 兼容接口无法覆盖的参数或能力。

## 环境变量

必须：

```text
DASHSCOPE_API_KEY
DASHSCOPE_BASE_URL
ALIYUN_VLM_MODEL
```

可选：

```text
ALIYUN_VLM_TIMEOUT_SECONDS
ALIYUN_VLM_MAX_RETRIES
ALIYUN_VLM_MAX_IMAGE_LONG_SIDE
ALIYUN_VLM_JPEG_QUALITY
```

说明：

- `DASHSCOPE_BASE_URL` 示例：`https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`。
- 模型名不硬编码。可由用户按账户可用模型指定，例如官方文档中出现的视觉模型或多模态模型。
- 脚本启动时只检查环境变量是否存在，不打印 Key 值。

## 输入

第一版支持两类输入：

```text
local_data/source_pdfs/*.pdf
local_data/.../*.png
```

推荐先跑小批量：

```text
local_data/source_pdfs/JS2207-00-00升降平台.pdf
```

但实现中不得出现 JS2207 特判。

## 输出

本地 dry-run 输出建议：

```text
local_data/aliyun_vlm_mvp/
```

文件：

```text
rendered_pages/
vlm_input_images/
vlm_requests.jsonl
vlm_raw_responses.jsonl
vlm_decisions.jsonl
vlm_decisions.csv
vlm_mvp_summary.json
needs_review.csv
previews/
```

固定审核入口：

```text
local_data/review_inbox/current/
```

审核入口至少包含：

```text
README.md
aliyun_vlm_mvp_review/review_index.html
aliyun_vlm_mvp_review/review_form.csv
aliyun_vlm_mvp_review/review_manifest.json
aliyun_vlm_mvp_review/assets/
```

人工填写表只保留：

- `序号`
- `文件名`
- `页码`
- `机器旋转是否正确`
- `正确旋转角度`
- `机器图号是否正确`
- `正确图号`
- `是否允许进入下一步`
- `备注`

内部字段、原始 JSON、置信分、长路径和候选列表只放机器报告。

## VLM 输出 schema

模型必须只返回 JSON。建议结构：

```json
{
  "page_orientation": {
    "current_clockwise_degrees": 0,
    "correction_clockwise_degrees": 0,
    "title_block_position": "bottom_right",
    "confidence": 0.0,
    "evidence": []
  },
  "drawing_number": {
    "candidates": [],
    "selected": "",
    "confidence": 0.0,
    "evidence": []
  },
  "quality_gate": {
    "needs_human_review": true,
    "review_reasons": []
  }
}
```

枚举约束：

- `current_clockwise_degrees`：`0`、`90`、`180`、`270`。
- `correction_clockwise_degrees`：`0`、`90`、`180`、`270`。
- `title_block_position`：`bottom_right`、`top_right`、`top_left`、`bottom_left`、`right`、`left`、`top`、`bottom`、`unknown`。
- `needs_human_review`：布尔值。

## 提示词原则

提示词不要求模型解释工程原理，只要求完成可校验任务：

1. 判断当前图片中标题栏所在位置。
2. 判断若要让标题栏处于正常阅读方向，需要顺时针旋转多少度。
3. 读取标题栏中的图号候选。
4. 无法确定时明确返回 `needs_human_review=true`。
5. 只返回 JSON，不返回 Markdown。

关键约束：

- 不允许猜测看不清的图号。
- 图号候选必须来自图中可见文本。
- 若多个候选接近，不能强行选唯一值。
- 旋转角度不确定时必须进入人工审核。

## 执行顺序

1. 规划、RPD、TODO 和回滚点提交。
2. 新增阿里 VLM MVP 脚本。
3. 脚本先支持 `--dry-run-build-requests`，只生成请求包，不联网。
4. 用户提供并确认 API Key、base URL、模型名和可外发范围。
5. 小批量联网调用，优先 3 到 5 页。
6. 校验 JSON 解析、schema、预览和人工审核入口。
7. 扩展到 JS2207 全量 dry-run。
8. 用户审核后，再决定是否接入正式 PDF 旋正和命名流程。

## 质量门

任一条件满足时进入人工审核：

- API 调用失败。
- JSON 解析失败。
- schema 校验失败。
- 旋转角度不是允许枚举。
- VLM 自报低置信。
- 图号为空。
- 多个图号候选冲突。
- 图号包含明显非法文件名字符且清洗后变化过大。
- VLM 旋转判断与本地 OpenCV/已有检测结果冲突。
- 抽检命中。

## 验证标准

实现后最低验证：

1. `python -m py_compile` 通过。
2. 无 API Key 时能生成请求包或给出清晰错误，不泄漏敏感信息。
3. dry-run 不修改原始 PDF。
4. dry-run 不正式重命名单页 PDF。
5. 每页都有请求记录、响应记录或失败记录。
6. 模型输出必须经过 schema 校验。
7. 低置信和异常样本进入 `local_data/review_inbox/current/`。
8. 人工审核表低噪声，不暴露内部调试字段。
9. `git status --short` 不显示 `local_data/` 私有数据进入 Git。

## 回滚准备

本计划、RPD 和 TODO 提交后作为实现前回滚点。若阿里 VLM 接入不稳定，可以回退到该点，只保留调研和计划，不影响既有 OpenCV/YOLO/OCR 产物。

## 批判性说明

把 VLM 放到 MVP 主线是当前阶段的合理选择，因为用户目标是端到端跑通，而不是继续证明某个本地检测器能被调好。

但 VLM 不是最终可信执行者。它的第一职责是快速产生可审核判断，帮助我们验证路线、收集失败样本和建立端到端接口。正式旋正、正式命名和无人批处理必须等 dry-run、人工审核和质量门稳定后再推进。
