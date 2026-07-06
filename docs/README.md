# 文档索引

本目录存放公开、可提交的项目文档。私有图纸、渲染图片、标注结果、训练数据和运行输出不放在这里。

## 分类

- `research/`：调研笔记、横向对标、技术路线依据。
- `plans/`：阶段计划、实验计划、实现前规划。
- `workflows/`：人工操作流程、标注工具使用说明。
- `decisions/`：当前有效的设计决策、旧方案状态和后续设计边界。

根目录还包含：

- [HANDOFF.md](../HANDOFF.md)：换账号或新会话接手时优先阅读。
- [TODO.md](../TODO.md)：当前任务状态。
- [reports/rpd-rotation-detection.md](../reports/rpd-rotation-detection.md)：需求、决策和阶段结果总记录。
- [rules/](../rules/README.md)：长期规则。
- [references/](../references/README.md)：外部资料索引。

## 推荐接手阅读顺序

1. [项目交接记录](../HANDOFF.md)
2. [项目协作规则](../AGENTS.md)
3. [当前 TODO](../TODO.md)
4. [机械图纸旋转方向自动识别 RPD](../reports/rpd-rotation-detection.md)
5. [账号切换当前状态交接计划](plans/101-account-switch-current-state-handoff-plan.md)
6. [项目目录、命名、配置与 EXE 发布综合整理计划](plans/102-project-layout-naming-config-exe-plan.md)
7. [GitHub 新仓库单快照发布计划](plans/103-github-new-repo-single-snapshot-plan.md)
8. [本地干净工作区切换计划](plans/104-local-clean-worktree-switch-plan.md)
9. [当前目录原地单提交历史重建计划](plans/105-in-place-single-history-reset-plan.md)
10. [本地磁盘数据清理方案](plans/106-local-data-disk-cleanup-plan.md)
11. [PDF 旋正 MVP 图号命名计划](plans/096-mvp-pdf-rotation-drawing-number-filename-plan.md)
12. [PDF 拆分、VLM 方向识别与旋正 MVP 脚本计划](plans/091-mvp-pdf-split-vlm-rotation-correction-script-plan.md)
13. [ROI 收敛多框展示案例生成计划](plans/100-roi-convergence-demo-cases-plan.md)
14. [阿里模型参数与准确性调研](research/2026-07-02-aliyun-model-parameter-accuracy-research.md)
15. [阿里云百炼 VLM 接入调研](research/2026-07-01-aliyun-vlm-integration-research.md)
16. [标题栏完整性 crop 与图号 OCR ROI 双轨策略决策](decisions/title-block-crop-and-ocr-roi-strategy.md)
17. [标题栏位置多证据仲裁决策](decisions/title-block-position-arbitration-design.md)

## Research

- [工程图纸方向识别调研](research/2026-06-23-engineering-drawing-orientation-research.md)
- [本地标题栏检测与 VLM 调研](research/2026-06-25-local-title-block-detector-and-vlm-research.md)
- [OBB 标注工具选择调研](research/2026-06-25-obb-annotation-tool-selection.md)
- [OCR/VLM 工作流调研](research/2026-06-25-ocr-vlm-workflow-research.md)
- [YOLO/OBB 调试方案调研](research/2026-06-25-yolo-obb-debugging-research.md)
- [ISAT 标注工具调研](research/2026-06-26-isat-annotation-tool-research.md)
- [YOLO/OBB 训练规划依据](research/2026-06-26-yolo-obb-training-basis.md)
- [标题栏规范调研](research/2026-06-28-title-block-standard-research.md)
- [OCR 引擎选型调研](research/2026-06-28-ocr-engine-selection-research.md)
- [标题栏位置多证据仲裁调研](research/2026-06-28-title-block-position-arbitration-research.md)
- [OCR 图像预处理增强调研](research/2026-06-29-ocr-image-preprocessing-research.md)
- [标题栏粗 crop 对图号 OCR 下游影响调研](research/2026-06-30-title-block-coarse-crop-ocr-downstream-research.md)
- [阿里云百炼 VLM 接入调研](research/2026-07-01-aliyun-vlm-integration-research.md)
- [阿里模型参数与准确性调研](research/2026-07-02-aliyun-model-parameter-accuracy-research.md)

## Decisions

- [标题栏位置多证据仲裁决策](decisions/title-block-position-arbitration-design.md)
- [标题栏完整性 crop 与图号 OCR ROI 双轨策略决策](decisions/title-block-crop-and-ocr-roi-strategy.md)

## Plans

### 交接与项目整理

- [项目结构整理计划](plans/001-project-structure-cleanup-plan.md)
- [项目交接与文档整理计划](plans/044-project-handoff-documentation-plan.md)
- [账号切换当前状态交接计划](plans/101-account-switch-current-state-handoff-plan.md)
- [项目目录、命名、配置与 EXE 发布综合整理计划](plans/102-project-layout-naming-config-exe-plan.md)
- [GitHub 新仓库单快照发布计划](plans/103-github-new-repo-single-snapshot-plan.md)
- [本地干净工作区切换计划](plans/104-local-clean-worktree-switch-plan.md)
- [当前目录原地单提交历史重建计划](plans/105-in-place-single-history-reset-plan.md)
- [本地磁盘数据清理方案](plans/106-local-data-disk-cleanup-plan.md)
- [docs/plans 编号命名整理计划](plans/062-docs-plan-numbering-plan.md)
- [项目结构整理与阿里云 VLM MVP 请求包实现计划](plans/074-project-organization-and-aliyun-vlm-mvp-implementation-plan.md)

### OpenCV 方向识别与评估

- [旋转方向识别计划](plans/002-rotation-detection-plan.md)
- [置信度提升计划](plans/015-confidence-improvement-plan.md)
- [三方比对计划](plans/016-three-way-rotation-comparison-plan.md)
- [OpenCV 阶段二修复计划](plans/003-opencv-stage2-error-fix-plan.md)
- [Ground truth 与评估计划](plans/004-ground-truth-evaluation-plan.md)
- [人工复核包计划](plans/005-manual-review-pack-plan.md)
- [顺时针 90 度增强计划](plans/006-augmented-90-sample-plan.md)
- [联合评估计划](plans/007-combined-evaluation-plan.md)
- [sample_042 低置信优化计划](plans/008-low-confidence-042-plan.md)

### OCR/VLM 与标题栏规范

- [OCR/VLM 兜底流程计划](plans/017-ocr-vlm-fallback-workflow-plan.md)
- [标题栏 OCR 与后处理诊断实验计划](plans/032-ocr-title-block-diagnostic-experiment-plan.md)
- [标题栏 OCR 与后处理诊断脚本实现计划](plans/033-ocr-title-block-diagnostic-implementation-plan.md)
- [标题栏诊断 HTML 图片修复计划](plans/034-ocr-title-block-diagnostic-html-image-fix-plan.md)
- [标题栏诊断人工复查记录计划](plans/035-ocr-title-block-diagnostic-manual-review-record-plan.md)
- [OCR 字段簇可用性探针计划](plans/048-ocr-field-cluster-probe-plan.md)
- [OCR 引擎选型调研计划](plans/049-ocr-engine-selection-research-plan.md)
- [RapidOCR 本地字段簇小实验计划](plans/050-rapidocr-local-field-cluster-experiment-plan.md)
- [标题栏规范调研与 round3 预测归档计划](plans/031-title-block-standard-research-and-round3-prediction-archive-plan.md)
- [标题栏位置多证据仲裁调研计划](plans/051-title-block-position-arbitration-research-plan.md)
- [标题栏仲裁准确率评估固化计划](plans/053-title-block-arbitration-accuracy-evaluation-plan.md)
- [标题栏位置仲裁记录计划](plans/052-title-block-arbitration-record-plan.md)
- [PDF 旋正与图号抽取 dry-run 计划](plans/054-pdf-correction-and-drawing-number-dry-run-plan.md)
- [63 张全量 PDF dry-run 测试计划](plans/055-full-63-pdf-dry-run-test-plan.md)
- [63 张全量标题栏 crop/OCR dry-run 计划](plans/056-full-63-title-block-ocr-dry-run-plan.md)
- [图号抽取低置信候选优化与命名质量门计划](plans/057-drawing-number-quality-gate-plan.md)
- [OCR 图像预处理增强调研计划](plans/058-ocr-image-preprocessing-research-plan.md)
- [OCR 图像预处理小实验计划](plans/059-ocr-image-preprocessing-small-experiment-plan.md)
- [63 条图号命名人工审核包计划](plans/060-full-63-naming-review-pack-plan.md)
- [标题栏 crop 质量修复与命名审核重启计划](plans/061-title-block-crop-quality-recovery-plan.md)
- [标题栏 crop 完整性审核结果归档与分层计划](plans/063-title-block-crop-review-result-archive-plan.md)
- [标题栏 crop 生成策略修复计划](plans/064-title-block-crop-generation-fix-plan.md)
- [标题栏粗 crop 对图号 OCR 影响调研计划](plans/065-title-block-coarse-crop-ocr-downstream-research-plan.md)
- [OCR 用细 ROI 小实验计划](plans/066-ocr-fine-roi-small-experiment-plan.md)
- [细 ROI 审核入口说明修复计划](plans/067-fine-roi-review-instruction-fix-plan.md)
- [账号切换交接更新计划](plans/068-account-switch-handoff-update-plan.md)
- [阿里云 VLM 旋正与图号读取 MVP 计划](plans/073-aliyun-vlm-rotation-drawing-number-mvp-plan.md)
- [阿里模型参数与准确性调研计划](plans/085-aliyun-model-parameter-accuracy-research-plan.md)
- [VLM 标题栏错题集优先模型测试计划](plans/086-vlm-title-block-error-first-model-test-plan.md)

### MCP/VLM teacher 与蒸馏

- [MCP/VLM teacher 复盘与蒸馏计划](plans/040-mcp-vlm-teacher-distillation-plan.md)
- [MCP/VLM teacher 小规模调用准备计划](plans/041-mcp-vlm-teacher-call-prep-plan.md)
- [MCP/VLM teacher provider 调用方式计划](plans/042-mcp-vlm-teacher-provider-call-plan.md)
- [MCP/VLM teacher 手动响应固定审核入口计划](plans/043-mcp-vlm-teacher-manual-review-inbox-plan.md)
- [MCP/VLM teacher 响应填写与校验计划](plans/045-mcp-vlm-teacher-response-fill-and-validation-plan.md)
- [MCP/VLM teacher 响应蒸馏分析计划](plans/046-mcp-vlm-teacher-response-distillation-analysis-plan.md)

### YOLO/OBB 数据、训练与后处理

- [YOLO/OBB 标题栏检测计划](plans/013-yolo-obb-title-block-experiment-plan.md)
- [YOLO/OBB 调试调研计划](plans/014-yolo-obb-debugging-research-plan.md)
- [YOLO/OBB 标签工具计划](plans/009-yolo-obb-label-tools-plan.md)
- [YOLO/OBB 冒烟训练准备计划](plans/012-yolo-obb-smoke-training-plan.md)
- [YOLO/OBB 第二轮首训计划](plans/018-yolo-obb-round2-training-plan.md)
- [YOLO/OBB 首训预测错误分层与改进计划](plans/019-yolo-obb-prediction-error-improvement-plan.md)
- [YOLO/OBB 预测后处理与失败样本复查包计划](plans/020-yolo-obb-postprocess-review-pack-plan.md)
- [YOLO/OBB 预测后处理脚本实现计划](plans/021-yolo-obb-postprocess-implementation-plan.md)
- [YOLO/OBB 后处理失败样本复查包实现计划](plans/022-yolo-obb-postprocess-failure-review-pack-implementation-plan.md)
- [YOLO/OBB 后处理复查归档与贴边规则计划](plans/023-yolo-obb-postprocess-review-archive-and-edge-contact-rule-plan.md)
- [YOLO/OBB 后处理贴边规则升级计划](plans/024-yolo-obb-postprocess-frame-contact-upgrade-plan.md)
- [YOLO/OBB sample_009 补标复查计划](plans/025-yolo-obb-sample-009-supplement-review-plan.md)
- [YOLO/OBB sample_009 复查归档与难例补强计划](plans/026-yolo-obb-sample-009-review-archive-hardcase-plan.md)
- [YOLO/OBB hard-case 再训练准备计划](plans/027-yolo-obb-hardcase-retraining-prep-plan.md)
- [YOLO/OBB round3 hard-case 数据集计划](plans/028-yolo-obb-round3-hardcase-dataset-plan.md)
- [YOLO/OBB round3 overlay 归档与训练准备计划](plans/029-yolo-obb-round3-overlay-archive-training-prep-plan.md)
- [YOLO/OBB round3 小规模训练计划](plans/030-yolo-obb-round3-training-plan.md)
- [YOLO/OBB round3 多候选后处理仲裁升级计划](plans/036-yolo-obb-round3-multicandidate-postprocess-plan.md)
- [YOLO/OBB 非标题栏表格误检泛化修正计划](plans/037-yolo-obb-nontitle-table-generalization-fix-plan.md)
- [YOLO/OBB 通用后处理多候选仲裁集成计划](plans/038-yolo-obb-general-postprocess-multicandidate-integration-plan.md)
- [YOLO/OBB 疑难样本分流质量门计划](plans/039-yolo-obb-difficult-case-routing-plan.md)
- [YOLO/OBB teacher 规则蒸馏到通用后处理计划](plans/047-yolo-obb-teacher-rule-postprocess-integration-plan.md)

### 标注工具

- [标注工具选择计划](plans/010-annotation-tool-selection-plan.md)
- [ISAT 调研计划](plans/011-isat-annotation-tool-research-plan.md)

## Workflows

- [ISAT OBB 标注流程](workflows/isat-obb-annotation-workflow.md)
- [Labelme OBB 标注流程](workflows/labelme-obb-annotation-workflow.md)
- [OCR 引擎选型与验证 SOP](workflows/ocr-engine-selection-sop.md)
