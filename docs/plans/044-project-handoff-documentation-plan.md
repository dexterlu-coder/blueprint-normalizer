# 项目交接与文档整理计划

## 背景

用户需要切换账号继续开发，新的 Codex 会话需要快速接手当前项目状态。当前公开文档已经按 `docs/research`、`docs/plans`、`docs/workflows`、`rules`、`reports`、`references` 分层，但根目录 README 的当前重点已滞后，且缺少一份可直接交给新会话读取的一页式交接记录。

## 目标

1. 更新根目录 README，指向当前 MCP/VLM teacher 手动响应阶段。
2. 更新 `docs/README.md`，补齐近期 MCP/VLM teacher、YOLO/OBB 后处理和标题栏规范相关计划入口。
3. 在项目根目录新增 `HANDOFF.md`，记录当前状态、关键结论、路径、下一步、禁止事项和验证命令。
4. 保持文档分门别类，不移动私有数据和本地运行产物。
5. 确保交接文档只包含可公开提交的信息，不把图纸内容或私有数据写入 Git。

## 非目标

本阶段不做：

- 不重训。
- 不调用 MCP/VLM。
- 不上传图纸。
- 不修改 `local_data/` 内容。
- 不改算法脚本。
- 不整理或删除本地私有数据。

## 输出

公开文档：

```text
README.md
docs/README.md
HANDOFF.md
TODO.md
reports/rpd-rotation-detection.md
```

## 验证

运行：

```text
git status --short
rg -n "MCP/VLM teacher|HANDOFF|当前重点" README.md docs/README.md HANDOFF.md TODO.md reports/rpd-rotation-detection.md
```

期望：

- 根目录存在 `HANDOFF.md`。
- README 当前重点与 `local_data/review_inbox/current/` 的 teacher 任务一致。
- 文档索引包含近期 teacher 阶段文档。
- `local_data/`、`outputs/`、`runs/` 不进入 Git。

## 回滚点

本计划、RPD 和 TODO 提交后作为交接文档整理前回滚点。
