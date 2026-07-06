# 顺时针 90 度增强样本计划

## 背景

当前 63 张人工确认样本中，旋转角度分布缺少顺时针 90 度样本，也就是标题栏位于左侧的图纸。若继续优化算法，模型可能对 `left -> 90 度` 这一类没有实测覆盖。

## 目标

从已人工确认的原始样本中随机抽取一批图纸，生成标题栏位于左侧的增强样本，用于补齐顺时针 90 度类别。

## 样本策略

- 不修改原始样本。
- 从 `local_data/experiment_samples/all/png/` 中抽取 20 张。
- 随机种子固定为 `20260625`，保证可复现。
- 优先保持来源多样性：
  - 从原 `right/270` 样本抽取 10 张，额外旋转 180 度。
  - 从原 `top/180` 样本抽取 9 张，额外旋转 270 度。
  - 从原 `bottom/0` 样本抽取 1 张，额外旋转 90 度。
- 目标增强样本统一为：
  - `title_block_position = left`
  - `rotation_degrees = 90`
  - `precise_title_block_position = 左侧`

## 输出

本地忽略目录：

- `local_data/experiment_samples/augmented_90/png/`
- `local_data/ground_truth/rotation_ground_truth_augmented_90.json`
- `local_data/ground_truth/rotation_ground_truth_augmented_90.csv`
- `outputs/rotation-detection/augmented_90/`
- `outputs/rotation-detection/evaluation_augmented_90/`

公开仓库只提交脚本、计划、RPD 和 TODO，不提交增强图纸或增强 ground truth。

## 实现步骤

1. 新增增强样本生成脚本。
2. 读取人工确认 ground truth 和 PNG 样本。
3. 按固定随机种子抽样。
4. 旋转 PNG，使标题栏最终位于左侧。
5. 生成增强 ground truth。
6. 让 OpenCV 检测脚本支持传入输入/输出目录。
7. 让评估脚本支持传入结果和 ground truth 路径。
8. 对增强样本运行检测和评估。

## 验收标准

- 生成 20 张增强 PNG。
- 增强 ground truth 共 20 条，全部为 `rotation_degrees = 90`。
- OpenCV 能对增强样本独立输出结果。
- 评估脚本能独立评估增强样本。
- 图纸、增强样本、评估输出继续保持在 `.gitignore` 覆盖范围内。

## 执行结果

已完成：

- `scripts/rotation/create_augmented_90_samples.py`
- 检测脚本输入/输出目录参数化。
- 评估脚本结果、ground truth、输出目录参数化。

增强样本：

- 共 20 张。
- 全部为 `left/90 度`。
- 随机种子为 `20260625`。

评估结果：

- 初次增强集评估：16/20，准确率 0.8。
- 增加左侧候选仲裁规则后：20/20，准确率 1.0。
- 原始 63 张人工确认集回归仍为 63/63，准确率 1.0。

