# 63 条图号命名人工审核包计划

## 背景

当前图号抽取与命名 dry-run 已经形成 63 条记录，其中：

- `auto_dry_run_ready=40`
- `blocked=21`
- `needs_human_review=2`

此前计划只针对 23 条非自动放行样本做 OCR 图像预处理小实验。但用户指出：40 条机器自动 ready 样本尚未被人工看过，不能直接视为可正式命名；23 条异常样本即使经过增强实验，也需要人工识别和审核。

这个判断是正确的。图号命名属于高风险动作，第一次形成命名链路时，必须先建立全量人工确认集。

## 本轮目标

1. 生成 63 条图号命名人工审核包。
2. 将 40 条 `auto_dry_run_ready` 标为“机器建议通过”，但不等于人工确认。
3. 将 23 条非自动放行标为“异常/需处理”。
4. 让用户审核每条拟图号和拟文件名是否可用。
5. 所有审核文件统一发布到 `local_data/review_inbox/current/`。
6. 只生成审核包，不正式重命名 PDF。

## 非目标

本轮不做：

- 不正式生成旋正 PDF。
- 不正式重命名单页 PDF。
- 不运行 23 条增强 OCR 小实验。
- 不调用云端 OCR/VLM。
- 不修改 ground truth。
- 不把 `auto_dry_run_ready` 当作 `production_ready`。
- 不在用户审核前自动回写人工确认。

## 输入

```text
local_data/full_63_title_block_ocr_dry_run/pdf_correction_dry_run_v2/dry_run_records.jsonl
local_data/full_63_title_block_ocr_dry_run/pdf_correction_dry_run_v2/dry_run_summary.csv
local_data/experiment_samples/all/png/
local_data/full_63_title_block_ocr_dry_run/crops/
```

## 输出

固定审核入口：

```text
local_data/review_inbox/current/
```

建议结构：

```text
README.md
naming_review/
  review_index.html
  review_form.csv
  review_manifest.json
  assets/
    pages/
    crops/
```

机器报告可另存：

```text
local_data/full_63_naming_review_pack/
```

## 人工审核字段

人工表只显示用户判断必须看到的信息：

- 序号
- 样本编号
- 机器候选图号
- 机器拟文件名
- 人工判断：通过 / 修正 / 打回
- 人工确认图号
- 备注

不在人工表中显示：

- 完整 JSON。
- 全量候选列表。
- 内部分数。
- 长路径。
- recipe 或算法调试字段。
- 机器分组。
- `auto_dry_run_ready`、`blocked`、`needs_human_review` 等内部状态。
- `drawing_number_low_confidence`、`duplicate_filename_candidate` 等阻断原因。

## HTML 审核页

每条记录显示：

- 校正后页面预览图。
- 校正后标题栏 crop。
- 样本编号。
- 机器候选图号。
- 机器拟文件名。
- OCR 摘要。
- 简短人工提示，例如“建议核对”或“需填写图号”，不展示内部状态码。

排列原则：

1. 先显示需要人工重点确认的样本。
2. 再显示其余样本。
3. 页面图和标题栏 crop 靠近展示。
4. 支持点击打开大图。
5. 减少调试信息和长文本。

## 审核后分流

人工审核结果后续再单独规划回写。本轮只生成包。

建议审核状态：

- `通过`：机器图号和拟文件名可用。
- `修正`：机器候选接近但需要填写人工确认图号。
- `打回`：当前 crop/OCR 不可信，需要增强 OCR、重新 crop、VLM 或人工进一步处理。

后续处理顺序：

1. 先导入人工审核结果。
2. 将通过/修正样本形成 `human_verified_naming` 记录。
3. 对打回样本再做 OCR 图像预处理小实验或人工专项处理。
4. 所有 63 条命名确认后，才允许规划正式 dry-run 输出 PDF。

## 质量门

必须满足：

1. 固定入口只包含本轮用户需要打开的文件副本。
2. 当前审核入口不能残留旧 teacher 任务。
3. 63 条记录全部覆盖。
4. 40 条自动 ready 只标记为机器建议，不标记为人工确认。
5. 需要重点确认的样本优先展示。
6. 不生成或重命名任何 PDF。
7. 人工表字段低噪声，不展示内部状态和阻断原因。
8. 审核页默认展示按 `correction_degrees` 校正后的 PNG 派生视图，方便同时审核旋转和图号；原始路径只放机器报告。

## 验收标准

实现后至少验证：

```text
python -m py_compile scripts\ocr\build_full_63_naming_review_pack.py
python scripts\ocr\build_full_63_naming_review_pack.py
```

预期：

- `review_record_count=63`
- `machine_suggested_count=40`
- `exception_count=23`
- 图片资产缺失数为 0。
- `local_data/review_inbox/current/README.md` 指向本轮命名审核任务。
- 不存在正式输出 PDF。

## 审核点

本轮实现完成后必须停在人工审核点。用户审核 `local_data/review_inbox/current/` 前，不得继续做增强 OCR 实验、回写人工结果或正式命名。

