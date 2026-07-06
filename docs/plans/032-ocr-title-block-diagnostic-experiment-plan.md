# 标题栏 OCR 与后处理诊断实验计划

## 背景

round3 预测复查已通过，用户补充了标题栏规范判断方向：

- 标题栏必须贴图纸外框线。
- 标题栏内部字段不是单词命中，而是组合规则。
- 标题栏内部表格常有大小不一、行列不规则的格子。
- 明细栏、技术要求表、零件局部表格可能包含部分相似文字，不能只凭文字或表格密度判定。

上一轮调研已沉淀到：

- `references/title-block-standard-research/README.md`
- `docs/research/2026-06-28-title-block-standard-research.md`
- `rules/mechanical-drawing-rotation.md`

本计划用于设计一个小型 OCR/后处理诊断实验，验证这些规则能否解释历史误检和多候选样本。

## 目标

1. 对 YOLO/OBB 候选框生成可解释诊断报告。
2. 验证字段簇组合是否能辅助区分真实标题栏和零件/局部表格误检。
3. 验证表格结构不均匀度是否能辅助区分标题栏和均匀表格状干扰。
4. 形成后续是否升级后处理、补样本或接入 OCR/VLM 的判断依据。

## 非目标

本阶段不做：

- 不重新训练 YOLO/OBB。
- 不修改现有标签。
- 不处理完整 PDF。
- 不发布新的人工标注任务。
- 不把 OCR 结果直接写入最终旋转判断。
- 不把单个字段命中作为标题栏充分条件。

## 实验样本

优先使用已有本地结果，不新增数据：

| 样本 | 目的 | 预期关注点 |
| --- | --- | --- |
| `sample_001` | 历史零件误检 | 零件线框是否缺少标题栏字段簇、是否不贴图框线 |
| `unclear90_001_from_sample_001` | 历史多候选和零件误检 | 多候选中真实标题栏与误检零件的证据差异 |
| `sample_009` | 历史多候选和边界问题 | 真实标题栏字段/结构与左下角误检零件差异 |
| `sample_010` | 历史边界/范围异常 | OCR/结构证据能否辅助确认真实标题栏范围 |
| `sample_020` | 历史边界/范围异常 | 贴边证据与表格结构证据是否一致 |
| `aug90_002_from_sample_010` | 普通表格误检为标题栏的当前回归样本 | 验证额外表格候选能否被识别为非标题栏；注意这类误检可出现在任意方向 |
| `aug90_007_from_sample_020` | 保护性正例 | 验证规则不过严 |
| `sample_040` | 普通保护性正例 | 验证规则对正常标题栏不过拟合 |

候选来源优先读取：

- `local_data/yolo_predictions/round3_train/`
- `local_data/yolo_predictions/round3_val/`
- `local_data/yolo_predictions/round3_round2_test/`
- `local_data/yolo_predictions/round3_round2_val/`
- `local_data/yolo_obb_dataset_round3/round3_manifest.csv`

## 诊断证据

每个候选框输出以下证据，不直接改最终结果：

### 1. 图框贴边证据

- `touches_frame_line`：候选是否贴图纸外框线。
- `frame_contact_score`：贴边强度。
- `frame_gap_px`：候选边界到图框线的近似空隙。
- `frame_contact_note`：扫描裁切、外框缺失或无法判断时的说明。

### 2. 位置证据

- `candidate_side`：候选位于页面下、右、上、左哪一侧。
- `rotation_angle_from_candidate`：按标题栏位置映射出的旋转角度。
- `position_prior_score`：候选位置是否符合标题栏先验。

### 3. 字段簇 OCR 证据

字段按两组统计：

人员与流程字段簇：

- `设计`
- `制图`
- `校对`
- `工艺`
- `标准` 或 `标准化`
- `审核`
- `批准`
- `日期`

图纸属性字段簇：

- `图名` 或 `名称`
- `图号` 或 `图样代号`
- `材料`
- `比例`
- `重量`
- `表面积`
- `单位`

输出建议：

- `role_field_hits`
- `property_field_hits`
- `role_cluster_score`
- `property_cluster_score`
- `field_cluster_score`
- `ocr_engine`
- `ocr_confidence_summary`
- `ocr_text_excerpt`

注意：`ocr_text_excerpt` 只放短摘要，完整 OCR 文本进入机器 JSON，不进入用户填写表。

### 4. 表格结构证据

- `grid_line_density`：候选内部横竖线密度。
- `cell_count_estimate`：估算单元格数量。
- `cell_area_variance`：单元格面积差异。
- `small_large_cell_mix_score`：小签字格和大信息格混合程度。
- `uniform_grid_penalty`：过于均匀时的降权。

### 5. 反例证据

- `inside_drawing_body_penalty`：候选明显位于图纸主体内部时降权。
- `single_word_only_penalty`：只命中单个字段时降权。
- `no_role_cluster_penalty`：缺少人员/流程字段簇时降权。
- `no_property_cluster_penalty`：缺少图纸属性字段簇时降权。
- `multi_candidate_relation`：多候选之间是否相连、重叠，以及未选候选是否可能是普通表格误检。

## 输出文件

计划生成到本地忽略目录：

```text
local_data/title_block_ocr_diagnostic/
```

建议输出：

```text
local_data/title_block_ocr_diagnostic/diagnostic_manifest.csv
local_data/title_block_ocr_diagnostic/diagnostic_report.json
local_data/title_block_ocr_diagnostic/crops/
local_data/title_block_ocr_diagnostic/overlays/
local_data/title_block_ocr_diagnostic/review_summary.html
```

其中：

- `diagnostic_report.json` 保存完整机器字段。
- `diagnostic_manifest.csv` 保存每个候选的主要证据摘要。
- `crops/` 保存候选裁剪图，便于 OCR 与人工抽查。
- `overlays/` 保存原图候选框和证据可视化。
- `review_summary.html` 只用于查看证据，不要求用户填写。

若后续需要用户判断，再单独生成固定审核入口，不在本实验计划中直接发布审核任务。

## 实现步骤

1. 新增诊断脚本计划回滚点。
2. 实现候选读取：
   - 读取 round3 预测结果。
   - 读取 round3 manifest。
   - 只抽取本计划指定样本。
3. 实现候选裁剪：
   - 按 OBB 候选生成旋转裁剪或外接裁剪。
   - 保存 crop 和 overlay。
4. 实现图框贴边和位置证据复用：
   - 优先复用现有后处理逻辑中的 `frame_contact_score` 或类似字段。
   - 若现有脚本未暴露字段，则先输出简化版贴边距离。
5. 实现 OCR 字段簇统计：
   - 优先使用本地可用 OCR 工具。
   - 若 OCR 工具不可用，脚本应输出 `ocr_unavailable`，不阻塞结构证据实验。
6. 实现表格结构诊断：
   - 基于候选 crop 提取横竖线。
   - 估算单元格大小差异和均匀网格惩罚。
7. 生成机器报告和 HTML 摘要。
8. 人工抽查 HTML 摘要，判断证据是否符合肉眼理解。

## 质量门

1. 实验覆盖计划中的 8 个重点样本。
2. 每个样本至少输出一个候选诊断记录。
3. 历史误检样本应能看到至少一种反证：
   - 不贴图框线。
   - 缺少字段簇组合。
   - 结构像均匀零件线框。
   - 位于图纸主体内部。
4. 保护性正例不应被字段簇或结构规则错误打成强反例。
5. `aug90_002_from_sample_010` 的多候选必须单独观察，不能仅因多框或相连表格被判为失败。
6. 实验输出仍是诊断报告，不直接覆盖 YOLO/OBB 最终预测结果。
7. `local_data/` 输出不进入 Git。

## 成功标准

实验成功不是追求 OCR 准确率，而是回答三个问题：

1. 字段簇组合能否解释历史零件误检？
2. 表格结构不均匀度能否辅助区分标题栏和均匀零件线框？
3. 这套证据是否足够稳定，值得进入下一轮后处理实现计划？

若答案为“是”，下一步规划后处理升级：

```text
YOLO/OBB 候选
-> 图框贴边证据
-> 位置证据
-> 字段簇 OCR 证据
-> 表格结构证据
-> 反例过滤
-> 单标题栏仲裁
-> 人工复核门
```

若答案为“否”，则不继续堆 OCR 规则，改为补充 hard-case 数据或引入 VLM 解释疑难候选。

## 回滚点

本计划、RPD 和 TODO 提交后作为实验实现前回滚点。
