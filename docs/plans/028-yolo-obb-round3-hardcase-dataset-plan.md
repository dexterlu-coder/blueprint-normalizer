# YOLO/OBB round3 hard-case 小数据集构建计划

## 背景

round2 首训后，用户确认“零件误检为标题栏”不是单点问题，应把相似图纸成组作为 hard-case 样本处理。

当前已完成：

- 生成 hard-case 清单：`local_data/yolo_hardcases/round3_retraining_prep/`
- 清单覆盖 8 条关键样本。
- 质量门通过：图片、真实标题栏标签、预测图和预测标签均存在。
- 误检零件只记录为 metadata，不写入 YOLO 标签。

## 目标

1. 构建独立的 round3 小数据集，不覆盖 round2。
2. 以 8 条 hard-case 清单为核心补强样本。
3. 加入一批普通正例，避免模型过度学习“不要检出”而损伤真实标题栏召回。
4. 生成 dataset yaml、summary、split manifest。
5. 生成 overlay 复查包并发布到固定审核入口。
6. 用户复查通过后，再进入 round3 小规模训练规划。

## 非目标

本阶段不做：

- 不启动 YOLO 训练。
- 不修改 round2 数据集。
- 不修改任何现有标签内容。
- 不新增负例类别。
- 不把误检零件画入标签。
- 不处理完整 PDF。

## 输入

- 基础数据集：`local_data/yolo_obb_dataset_round2/`
- hard-case 清单：
  - `local_data/yolo_hardcases/round3_retraining_prep/hardcase_manifest.csv`
  - `local_data/yolo_hardcases/round3_retraining_prep/hardcase_manifest.json`

## 输出

建议输出：

```text
local_data/yolo_obb_dataset_round3/
  data.yaml
  dataset_summary.json
  round3_manifest.csv
  images/{train,val,test}/
  labels/{train,val,test}/
```

overlay 复查输出：

```text
local_data/yolo_obb_dataset_round3/overlays/
local_data/review_inbox/current/round3_overlay_review/
```

## 数据构建策略

### hard-case 样本

必须纳入：

| 样本 | 建议 split | 角色 |
| --- | --- | --- |
| `sample_009` | train | 零件误检 + 多候选 |
| `sample_001` | train | 零件误检 |
| `unclear90_001_from_sample_001` | train | 零件误检 + 多候选 |
| `sample_020` | train | 边界/范围异常 |
| `sample_010` | train | 边界/范围异常 |
| `aug90_002_from_sample_010` | val | 保护性正例 |
| `aug90_007_from_sample_020` | val | 保护性正例 |
| `sample_040` | val | 保护性正例 |

说明：

- 已确认的失败样本进入 train，给训练侧直接补强。
- 保护性正例保留在 val，用于防止策略过严。
- 后续训练评估必须额外跑 round2 test/hard-case 预测，不只看训练指标。

### 普通正例

从 round2 train 中补入普通正例，原则：

- 优先选择现有 round2 train 样本，不引入新标注。
- 不选择 source sample 与 val/test 保护性样本冲突的记录。
- 补入数量第一版控制在约 12 到 20 条，避免 hard-case 被淹没。
- 普通正例仍只包含 `title_block` 标签。

## 质量门

构建后必须满足：

1. round3 数据集独立存在，不覆盖 round2。
2. 每张图片都有同名标签。
3. 每个标签文件只有 1 条 `title_block`。
4. OBB 坐标在 0 到 1 之间。
5. hard-case 清单中的 8 条全部被纳入。
6. 误检零件没有出现在任何 YOLO 标签中。
7. 固定审核入口只暴露 overlay、CSV、README 等用户需要看的材料。
8. `local_data/` 不进入 Git。

## 实施步骤

1. 提交本计划、RPD 和 TODO，作为实现前回滚点。
2. 新增 round3 数据集构建脚本。
3. 生成 `local_data/yolo_obb_dataset_round3/`。
4. 运行标签/数据集质量校验。
5. 生成 overlay 图片。
6. 发布 overlay 复查包到 `local_data/review_inbox/current/round3_overlay_review/`。
7. 记录生成结果到 RPD/TODO。

## 回滚点

本计划提交后作为 round3 数据集构建前回滚点。
