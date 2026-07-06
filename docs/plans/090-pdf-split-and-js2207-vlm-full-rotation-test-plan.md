# PDF 拆分与 JS2207 VLM 全量方向测试计划

日期：2026-07-02

## 背景

用户要求将 `local_data/source_pdfs/` 下两个 PDF 图纸文件全部拆分出来，分别放入两个文件夹，并优先测试 `JS2207-00-00升降平台.pdf` 中全部图纸方向。

上一轮错题集审核显示，按旋转角度口径：

- `qwen3.7-plus / 非思考`：人工审核 15/15。
- `qwen3.7-max-2026-06-08 / 非思考`：人工审核 15/15。

因此本轮进入 JS2207 全量方向测试，但仍需人工审核后再决定是否用于后续批处理。

## 目标

1. 将两个源 PDF 全部拆分为单页 PDF，并分别存放在两个清晰目录中。
2. 将单页 PDF 渲染为原向 PNG，供审核和 VLM 输入使用。
3. 优先对 JS2207 全部页面调用两个模型：
   - `qwen3.7-plus / 非思考`
   - `qwen3.7-max-2026-06-08 / 非思考`
4. 只让模型判断当前图片屏幕坐标下的标题栏位置，由程序按规则派生当前顺时针旋转角度。
5. 发布低噪声人工审核包到固定入口 `local_data/review_inbox/current/`。

## 输出目录

拆分与渲染输出放入本地忽略目录：

- `local_data/split_source_pdfs/js2207_lifting_platform/`
- `local_data/split_source_pdfs/ykj125_briquetting_machine/`

JS2207 模型测试输出放入本地忽略目录：

- `local_data/vlm_js2207_full_rotation_test/`

固定审核入口：

- `local_data/review_inbox/current/js2207_vlm_full_rotation_review/`

## 人工审核表字段

审核表只保留用户判断旋转角度必须看到的字段：

- `页码`
- `模型`
- `模型派生当前旋转角度`
- `旋转角度是否正确`
- `正确旋转角度`
- `备注`

标题栏位置代码、prompt、raw response、置信度、错误原因、图片路径和调试字段只放入机器报告或 manifest，不出现在人工填写表中。

## 模型参数

- `temperature=0`
- `enable_thinking=false`
- 不设置 `top_p`
- 使用 OpenAI 兼容 Chat Completions 接口
- 使用 `response_format={"type":"json_object"}`

## 约束

- 不读取或打印 `.env/.env` 中的 API Key。
- 不旋转输入图纸。
- 不 resize 输入图片。
- 不使用 JPEG 或有损压缩。
- 不生成正式旋正 PDF。
- 不重命名原始 PDF 或拆分页。
- 不把 `local_data/`、`.env/` 或图纸资料纳入 Git。
- 不将 JS2207 本轮结果直接写入 ground truth。

## 实现计划

1. 更新 RPD 和 TODO，提交文档回滚点。
2. 新增批处理脚本，复用既有 PDF 拆分、Ghostscript 渲染、Excel 生成和固定审核入口发布逻辑。
3. 拆分并渲染两个源 PDF。
4. 对 JS2207 原向 PNG 执行双模型调用。
5. 生成机器报告、原始响应、决策 JSONL/CSV 和 run summary。
6. 发布 HTML + Excel + 图片副本到固定审核入口。
7. 校验页面数、图片数、Excel 行数和审核入口内容。

## 验收标准

1. 两个 PDF 均已拆分为单页 PDF，并分别在独立文件夹中存放。
2. JS2207 页面按页码顺序完成双模型方向测试。
3. 审核 HTML 按页码顺序展示原向图片，图片清晰、不裁切。
4. Excel 行数等于 `JS2207 页数 * 2`，且只包含低噪声人工字段。
5. 固定审核入口 README 只指向本轮 HTML 和 Excel。
6. 未生成正式旋正 PDF，未重命名 PDF，未提交私有数据。

## 回滚准备

先提交本计划、RPD 和 TODO。若后续脚本、拆分或模型调用流程有误，可回退到该文档回滚点。
