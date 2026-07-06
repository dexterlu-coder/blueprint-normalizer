# 账号切换交接更新计划

## 背景

用户准备切换账号后继续对话，需要当前项目状态可被新会话快速接手。

现有 `HANDOFF.md` 仍停留在 2026-06-28 的 MCP/VLM teacher 阶段，已经不符合当前实际状态。当前项目已经进入细 ROI 与图号候选人工审核阶段。

## 目标

1. 更新 `HANDOFF.md`，让新会话优先看到当前真实状态。
2. 记录当前固定审核入口和用户需要填写的文件。
3. 记录最近关键提交、下一步和暂停点。
4. 明确暂时不要做的事项，避免新会话跳过人工审核。
5. 更新 RPD 和 TODO，留下交接更新记录。

## 非目标

本轮不做：

- 不修改算法。
- 不重新跑 OCR。
- 不生成或重命名 PDF。
- 不归档当前审核入口。
- 不改用户需要填写的 CSV。

## 当前状态摘要

- 当前固定审核入口：
  - `local_data/review_inbox/current/README.md`
  - `local_data/review_inbox/current/fine_roi_review/review_index.html`
  - `local_data/review_inbox/current/fine_roi_review/review_form.csv`
- 当前待用户审核：
  - 32 条细 ROI 与图号候选。
- 最近关键提交：
  - `1eaffb3 feat: add ocr fine roi experiment`
  - `bc28dbc fix: explain fine roi review form`

## 验收标准

1. `HANDOFF.md` 当前状态与 `TODO.md` 一致。
2. `HANDOFF.md` 指向当前固定审核入口，而不是旧 teacher 入口。
3. `HANDOFF.md` 明确下一步等待用户审核细 ROI 与图号候选。
4. `HANDOFF.md` 明确审核完成前不得重建 63 条命名审核包、不得执行图像预处理实验、不得生成/重命名 PDF。
5. `git status --short` 干净。

## 回滚准备

本计划、RPD 和 TODO 提交后作为交接更新前回滚点。若交接文档有遗漏，可在该提交后继续修正。
