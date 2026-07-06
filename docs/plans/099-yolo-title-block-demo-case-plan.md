# YOLO 标题栏识别展示案例生成计划

日期：2026-07-03

## 背景

用户需要一张此前使用本地 YOLO/OBB 模型识别机械图纸标题栏的案例，用于向他人展示当时的识别效果。用户希望形式类似此前人工审核用的 HTML 文件。

历史材料位于本地归档目录，例如：

```text
local_data/review_inbox/archive/round3_prediction_review_20260628_reviewed/
```

## 目标

1. 从历史 YOLO/OBB 预测复查包中选择一个清晰样例。
2. 复制预测 overlay 图片到固定入口。
3. 生成单案例 HTML 页面：
   - 显示本地 YOLO/OBB 预测图。
   - 保留样本名、阶段、预测框数量、用途说明。
   - 尽量保持与此前审核 HTML 相似的布局。
4. 发布到固定入口：

```text
local_data/review_inbox/current/yolo_title_block_demo/
```

## 选择样例

优先选择：

- 标题栏边框清晰。
- YOLO 预测框完整覆盖标题栏。
- 标签和置信度可见。
- 页面内容不需要额外解释也能看懂。

候选样例：

```text
round2_val_regression_sample_020.jpg
```

## 非目标

- 不重新训练 YOLO。
- 不重新运行 YOLO 推理。
- 不修改历史归档材料。
- 不把 `local_data/` 产物提交到 Git。
- 不生成大型多样本审核包。

## 验收标准

1. 固定入口包含 `review_index.html`。
2. HTML 可直接打开并看到单张 YOLO 标题栏识别案例。
3. HTML 引用的图片已复制到同一入口子目录。
4. `local_data/review_inbox/current/README.md` 指向该展示入口。

