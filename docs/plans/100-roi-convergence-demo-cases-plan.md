# ROI 收敛多框展示案例生成计划

日期：2026-07-03

## 背景

用户指出上一轮生成的 YOLO 单框展示页形式不对。当前需要的是此前收敛和调整 ROI 时用于人工审核的页面形态：在同一张图上叠加多个彩色框，用于对比不同 ROI 策略或收窄前后候选区域，并且案例数量不少于 10 张，最好包含识别出错或高风险样本。

历史材料主要来自：

```text
local_data/ocr_fine_roi_experiment/overlays/
local_data/ocr_fine_roi_tightening_experiment/overlays/
local_data/ocr_fine_roi_experiment/review_manifest.json
local_data/ocr_fine_roi_tightening_experiment/review_manifest.json
```

## 目标

1. 从历史 ROI 实验中选择不少于 10 张案例。
2. 优先包含 `needs_review`、候选冲突、图号缺失、低置信度等错误或风险样本。
3. 每张案例以三策略 ROI overlay 为主图，展示红、绿、蓝等多彩候选框。
4. 同步提供 ROI 收窄前后 overlay，便于说明“当时如何收敛调整 ROI”。
5. 发布到固定入口：

```text
local_data/review_inbox/current/roi_convergence_demo/
```

## 样本选择

优先风险样本：

- `sample_035`
- `sample_041`
- `sample_044`
- `sample_047`
- `sample_049`
- `sample_055`
- `sample_062`
- `sample_009`

正常对照样本：

- `sample_001`
- `sample_002`
- `sample_019`

选择原则：

- 风险样本要覆盖图号缺失、候选冲突、低置信度或 OCR 模糊。
- 正常样本用于对照说明 ROI 策略在清晰标题栏上的预期效果。
- 所有展示图片必须来自历史实验 overlay，不重新推理，不重新训练。

## 展示内容

HTML 页面应包含：

- 简短说明和图例。
- 每个样本的三策略 ROI overlay。
- 每个样本的收窄前后 ROI overlay。
- 风险标签和简短原因。
- 可点击放大图片，便于展示和讲解。

## 非目标

- 不重新训练 YOLO/OBB。
- 不重新调用 OCR/VLM。
- 不改写历史实验结果。
- 不把 `local_data/` 展示产物提交到 Git。

## 验收标准

1. 固定入口包含 `review_index.html`。
2. 展示页至少包含 10 张案例。
3. 每个案例至少包含三策略 ROI 多彩框图片。
4. 至少包含若干识别错误或风险案例。
5. `local_data/review_inbox/current/README.md` 指向本轮展示入口。
