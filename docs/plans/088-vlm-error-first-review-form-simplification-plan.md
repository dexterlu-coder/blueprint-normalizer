# VLM 错题集审核表降噪计划

日期：2026-07-02

## 背景

用户指出当前错题集审核 Excel 暴露了不需要用户填写和判断的字段。项目 `AGENTS.md` 已明确要求：

- 人工填写表只显示用户完成当前判断必须看到的信息。
- 不暴露内部字段、调试分数、冗余路径、长 JSON、候选列表或算法细节。
- 技术字段放入单独 JSON、机器报告或日志文件。

当前 `vlm_error_first_review.xlsx` 仍包含样本编号、标题栏位置代码、上一轮人工正确位置、上一轮 Plus 误判位置等字段。它们对本轮“旋转角度是否正确”人工判断不是必须字段，应从人工表中移除。

## 目标

重建当前审核包，Excel 只保留：

- `页码`
- `模型`
- `模型派生当前旋转角度`
- `旋转角度是否正确`
- `正确旋转角度`
- `备注`

机器追溯字段继续保留在 `review_manifest.json`、`run_summary.json`、`vlm_decisions.jsonl/csv`。

## 非目标

- 不重新调用 API。
- 不修改 prompt/schema。
- 不修改模型结果。
- 不生成正式旋正 PDF。
- 不重命名 PDF。
- 不扩大到全量图纸。

## 实现计划

1. 调整 `scripts/experiments/build_vlm_title_block_error_first_review.py` 的人工表字段。
2. 将完整行数据写入 `review_manifest.json`，便于追溯。
3. 使用 `--reuse-raw-responses` 重建当前审核包。
4. 验证 Excel 表头、行数、图片副本和固定入口。
5. 更新 RPD/TODO 并提交实现。

## 验收标准

1. `vlm_error_first_review.xlsx` 只包含 6 个低噪声字段。
2. Excel 行数仍为 60。
3. HTML、Excel、CSV、manifest 和 images 仍位于 `local_data/review_inbox/current/`。
4. 不重新联网。
5. 用户审核前不进入全量测试。

## 回滚准备

先提交本计划、RPD 和 TODO。若重建审核包不符合要求，可回退到该计划提交。
