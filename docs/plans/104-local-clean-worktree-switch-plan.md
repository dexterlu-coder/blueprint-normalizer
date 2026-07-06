# 本地干净工作区切换计划

日期：2026-07-06

## 背景

GitHub 新仓库 `dexterlu-coder/blueprint-normalizer` 已创建并验收，旧仓库 `dexterlu-coder/pictureAnalyse` 已删除。新仓库保持单提交历史，只保留当前公开快照。

当前打开的本地目录仍是旧 Git 工作区：

```text
D:\project\codex\BlueprintNormalizer
```

这个工作区仍保留 269+ 个本地历史提交，并且 `origin` 仍指向已删除的旧仓库：

```text
https://github.com/dexterlu-coder/pictureAnalyse.git
```

因此不能直接把当前工作区的 `origin` 改到新仓库后普通 `git push`，否则有把旧历史推入新仓库的风险。

## 目标

- 保留当前旧历史工作区作为本地备份和回滚参照。
- 从新 GitHub 仓库重新 clone 一个干净工作区。
- 干净工作区应只有单提交历史。
- 干净工作区的 `origin` 应指向 `https://github.com/dexterlu-coder/blueprint-normalizer.git`。
- 验收干净工作区后，后续开发应从干净工作区重新打开 Codex/终端。
- 不移动、不删除当前旧历史工作区。
- 不提交 `local_data/`、`.env/`、`outputs/`、`runs/` 或真实配置文件。

## 推荐路径

由于当前会话正在占用：

```text
D:\project\codex\BlueprintNormalizer
```

本轮先创建旁边的新工作区：

```text
D:\project\codex\BlueprintNormalizer_clean
```

确认无误后，后续可以人工决定是否：

- 继续使用 `BlueprintNormalizer_clean` 作为正式工作区。
- 或关闭所有相关终端后，把旧 `BlueprintNormalizer` 目录改名为备份，再把 `BlueprintNormalizer_clean` 改名为 `BlueprintNormalizer`。

本轮不执行目录替换，避免在当前会话中移动正在使用的工作目录。

## 执行步骤

1. 确认当前旧工作区干净。
2. 提交本计划、RPD、TODO 和 HANDOFF 更新，作为执行前回滚点。
3. 检查目标路径 `D:\project\codex\BlueprintNormalizer_clean` 是否已存在。
4. 若不存在，从新仓库 clone：

```powershell
git clone https://github.com/dexterlu-coder/blueprint-normalizer.git D:\project\codex\BlueprintNormalizer_clean
```

5. 在干净工作区执行验收：

```powershell
git rev-list --count HEAD
git log --oneline -1
git remote -v
git ls-files local_data .env outputs runs blueprint-normalizer.toml
python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py
```

预期：

- 提交数为 `1`。
- 最新提交为 `Initial snapshot for BlueprintNormalizer`。
- `origin` 指向 `blueprint-normalizer`。
- 禁区路径检查无输出。
- `py_compile` 无输出且退出码为 0。

6. 若本轮记录执行结果后再次覆盖推送新仓库单提交快照，则刷新干净工作区到最新 `origin/master` 并复验。

## 风险与边界

- 不在旧历史工作区执行普通 `git push`。
- 不直接删除或重建当前旧工作区的 `.git`。
- 不在当前会话中移动顶层目录。
- 干净工作区创建在项目父目录，需要文件系统写入权限和 GitHub 网络访问。
- 旧历史工作区中的 `local_data/` 私有数据不会自动复制到干净工作区；后续若业务运行需要私有输入，应按隐私规则单独迁移或重新放置。

## 验收标准

- `D:\project\codex\BlueprintNormalizer_clean` 存在。
- 该目录是从新仓库 clone 的 Git 工作区。
- 该目录只有单提交历史。
- 该目录 remote 指向 `blueprint-normalizer`。
- 该目录不跟踪私有路径或真实配置。
- MVP 脚本非联网编译检查通过。
- 当前旧历史工作区保持不变，继续作为备份。
- 后续开发从干净工作区重新打开。
