# 阿里云 VLM 接入方式复核计划

## 背景

用户希望重新调研“阿里的 VLM 如何接入”。项目中已有 2026-07-01 的阿里云百炼 VLM 接入调研，并已实现 dry-run 请求包生成脚本，但在真正联网调用前，需要按当前官方文档再次复核接入方式、环境变量、视觉输入格式和项目落地边界。

## 目标

1. 复核阿里云百炼 VLM 当前官方接入方式。
2. 明确 OpenAI 兼容接口和 DashScope 原生接口的差异。
3. 明确本地图纸图片如何通过 Base64 data URL 传入。
4. 明确 API Key、base URL、模型名的配置方式。
5. 更新资料索引和调研笔记，给出项目下一步建议。

## 非目标

本轮不做：

- 不联网调用模型。
- 不上传图纸。
- 不要求用户提供 API Key。
- 不修改正式 PDF。
- 不重命名单页 PDF。
- 不发布新的审核入口。

## 调研来源

优先官方文档：

- 阿里云百炼图像与视频理解。
- 阿里云百炼首次 API 调用。
- 阿里云百炼模型列表。
- DashScope / OpenAI 兼容接口相关说明。

## 输出

更新：

```text
references/aliyun-vlm-integration/README.md
docs/research/2026-07-01-aliyun-vlm-integration-research.md
```

必要时更新：

```text
reports/rpd-rotation-detection.md
TODO.md
```

## 验收标准

1. 明确推荐第一版仍使用 `aliyun_openai_compatible`。
2. 明确环境变量：
   - `DASHSCOPE_API_KEY`
   - `DASHSCOPE_BASE_URL`
   - `ALIYUN_VLM_MODEL`
3. 明确本地图片用 Base64 data URL 作为 `image_url.url`。
4. 明确联网调用前必须由用户确认图纸可外发范围。
5. `git status --short` 不显示 `local_data/` 私有输出进入 Git。

## 回滚准备

本计划、RPD 和 TODO 提交后作为调研文档更新前回滚点。若官方文档复核结论不适合当前脚本，可回退到该提交后重新设计 provider。
