# MVP PDF 拆分、VLM 方向识别与旋正脚本计划

日期：2026-07-02

## 背景

用户希望当前先完成 MVP：将前面的图纸拆分脚本和图纸旋转方向识别流程合并为一个 Python 脚本。该脚本读取它所在目录中的 `input/` 目录里的 PDF 图纸，将拆分好的图纸保存为若干 PDF 文件，输出到 `output/` 目录中，并根据识别出的图纸旋转信息把图纸摆正。

上一轮 JS2207 人工审核结论：

- `qwen3.7-plus / 非思考` 可作为 MVP 主方案。
- JS2207 图纸页识别正确率仍不是 100%，第 15 页和第 22 页被判错。
- 因此该 MVP 不能作为无人值守正式批处理，只能作为可追溯的 MVP 自动化链路。

## 目标

1. 新增一个自包含 MVP 脚本目录，脚本从自身所在目录解析：
   - `input/`
   - `output/`
   - `work/`
2. 读取 `input/` 中的 PDF。
3. 将每个 PDF 拆分为单页 PDF。
4. 将单页 PDF 渲染为原向 PNG，用于 VLM 判断标题栏当前位置。
5. 使用 `qwen3.7-plus / 非思考` 判断标题栏位置。
6. 程序按规则派生当前顺时针旋转角度和校正角度。
7. 对可明确校正的页面输出旋正后的单页 PDF 到 `output/`。
8. 对无法明确校正的页面输出未旋转副本，并在报告中标记需要人工复核。

## 非目标

- 不做图号 OCR。
- 不按图号重命名。
- 不合并回多页 PDF。
- 不生成正式交付 PDF 包。
- 不跳过人工复核质量门。
- 不把本地 `input/`、`output/`、`work/` 产物提交到 Git。

## 工程判断

为了保留图纸质量，旋正 PDF 应优先使用 PDF 页面旋转属性或页面对象旋转能力，不把页面渲染成图片后重新生成 PDF。渲染 PNG 只用于 VLM 识别和必要的视觉检查。

批判性风险：

1. 当前 `qwen3.7-plus / 非思考` 在 JS2207 审核中仍有错误，不能直接无人值守放行。
2. 模型可能将明细表、局部表格或无标题栏页面误判为标题栏。
3. 单页 PDF 的已有 `/Rotate` 属性可能与物理内容方向叠加，脚本必须记录原始旋转和应用旋转。
4. VLM 请求逐页独立发送，提示词会重复消耗 token；MVP 暂不优化。
5. 网络/API 失败不能悄悄输出“看似成功”的旋正 PDF。

## 质量门

页面输出状态分为：

- `corrected`：已获得明确校正角度，并生成旋正 PDF。
- `copied_needs_review`：无法获得明确校正角度或模型/解析/API 失败，输出未旋转副本并标记复核。
- `failed`：拆分、渲染或写 PDF 失败。

报告至少包含：

- 源 PDF。
- 页码。
- 输出 PDF 路径。
- VLM 标题栏位置。
- 当前顺时针旋转角度。
- 校正顺时针旋转角度。
- API/解析/schema 状态。
- 输出状态。
- 复核原因。

## 目录设计

建议新增：

```text
tools/pdf_rotation_mvp/
  run_pdf_rotation_mvp.py
  input/.gitkeep
  output/.gitkeep
  work/.gitkeep
  README.md
```

`.gitignore` 需要忽略：

```text
/tools/pdf_rotation_mvp/input/*
/tools/pdf_rotation_mvp/output/*
/tools/pdf_rotation_mvp/work/*
```

并保留 `.gitkeep`。

## 参数

默认参数：

- 模型：`qwen3.7-plus`
- `temperature=0`
- `enable_thinking=false`
- 不设置 `top_p`
- 渲染 DPI：150
- 环境文件：项目根目录 `.env/.env`

命令行参数可覆盖：

- `--input-dir`
- `--output-dir`
- `--work-dir`
- `--env-file`
- `--model`
- `--render-dpi`
- `--limit-pages`
- `--dry-run`

## 实现计划

1. 新增 MVP 工具目录和 README。
2. 新增脚本，复用已有 prompt、VLM 调用和旋转映射逻辑。
3. 用 `pypdf` 拆分和旋转 PDF 页面。
4. 用 Ghostscript 渲染单页 PDF 为 PNG。
5. 逐页调用 VLM 并保存原始响应、决策、manifest 和 summary。
6. 对全请求失败增加硬阻断。
7. 编译检查脚本。
8. 使用 `--dry-run --limit-pages 1` 验证本地拆分/渲染/报告链路，不联网。

## 验收标准

1. 脚本能从自身目录的 `input/` 读取 PDF。
2. `output/` 中按源 PDF 名和页码输出单页 PDF。
3. `work/` 中保留单页拆分、渲染 PNG、raw responses、decisions 和 summary。
4. 对可明确校正页生成旋正 PDF。
5. 对不明确页不强行旋正，并记录复核原因。
6. 脚本语法检查通过。
7. MVP 工具目录的输入输出产物不进入 Git。

## 回滚准备

先提交本计划、RPD 和 TODO。若后续脚本实现或验证失败，可回退到该文档回滚点。
