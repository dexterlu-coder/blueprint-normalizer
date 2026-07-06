# 标题栏 crop 完整性审核结果归档与分层计划

## 背景

用户已完成 `local_data/review_inbox/current/title_block_crop_review/review_form.csv` 的标题栏 crop 完整性专项审核。

当前阶段不能直接进入图号命名，也不能直接修改 crop 生成逻辑。需要先把用户填写结果保全、归档、结构化，并用少量视觉抽样确认问题分层，作为后续修复 crop 生成策略的输入。

## 目标

1. 归档当前固定审核入口，保留用户已填写的原始 `review_form.csv`、HTML 和全部图片资产。
2. 读取用户表格时兼容 UTF-8、UTF-8 BOM、GBK/GB18030，避免 Excel 保存后的中文备注丢失。
3. 生成机器可读审核摘要，统计完整、未完整、问题类型和备注样本。
4. 生成低噪声人工摘要，便于后续讨论，不暴露 bbox、score、候选 JSON 或长路径。
5. 抽样视觉核对典型样本，确认“右侧缺失”“半截标题栏”“错框/混入主体”“浅字质量问题”等分层。
6. 重置 `local_data/review_inbox/current/`，避免用户继续打开已完成任务作为当前入口。

## 非目标

- 不修复标题栏 crop 生成策略。
- 不运行 OCR 图像预处理小实验。
- 不重新生成 63 条图号命名审核包。
- 不生成正式旋正 PDF。
- 不重命名 PDF。
- 不把当前审核结果当作最终图号命名结果。

## 输入

固定审核入口：

```text
local_data/review_inbox/current/title_block_crop_review/
```

关键文件：

- `review_form.csv`
- `review_index.html`
- `review_manifest.json`
- `assets/pages_corrected/`
- `assets/crops_current/`
- `assets/overlays/`

## 输出

归档目录建议：

```text
local_data/review_inbox/archive/title_block_crop_review_YYYYMMDD_reviewed/
```

业务摘要目录建议：

```text
local_data/title_block_crop_quality_review/
```

输出文件：

- `filled_review_summary.json`
- `filled_review_summary.csv`
- `human_summary.md`

其中 `json/csv` 可包含机器使用字段；`human_summary.md` 只保留低噪声结论和样本分层。

## 工作步骤

1. 检查当前入口是否存在 `title_block_crop_review/`，且包含 63 条审核记录。
2. 复制或移动当前入口到归档目录，确保不覆盖已有归档。
3. 读取 `review_form.csv`，自动识别 UTF-8、UTF-8 BOM、GBK/GB18030。
4. 统计总样本数、完整数量、未完整数量、问题类型分布和带备注样本列表。
5. 输出机器摘要和人工摘要。
6. 抽样核对：
   - 右侧尾部缺失：`sample_006`、`sample_016`。
   - 只覆盖半截标题栏：`sample_008`、`sample_022`、`sample_032`。
   - 错框或混入主体：`sample_009`。
   - 浅字与短横线不清：`sample_035`、`sample_039`、`sample_042`。
7. 重置 `local_data/review_inbox/current/README.md` 为无当前待审核任务，并移除已完成任务副本。
8. 在 RPD 和 TODO 中记录归档路径、统计结果和下一步建议。

## 验收标准

1. 原始填写表已在归档目录保留，且可按 GB18030/GBK 兼容方式读取。
2. 归档目录包含本轮审核 HTML、CSV、manifest 和三类图片资产。
3. 机器摘要包含 63 条记录。
4. 人工摘要不暴露内部字段、调试分数、长路径、候选列表或 JSON。
5. `local_data/review_inbox/current/` 不再保留已完成的审核任务。
6. RPD 记录完整/未完整数量、典型样本和下一步修复方向。
7. 当前阶段未修改 crop 算法、未生成正式 PDF、未重命名 PDF。

## 回滚准备

本计划、RPD 和 TODO 提交后再执行归档脚本或批处理。若归档过程异常，可回退到该提交，并从当前 `review_inbox/current/` 重新执行归档。
