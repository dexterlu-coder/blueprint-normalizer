# JS2207 MVP 图号命名审核结果归档计划

日期：2026-07-03

## 背景

用户已完成 `local_data/review_inbox/current/js2207_mvp_drawing_number_full_flow_review/review_form.csv` 人工审核填写。

本轮需要读取审核表，统计用户判断，归档当前固定审核入口，并重置 `local_data/review_inbox/current/`。

## 目标

1. 读取用户填写的 `review_form.csv`。
2. 统计：
   - 总记录数。
   - 人工判断分布。
   - 正确页数。
   - 删除或需特殊处理页数。
   - 用户备注。
3. 重点记录用户对无图号页面的规则建议：
   - 如果最终需要保留无标题栏/无图号页面，文件名应命名为 `人工复核_XX`。
   - `XX` 使用数字，避免文件名重复。
4. 归档当前审核入口：
   - `local_data/review_inbox/archive/current_archived_after_js2207_mvp_drawing_number_full_flow_review_<timestamp>/`
5. 重置 `local_data/review_inbox/current/` 为无待审核任务。
6. 将审核统计和产品规则写回 RPD/TODO。

## 非目标

- 不重新调用阿里云模型。
- 不修改用户填写的审核表。
- 不立即重命名输出 PDF。
- 不删除 `tools/pdf_rotation_mvp/output/` 中的本轮测试结果。
- 不提交 `local_data/`、MVP `input/output/work` 或模型响应。

## 质量门

- 归档前必须确认当前审核入口存在且包含 `review_form.csv`。
- 归档必须移动整个 `current` 内容，不能只移动 CSV。
- 重置后的 `current` 必须包含简短 README，说明当前无待审核任务。
- 对审核表编码要做兜底读取，避免 Excel 保存导致中文乱码时误统计。

## 验收标准

1. 生成审核统计摘要。
2. 当前审核入口已归档。
3. `local_data/review_inbox/current/README.md` 显示当前无待审核任务。
4. TODO 和 RPD 记录本轮审核结果。

