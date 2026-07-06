# pictureAnalyse

机械图纸扫描件处理实验项目。

目标是识别扫描版机械图纸的页面旋转方向，并逐步形成可复核、可解释、可回滚的标题栏检测工作流。判断依据是：符合机械制图规范的图纸，其标题栏在正确方向下应位于页面下方或右下方。

## 文档入口

- [换账号接手交接记录](HANDOFF.md)
- [项目协作规则](AGENTS.md)
- [TODO](TODO.md)
- [文档索引](docs/README.md)
- [参考资料索引](references/README.md)
- [规则索引](rules/README.md)
- [报告索引](reports/README.md)

## 当前重点

已完成 OpenCV 方向识别基线、全量人工确认 ground truth、顺时针 90 度增强样本、YOLO/OBB 标题栏标注、round2/round3 训练与预测复查、通用 YOLO/OBB 多候选后处理、疑难样本分流、MCP/VLM teacher 复盘、OCR/细 ROI 实验和 JS2207 泛化测试。

当前主线是阿里云 VLM 旋正与图号读取 MVP。第一步只生成 dry-run 请求包，不联网、不正式旋正 PDF、不重命名 PDF。

当前固定入口位于：

```text
local_data/review_inbox/current/
```

其中仍保留 JS2207 泛化测试部分人工反馈。发布任何新审核入口前，必须先归档当前入口。

先阅读根目录 [HANDOFF.md](HANDOFF.md)，再继续开发。当前不应直接重训、不应覆盖 JS2207 已填写反馈、不应联网调用云端 VLM，除非用户确认 Key、base URL、模型名和图纸可外发范围。

## 数据与隐私

图纸原件、拆分 PDF、渲染 PNG、临时输出和个人草稿不进入公开仓库。

本地私有资料统一放在 `local_data/`，并由 `.gitignore` 排除。

当前本地私有目录约定：

- `local_data/source_pdfs/`：原始 PDF。
- `local_data/experiment_samples/all/pdf/`：全量单页 PDF 实验样本。
- `local_data/experiment_samples/all/png/`：全量 PNG 实验样本。
- `local_data/experiment_samples/first20/pdf/`：前 20 张单页 PDF 实验样本。
- `local_data/experiment_samples/first20/png/`：前 20 张 PNG 实验样本。
- `local_data/review_inbox/current/`：固定人工审核入口。
- `local_data/aliyun_vlm_mvp/`：阿里云 VLM MVP dry-run 请求包。
- `local_data/yolo_obb_dataset_round2/`：第二轮人工确认 YOLO/OBB 本地训练数据集。
- `local_data/yolo_runs/round2_yolo11n_obb/`：第二轮 YOLO/OBB 首训本地训练产物。
- `local_data/mcp_vlm_teacher_review/`：MCP/VLM teacher 复盘本地产物。
- `local_data/mcp_vlm_teacher_call_prep/`：teacher 小规模调用准备包。
- `local_data/mcp_vlm_teacher_provider/`：teacher provider 请求、响应模板和校验结果。

## 阶段一运行方式

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

运行全量实验样本识别：

```powershell
python -m scripts.rotation.detect_rotation_stage1
```

输出会写入本地忽略目录：

- `outputs/rotation-detection/stage1/results.json`
- `outputs/rotation-detection/stage1/results.csv`
- `outputs/rotation-detection/stage1/debug/*.png`
