# 账号切换当前状态交接计划

日期：2026-07-04

## 背景

用户准备切换账号，需要把当前所有应保存的项目状态记录清楚，确保新账号或新会话可以直接接手。现有根目录 `HANDOFF.md` 已滞后，仍记录 2026-07-02 早期阿里云 VLM MVP 状态，未覆盖后续图纸旋正、图号命名、用户审核结果、ROI 收敛展示包等最新状态。

## 目标

1. 更新根目录 `HANDOFF.md`，作为账号切换后的首要交接入口。
2. 记录当前 Git 状态、最近关键提交和文档索引。
3. 记录当前固定审核入口：

```text
local_data/review_inbox/current/
```

4. 记录本地私有产物位置，但不提交产物、不泄露 API key。
5. 记录当前 MVP 流水线状态、已知问题、下一步优先事项和暂停点。
6. 更新 RPD 和 TODO，并提交回滚点与完成记录。

## 必须记录的状态

- 当前 Git 工作区是否干净。
- 当前固定入口内容和用途。
- 当前公开主线：PDF 拆分、VLM 方向识别、旋正、标题栏图号 OCR、按图号命名 PDF 的 MVP。
- 当前推荐模型：MVP 阶段使用 `qwen3.7-plus / 非思考`。
- API key 位置：`.env/.env`，只记录路径，不读取、不打印、不提交。
- 阿里云联网命令必须提权或复用已批准前缀，避免普通沙箱 socket 权限错误。
- 当前源 PDF：
  - `local_data/source_pdfs/JS2207-00-00升降平台.pdf`
  - `local_data/source_pdfs/YKJ125-00-00-2525铁屑压块机生产图（250911章）解密.pdf`
- 当前工具：
  - `tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py`
  - `tools/pdf_rotation_mvp/input/`
  - `tools/pdf_rotation_mvp/output/`
  - `tools/pdf_rotation_mvp/work/`
- 当前已知问题：
  - 第 22 页方向仍未摆正。
  - 无标题栏/无图号页需要落实 `待人工复核_XX` 命名规则。
  - 后续任何新审核入口必须先归档当前 `current`。

## 非目标

- 不重新调用阿里云模型。
- 不重新处理 PDF。
- 不修改 MVP 脚本逻辑。
- 不归档或覆盖当前固定入口。
- 不读取、打印、复制或提交 `.env/.env` 中的密钥。
- 不提交 `local_data/`、`output/`、模型响应或图纸 PDF。

## 验收标准

1. `HANDOFF.md` 当前状态与 `TODO.md` 和 RPD 一致。
2. `HANDOFF.md` 明确新会话先读文件、当前入口、下一步、禁止事项和可运行检查。
3. `HANDOFF.md` 不包含密钥内容或私有图纸正文。
4. RPD 和 TODO 留下本轮交接记录。
5. Git 提交完成后，除允许的本地私有产物外，公开工作区状态清晰。

## 回滚准备

先提交本计划、RPD 和 TODO，作为更新交接文档前回滚点。若交接文档遗漏状态，可在该回滚点之后继续修正。
