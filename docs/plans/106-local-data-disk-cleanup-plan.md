# 本地磁盘数据清理方案

日期：2026-07-06

## 背景

当前 Git 历史已经原地重建为单提交，`.git` 目录约 1.6 MB，不再是磁盘占用来源。项目目录仍超过 5 GB，主要原因是 `.gitignore` 排除的本地私有数据、审核包、渲染图、PDF 拆分页、模型响应和实验输出仍保留在磁盘上。

本方案只规划本地磁盘清理，不删除任何文件。后续执行删除前必须再次确认具体清单。

## 当前占用概览

顶层目录占用：

| 路径 | 约占用 | 说明 |
| --- | ---: | --- |
| `local_data/` | 5.16 GB | 私有图纸、审核包、实验数据、模型响应、历史快照 |
| `tools/pdf_rotation_mvp/` | 387 MB | MVP 输入、输出、工作目录和脚本 |
| `outputs/` | 193 MB | 旧 OpenCV/rotation 输出 |
| `runs/` | 13 MB | 训练或实验运行输出 |
| `.git/` | 1.6 MB | 已清理为单提交历史 |

`local_data/` 主要占用：

| 路径 | 约占用 | 初步判断 |
| --- | ---: | --- |
| `local_data/review_inbox/archive/` | 2.46 GB | 历史审核入口归档，最大占用 |
| `local_data/split_source_pdfs/` | 372 MB | PDF 拆分页，可再生 |
| `local_data/experiment_samples/` | 343 MB | 实验样本 PDF/PNG，可再生但常用于调试 |
| `local_data/full_63_title_block_ocr_dry_run/` | 293 MB | 旧 OCR dry-run 产物 |
| `local_data/vlm_title_block_generalization_blind_ykj125/` | 277 MB | 旧 VLM 泛化测试产物 |
| `local_data/source_pdfs/` | 226 MB | 原始源 PDF，默认保留 |
| `local_data/js2207_generalization_test/` | 219 MB | JS2207 泛化测试产物 |
| `local_data/js2207_real_pdf_vlm_title_block*/` | 378 MB | JS2207 VLM 测试产物 |
| `local_data/yolo_obb_dataset_round3/` | 155 MB | YOLO/OBB 数据集 |

`tools/pdf_rotation_mvp/` 主要占用：

| 路径 | 约占用 | 初步判断 |
| --- | ---: | --- |
| `tools/pdf_rotation_mvp/work/` | 202 MB | MVP 中间文件、渲染图、响应日志 |
| `tools/pdf_rotation_mvp/output/` | 123 MB | MVP 输出 PDF 和报告 |
| `tools/pdf_rotation_mvp/input/` | 61 MB | MVP 输入 PDF 副本 |

## 必须保留

默认不删除：

- `.env/`：本地密钥目录，虽然体积很小，但不能读取、打印或提交。
- `local_data/source_pdfs/`：原始 PDF，除非用户确认已有外部备份。
- `local_data/review_inbox/current/`：固定当前审核入口。
- `AGENTS.md`、`HANDOFF.md`、`TODO.md`、`docs/`、`reports/`、`rules/`、`references/`、`scripts/`、`tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py`。
- `tools/pdf_rotation_mvp/input/.gitkeep`、`output/.gitkeep`、`work/.gitkeep`。

## 可直接删除候选

这些是低风险候选，主要是过程性输出或本轮迁移产生的临时快照。删除前仍需用户确认。

| 路径/模式 | 约释放 | 原因 |
| --- | ---: | --- |
| `local_data/github_single_snapshot_*` | 约 20 MB | 本轮 GitHub 单快照迁移临时目录和 zip，已无业务价值 |
| `local_data/github_single_snapshot_clone_*` | 约 8 MB | 本轮远端验收临时 clone |
| `tools/pdf_rotation_mvp/__pycache__/` | 0.1 MB | Python 缓存 |
| `outputs/` | 193 MB | 旧 rotation 输出，可再生 |
| `runs/` | 13 MB | 旧训练/实验运行输出，若不再查训练细节可删 |

预计保守释放：约 230 MB。

## 标准清理候选

这些是可再生或已有文档记录的历史实验产物。适合在确认近期不需要复看图片、HTML 或模型响应后删除。

| 路径 | 约释放 | 风险 |
| --- | ---: | --- |
| `local_data/review_inbox/archive/` | 2.46 GB | 删除后无法直接打开历史审核 HTML，只能看文档摘要 |
| `local_data/split_source_pdfs/` | 372 MB | 拆分页可由源 PDF 再生 |
| `local_data/full_63_title_block_ocr_dry_run/` | 293 MB | 旧 OCR dry-run 产物，删除后不能直接复查原响应 |
| `local_data/vlm_title_block_generalization_blind_ykj125/` | 277 MB | 旧 VLM 泛化测试产物 |
| `local_data/js2207_generalization_test/` | 219 MB | 旧泛化测试产物 |
| `local_data/js2207_real_pdf_vlm_title_block/` | 189 MB | 旧 JS2207 VLM 测试产物 |
| `local_data/js2207_real_pdf_vlm_title_block_prompt_retest/` | 189 MB | 旧 prompt 复测产物 |
| `tools/pdf_rotation_mvp/work/` | 202 MB | MVP 中间文件和模型响应，删除后不能复查本轮细节 |
| `tools/pdf_rotation_mvp/output/` | 123 MB | MVP 输出 PDF 和报告，删除前建议保留 summary/report 备份 |
| `tools/pdf_rotation_mvp/input/` 中真实 PDF | 61 MB | 输入副本，可由 `local_data/source_pdfs/` 恢复 |

预计标准释放：约 4.3 GB。

## 极简清理候选

如果目标是让项目目录尽量接近公开仓库体积，可以进一步删除大部分 `local_data/` 实验数据，仅保留源 PDF、当前审核入口和必要私密配置。

可考虑删除：

- `local_data/experiment_samples/`：343 MB。
- `local_data/yolo_obb_dataset_round2/`：82 MB。
- `local_data/yolo_obb_dataset_round3/`：155 MB。
- `local_data/yolo_obb_dataset_smoke/`：62 MB。
- `local_data/ocr_fine_roi_experiment/`：60 MB。
- `local_data/ocr_fine_roi_tightening_experiment/`：41 MB。
- `local_data/yolo_predictions/`：45 MB。
- 其他旧 probe、teacher、dry-run、review pack 目录。

预计极简释放：在标准清理基础上再释放约 0.8 GB 到 1.0 GB。

## 推荐执行策略

推荐采用两步走：

1. **保守清理**
   - 删除 GitHub 迁移临时快照目录/zip。
   - 删除 `outputs/`、`runs/`。
   - 删除 Python 缓存。
   - 不动 `local_data/review_inbox/archive/` 和 MVP 输出。

2. **标准清理**
   - 用户确认历史审核 HTML、图片、VLM/OCR 原始响应不再需要直接打开后，删除 `review_inbox/archive/` 和旧实验产物。
   - 删除前生成一份机器清单，记录目录名、大小、文件数和删除时间。

不建议第一轮直接极简清理。机械图纸、审核包和模型响应对问题复盘仍有价值，先保守释放一部分空间更稳。

## 删除前质量门

任何删除批处理前必须满足：

- 输出待删除清单。
- 清单包含绝对路径、大小、文件数。
- 路径必须全部位于 `D:\project\codex\BlueprintNormalizer` 下。
- 不删除 `.env/`。
- 不删除 `local_data/source_pdfs/`，除非用户单独确认。
- 不删除 `local_data/review_inbox/current/`。
- 不删除 Git 跟踪文件。
- 删除后重新运行：

```powershell
git status --short --branch
git rev-list --count HEAD
python -m py_compile tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py
```

## 后续执行建议

下一步应先让用户选择清理档位：

- 保守清理：预计释放约 230 MB，风险最低。
- 标准清理：预计释放约 4.3 GB，需确认不再需要历史审核包和旧实验产物。
- 极简清理：预计总释放约 5 GB，适合只保留源 PDF、当前入口和公开代码。

用户确认档位后，再生成具体删除清单并等待最终确认，不直接删除。
