# 细 ROI 收窄复核结果归档与分层计划

## 背景

用户已完成当前细 ROI 收窄复核表。

初步读取结果：

- 审核记录：32 条。
- `新版ROI判断=正确`：31 条。
- `相对旧ROI是否更好=更好`：31 条。
- `sample_001` 标记为 `范围太小`、`更差`、`裁掉标题栏`。
- `sample_001` 备注为：旧 ROI 的高度更好，新 ROI 的左右范围合适。

这说明当前收窄策略整体有效，但 `sample_001` 暴露出上侧/高度收窄过激风险，应把“左右收窄”和“高度收窄”拆开固化。

## 目标

1. 归档当前已填写的细 ROI 收窄复核入口，保留用户原始填写表和审核资产。
2. 重置 `local_data/review_inbox/current/`。
3. 生成机器可读统计摘要和人工可读分层摘要。
4. 输出可执行规则建议：
   - 多数样本可接受新版 ROI 收窄。
   - `sample_001` 应保留旧 ROI 高度，但采用新版左右范围。
   - 后续固化策略时避免把“上侧减少 20%”无条件套用到所有样本。
5. 继续保持本轮不修正图号识别、不生成 PDF、不重命名 PDF。

## 非目标

本轮不做：

- 不修改 ROI 生成算法。
- 不重新跑 OCR。
- 不重建 63 条命名审核包。
- 不执行浅字标题栏 OCR 图像预处理实验。
- 不生成正式 PDF。
- 不重命名单页 PDF。
- 不把 `local_data/` 私有审核结果加入 Git。

## 输出

归档目录：

```text
local_data/review_inbox/archive/
```

业务摘要目录：

```text
local_data/fine_roi_tightening_review/
```

建议输出文件：

```text
filled_review_summary.json
filled_review_summary.csv
human_summary.md
```

## 验收标准

1. 能自动读取当前人工审核 CSV，包括 `utf-8-sig`、`utf-8`、`gb18030`。
2. 归档目录保留原始 `review_form.csv`、HTML、manifest 和图片资产。
3. `current` 重置为无待审核任务说明。
4. 摘要中明确 31 条通过、1 条 `sample_001` 需调整。
5. 摘要中明确 `modified_pdf=false`、`renamed_pdf=false`。
6. `git status --short` 不显示 `local_data/` 私有数据进入 Git。
7. 脚本通过 `python -m py_compile`。

## 回滚准备

本计划、RPD 和 TODO 提交后作为归档实现前回滚点。若归档摘要字段或分层规则不合适，可回退到该提交后重新设计。
