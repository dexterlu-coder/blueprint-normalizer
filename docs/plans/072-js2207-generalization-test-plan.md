# JS2207 泛化测试计划

## 背景

用户新增一套测试图纸：

```text
local_data/source_pdfs/JS2207-00-00升降平台.pdf
```

这套图纸用于检验现有旋转方向识别与标题栏检测流程的通用性。用户明确要求：

- 严禁对 `JS2207` 做针对性优化。
- 图纸旋转方向是随机的。
- 必须使用之前完成的工具和工作流执行旋转识别与标题栏识别。
- 完成后发布到固定审核入口，等待用户审核。

## 目标

1. 将 `JS2207` 原 PDF 拆成单页 PDF。
2. 将单页 PDF 渲染为 PNG，作为既有 OpenCV 旋转检测脚本输入。
3. 复用 `scripts/rotation/detect_rotation_stage1.py` 识别标题栏所在侧、旋转角度和校正角度。
4. 复用既有标题栏 crop 生成逻辑，基于检测候选框生成校正后整页、标题栏 crop 和位置示意图。
5. 在固定入口 `local_data/review_inbox/current/` 生成低噪声人工审核包。
6. 保留机器报告，用于后续判断泛化失败模式，但不把测试结果反向用于本轮调参。

## 非目标

本轮不做：

- 不修改标题栏检测策略、阈值、候选打分或仲裁逻辑。
- 不为 `JS2207` 文件名、页码、图幅、标题栏样式写特判。
- 不校正生成正式 PDF。
- 不重命名单页 PDF。
- 不修正图号识别正确性。
- 不重建 63 条图号命名审核包。
- 不把 `local_data/` 私有输入、输出或审核结果加入 Git。

## 输入

```text
local_data/source_pdfs/JS2207-00-00升降平台.pdf
```

## 输出

私有测试输出：

```text
local_data/js2207_generalization_test/
```

固定审核入口：

```text
local_data/review_inbox/current/
```

审核入口至少包含：

```text
README.md
js2207_generalization_review/review_index.html
js2207_generalization_review/review_form.csv
js2207_generalization_review/review_manifest.json
js2207_generalization_review/assets/
```

人工填写表只保留当前判断所需字段：

- `序号`
- `页码`
- `样本编号`
- `机器判断旋转是否正确`
- `机器标题栏位置是否正确`
- `正确标题栏位置`
- `正确旋转角度`
- `备注`

## 执行策略

1. 新增一个通用编排脚本，只负责输入拆分、渲染、调用既有检测、生成审核包。
2. 编排脚本不得改动 `detect_rotation_stage1.py` 的算法逻辑。
3. 标题栏 crop 生成优先复用 `build_full_63_title_block_ocr_dry_run.py` 中已有的旋正、候选框变换和 crop recovery 函数。
4. 若某页检测低置信或 crop 生成失败，仍进入审核包，不做自动修补或针对性二次检测。
5. 机器报告可以记录置信度、bbox 和内部路径，但人工表与 HTML 不展示调试分数、长 JSON 或候选列表。

## 验收标准

1. 脚本通过 `python -m py_compile`。
2. 成功读取 `JS2207` PDF 并生成逐页 PNG。
3. 成功运行既有 OpenCV 旋转检测，输出逐页结果。
4. 固定审核入口包含所有需要用户打开、填写、审核和参考的文件副本。
5. `review_index.html` 可逐页查看原渲染图、校正后整页、标题栏 crop 和位置示意图。
6. `review_form.csv` 字段低噪声，不暴露内部技术字段。
7. summary 明确 `modified_pdf=false`、`renamed_pdf=false`。
8. `git status --short` 不显示 `local_data/` 私有数据进入 Git。

## 回滚准备

本计划、RPD 和 TODO 提交后作为执行前回滚点。若 JS2207 泛化测试暴露失败，应先记录失败样本与现象，等待用户审核，不在本轮直接调参。

