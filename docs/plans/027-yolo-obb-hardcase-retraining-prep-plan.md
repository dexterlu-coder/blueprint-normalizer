# YOLO/OBB hard-case 再训练准备计划

## 背景

YOLO/OBB 首训和后处理复查已经暴露出一类稳定风险：

- 图纸中的零件、局部框线或表格状结构可能被误检为标题栏。
- 这不是 `sample_009` 单点问题。
- 用户判断：类似图纸应作为“零件误检为标题栏”的难例样本批量纳入，避免一步步试错浪费时间。

该判断成立。当前后处理已加入“标题栏必须贴图纸外框线”的规则，但模型训练侧仍需要 hard-case 样本组来降低误检概率。

## 目标

1. 建立 YOLO/OBB hard-case 清单，而不是只处理单个 `sample_009`。
2. 将类似“零件误检为标题栏”的图纸成组纳入后续再训练准备。
3. 明确 hard-case 样本只标真实标题栏，不标误检零件。
4. 同时保留少量已确认正例，防止后处理或训练过度打压真实标题栏。
5. 在再训练前先完成 hard-case 清单、数据来源、质量门和回滚点。

## 非目标

本阶段不做：

- 不立即训练。
- 不修改现有 YOLO/OBB 数据集。
- 不批量改标签。
- 不新增 `negative` 类别。
- 不把零件误检区域画成 `title_block`。
- 不处理完整 PDF。

## hard-case 分组

### A. 已确认零件误检/多候选失败

必须纳入：

| 样本 | 来源 | 原因 |
| --- | --- | --- |
| `sample_009` | val | 左下角零件误检为标题栏；多候选；真实标题栏候选未完整覆盖 |
| `sample_001` | test | 图纸主体零件误检为标题栏 |
| `unclear90_001_from_sample_001` | test | 多候选；多个零件误检为标题栏 |

### B. 边界/范围异常失败

建议纳入，但作为边界质量 hard-case，不作为零件误检：

| 样本 | 来源 | 原因 |
| --- | --- | --- |
| `sample_020` | val | 预测框越界/范围过大 |
| `sample_010` | test | 预测框范围过大 |

### C. 保护性正例

必须保留少量正例，防止 hard-case 策略过严：

| 样本 | 来源 | 原因 |
| --- | --- | --- |
| `aug90_002_from_sample_010` | test | 曾被后处理误拦截，用户确认识别无误 |
| `aug90_007_from_sample_020` | val | 正例对照 |
| `sample_040` | val | 正例对照，侧边标题栏参考 |

## 相似图纸筛选策略

第一版不做复杂视觉聚类，先使用稳定可解释的规则筛选：

1. 从已有失败样本来源扩展：
   - `sample_001` 及其增强/不清晰版本。
   - `sample_009` 及其历史标注/预测材料。
   - `unclear90_001_from_sample_001`。
2. 从后处理报告中筛：
   - `issue_types` 包含 `part_false_positive`。
   - `issue_types` 包含 `multi_candidate` 且候选中有 `frame_contact_gap` 或中心区域候选。
3. 从历史 hard-case/round2 包中筛：
   - 用户已标记不好判断、低置信、误判或相似表格干扰的样本。
4. 从保护性正例中保留：
   - 已确认可接受但形态接近失败场景的样本，避免模型过度回避边缘附近真实标题栏。

## 数据规则

- 每张图仍只允许一个 `title_block` 标注。
- 误检零件只记录在 hard-case metadata 中，不进入 YOLO 标签。
- 如果现有标题栏标注可沿用，不重新画框。
- 如果发现标注边界不准，必须重新走固定审核入口和 overlay 复查。
- hard-case 清单输出到本地 ignored 目录，不进入 Git。

## 建议本地输出

```text
local_data/yolo_hardcases/round3_retraining_prep/
  hardcase_manifest.json
  hardcase_manifest.csv
  hardcase_summary.json
```

字段建议：

```text
sample
split
group
source_reason
decision
use_existing_label
negative_note
image_path
label_path
prediction_image
prediction_label
```

## 后续训练前质量门

进入再训练前必须满足：

1. hard-case 清单已生成。
2. 清单包含已确认零件误检、多候选、边界异常和保护性正例。
3. 所有 hard-case 的真实标题栏标签存在且可追溯。
4. 误检零件没有被写入 YOLO 标签。
5. 如需新增/重画标注，必须先发布固定审核入口。
6. RPD/TODO 已记录清单结果和回滚点。

## 下一步执行

1. 新增 hard-case 清单生成脚本或使用临时脚本生成本地清单。
2. 输出 `local_data/yolo_hardcases/round3_retraining_prep/`。
3. 校验清单覆盖关键样本：
   - `sample_009`
   - `sample_001`
   - `unclear90_001_from_sample_001`
   - `sample_020`
   - `sample_010`
   - `aug90_002_from_sample_010`
4. 记录清单结果到 RPD。
5. 再规划是否构建 round3 数据集和启动小规模再训练。

## 回滚点

本计划、RPD 和 TODO 提交后作为 hard-case 清单生成前的回滚点。
