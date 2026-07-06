# 当前目录原地单提交历史重建计划

日期：2026-07-06

## 背景

用户明确要求：在当前 `D:\project\codex\BlueprintNormalizer` 中删除旧 Git 历史，只保留当前最近版本；不需要新开一个项目文件夹。

上一轮执行中错误创建了同级干净工作区：

```text
D:\project\codex\BlueprintNormalizer_clean
```

这不符合用户原意。本计划用于纠偏：

- 删除误创建的 `BlueprintNormalizer_clean`。
- 在当前目录 `BlueprintNormalizer` 原地重建 `.git`。
- 当前目录最终只保留一个初始提交。
- `origin` 指向新仓库 `blueprint-normalizer`。

## 目标

- 当前目录保持为：

```text
D:\project\codex\BlueprintNormalizer
```

- 当前目录 Git 历史重建为单提交。
- 删除误创建的同级目录：

```text
D:\project\codex\BlueprintNormalizer_clean
```

- 设置 remote：

```text
https://github.com/dexterlu-coder/blueprint-normalizer.git
```

- 本地与 GitHub 新仓库均保持单提交历史。
- 不跟踪 `local_data/`、`.env/`、`outputs/`、`runs/`、真实配置或模型响应。

## 执行步骤

1. 确认用户已明确授权执行破坏性历史重建。
2. 提交本计划、RPD、TODO、HANDOFF 作为最后旧历史回滚点。
3. 删除误创建的 `D:\project\codex\BlueprintNormalizer_clean`。
4. 删除当前目录中的 `.git`。
5. 在当前目录重新初始化 Git：

```powershell
git init
git add .
git commit -m "Initial snapshot for BlueprintNormalizer"
git remote add origin https://github.com/dexterlu-coder/blueprint-normalizer.git
```

6. 本地验收：

```powershell
git rev-list --count HEAD
git log --oneline -1
git remote -v
git ls-files local_data .env outputs runs blueprint-normalizer.toml
python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py
```

7. 覆盖推送到新仓库，保持新仓库单提交历史：

```powershell
git push --force-with-lease -u origin master
```

## 风险

- 删除当前目录 `.git` 后，本地旧 269+ 提交历史不再可用。
- 删除 `BlueprintNormalizer_clean` 后，该误创建目录不再可用。
- 历史文档中的旧提交 hash 只作为文字记录保留，不能在当前仓库中 `git show`。

## 验收标准

- `D:\project\codex\BlueprintNormalizer_clean` 不存在。
- 当前目录 `D:\project\codex\BlueprintNormalizer` 存在。
- 当前目录 `git rev-list --count HEAD` 输出 `1`。
- 当前目录 `origin` 指向 `blueprint-normalizer`。
- 禁区路径检查无输出。
- MVP 脚本编译检查通过。
- GitHub 新仓库 `master` 指向当前目录的单提交。
