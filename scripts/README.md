# 脚本索引

本目录只放可公开提交的自动化脚本。私有图纸、渲染图、审核结果、训练数据和运行输出仍放在 `local_data/`、`outputs/` 或 `runs/`，并由 `.gitignore` 排除。

## 分类

- `common/`：跨流程公共工具，例如路径解析、OBB 标签解析。
- `rotation/`：OpenCV 旋转方向识别、ground truth、增强样本和评估。
- `ocr/`：标题栏 crop、OCR、图号候选、PDF dry-run、细 ROI 与人工审核归档。
- `yolo_obb/`：YOLO/OBB 标注、数据集、预测后处理和复查包。
- `vlm/`：MCP/VLM teacher、provider 请求包和阿里云 VLM MVP。
- `experiments/`：特定测试或一次性编排，例如 JS2207 泛化测试。

## 常用入口

```powershell
python -m scripts.rotation.detect_rotation_stage1
python -m scripts.rotation.run_combined_evaluation
python -m scripts.experiments.build_js2207_generalization_review_pack
python -m scripts.experiments.build_aliyun_vlm_position_probe_images
python -m scripts.experiments.build_js2207_real_vlm_title_block_review
python -m scripts.experiments.archive_js2207_real_vlm_excel_review
python -m scripts.experiments.evaluate_js2207_vlm_prompt_retest
python -m scripts.experiments.publish_js2207_vlm_prompt_retest_review
python -m scripts.experiments.build_vlm_title_block_error_first_review
python -m scripts.vlm.build_aliyun_vlm_mvp_requests --dry-run-build-requests
python -m scripts.vlm.run_aliyun_vlm_mvp_smoke --dry-run --limit-pages 2
```

## 当前主线

当前主线是阿里云 VLM 旋正与图号读取 MVP。第一步只生成请求包，不联网、不正式旋正 PDF、不重命名 PDF。

```powershell
python -m scripts.vlm.build_aliyun_vlm_mvp_requests --limit-pages 5
```

输出位于：

```text
local_data/aliyun_vlm_mvp/
```

该脚本会检查 `DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`、`ALIYUN_VLM_MODEL` 是否存在，但不会打印 Key 值。

双模型小批量联网烟测入口：

```powershell
python -m scripts.vlm.run_aliyun_vlm_mvp_smoke --limit-pages 2
```

默认从 `.env/.env` 读取 `DASHSCOPE_API_KEY` 和 `DASHSCOPE_BASE_URL`，测试 `qwen3-vl-flash` 与 `qwen3-vl-plus`，输出原始响应、结构化决策、双模型对比和 `needs_review.csv`。VLM 只判断当前屏幕坐标下的标题栏位置，脚本本地派生旋转角度；脚本不会打印 Key 值，不会生成正式 PDF，也不会重命名 PDF。

标题栏不同位置受控复测图片生成入口：

```powershell
python -m scripts.experiments.build_aliyun_vlm_position_probe_images
```

默认以 `js2207_page_001.png` 为基准生成四张旋转图，用于比较 VLM 对 `top_right`、`bottom_right`、`bottom_left`、`top_left` 的屏幕坐标判断。

JS2207 真实 PDF 原向标题栏位置审核入口：

```powershell
python -m scripts.experiments.build_js2207_real_vlm_title_block_review
```

该脚本会重新拆分源 PDF、原向渲染 PNG、以 PNG 原图 data URL 调用 VLM，并发布 Excel/HTML 审核入口到 `local_data/review_inbox/current/`。

JS2207 真实 PDF Excel 审核结果归档入口：

```powershell
python -m scripts.experiments.archive_js2207_real_vlm_excel_review
```

该脚本只读取用户填写的 Excel，不把 CSV 当作人工来源；默认校验 58 行且至少有人工填写内容，然后归档 `local_data/review_inbox/current/`，生成 Excel 审核摘要，并重置固定审核入口。

JS2207 VLM prompt 复测评估入口：

```powershell
python -m scripts.experiments.evaluate_js2207_vlm_prompt_retest
```

该脚本用已归档 Excel 审核结果作为真值，评估新版 VLM prompt 输出，并生成新旧正确率对比；不读取 CSV 作为人工来源，不生成正式 PDF，也不重命名 PDF。

JS2207 VLM prompt 复测审核包发布入口：

```powershell
python -m scripts.experiments.publish_js2207_vlm_prompt_retest_review
```

该脚本基于已有复测结果发布 HTML/Excel 审核包到固定入口，不重新联网、不生成正式 PDF、不重命名 PDF。

VLM 标题栏错题集优先模型测试入口：

```powershell
python -m scripts.experiments.build_vlm_title_block_error_first_review
```

该脚本读取上一轮 YKJ125 人工审核表中 `qwen3-vl-plus` 的错误页，复用原向 PNG，不旋转、不 resize、不压缩，测试 `qwen3-vl-plus` 非思考、`qwen3-vl-plus` 思考预算、`qwen3.7-plus` 和 `qwen3.7-max-2026-06-08`，并发布旋转分组优先的 HTML/Excel 审核包到固定入口。若只需用已保存响应重建审核包，可传入 `--reuse-raw-responses`。
