# 联合评估计划

## 背景

当前已有两套评估集：

- 原始人工确认集：63 张。
- 顺时针 90 度增强集：20 张。

后续每次优化算法时，如果只跑其中一套，可能出现修复一个类别但破坏另一个类别的问题。因此需要一键联合评估。

## 目标

新增联合评估脚本，统一运行检测和评估，并输出总览。

## 输入

- 原始 PNG：`local_data/experiment_samples/all/png/`
- 原始 ground truth：`local_data/ground_truth/rotation_ground_truth.json`
- 增强 90 PNG：`local_data/experiment_samples/augmented_90/png/`
- 增强 90 ground truth：`local_data/ground_truth/rotation_ground_truth_augmented_90.json`

## 输出

本地忽略目录：

- `outputs/rotation-detection/combined_evaluation/combined_summary.json`
- `outputs/rotation-detection/combined_evaluation/combined_summary.csv`

单集输出仍保留在：

- `outputs/rotation-detection/stage1/`
- `outputs/rotation-detection/evaluation/`
- `outputs/rotation-detection/augmented_90/`
- `outputs/rotation-detection/evaluation_augmented_90/`

## 指标

联合评估至少输出：

- 数据集名称。
- 样本数。
- 正确数。
- 错误数。
- 准确率。
- 需要复核数量。
- 最低置信度。
- 最高置信度。
- 平均置信度。
- 错误样本。
- 复核样本。

总览还需要输出所有数据集合计：

- 总样本数。
- 总正确数。
- 总错误数。
- 联合准确率。
- 总复核数。

## 验收标准

- 一条命令能完成原始集和增强集检测、评估、汇总。
- 当前联合评估结果应为 83/83。
- 输出文件在 ignored 目录，不进入 Git。

## 执行结果

已完成：

- `scripts/rotation/run_combined_evaluation.py`
- `outputs/rotation-detection/combined_evaluation/combined_summary.json`
- `outputs/rotation-detection/combined_evaluation/combined_summary.csv`

当前联合评估结果：

- 总样本数：83。
- 正确数：83。
- 错误数：0。
- 联合准确率：1.0。
- 需要复核：2。
- 复核样本：`sample_042`、`aug90_016_from_sample_042`。

