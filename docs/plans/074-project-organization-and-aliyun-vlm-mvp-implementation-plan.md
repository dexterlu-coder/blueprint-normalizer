# 项目结构整理与阿里云 VLM MVP 请求包实现计划

## 背景

当前公开仓库已经沉淀了较多阶段性脚本，`scripts/` 根目录同时包含 OpenCV 方向识别、YOLO/OBB、OCR、人工审核归档、MCP/VLM teacher 和 JS2207 泛化测试脚本。继续把所有脚本平铺在同一目录，会增加接手成本，也会让下一步阿里云 VLM MVP 脚本难以归类。

同时，JS2207 泛化测试已经暴露本地流程的泛化风险。当前主线应优先实现阿里云 VLM MVP 的离线请求包生成能力，但不得覆盖当前固定审核入口中已填写的 JS2207 部分人工反馈。

## 目标

1. 清理公开文档中明显误输入和过期状态。
2. 将公开脚本按领域分入子目录，形成清晰的脚本索引。
3. 将脚本调用方式统一为 `python -m scripts.<category>.<module>`。
4. 更新公开文档中的脚本路径和关键运行命令。
5. 保护 `local_data/review_inbox/current/` 中 JS2207 已填写的 6 条反馈，必要时归档为部分审核结果。
6. 新增阿里云 VLM MVP 离线请求包生成脚本，只生成请求包和机器报告，不联网调用。

## 非目标

本轮不做：

- 不删除 `local_data/`、`outputs/`、`runs/` 中的私有或可再生产物。
- 不覆盖当前固定审核入口中的 JS2207 已填写反馈。
- 不正式旋正 PDF。
- 不重命名 PDF。
- 不联网调用阿里云 VLM。
- 不把 API Key 写入仓库、日志或本地输出。
- 不对 JS2207 写特判或继续调本地标题栏检测策略。

## 脚本目录目标结构

```text
scripts/
  README.md
  __init__.py
  common/
  rotation/
  ocr/
  yolo_obb/
  vlm/
  experiments/
```

分类原则：

- `common/`：跨流程公共工具。
- `rotation/`：OpenCV 旋转识别、ground truth、评估和增强样本。
- `ocr/`：标题栏 crop、OCR、图号候选、PDF dry-run、细 ROI 与审核归档。
- `yolo_obb/`：OBB 标注、数据集、训练后处理和复查包。
- `vlm/`：MCP/VLM teacher、provider 请求和阿里云 VLM MVP。
- `experiments/`：特定泛化测试或一次性实验编排，例如 JS2207。

## 阿里云 VLM MVP 请求包

新增脚本建议：

```text
scripts/vlm/build_aliyun_vlm_mvp_requests.py
```

第一版能力：

1. 从 PDF 或 PNG 输入构造页面任务。
2. 对图片做长边限制和 JPEG 压缩。
3. 生成 Base64 data URL。
4. 输出 OpenAI 兼容 chat completions 请求 JSONL。
5. 输出 prompt、response schema、manifest、summary 和 request CSV。
6. 检查环境变量是否存在，但不打印 `DASHSCOPE_API_KEY`。
7. 默认只支持 `--dry-run-build-requests`，不联网。

输出目录：

```text
local_data/aliyun_vlm_mvp/
```

请求包文件：

```text
vlm_requests.jsonl
vlm_request_manifest.json
vlm_request_manifest.csv
vlm_prompt.md
vlm_response_schema.json
vlm_mvp_summary.json
vlm_input_images/
```

## 固定审核入口处理

当前固定入口仍包含 JS2207 泛化测试部分人工反馈：

- 总页数：29。
- 已填写：6。
- 未填写：23。
- 已指出旋转/标题栏位置错误：第 3 页、第 6 页。

在发布任何新的审核入口前，必须先把当前入口归档到：

```text
local_data/review_inbox/archive/js2207_generalization_review_partial_<timestamp>/
```

若本轮只生成阿里云 VLM 请求包、不发布人工审核入口，则可以不替换 `current`。但 `HANDOFF.md` 和 `README.md` 必须说明当前入口状态，避免误以为没有待审核文件。

## 验证标准

1. `python -m py_compile` 覆盖整理后的关键脚本。
2. 关键脚本模块导入不因移动目录失败。
3. `scripts/README.md` 能说明脚本分类和常用入口。
4. 公开文档不再指向已移动的关键脚本旧路径。
5. 阿里云 VLM 请求包脚本在无 API Key 时仍能 dry-run 生成请求包，并且不泄漏敏感值。
6. dry-run 不修改原始 PDF。
7. dry-run 不重命名单页 PDF。
8. `git status --short` 不显示 `local_data/` 私有数据进入 Git。

## 回滚准备

本计划、RPD 和 TODO 提交后作为结构整理和 VLM 请求包实现前回滚点。若脚本移动造成引用问题，可以回退到该提交，再缩小整理范围或改为只补索引不移动脚本。
