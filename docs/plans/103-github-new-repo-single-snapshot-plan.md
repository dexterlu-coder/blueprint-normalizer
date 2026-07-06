# GitHub 新仓库单快照发布计划

日期：2026-07-06

## 背景

项目本地顶层目录已由 `pictureAnalyse` 改为 `BlueprintNormalizer`。用户希望 GitHub 仓库也改为新名称，并且远端只保留当前最近版本，不再保留旧项目历史提交。

上一版讨论中曾考虑先删除旧 GitHub 仓库再新建。用户已修正执行顺序：应先创建并提交新项目，确认新仓库可用后，再删除旧仓库。这个顺序更稳定，避免在新仓库验证前失去旧远端备份。

## 当前事实

- 当前本地路径：`D:\project\codex\BlueprintNormalizer`。
- 当前 remote：`https://github.com/dexterlu-coder/pictureAnalyse.git`。
- 当前本地分支：`master`。
- 当前本地历史：269 个提交。
- 当前公开工作区干净。
- 当前 tracked 文件未包含 `local_data/`、`.env/`、`outputs/`、`runs/` 或 MVP 真实运行产物。
- 当前目标新仓库名：`blueprint-normalizer`。

## 目标

- 新建 GitHub 仓库 `blueprint-normalizer`。
- 将当前公开文件快照作为新仓库的唯一初始提交。
- 新仓库确认无误前，不删除旧 GitHub 仓库 `pictureAnalyse`。
- 新仓库确认无误后，再由用户确认删除旧仓库。
- 不提交历史模型响应、图纸 PDF、`local_data/`、真实配置、密钥或运行输出。

## 推荐执行顺序

### 阶段 0：文档与回滚点

- 新增本计划。
- 更新 RPD。
- 更新 TODO。
- 补充 `.gitignore`，至少忽略：
  - `blueprint-normalizer.toml`
  - `/dist/`
  - `/build/`
  - PyInstaller 生成目录与临时文件
- 提交文档与忽略规则回滚点。

### 阶段 1：创建旁路发布快照工作区

优先不直接改写当前仓库的 `.git`。在项目同级或临时目录创建一个发布快照工作区，只复制当前 Git 跟踪的公开文件，并排除：

- `.git/`
- `.env/`
- `local_data/`
- `outputs/`
- `runs/`
- MVP `input/output/work` 中除 `.gitkeep` 以外的真实产物
- 真实 `blueprint-normalizer.toml`

随后在发布快照工作区执行：

```powershell
git init
git add .
git commit -m "Initial snapshot for BlueprintNormalizer"
```

这样新仓库只有一个提交，而当前本地原仓库的 269 个提交仍保留，便于新仓库验证前回滚。

### 阶段 2：创建新 GitHub 仓库并推送

在 GitHub 创建空仓库：

```text
dexterlu-coder/blueprint-normalizer
```

新仓库不要初始化 README、LICENSE 或 `.gitignore`，避免和本地单快照提交冲突。

将发布快照工作区推送到新仓库：

```powershell
git remote add origin https://github.com/dexterlu-coder/blueprint-normalizer.git
git push -u origin master
```

如果使用 GitHub CLI，也必须保持仓库为空并从发布快照工作区推送。

### 阶段 3：新仓库验收

删除旧仓库前，必须确认：

- GitHub 页面能打开 `blueprint-normalizer`。
- GitHub 默认分支包含单个初始提交。
- README、AGENTS、HANDOFF、TODO、docs、scripts、tools MVP 入口可见。
- GitHub 文件列表不包含 `local_data/`、`.env/`、真实配置、图纸 PDF、模型响应或运行输出。
- 从新仓库重新 clone 后，`git log --oneline` 只有单快照提交。
- clone 后能看到 `tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py` 和当前文档入口。
- 非联网编译检查通过：

```powershell
python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py
```

### 阶段 4：切换主工作区 remote

新仓库验收通过后，再决定是否把当前主工作区切到新 remote：

```powershell
git remote set-url origin https://github.com/dexterlu-coder/blueprint-normalizer.git
```

若仍希望主工作区也只保留单提交历史，可以在确认新仓库可用后，用新仓库重新 clone 替换当前工作区，或对当前工作区执行受控的历史重建。优先推荐重新 clone，风险更低。

### 阶段 5：删除旧 GitHub 仓库

仅在用户确认新仓库验收通过后，删除旧仓库：

```text
dexterlu-coder/pictureAnalyse
```

删除前再次确认：

- 新仓库可访问。
- 新仓库内容完整。
- 新仓库不含私有资料。
- 新仓库 clone 验证通过。
- 用户不再需要旧仓库的 issue、star、settings、权限配置或历史提交。

## 不采用的顺序

不先删除旧 GitHub 仓库。原因：

- 删除旧仓库会丢失远端备份和 GitHub 侧状态。
- 如果新仓库创建或推送遇到权限、网络、命名冲突等问题，会失去一个稳定参照。
- 当前本地历史虽完整，但保留旧远端直到新仓库验收通过更符合稳定可靠优先原则。

## 风险与边界

- 新仓库只保留单快照提交后，旧提交 hash 不再存在于新远端。
- 历史文档中引用的旧提交号只作为文字记录，不能在新仓库中 `git show`。
- 删除旧仓库会丢失 GitHub 侧 issue、star、watcher、仓库设置、权限配置和旧远端历史。
- 当前计划只处理 GitHub 仓库发布形态，不进行源码目录迁移、不修改 MVP 逻辑、不调用阿里云模型。

## 验收标准

- 新 GitHub 仓库 `blueprint-normalizer` 已创建。
- 新仓库只包含当前公开快照的一个初始提交。
- 新仓库不包含私有资料、密钥、图纸 PDF、模型响应或运行输出。
- 新仓库 clone 后非联网检查通过。
- 旧仓库在新仓库验收通过前仍保留。
- 删除旧仓库必须单独获得用户确认。
