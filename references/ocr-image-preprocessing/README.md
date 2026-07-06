# OCR 图像预处理增强调研样本索引

日期：2026-06-29

## 学习目标

为机械图纸标题栏 crop 的 OCR 图号抽取寻找成熟的图像预处理方案。重点不是“把图片变好看”，而是让 OCR 和图号质量门有机会从不清晰样本中获得更稳定的字段簇和图号候选。

## 样本索引

| 样本 | 类型 | 来源 | 一句话价值 | 不适合照搬 |
| --- | --- | --- | --- | --- |
| OpenCV Image Thresholding | 官方文档 | https://docs.opencv.org/4.x/d7/d4d/tutorial_py_thresholding.html | 覆盖全局阈值、自适应阈值、Otsu，适合构造本地轻量二值化变体 | 不应只选一个阈值算法全局套用 |
| OpenCV Histogram Equalization / CLAHE | 官方文档 | https://docs.opencv.org/4.x/d5/daf/tutorial_py_histogram_equalization.html | 支持全局均衡和 CLAHE 局部对比度增强，适合浅色扫描 crop | CLAHE 会放大噪声，需限制参数并与 OCR 结果对比 |
| OpenCV Smoothing / Filtering | 官方文档 | https://docs.opencv.org/4.x/d4/d13/tutorial_py_filtering.html | 说明低通滤波可去噪但会模糊边缘 | 机械图纸小字和细线不能过度平滑 |
| OpenCV Morphological Transformations | 官方文档 | https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html | 腐蚀、膨胀、开闭运算可用于去小噪声或修复断笔 | 容易让文字与表格线粘连，不能默认自动放行 |
| OpenCV Non-local Means Denoising | 官方文档 | https://docs.opencv.org/4.x/d5/d69/tutorial_py_non_local_means.html | 可作为比简单模糊更保细节的去噪候选 | 计算更慢，参数过强会丢细节 |
| Tesseract ImproveQuality | 官方文档 | https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html | 系统列出反色、缩放、二值化、去噪、膨胀/腐蚀、deskew、border 等 OCR 前处理经验 | Tesseract 内部策略不等于 RapidOCR，但问题模型可迁移 |
| OCR-D Workflow Guide | 官方工作流 | https://ocr-d.de/en/workflows | 将增强、二值化、裁剪、去噪、deskew、dewarp 分成可审计步骤 | 面向书页 OCR，不能整体搬到标题栏 crop |
| scikit-image Niblack / Sauvola | 官方示例 | https://scikit-image.org/docs/stable/auto_examples/segmentation/plot_niblack_sauvola.html | 对背景不均匀文本图像，局部阈值比全局阈值更有针对性 | 需要额外依赖或自行实现，不应作为第一步强依赖 |
| scikit-image Unsharp Masking | 官方示例 | https://scikit-image.org/docs/stable/auto_examples/filters/plot_unsharp_mask.html | 锐化可用原图与模糊图的差分细节增强边缘 | 锐化会放大噪声和表格线，必须限制强度 |
| ScanTailor Advanced | 开源工具 | https://github.com/4lex4/scantailor-advanced | 成熟扫描页后处理工具，包含 deskew、边框、内容区域、输出控制等思路 | 更适合整页扫描后处理，不适合作为标题栏 crop 自动主线 |
| unpaper | 开源工具 | https://github.com/unpaper/unpaper | 扫描纸张后处理工具，适合参考去边、清理、deskew 思路 | 主要面向纸页扫描，不直接解决小标题栏图号 |
| Document image enhancement survey | 论文 | https://arxiv.org/abs/2112.02719 | 梳理文档增强任务：二值化、去模糊、去噪、去褪色、阴影等 | 深度学习增强不是当前默认路线 |
| OCR accuracy preprocessing approach | 论文 | https://arxiv.org/abs/1509.03456 | 提出局部亮度/对比度、灰度转换、Unsharp Mask、全局二值化组合可提升 OCR | 场景偏相机文档，机械标题栏需要单独验证 |
| Text image super-resolution for OCR | 论文 | https://arxiv.org/abs/1506.02211 | 说明低分辨率文本可通过超分辨率提升 OCR | 超分可能生成伪细节，图号命名不能直接放行 |

## 结论摘要

成熟方案不是单一“增强滤镜”，而是一套可回退的派生图像工作流：

```text
原始 crop
  -> 派生多个增强版本
  -> 分别 OCR
  -> 按字段簇、图号候选、命名风险选择证据
  -> 原图和增强图全部留档
```

本项目下一轮应优先测试 OpenCV 可直接实现的轻量变体，不应一开始引入深度学习超分或整页扫描后处理工具。
