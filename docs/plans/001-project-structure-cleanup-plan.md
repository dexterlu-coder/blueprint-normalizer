# 项目目录整理计划

## 目标

整理当前项目目录，让公开仓库和本地私有数据边界清晰：

- 公开仓库只保留源码、规则、规划、RPD、参考资料和依赖说明。
- 图纸原件和实验样本只保留在 `local_data/`。
- 可再生输出、旧临时目录、缓存和无关草稿删除。
- 不删除原始 PDF 和前 20 张实验样本。

## 目标结构

整理后建议结构：

```text
.
├── AGENTS.md
├── README.md
├── TODO.md
├── requirements.txt
├── docs/
├── references/
├── reports/
├── rules/
├── scripts/
└── local_data/                  # ignored, 本地私有
    ├── source_pdfs/             # 原始 PDF，保留
    └── experiment_samples/
        └── first20/
            ├── pdf/             # 前 20 张单页 PDF，保留
            └── png/             # 前 20 张渲染 PNG，保留
```

## 删除项

以下内容可删除：

- `output/`：旧单页 PDF 输出目录，已被 `local_data/experiment_samples/first20/pdf/` 取代。
- `tmp/`：旧临时渲染目录，已无保留价值。
- `outputs/`：算法输出结果，可由脚本重新生成。
- `local_data/split_pdfs/`：前 5 张单页 PDF，已包含在 first20 样本内。
- `local_data/previews/`：前 5 张 PNG 预览，已包含在 first20 样本内。
- `scripts/__pycache__/`：Python 缓存。
- `reports/candidates/`：课程候选问题草稿，不属于当前公开代码项目。
- `reports/homework-submission-draft.md`：课程作业草稿，不属于当前公开代码项目。

## 保留项

以下内容必须保留：

- `local_data/source_pdfs/`：原始 PDF。
- `local_data/experiment_samples/first20/pdf/`：前 20 张单页 PDF 实验样本。
- `local_data/experiment_samples/first20/png/`：前 20 张 PNG 实验样本。
- 所有 Git 跟踪文件。

## 安全要求

- 删除前必须确认路径解析后仍在项目根目录内。
- 不使用 `git reset --hard` 或 `git checkout --`。
- 删除只针对本计划列出的 ignored 或无关草稿路径。
- 删除后运行 `git status --short --ignored` 和样本数量检查。
