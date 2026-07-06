# 标题栏诊断 HTML 图片路径修复计划

## 背景

用户打开 `local_data/title_block_ocr_diagnostic/review_summary.html` 后，页面中只能看到损坏图片占位和链接文字，无法直接审核 overlay 图片。

原因判断：

- `review_summary.html` 位于 `local_data/title_block_ocr_diagnostic/`。
- 脚本写入的图片路径是 `local_data/title_block_ocr_diagnostic/overlays/...` 这类从项目根开始的相对路径。
- 浏览器会按 HTML 所在目录解析相对路径，于是实际查找路径变成 `local_data/title_block_ocr_diagnostic/local_data/title_block_ocr_diagnostic/overlays/...`，导致图片加载失败。

## 目标

1. 修复 `scripts/ocr/build_title_block_ocr_diagnostic.py` 的 HTML 生成逻辑。
2. HTML 中 overlay 和 crop 链接必须相对于 `review_summary.html` 所在目录。
3. 重新生成本地诊断输出。
4. 验证 HTML 中不再出现错误的 `local_data/title_block_ocr_diagnostic/...` 图片 `src`。

## 非目标

本阶段不做：

- 不改变诊断算法。
- 不改变候选数量、结构特征或 OCR 状态。
- 不重新训练模型。
- 不发布固定审核入口。

## 实现方案

- 新增一个相对路径 helper：

```text
html_rel_path(target, html_path)
```

- 在 `write_html()` 中将：
  - `record["overlay_path"]`
  - `candidate["crop_path"]`

  转为相对于 `review_summary.html` 父目录的路径。

## 验证

运行：

```text
python -m py_compile scripts/ocr/build_title_block_ocr_diagnostic.py
python scripts/ocr/build_title_block_ocr_diagnostic.py
```

然后检查：

- `review_summary.html` 中图片路径应类似：

```text
overlays/round3_train__sample_001.jpg
crops/round3_train__sample_001__candidate_0.png
```

- 不应再出现：

```text
local_data/title_block_ocr_diagnostic/overlays/...
local_data/title_block_ocr_diagnostic/crops/...
```

## 回滚点

本计划、RPD 和 TODO 提交后作为修复脚本前回滚点。

