# YOLO/OBB 后处理失败样本复查包实现计划

## 背景

已完成 YOLO/OBB 首训预测后处理脚本：

- `scripts/yolo_obb/postprocess_yolo_obb_predictions.py`
- 本地输出目录：`local_data/yolo_postprocess/round2_first_train/`
- 关键输出：`postprocess_report.json`、`postprocess_summary.csv`、`failure_case_manifest.json`

后处理结果显示 14 张 val/test 样本中：

- `accepted`：8
- `needs_review`：6
- 人工不可接受样本：5
- 额外保守拦截正例：`test/aug90_002_from_sample_010`

下一步需要生成失败样本复查包，让用户确认错误归因、最终候选是否可接受，以及是否需要补标或修正原标注。

## 目标

1. 新增失败样本复查包生成脚本。
2. 将后处理 manifest 中的失败样本和正例对照发布到固定审核入口。
3. 生成低噪声 HTML 和 CSV，便于人工快速复核。
4. 保留机器报告供后续自动归档和分析使用。
5. 不重新训练，不修改数据集，不处理完整 PDF。

## 非目标

本轮不做：

- 不调整后处理阈值。
- 不重新运行 YOLO 训练。
- 不修改 YOLO 标签。
- 不发布完整 PDF 批处理结果。
- 不接入 OCR/VLM。
- 不自动归档用户尚未填写的复查结果。

## 新增脚本

建议新增：

```text
scripts/yolo_obb/build_yolo_postprocess_failure_review_pack.py
```

职责：

- 读取 `failure_case_manifest.json`。
- 读取 `postprocess_report.json` 补充人工展示需要的低噪声字段。
- 复制复查所需图片到 `local_data/review_inbox/current/`。
- 生成 `review_index.html`。
- 生成 `review_form.csv`。
- 生成 `machine_report.json`。
- 写入当前审核入口 `README.md`。

不负责：

- 后处理候选重新计算。
- 修改 `postprocess_report.json`。
- 训练或预测。
- 自动归档旧审核任务。

## 默认输入

```text
local_data/yolo_postprocess/round2_first_train/postprocess_report.json
local_data/yolo_postprocess/round2_first_train/failure_case_manifest.json
local_data/yolo_predictions/
local_data/yolo_obb_dataset_round2/
```

## 默认输出

固定审核入口：

```text
local_data/review_inbox/current/
```

建议结构：

```text
local_data/review_inbox/current/
  README.md
  yolo_postprocess_failure_review/
    review_index.html
    review_form.csv
    machine_report.json
    images/
      prediction/
      source/
      labels/
```

## 固定入口安全检查

脚本运行前必须检查：

1. `local_data/review_inbox/current/` 不存在未归档任务。
2. 若 `current/README.md` 表示当前无待审核任务，可覆盖生成。
3. 若目标复查目录已存在，应默认拒绝覆盖，除非显式传入 `--force`。
4. 不删除 `archive/` 中的历史审核材料。

## 人工 HTML

页面标题：

```text
YOLO/OBB 后处理失败样本复查
```

每条样本应展示：

- 序号。
- 数据集和样本编号。
- 后处理状态。
- 低噪声问题类型中文摘要。
- 预测 overlay 图。
- 数据集原图。
- 若存在标注 overlay 或标签参考图，则放在同一样本附近。

页面不展示：

- 候选框坐标。
- 模型置信度列表。
- 原始 JSON。
- 长路径。
- 内部评分细节。

## 人工 CSV

字段只保留：

```text
序号
数据集
样本编号
后处理状态
问题类型
问题类型是否正确
最终候选是否可接受
是否需要补标
是否需要修正原标注
备注
```

其中 `后处理状态` 和 `问题类型` 用于用户判断，不要求用户改写。

## 机器报告

`machine_report.json` 应保存：

- 本轮复查包生成时间。
- 输入报告路径。
- 每条样本的完整 source path 与 review path。
- 对应后处理 issue_types。
- 对应 manifest reason。
- 是否为 failure 或 positive_control。

该文件供自动化归档和后续分析使用，不作为用户主要入口。

## 复查范围

第一版使用 `failure_case_manifest.json`，预计包含：

- 6 条 `needs_review` 样本。
- 3 条 positive control。
- 共 9 条记录。

必须包含：

- `val/sample_009`
- `val/sample_020`
- `test/sample_001`
- `test/sample_010`
- `test/unclear90_001_from_sample_001`
- `test/aug90_002_from_sample_010`

## 验证标准

实现后最低验证：

1. 脚本语法检查通过。
2. 生成固定入口 `local_data/review_inbox/current/README.md`。
3. 生成 `review_index.html`、`review_form.csv`、`machine_report.json`。
4. CSV 记录数与 manifest 记录数一致，预计 9 条。
5. 6 条 `needs_review` 样本全部出现在 CSV。
6. 页面引用图片均为 `current/` 内副本，不依赖业务目录长路径。
7. `git status` 不包含 `local_data/` 中的审核包文件。

## 回滚点

本计划、RPD 和 TODO 提交后作为实现失败样本复查包脚本前的回滚点。

