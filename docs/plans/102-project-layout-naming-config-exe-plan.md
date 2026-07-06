# 项目目录、命名、配置与 EXE 发布综合整理计划

日期：2026-07-06

## 背景

当前项目名 `pictureAnalyse` 更像临时实验目录，不足以表达项目正在形成的能力：机械图纸 PDF 拆分、方向识别、旋正、标题栏图号读取、按图号命名单页 PDF。当前主程序位于 `tools/pdf_rotation_mvp/`，容易让人误解为辅助工具，而不是面向用户的正式程序。

用户希望项目最终能编译成 Windows `.exe`，并采用接近 Linux/便携式程序的习惯：程序文件与配置文件放在同一个应用目录内，配置只影响当前程序，不污染其他项目或系统环境。

本计划只做目录、命名、配置与发布形态的综合设计。未获审核前，不移动源码、不修改程序逻辑、不读取或写入真实 API key。

## 调研依据

- Python 官方打包生态推荐 `src/` 布局，将可导入源码包放入 `src/<package>/`，避免仓库根目录污染导入路径。
- Python 命令行程序通常通过 `pyproject.toml` 的 `[project.scripts]` 暴露入口，而不是要求用户直接运行仓库内某个脚本文件。
- Python 项目的构建产物通常进入 `dist/`，不提交进 Git；安装后生成的可执行入口由 venv、pip、pipx 或打包器生成。
- PyInstaller 这类 `.exe` 打包工具通常将运行目录与打包时临时目录区分处理；外部可编辑配置不应打入只读包内部，而应放在 exe 同级目录。
- 阿里云百炼/DashScope 推荐以 API key 访问模型；本项目按用户偏好改为优先读取当前应用目录内的配置文件，不强制使用全局环境变量。
- GitHub 官方支持仓库重命名并为旧 URL 提供重定向；若删除重建仓库，则应确认本地 Git 历史完整。
- GitHub README 应说明项目用途、使用方式、获取帮助方式；本项目额外要求 README 对 AI 接手友好。

参考链接：

- `https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/`
- `https://packaging.python.org/en/latest/guides/creating-command-line-tools/`
- `https://packaging.python.org/en/latest/guides/writing-pyproject-toml/`
- `https://pyinstaller.org/en/stable/runtime-information.html`
- `https://pyinstaller.org/en/stable/spec-files.html`
- `https://www.alibabacloud.com/help/en/model-studio/get-api-key`
- `https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository`
- `https://docs.github.com/en/repositories/creating-and-managing-repositories/deleting-a-repository`
- `https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes`

## 推荐新名称

用户已确认采用：

```text
BlueprintNormalizer
```

命名对应关系：

| 场景 | 名称 |
| --- | --- |
| 产品名 | `BlueprintNormalizer` |
| Windows 程序名 | `BlueprintNormalizer.exe` |
| Linux 程序名 | `blueprint-normalizer` |
| Python 包名 | `blueprint_normalizer` |
| CLI 命令 | `blueprint-normalizer` |
| GitHub 仓库名 | `blueprint-normalizer` |
| 本地顶层目录建议名 | `BlueprintNormalizer` |

选择理由：

- `BlueprintNormalizer` 比 `pictureAnalyse` 更像正式产品名，表达“将图纸整理为统一可读、可命名、可交付状态”。
- `Normalizer` 覆盖方向旋正、图号命名、质量门和后续批量输出，不局限于当前单一脚本。
- `blueprint_normalizer` 符合 Python 包名规范。
- `blueprint-normalizer` 符合命令行和 GitHub 仓库常见命名习惯。
- Windows exe 使用 PascalCase，Linux 可执行文件使用小写连字符，贴合各自平台习惯。

备选名称：

| 名称 | 优点 | 不采用原因 |
| --- | --- | --- |
| `MechDraw` | 简短，聚焦机械图纸 | 用户更喜欢 `BlueprintNormalizer`，且 `Normalizer` 更贴合最终交付流程 |
| `DrawingNormalizer` | 表达旋正/规范化 | 偏长，且弱化机械图纸领域 |
| `MechanicalDrawingProcessor` | 非常明确 | 作为 exe 和包名过长 |
| `SheetAligner` | 方向校正语义清楚 | 无法覆盖图号 OCR 与命名 |

## 顶层目录改名

本地顶层目录当前为：

```text
D:\project\codex\pictureAnalyse
```

建议由用户手动改为：

```text
D:\project\codex\BlueprintNormalizer
```

注意：

- Git 不跟踪父目录名，改名不会破坏 `.git` 历史。
- 当前 Codex 会话的工作目录会因此失效；改名后应从新路径重新打开 Codex/终端。
- 改名前应确认 `git status --short` 干净。
- 改名后第一件事应运行：

```powershell
git -c core.excludesFile= status --short
git remote -v
```

预期：

- Git 工作区仍干净。
- remote 暂时仍指向旧 GitHub 仓库，后续在 GitHub 处理阶段更新。

## 目标源码目录

整理后，公开源码应集中在 `src/blueprint_normalizer/`：

```text
BlueprintNormalizer/
├─ src/
│  └─ blueprint_normalizer/
│     ├─ __init__.py
│     ├─ __main__.py
│     ├─ cli.py
│     ├─ config.py
│     ├─ paths.py
│     ├─ common/
│     ├─ rotation/
│     ├─ ocr/
│     ├─ yolo_obb/
│     ├─ vlm/
│     ├─ experiments/
│     └─ pdf_rotation_mvp/
│        ├─ __init__.py
│        ├─ cli.py
│        ├─ pipeline.py
│        ├─ prompts/
│        └─ schemas/
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  └─ fixtures/
├─ docs/
│  ├─ plans/
│  ├─ research/
│  ├─ workflows/
│  ├─ decisions/
│  ├─ reports/
│  ├─ rules/
│  └─ references/
├─ etc/
│  ├─ blueprint-normalizer.example.toml
│  └─ README.md
├─ packaging/
│  └─ pyinstaller/
│     └─ BlueprintNormalizer.spec
├─ local_data/
├─ outputs/
├─ runs/
├─ pyproject.toml
├─ README.md
├─ AGENTS.md
├─ HANDOFF.md
└─ TODO.md
```

## 目录映射

| 当前路径 | 目标路径 | 说明 |
| --- | --- | --- |
| `scripts/common/` | `src/blueprint_normalizer/common/` | 公共模块 |
| `scripts/rotation/` | `src/blueprint_normalizer/rotation/` | 旋转检测与评估 |
| `scripts/ocr/` | `src/blueprint_normalizer/ocr/` | OCR、ROI、图号候选 |
| `scripts/yolo_obb/` | `src/blueprint_normalizer/yolo_obb/` | YOLO/OBB 数据与后处理 |
| `scripts/vlm/` | `src/blueprint_normalizer/vlm/` | VLM 请求、响应与 teacher 流程 |
| `scripts/experiments/` | `src/blueprint_normalizer/experiments/` | 历史实验编排 |
| `tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py` | `src/blueprint_normalizer/pdf_rotation_mvp/` | 正式 MVP 程序模块 |
| `reports/` | `docs/reports/` | 需求和阶段记录归入文档树 |
| `rules/` | `docs/rules/` | 长期规则归入文档树 |
| `references/` | `docs/references/` | 外部资料索引归入文档树 |
| `tools/` | 删除或保留为空 | 不再承载正式程序 |

不移动：

- `.env/`：旧本地密钥目录，迁移完成后可废弃，但不提交、不读取。
- `local_data/`：私有图纸、审核入口、本地数据，继续忽略。
- `outputs/`：可再生输出，继续忽略。
- `runs/`：训练和实验输出，继续忽略。
- `tools/pdf_rotation_mvp/input/output/work` 中的现有私有产物：不作为公开迁移对象。

## 最终 EXE 运行目录

最终发布给用户的目录建议为：

```text
BlueprintNormalizer/
├─ BlueprintNormalizer.exe
├─ blueprint-normalizer.toml
├─ input/
├─ output/
├─ work/
├─ logs/
└─ README.txt
```

设计原则：

- `BlueprintNormalizer.exe` 与 `blueprint-normalizer.toml` 同级。
- 用户只需要把 PDF 放入 `input/`，运行 exe 后从 `output/` 取结果。
- `work/` 保存中间页、渲染图、模型响应、机器报告；默认保留，便于错误分层和人工复核。
- `logs/` 保存运行日志；日志不得打印 API key。
- 这个目录可以整体复制到其他位置使用，不依赖系统级环境变量。

Linux 发布目录对应为：

```text
blueprint-normalizer/
├─ blueprint-normalizer
├─ blueprint-normalizer.toml
├─ input/
├─ output/
├─ work/
├─ logs/
└─ README.txt
```

## 配置文件设计

公开仓库只提交模板：

```text
etc/blueprint-normalizer.example.toml
```

真实配置文件：

```text
blueprint-normalizer.toml
```

真实配置文件应加入 `.gitignore`，不得提交。最终 exe 发布目录中的 `blueprint-normalizer.toml` 与 `BlueprintNormalizer.exe` 同级。

建议模板内容：

```toml
[qwen]
api_key = ""
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
model = "qwen3.7-plus"
temperature = 0
enable_thinking = false
top_p = ""

[paths]
input_dir = "input"
output_dir = "output"
work_dir = "work"
log_dir = "logs"

[runtime]
keep_work_files = true
dry_run = false
```

配置优先级：

1. 命令行显式传入：`--config <path>`。
2. `BlueprintNormalizer.exe` 同级的 `blueprint-normalizer.toml`。
3. 开发态仓库根目录的 `blueprint-normalizer.toml`。
4. 仅在配置允许时，兼容读取环境变量或旧 `.env/.env`。

默认策略：

- 优先使用同目录配置文件。
- 不要求用户设置系统环境变量，避免影响其他项目。
- `blueprint-normalizer config check` 只显示配置项是否存在，不显示 key 内容。
- `blueprint-normalizer config init` 可以从 `etc/blueprint-normalizer.example.toml` 或内置模板生成本地 `blueprint-normalizer.toml`。

## 命令入口设计

开发态命令：

```powershell
python -m blueprint_normalizer pdf-rotation-mvp run --config blueprint-normalizer.toml
```

安装态命令：

```powershell
blueprint-normalizer pdf-rotation-mvp run --config blueprint-normalizer.toml
```

EXE 形态命令：

```powershell
.\BlueprintNormalizer.exe pdf-rotation-mvp run
```

常用子命令：

```text
blueprint-normalizer config init
blueprint-normalizer config check
blueprint-normalizer pdf-rotation-mvp run
blueprint-normalizer pdf-rotation-mvp dry-run
```

## 开发态与使用者自行编译

仓库应同时支持两类使用方式：

1. 开发者调试：直接用 Python 源码运行和测试。
2. 下载使用者：按 README 指引自行在 Windows 或 Linux 上编译本平台可执行文件。

开发者调试建议：

```powershell
python -m pip install -e .
python -m blueprint_normalizer --help
python -m blueprint_normalizer pdf-rotation-mvp dry-run --config blueprint-normalizer.toml
```

Windows 使用者自行构建：

```powershell
python -m pip install -r requirements.txt
python -m pip install pyinstaller
pyinstaller packaging\pyinstaller\BlueprintNormalizer.spec
```

Linux 使用者自行构建：

```bash
python -m pip install -r requirements.txt
python -m pip install pyinstaller
pyinstaller packaging/pyinstaller/BlueprintNormalizer.spec
```

跨平台原则：

- Windows `.exe` 在 Windows 环境构建。
- Linux 可执行文件在 Linux 环境构建。
- 发布包中不包含真实 `blueprint-normalizer.toml`，只包含可复制的模板。
- 真实联网 smoke test 仍遵守阿里云联网提权规则。

后续可以新增 GitHub Actions matrix：

```yaml
strategy:
  matrix:
    os: [windows-latest, ubuntu-latest]
```

GitHub Actions 目标是生成 release artifact：

```text
BlueprintNormalizer-windows-x64.zip
BlueprintNormalizer-linux-x64.tar.gz
```

## GitHub 仓库处理

目标仓库名：

```text
blueprint-normalizer
```

推荐方案：

- 从 GitHub 页面将旧仓库 `pictureAnalyse` 重命名为 `blueprint-normalizer`。
- GitHub 官方会为旧 URL 提供重定向，随后本地执行：

```powershell
git remote set-url origin https://github.com/dexterlu-coder/blueprint-normalizer.git
git remote -v
```

用户当前判断该仓库没有关注者，因此也可以删除旧仓库后重新创建新仓库。若采用删除重建：

- 删除前确认本地仓库完整且 `git status --short` 干净。
- 新建仓库时不要初始化 README、LICENSE 或 `.gitignore`，避免与本地历史冲突。
- 新仓库创建后执行：

```powershell
git remote set-url origin https://github.com/dexterlu-coder/blueprint-normalizer.git
git push -u origin master
```

注意：

- 删除 GitHub 仓库不会删除本地 `.git` 历史。
- 删除重建会丢失 GitHub 仓库设置、issue、star、权限等远程状态；当前无人关注时风险较低。
- 具体处理 GitHub 前，先完成本地顶层目录改名和交接检查。

## 面向 AI 的 README 契约

根目录 README 不只服务人类，也要方便 AI 快速接手。后续 README 应采用稳定、低噪声、可检索的结构：

```text
# BlueprintNormalizer

## AI Quick Context
- product:
- repository:
- package:
- current_goal:
- main_entrypoints:
- config_file:
- private_data:
- do_not_commit:
- current_review_inbox:
- known_risks:
- next_steps:

## Human Quick Start
## Development Setup
## Configuration
## Run With Python
## Build Executable
## Release Layout
## Directory Map
## Data And Privacy
## Quality Gates
## Documentation Index
## Maintainer Handoff
```

原则：

- README 顶部用 `AI Quick Context` 给出机器可直接读取的事实清单。
- 人类快速使用路径靠前，长历史和调研放入 `docs/`。
- 路径、配置文件名、命令名要统一，不让 AI 在旧名和新名之间猜。
- 明确 `local_data/`、`outputs/`、`runs/`、真实配置文件和模型响应不得提交。
- 明确当前审核入口 `local_data/review_inbox/current/` 的规则。
- README 不记录真实 API key，不粘贴模型原始响应。

## 对源码的影响

目录调整会影响源码，不能只移动文件。

必须修改的内容：

- 包导入路径：从 `scripts.*` 改为 `blueprint_normalizer.*`。
- 项目根定位：不能继续依赖 `Path(__file__).resolve().parents[2]`，应统一通过 `blueprint_normalizer.paths` 判断开发态根目录、exe 运行目录和工作目录。
- MVP 默认路径：从 `tools/pdf_rotation_mvp/input/output/work` 改为运行目录下的 `input/output/work`。
- 配置加载：从 `.env/.env` 和环境变量优先，改为 `blueprint-normalizer.toml` 优先。
- 命令文档：所有当前入口文档需要更新为 `blueprint-normalizer` 或 `BlueprintNormalizer.exe` 命令。
- 阿里云联网执行规则：旧批准前缀 `python tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 会失效，真实联网模型调用需要新增批准命令前缀或继续使用 `sandbox_permissions=require_escalated`。
- 测试路径：新增 `tests/` 后，需要覆盖导入、配置解析、路径解析、文件命名质量门等低风险测试。

允许保留历史记录中的旧路径：

- 旧计划、旧 RPD 段落、历史执行记录可以保留当时路径，不做机械全局替换。
- 当前 README、HANDOFF、docs 索引、运行说明必须更新为新入口。

## 统一实施计划

本节是工程化整理的唯一阶段管理入口。后续不再为每个阶段新增独立计划文件；阶段细节、风险、验收和阻断条件统一补充到本节。历史执行结果仍记录在 RPD，当前可执行清单仍同步到 `TODO.md`。

统一管理规则：

- 一个主计划：本文件负责管理阶段 0 到阶段 7 的范围、顺序、验收和阻断条件。
- 一个任务板：`TODO.md` 只保留当前可执行 checklist，不承载长篇背景。
- 一个事实记录：`reports/rpd-rotation-detection.md` 记录用户决策、执行结果和验证输出。
- 不为阶段 1、阶段 2 等继续新增分散计划文件。
- 若阶段计划需要修正，直接修订本节，并同步 RPD/TODO。
- 每个阶段执行前仍按 AGENTS 规则：先规划，再 RPD，再 TODO，再提交回滚点，最后实现。

### 阶段 0：规划、命名、Git 和本地收口

状态：已完成。

完成内容：

- 确认产品名 `BlueprintNormalizer`。
- 确认 Python 包名 `blueprint_normalizer`、CLI 命令 `blueprint-normalizer`、GitHub 仓库名 `blueprint-normalizer`。
- 顶层目录已改为 `D:\project\codex\BlueprintNormalizer`。
- 新 GitHub 仓库已建立：`https://github.com/dexterlu-coder/blueprint-normalizer.git`。
- 旧 GitHub 仓库 `pictureAnalyse` 已删除。
- 当前目录已原地重建为单提交 Git 仓库。
- 本地磁盘清理只制定方案，用户已决定跳过清理执行。

验收：

- `git rev-list --count HEAD` 为 `1`。
- `origin` 指向 `blueprint-normalizer`。
- `git ls-files local_data .env outputs runs blueprint-normalizer.toml` 无输出。

### 阶段 1：项目元信息、配置模板和 CLI 骨架

状态：已完成。

目标：

- 建立标准 Python `src/` 布局。
- 建立 `blueprint-normalizer` CLI 入口。
- 建立同目录配置模板和安全解析逻辑。
- 建立基础测试目录和最小非联网测试。
- 建立 PyInstaller 打包目录占位。

明确不做：

- 不迁移 `scripts/`。
- 不迁移 `tools/pdf_rotation_mvp/`。
- 不读取 `.env/.env`。
- 不读取真实 `blueprint-normalizer.toml`。
- 不调用阿里云、DashScope 或 OpenAI-compatible endpoint。
- 不处理真实 PDF、不生成审核包、不改动 `local_data/review_inbox/current/`。

已落地文件：

```text
pyproject.toml
src/blueprint_normalizer/__init__.py
src/blueprint_normalizer/__main__.py
src/blueprint_normalizer/cli.py
src/blueprint_normalizer/config.py
src/blueprint_normalizer/paths.py
etc/blueprint-normalizer.example.toml
etc/README.md
tests/
packaging/pyinstaller/BlueprintNormalizer.spec
```

已通过非联网验证：

```powershell
python -m py_compile ...
python -m compileall src tests
$env:PYTHONPATH='src'; python -m blueprint_normalizer --help
$env:PYTHONPATH='src'; python -m blueprint_normalizer config check --config etc\blueprint-normalizer.example.toml
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
```

注意：

- 当前 PyInstaller spec 只是占位，不代表 EXE 已可打包。
- 当前 CLI 只提供骨架能力，不承载真实 MVP 批处理。

### 阶段 2：收窄版 MVP 主线迁移

状态：待执行。

核心决策：

阶段 2 不再执行 `scripts/*` 全量迁移。先只处理当前正式 MVP 主线 `tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py`，把用户真正会运行的流程稳定迁入 `src/blueprint_normalizer/pdf_rotation_mvp/`。历史实验脚本延后单独处理。

风险判断：

- `scripts/*` 覆盖 OpenCV、YOLO/OBB、OCR、VLM、历史实验和审核包脚本；一次性迁移会导致导入路径、本地数据路径、文档命令、联网批准前缀同时变化。
- 旧 MVP 当前读取 `DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`，新目标要求优先读取同目录 `blueprint-normalizer.toml`。
- 旧 MVP 默认路径绑定 `tools/pdf_rotation_mvp/input/output/work`，新目标要求应用目录下 `input/output/work/logs`。
- EXE 打包还未验证 Ghostscript、外部命令、模板配置复制和真实配置排除。

分步计划：

1. 只读审计旧 MVP
   - 审计 `tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py` 的函数边界、全局变量、路径默认值、凭据读取、联网函数和外部命令。
   - 记录需要参数化的对象：`SCRIPT_DIR`、默认 `input/output/work`、`DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`、联网请求函数、Ghostscript 调用。
   - 不修改源码。

   已完成审计结论：
   - 旧 MVP 主程序为 1274 行单文件脚本，当前可编译。
   - 全局路径默认值绑定 `SCRIPT_DIR / input|output|work`，配置默认值绑定 `REPO_ROOT / .env / .env`。
   - `run()` 会校验 `output_dir`、`work_dir` 必须位于 `SCRIPT_DIR` 下，并会清空 `work_dir` 以及每个源 PDF 对应的输出子目录。
   - `--dry-run` 只跳过 VLM 联网和最终纠正成功状态，不是纯结构检查；仍会收集真实 PDF、拆分页、Ghostscript 渲染、生成 work/output 报告和复制 needs-review PDF。
   - 凭据读取通过 `read_env_file()`、`load_env()` 写入 `os.environ`，后续从 `DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL` 读取。
   - 联网调用集中在 `post_chat_completion()`，由 `urllib.request.urlopen()` POST 到 chat completions endpoint；调用入口集中在 `call_vlm_for_records()`。
   - 外部命令集中在 `find_ghostscript()`、`run_command()`、`render_pdf_page()`，依赖 `gswin64c`、`gswin32c` 或 `gs`。
   - 适合优先迁移的纯逻辑包括文件名清洗、图号规范化、位置到旋转角度映射、模型响应 JSON 解析、响应校验、决策构建和报告行构建。
   - 需要延后或隔离迁移的副作用逻辑包括路径清空、PDF 拆分、Ghostscript 渲染、VLM 联网、PDF 旋转/复制和最终发布。
   - 第一批纯逻辑已迁入 `src/blueprint_normalizer/pdf_rotation_mvp/domain.py`，覆盖文件名、图号、位置映射、响应解析和决策构建；副作用逻辑仍未迁入。

2. 创建包内 MVP 目录

```text
src/blueprint_normalizer/pdf_rotation_mvp/
├─ __init__.py
├─ cli.py
├─ pipeline.py
├─ legacy_adapter.py
├─ prompts/
└─ schemas/
```

3. 建立配置适配层
   - 扩展 `blueprint_normalizer.config`，将 TOML 模板转换为 MVP 运行配置。
   - `--config <path>` 优先。
   - EXE 同级配置和开发根目录配置作为默认候选。
   - 环境变量或旧 `.env/.env` 只能作为显式兼容 fallback。
   - 不打印 `api_key`。
   - 阶段 2 新 dry-run 不应复用旧脚本 `--dry-run` 语义；必须是包内新增的结构检查，不读取真实 PDF、不调用 Ghostscript、不写输出目录、不读取 `.env/.env`。

4. 新增 CLI dry-run

```powershell
python -m blueprint_normalizer pdf-rotation-mvp dry-run
```

本阶段 dry-run 只检查：

- 配置可解析。
- 输入、输出、工作目录语义可计算。
- 外部命令依赖只做存在性或跳过说明。
- 不处理真实 PDF。
- 不调用阿里云。

   已完成本小步：
   - 已新增 `src/blueprint_normalizer/pdf_rotation_mvp/` 包目录。
   - 已新增包内 `cli.py`、`pipeline.py`、`legacy_adapter.py`。
   - 已新增 `prompts/`、`schemas/` 占位目录。
   - 已在主 CLI 挂载 `pdf-rotation-mvp dry-run`。
   - 新 dry-run 只做配置解析、路径语义计算和脱敏状态输出，不读取 `.env/.env`、不处理真实 PDF、不调用阿里云、不调用 Ghostscript、不创建目录。
   - 已新增单元测试覆盖假 key 脱敏、显式配置优先和 side-effect 标记。
   - 已新增纯逻辑单元测试覆盖方向决策、图号决策、JSON 解析、文件名质量门和旋转映射。
   - 已新增 `runtime_config.py`，将 TOML 适配为包内运行配置对象，dry-run 已复用该配置对象。

5. 最小主线迁移
   - 先迁移纯函数、常量、数据结构。
   - 再迁移路径参数。
   - 最后迁移 CLI 参数。
   - 旧入口 `tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py` 暂时保留，作为回归对照或薄 wrapper。

阻断条件：

- dry-run 可能调用阿里云。
- stdout/stderr 可能打印 API key。
- 新入口默认写入 `local_data/` 或 `local_data/review_inbox/current/`。
- 新入口默认删除、清空或覆盖旧 MVP `output/work`。
- 旧入口不可编译。
- `git ls-files local_data .env outputs runs blueprint-normalizer.toml` 出现输出。

验收：

- 旧入口 `python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 通过。
- 新包 `python -m py_compile src\blueprint_normalizer\pdf_rotation_mvp\*.py` 通过。
- CLI help/config check/dry-run 通过。
- 假 key 脱敏测试通过。
- 配置优先级测试通过。
- dry-run 不读取 `.env/.env`、不访问网络、不要求真实 PDF、不写固定审核入口。

完成定义：

- 新包内存在 MVP 主线目录。
- 配置适配层明确。
- 新 CLI dry-run 可运行且不联网。
- 旧入口仍可编译或作为 wrapper 保留。
- 后续真实联网 smoke test 的入口和提权规则已明确，但本阶段不执行真实联网调用。

### 阶段 3：CLI、运行目录和真实 MVP 命令

状态：待执行。

目标：

- 实现 `blueprint-normalizer config init`。
- 实现 `blueprint-normalizer config check`，不打印 API key。
- 实现 `blueprint-normalizer pdf-rotation-mvp dry-run`。
- 实现 `blueprint-normalizer pdf-rotation-mvp run`。
- 将运行默认路径切换为应用目录下 `input/output/work/logs`。
- 保持人工复核和错误分层产物完整。

约束：

- 真实联网模型调用仍必须直接使用已批准命令前缀或 `sandbox_permissions=require_escalated`。
- 普通非联网 dry-run 不得访问阿里云。
- 不得读取、打印或提交 `.env/.env` 中的密钥。

验收：

- CLI help 和子命令 help 可运行。
- `config init` 不覆盖已存在真实配置，除非用户显式确认。
- `config check` 对假 key 做脱敏输出。
- dry-run 不联网、不上传图纸、不创建大产物。

### 阶段 4：文档目录迁移和当前入口更新

状态：待执行。

目标：

- 用 `git mv` 将 `reports/` 迁入 `docs/reports/`。
- 用 `git mv` 将 `rules/` 迁入 `docs/rules/`。
- 用 `git mv` 将 `references/` 迁入 `docs/references/`。
- 更新根 README，加入稳定的 `AI Quick Context`。
- 更新 `HANDOFF.md` 中当前路径、remote、入口命令和下一步。
- 更新 `docs/README.md`、`docs/reports/README.md`、`docs/rules/README.md`、`docs/references/README.md`。
- 更新 `tools/pdf_rotation_mvp/README.md` 或迁移其内容到正式文档。
- 更新当前说明中的旧命令 `python tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py` 和 `python -m scripts...`。
- 更新阿里云联网执行规则中的旧批准命令前缀说明。

约束：

- 历史计划和 RPD 中旧路径语境允许保留，不做机械全局替换。
- 当前 README、HANDOFF、docs 索引、运行说明必须使用新入口。
- 不删除历史资料，除非有明确替代入口。

验收：

- README 顶部有 `AI Quick Context`。
- 当前运行命令统一为 `blueprint-normalizer` 或 `BlueprintNormalizer.exe`。
- 文档索引能找到计划、报告、规则和参考资料。

### 阶段 5：持续测试与验证

状态：待执行。

原则：

阶段 5 不是把测试全部后置。阶段 2、3、4 每一步都要有自己的非联网验收；阶段 5 负责把这些验证固化为长期测试。

测试范围：

- 包导入测试。
- 配置解析测试。
- 配置优先级测试。
- 假 key 脱敏测试。
- 开发态/EXE 态路径解析测试。
- 图号文件名规则测试。
- dry-run 不联网测试。
- 旧入口 wrapper 兼容测试。

验收：

- `python -m py_compile` 或等效编译检查通过。
- `python -m unittest discover -s tests -v` 通过。
- CLI help/config check/dry-run 非联网验证通过。
- 禁区路径未进入 Git。

### 阶段 6：EXE 打包准备

状态：待执行。

目标：

- 完善 `packaging/pyinstaller/BlueprintNormalizer.spec`。
- 输出目录为 `dist/BlueprintNormalizer/`。
- 发布包包含 `BlueprintNormalizer.exe`、配置模板、`input/`、`output/`、`work/`、`logs/`、`README.txt`。
- 将 `blueprint-normalizer.example.toml` 作为模板放入发布包，不包含真实 key。
- 明确 Ghostscript 或其他外部依赖的处理方式。

约束：

- 不把真实 `blueprint-normalizer.toml` 打入 exe 或发布包。
- 不把 API key、模型响应、真实图纸、审核包放入发布包。
- 打包验证先做非联网检查。

验收：

- 发布目录结构符合最终 EXE 运行目录设计。
- 模板配置可复制为真实配置。
- EXE help 可运行。
- EXE dry-run 不联网。

### 阶段 7：历史脚本迁移和最终收尾

状态：待执行。

目标：

- 在 MVP 主线稳定后，再单独规划 `scripts/*` 历史脚本迁移。
- 区分生产代码、实验脚本、一次性审核包脚本和历史归档脚本。
- 将仍有价值的公共模块迁入 `src/blueprint_normalizer/`。
- 将不再作为正式入口的脚本标注为历史或归档。
- 清理迁移后遗留空目录、旧入口说明和过期 TODO。

约束：

- 不把历史实验脚本混入正式运行入口。
- 不把联网脚本的批准命令前缀悄悄变更为未记录状态。
- 不迁移或提交 `local_data/`、`.env/`、`outputs/`、`runs/`、真实配置。

验收：

- 正式入口唯一且清晰。
- 历史脚本有明确归档或迁移状态。
- README/HANDOFF/TODO/RPD 对当前入口口径一致。

## 验收标准

- 用户审核或明确同意当前阶段后才执行对应迁移或实现。
- 阶段范围、风险、验收和阻断条件统一维护在本文件。
- 公开源码集中在 `src/blueprint_normalizer/`。
- 正式程序入口不再位于 `tools/`。
- 运行配置文件 `blueprint-normalizer.toml` 可与程序同目录放置。
- 模板配置公开可提交，真实配置被 `.gitignore` 排除。
- `BlueprintNormalizer.exe` 的发布目录设计支持 `input/output/work/logs` 同目录运行。
- Linux 发布包支持 `blueprint-normalizer` 可执行文件和同目录配置。
- README 同时满足人类快速使用和 AI 快速接手。
- GitHub 仓库目标名明确为 `blueprint-normalizer`。
- 不读取、不打印、不提交真实 API key。
- 不覆盖 `local_data/review_inbox/current/`。
- 不提交 `local_data/`、`outputs/`、`runs/` 或 MVP 私有输出。
- 非联网检查通过后，再按阿里云联网规则执行 smoke test。

## 回滚准备

本计划、RPD 和 TODO 提交后作为执行前回滚点。当前仓库按用户要求保持单提交历史，因此后续阶段使用 `git commit --amend --no-edit` 收口，但每个阶段必须在 RPD 记录执行前后提交哈希、变更摘要和验证结果。若源码迁移或 CLI 改造失败，优先回退本阶段新增文件和入口挂载，不删除旧 MVP、本地私有数据或固定审核入口。
