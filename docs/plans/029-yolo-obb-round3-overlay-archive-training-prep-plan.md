# YOLO/OBB round3 overlay 复查归档与训练准备计划

## 背景

用户已完成 `local_data/review_inbox/current/round3_overlay_review/review_form.csv` 审核，并确认 24 条 round3 overlay 全部正确。

当前 round3 数据集状态：

- 数据集目录：`local_data/yolo_obb_dataset_round3/`
- 总样本数：24。
- train：21。
- val：3。
- hard-case 清单 8 条全覆盖。
- 每张图仍只有 1 条真实 `title_block` 标签。
- 误检零件没有进入 YOLO 标签。

## 目标

1. 归档当前固定审核入口。
2. 重置 `local_data/review_inbox/current/` 为无待审核任务。
3. 记录用户审核结论：24 条全部正确，均不需要重画。
4. 记录 round3 数据集已具备训练前提。
5. 为下一步 round3 小规模训练规划建立清晰起点。

## 非目标

本阶段不做：

- 不启动 YOLO 训练。
- 不修改 round3 标签。
- 不修改 round2 数据集。
- 不处理完整 PDF。
- 不删除 round3 数据集或审核归档。

## 归档位置

计划归档到：

```text
local_data/review_inbox/archive/round3_overlay_review_20260628_approved/
```

归档内容应包含：

- `README.md`
- `round3_overlay_review/review_index.html`
- `round3_overlay_review/review_form.csv`
- `round3_overlay_review/machine_report.json`
- `round3_overlay_review/images/`

## 质量门

归档后必须满足：

1. 归档目录存在。
2. 归档目录包含用户填写后的 `review_form.csv`。
3. `current/` 只保留 `README.md`。
4. `current/README.md` 明确当前没有待审核任务。
5. `local_data/` 不进入 Git。
6. RPD/TODO 记录归档位置和用户审核结论。

## 后续训练准备结论

用户审核全部正确后，round3 数据集可以进入小规模训练规划。

训练规划仍需单独进行，不在本阶段直接训练。下一阶段需要明确：

- 使用 `yolo11n-obb.pt` 还是 round2 权重继续训练。
- 训练轮次、imgsz、batch、patience。
- 输出目录和训练后预测复查范围。
- round2 vs round3 的对比指标。
- `sample_009`、`sample_001`、`unclear90_001_from_sample_001`、`aug90_002_from_sample_010` 等关键回归样本。

## 回滚点

本计划、RPD 和 TODO 提交后作为归档当前固定审核入口前的回滚点。
