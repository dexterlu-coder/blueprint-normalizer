# 阿里云模型联网沙箱规则固化计划

日期：2026-07-03

## 背景

用户已完成 JS2207 标题栏图号 OCR 四模型审核表填写，并指出每次运行阿里云模型测试脚本时，普通沙箱都会拦截联网请求，导致先失败一次再提权重跑，浪费时间并污染失败日志。

过往现象：

- 普通沙箱运行阿里云百炼模型调用时，会出现 Windows socket 权限错误。
- 失败后再使用 `sandbox_permissions=require_escalated` 才能正常访问阿里云接口。
- 这类失败不是模型、API key、endpoint 或 prompt 问题，而是执行环境网络权限问题。

## 目标

将该经验固化到 `AGENTS.md`，让后续涉及阿里云百炼 / DashScope / OpenAI-compatible endpoint 的真实模型调用、批量实验、smoke test、OCR/VLM 测试时，默认直接使用提权联网执行或已批准前缀。

## 非目标

- 不修改任何模型调用脚本。
- 不重新运行模型测试。
- 不读取或暴露 `.env/.env` 中的 API key。
- 不改动当前审核入口或用户已填写表格。

## 规则草案

在 `AGENTS.md` 中新增“阿里云模型联网执行规则”：

- 涉及阿里云百炼、DashScope、OpenAI-compatible endpoint 的真实模型调用时，直接使用 `sandbox_permissions=require_escalated` 或已批准命令前缀运行。
- 不先在普通沙箱中试跑联网请求。
- 提权理由应说明这是为了访问阿里云模型接口，避免沙箱 socket 权限错误。
- 不得因此跳过 dry-run、少量 smoke test、日志脱敏、人工审核入口和质量门。
- 仍不得读取、打印或提交 `.env/.env` 中的密钥。

## 验收标准

1. `AGENTS.md` 包含明确规则。
2. `TODO.md` 和 RPD 记录本次规范固化。
3. 提交前后工作区可追踪，私有数据不进入 Git。

