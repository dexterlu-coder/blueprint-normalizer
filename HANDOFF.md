# BlueprintNormalizer 账号切换交接文档

交接时间：2026-07-08

当前项目路径：

```text
D:\project\codex\BlueprintNormalizer
```

当前 GitHub 仓库：

```text
https://github.com/dexterlu-coder/blueprint-normalizer.git
```

当前分支和提交：

```text
branch: master
commit: run `git log --oneline -1` to confirm the current single snapshot
pre-handoff-refresh baseline: 6018d55 Initial snapshot for BlueprintNormalizer
history: 1 commit
```

## 新账号接手先读

1. `AGENTS.md`
2. `HANDOFF.md`
3. `TODO.md`
4. `reports/rpd-rotation-detection.md`
5. `README.md`
6. `etc/blueprint-normalizer.example.toml`
7. `tools/pdf_rotation_mvp/README.md`

## 当前状态一句话

项目已经完成顶层目录改名、GitHub 新仓库切换、旧仓库删除、当前目录原地单提交历史重建，以及阶段 2 的多数包内模块迁移。当前仍未完成的是 `TODO.md` 中的阶段 2 父任务：最小 MVP 主线尚未完整接通到包内 `run`，阶段 3 CLI/配置加载也尚未开始。

## 当前 Git 状态

最后一次核对时：

- 工作区干净。
- `master` 与 `origin/master` 同步。
- 本地历史只有 1 个提交。
- `origin` 指向 `https://github.com/dexterlu-coder/blueprint-normalizer.git`。
- 禁区路径未进入 Git：`local_data`、`.env`、`outputs`、`runs`、真实 `blueprint-normalizer.toml`。

接手后先运行：

```powershell
git status --short --branch
git log --oneline -1
git rev-list --count HEAD
git remote -v
git ls-files local_data .env outputs runs blueprint-normalizer.toml
```

预期：

- `git status` 显示 `## master...origin/master`，无文件改动。
- 最新提交是 1 个 `Initial snapshot for BlueprintNormalizer` 单提交快照。
- `git rev-list --count HEAD` 输出 `1`。
- 禁区路径检查无输出。

## 已完成的仓库与命名事项

- 顶层目录已从旧项目名改为 `BlueprintNormalizer`。
- 新 GitHub 仓库已创建并确认可用。
- 旧 GitHub 仓库 `pictureAnalyse` 已删除。
- 当前目录已原地重建为单提交 Git 历史，没有再使用误创建的平行项目目录。
- 当前远端已指向 `blueprint-normalizer`。

项目命名约定：

```text
产品名：BlueprintNormalizer
本地顶层目录：BlueprintNormalizer
GitHub 仓库名：blueprint-normalizer
Python 包名：blueprint_normalizer
CLI 命令：blueprint-normalizer
配置文件：blueprint-normalizer.toml
示例配置：etc/blueprint-normalizer.example.toml
```

## 当前 TODO 真实进度

以 `TODO.md` 为准。

已完成并标记 `[x]` 的主要阶段 2 子任务：

- Python `src/` 布局和基础 CLI/dry-run 骨架。
- `runtime_config.py`
- `domain.py`
- `execution_plan.py`
- `workflow.py`
- `io_boundary.py`
- `report_writer.py`
- prompt 资源迁移。
- `vlm_request.py` 中的请求构造、data URL、脱敏日志行。
- `run_summary.py`
- `pipeline.py` 的 `build_run_disabled_report()` 守门骨架。
- `pdf_output.py` 的 `rotate_or_copy_pdf()` 和 `publish_final_pdfs()`。
- `title_block_crop.py` 的 `crop_title_block_candidate()`。
- 对应单元测试和非联网验证。

仍未完成并保持 `[ ]` 的关键项：

- `迁移最小 MVP 主线到包内模块，逐步接入拆页渲染、模型请求、旋转发布和报告写出。`
- 阶段 3：CLI、运行目录和配置加载。
- 阶段 4：文档目录迁移和入口更新。
- 阶段 5：测试与验证。
- 阶段 6：EXE 打包准备。
- 后续业务待办。

重要判断：不要因为阶段 2 多个子模块已完成，就把阶段 2 父任务勾掉。完整包内 `run` 尚未接通拆页、Ghostscript 渲染、真实模型请求、旋转发布、标题栏裁剪、图号识别和报告写出。

## 最近完成的小步

最近完成的是标题栏裁剪候选图迁移：

- 新增 `src/blueprint_normalizer/pdf_rotation_mvp/title_block_crop.py`。
- 新增 `tests/unit/test_pdf_rotation_mvp_title_block_crop.py`。
- 迁移旧 MVP 的 `crop_title_block_candidate()`。
- 保留横向图底部 30%、竖向图底部 35% 的裁剪策略。
- 单元测试只使用临时合成 PNG，不读取真实图纸。

最后一次完整非联网验证通过：

```powershell
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
python -m compileall src tests
python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py
$env:PYTHONPATH='src'; python -m blueprint_normalizer pdf-rotation-mvp dry-run --config etc\blueprint-normalizer.example.toml
git ls-files local_data .env outputs runs blueprint-normalizer.toml
```

当时单元测试总数：55 个，通过。

## 当前 CLI 状态

已存在：

```powershell
python -m blueprint_normalizer --help
python -m blueprint_normalizer config check --config etc\blueprint-normalizer.example.toml
python -m blueprint_normalizer pdf-rotation-mvp dry-run --config etc\blueprint-normalizer.example.toml
```

其中 `pdf-rotation-mvp dry-run` 是非联网报告，不读 PDF、不调用模型、不调用 Ghostscript、不写审核入口。

尚未完成：

```powershell
blueprint-normalizer config init
blueprint-normalizer pdf-rotation-mvp run
```

`pdf-rotation-mvp run` 目前仍应被视为未启用真实副作用流程。

## 旧 MVP 入口状态

旧入口仍保留作为回归对照：

```text
tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py
```

当前阶段不要删除旧入口，不要把它改成真实主入口。后续若要变成薄 wrapper，应先按 `AGENTS.md` 要求规划、更新 RPD、更新 TODO、提交回滚点，再实现。

## 私有数据与密钥

严禁读取、打印、提交：

```text
.env/.env
blueprint-normalizer.toml
local_data/
outputs/
runs/
真实图纸 PDF
模型请求/响应原文
```

真实配置文件尚不应提交。仓库中只能保留：

```text
etc/blueprint-normalizer.example.toml
```

## 阿里云模型联网规则

当前交接不需要联网模型调用。

后续一旦涉及阿里云百炼、DashScope、OpenAI-compatible endpoint 的真实模型调用、OCR/VLM 测试、smoke test 或批量实验：

- 直接使用已批准命令前缀或 `sandbox_permissions=require_escalated`。
- 不要先在普通沙箱中试跑真实联网请求。
- 提权理由要说明是为了访问阿里云模型接口、避免沙箱 Windows socket 权限错误。
- 不得因此跳过 dry-run、日志脱敏、质量门、错误分层、人工审核入口或回滚准备。
- 不得读取、打印、提交 `.env/.env` 中的密钥。

## 固定审核入口规则

所有需要用户打开、填写、标注或参考的当前任务文件，必须统一放在：

```text
local_data/review_inbox/current/
```

新账号接手后不要随意覆盖该目录。发布新的审核包前，先确认当前内容是否需要归档。

## 下一步建议

优先按 `TODO.md` 继续，不要跳阶段。

推荐下一步：

1. 重新阅读 `TODO.md` 中阶段 2 未完成父任务。
2. 用批判性思维判断：是继续把最小 MVP 主线接通到包内 `run`，还是先把该父任务拆成更小的剩余子任务。
3. 若继续阶段 2，先在 RPD 中规划下一个小步，不要直接接入真实模型或真实 PDF。
4. 若准备进入阶段 3，必须先处理阶段 2 父任务的状态：完成、拆分、或明确后置，不能让 TODO 语义悬空。
5. 任何实现前都遵守 `AGENTS.md` 工作流：先规划、再 RPD、再 TODO、再提交回滚点、最后实现。

不要马上做：

- 不要直接运行真实 `pdf-rotation-mvp run`。
- 不要读取 `.env/.env`。
- 不要处理真实业务 PDF。
- 不要调用阿里云。
- 不要移动 `reports/`、`rules/`、`references/`，除非进入阶段 4 并先完成规划。
- 不要删除旧 MVP 脚本。
- 不要把阶段 2 父任务误标为完成。

## 接手后最小检查命令

```powershell
git status --short --branch
git log --oneline -1
git rev-list --count HEAD
git remote -v
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
python -m compileall src tests
python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py
$env:PYTHONPATH='src'; python -m blueprint_normalizer pdf-rotation-mvp dry-run --config etc\blueprint-normalizer.example.toml
git ls-files local_data .env outputs runs blueprint-normalizer.toml
```

预期：

- 测试全部通过。
- dry-run 报告显示不读 PDF、不调用模型、不调用 Ghostscript、不写 `local_data/review_inbox/current/`。
- 禁区路径检查无输出。
