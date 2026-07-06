# YOLO/OBB 疑难样本分流质量门计划

## 背景

YOLO/OBB round3 多候选仲裁已合并到通用后处理链路，当前回归结果显示：

- round2 首训 14 条全覆盖，5 条人工不可接受样本仍进入 `needs_review`。
- round3 重点预测 16 条全覆盖，2 条普通表格误检候选进入 `rejected_candidates`。
- 当前没有证据要求立即重新训练。

下一步需要把“什么时候自动接受、什么时候人工复核、什么时候才进入 OCR/VLM 或再训练候选”固化为可重复质量门，避免把 VLM 当成默认下一步，也避免在没有新失败证据时反复重训。

## 目标

1. 设计 YOLO/OBB 后处理后的疑难样本分流规则。
2. 明确 `auto_accept`、`human_review`、`ocr_candidate`、`vlm_candidate`、`retrain_candidate` 的触发条件。
3. 新增只读路由脚本，读取已有 `postprocess_report.json`，输出机器清单。
4. 先对 round2 首训和 round3 重点预测报告运行分流回归。
5. 不发布新的固定审核入口，避免制造不必要的人工任务。

## 非目标

本阶段不做：

- 不重新训练 YOLO/OBB。
- 不修改标签或数据集。
- 不调用 OCR。
- 不调用 VLM。
- 不接入云端 provider。
- 不处理完整 PDF。
- 不发布 `local_data/review_inbox/current/` 审核任务。

## 输入

使用已有后处理报告：

```text
local_data/yolo_postprocess/round2_first_train/postprocess_report.json
local_data/yolo_postprocess/general_round3_diagnostic/postprocess_report.json
```

## 输出

输出到 ignored 本地目录：

```text
local_data/yolo_postprocess/routing/
```

输出文件：

```text
routing_report.json
routing_summary.csv
route_records.csv
```

## 分流类别

### auto_accept

满足以下条件时可进入自动接受候选：

- 后处理状态为 `accepted`。
- 存在 `selected_title_block`。
- 没有阻断类 issue。
- 选中候选贴图框线，或已有人工保护性正例/结构证据支持。
- 多候选已仲裁且未选候选都有明确拒绝原因。

### human_review

满足以下任一条件时进入人工复核候选：

- 后处理状态为 `needs_review`。
- 缺少标题栏候选。
- 用户历史人工判定不可接受。
- 框越界、范围过大、标题栏未完整覆盖。
- 选中候选没有贴图框线且缺少其他强证据。
- 多候选未能明确拒绝非标题栏候选。

### ocr_candidate

满足以下任一条件时进入 OCR 候选：

- 候选贴边和几何证据基本可用，但标题栏真实性仍需要字段簇确认。
- 出现 `role_cluster_weak`、`property_cluster_weak` 或 `ocr_unavailable`。
- 普通表格误检风险存在，但结构证据不足以完全解释。

OCR 只作为字段簇证据，不单独覆盖贴边、几何和人工复核规则。

### vlm_candidate

满足以下任一条件时进入 VLM 候选：

- 后处理、OCR 或结构证据冲突，人工复核成本较高。
- 新版式、新供应商、新扫描批次导致几何规则解释不足。
- 多候选均贴边，且普通表格/标题栏边界无法靠结构规则区分。

VLM 只作为疑难样本解释层，不作为默认全量流程。

### retrain_candidate

满足以下任一条件时进入再训练候选：

- 同类漏检或误检在人工复核中重复出现。
- 后处理只能拦截但无法稳定选择真实标题栏。
- 正常样本召回下降。
- 新样本分布与当前 round3 hard-case 明显不同。

再训练候选只代表“需要积累数据和复查”，不代表立即训练。

## 脚本设计

新增脚本：

```text
scripts/yolo_obb/build_yolo_obb_routing_report.py
```

职责：

1. 读取一个或多个 `postprocess_report.json`。
2. 对每条记录计算分流类别和原因。
3. 输出 JSON 完整报告。
4. 输出 CSV 摘要，方便后续人工或自动流程筛选。
5. 不修改原后处理报告。
6. 不写入固定审核入口。

## 验证

运行：

```text
python -m py_compile scripts/yolo_obb/build_yolo_obb_routing_report.py
python scripts/yolo_obb/build_yolo_obb_routing_report.py
```

期望：

- round2 首训 14 条被覆盖。
- round3 重点预测 16 条被覆盖。
- round2 5 条 `needs_review/manual_rejected` 不进入纯 `auto_accept`。
- round3 两条 `aug90_002_from_sample_010` 多候选记录进入 `auto_accept`，同时保留 rejected candidate 说明。
- `ocr_candidate` 只作为候选标记，不触发实际 OCR。
- `vlm_candidate` 只作为候选标记，不触发实际 VLM。

## 回滚点

本计划、RPD 和 TODO 提交后作为实现分流脚本前回滚点。

