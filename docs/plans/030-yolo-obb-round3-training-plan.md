# YOLO/OBB round3 小规模训练计划

## 背景

round3 hard-case 小数据集已经完成并通过人工 overlay 复查：

- 数据集：`local_data/yolo_obb_dataset_round3/`
- 总数：24。
- train：21。
- val：3。
- hard-case：8 条全覆盖。
- 用户确认：24 条标题栏红框全部正确，均不需要重画。

round3 的目的不是扩大泛化宣称，而是针对 round2 暴露的“零件误检为标题栏、多候选、范围过大”问题做小规模补强。

## 目标

1. 用人工确认的 round3 数据集做一次短轮次训练。
2. 观察 hard-case 是否改善：
   - `sample_009`
   - `sample_001`
   - `unclear90_001_from_sample_001`
   - `sample_020`
   - `sample_010`
3. 保护已确认正例不被误伤：
   - `aug90_002_from_sample_010`
   - `aug90_007_from_sample_020`
   - `sample_040`
4. 训练后生成预测结果和复查入口，不静默接受模型输出。
5. 与 round2 结果做可解释对比。

## 非目标

本阶段不做：

- 不处理完整 PDF。
- 不替代 OpenCV 主流程。
- 不宣称工业级最终准确率。
- 不上传训练数据、权重或预测图片。
- 不把训练产物提交 Git。
- 不跳过预测复查。

## 权重选择

首选继续训练 round2 权重：

```text
local_data/yolo_runs/round2_yolo11n_obb/weights/best.pt
```

理由：

- round2 已完成首训并能学习到标题栏。
- round3 是针对已知错误的小规模补强，更适合从 round2 权重继续。
- 若 round2 权重不可用，再退回 `yolo11n-obb.pt`。

## 数据集

使用：

```text
local_data/yolo_obb_dataset_round3/data.yaml
```

当前分布：

- train：21
- val：3
- test：0

说明：

- round3 val 是保护性正例，不是完整泛化评估集。
- 泛化与回归必须额外预测 round2 val/test 和 hard-case 清单样本。
- `sample_010`、`sample_020` 存在保护性同源重叠，这是刻意的 guardrail，不作为普通泛化指标解释。

## 训练命令草案

首选命令：

```powershell
yolo obb train model=local_data/yolo_runs/round2_yolo11n_obb/weights/best.pt data=local_data/yolo_obb_dataset_round3/data.yaml epochs=25 imgsz=1024 batch=2 plots=True project=local_data/yolo_runs name=round3_yolo11n_obb_hardcase
```

CPU 或显存不足时：

```powershell
yolo obb train model=local_data/yolo_runs/round2_yolo11n_obb/weights/best.pt data=local_data/yolo_obb_dataset_round3/data.yaml epochs=20 imgsz=768 batch=1 plots=True project=local_data/yolo_runs name=round3_yolo11n_obb_hardcase_cpu
```

## 训练前检查

训练前必须确认：

1. `local_data/yolo_runs/round2_yolo11n_obb/weights/best.pt` 存在。
2. `local_data/yolo_obb_dataset_round3/data.yaml` 存在。
3. round3 校验报告 error_count 为 0。
4. round3 overlay 已由用户确认全部正确。
5. `local_data/review_inbox/current/` 当前无待审核任务。
6. Git 工作区干净，训练产物不会进入 Git。

## 训练后预测范围

训练后必须预测：

1. round3 val，用于保护性正例回归。
2. round3 train，用于确认 hard-case 是否被学到。
3. round2 test，用于检查是否破坏原 test 难例。
4. round2 val，用于检查是否破坏原 val 对照。

建议输出：

```text
local_data/yolo_predictions/round3_train/
local_data/yolo_predictions/round3_val/
local_data/yolo_predictions/round3_round2_test/
local_data/yolo_predictions/round3_round2_val/
```

## 训练后质量门

训练后必须满足：

1. 训练命令、输出目录、权重路径已记录。
2. 训练曲线和验证图片存在。
3. 预测结果覆盖指定范围。
4. 预测复查包发布到固定入口。
5. 用户复查后才能判定 round3 是否优于 round2。
6. 必须重点记录：
   - 零件误检是否减少。
   - 多候选是否减少。
   - 范围过大是否改善。
   - 保护性正例是否仍正确。

## 失败处理

- 若训练失败：先检查路径、权重、Ultralytics 环境和 data.yaml。
- 若 hard-case 仍误检：不要直接扩大训练轮次，先看预测图和候选分层。
- 若保护性正例被误伤：优先回到数据构成和后处理策略，不直接接受模型。
- 若 train 明显过拟合而 round2 val/test 变差：回退训练策略，考虑增加普通正例或降低训练轮次。

## 回滚点

本计划、RPD 和 TODO 提交后作为 round3 小规模训练前的回滚点。
