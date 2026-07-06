# TODO

## 当前审核点

- [x] 已确认工程化整理详细计划存在于 `docs/plans/102-project-layout-naming-config-exe-plan.md`，并已将迁移、删除、调整、测试、打包事项展开写入本 TODO。
- [x] 已按用户要求压缩历史已完成流水账，TODO 只保留阶段摘要、当前执行队列和后续待办。
- [x] 已开始执行阶段 1：项目元信息、配置模板和 CLI 骨架。
- [x] 阶段 1 已完成：项目元信息、配置模板、CLI 骨架、测试骨架和 PyInstaller 占位已通过非联网验证。
- [x] 已完成阶段 2 对抗性审核，并将阶段 2 收窄为 MVP 主线迁移计划。
- [x] 已将工程化阶段 0-7 统一整合进 `docs/plans/102-project-layout-naming-config-exe-plan.md`，不再分散维护阶段计划文件。
- [x] 已开始执行阶段 2：先做旧 MVP 主程序只读审计，不改源码、不调用阿里云、不处理真实 PDF。

## 已完成历史摘要

详细过程不再在 TODO 中逐条展开，追溯入口为：

- `reports/rpd-rotation-detection.md`
- `docs/plans/`
- `HANDOFF.md`

已完成阶段摘要：

- [x] 公开仓库整理：已建立 `.gitignore`，图纸原件、拆分页、渲染图、临时目录和本地私有数据不进入 Git。
- [x] OpenCV 方向识别基线：已完成样本抽取、旋转检测、ground truth、自动评估、人工复核包和 83/83 联合评估。
- [x] YOLO/OBB 标题栏路线：已完成标注流程、数据集校验、round2/round3 训练、后处理、失败分流、teacher 规则蒸馏和相关复查归档。
- [x] OCR/ROI 路线：已完成标题栏 crop、OCR 字段簇、图号候选、命名质量门、细 ROI 收窄、人工校正规律沉淀和本地实验记录。
- [x] VLM/阿里云路线：已完成接入调研、联网执行规则固化、JS2207/YKJ125 多轮标题栏位置与方向测试、错题集评估和模型参数调研。
- [x] PDF 旋正与图号命名 MVP：已完成自包含 MVP 脚本、方向识别、单页旋正、图号读取、按图号命名、审核包发布和结果归档。
- [x] 人工审核入口规则：已固定当前审核入口为 `local_data/review_inbox/current/`，并完成多轮审核包发布、归档和入口重置。
- [x] 项目交接与文档整理：已更新 README、docs 索引、HANDOFF、RPD 和长期规则。
- [x] 项目命名与 GitHub 整理：已采用 `BlueprintNormalizer`，新仓库为 `blueprint-normalizer`，旧仓库 `pictureAnalyse` 已删除。
- [x] Git 历史收口：当前 `D:\project\codex\BlueprintNormalizer` 已原地重建为单提交仓库并推送到新仓库。
- [x] 本地磁盘清理：已制定清理方案，用户决定跳过清理执行，继续工程化整理。

## 当前执行队列：工程化整理

### 阶段 1：项目元信息、配置模板和 CLI 骨架

- [x] 规划阶段 1 项目元信息、配置模板和 CLI 骨架执行细节。
- [x] 提交阶段 1 执行前回滚点。
- [x] 新增 `pyproject.toml`，配置 `blueprint-normalizer` CLI 入口和 `src/` 布局。
- [x] 新增 `src/blueprint_normalizer/__init__.py`。
- [x] 新增 `src/blueprint_normalizer/__main__.py`。
- [x] 新增 `src/blueprint_normalizer/cli.py`。
- [x] 新增 `src/blueprint_normalizer/config.py`。
- [x] 新增 `src/blueprint_normalizer/paths.py`。
- [x] 新增 `etc/blueprint-normalizer.example.toml`。
- [x] 新增 `etc/README.md` 说明模板配置与真实配置边界。
- [x] 复核 `.gitignore` 覆盖 `blueprint-normalizer.toml`、`build/`、`dist/`、本地数据和发布产物。
- [x] 新增 `tests/`、`tests/unit/`、`tests/integration/`、`tests/fixtures/` 基础结构。
- [x] 新增配置解析单元测试。
- [x] 新增开发态/EXE 态路径解析单元测试。
- [x] 新增 CLI 帮助命令非联网测试。
- [x] 新增 `packaging/`、`packaging/pyinstaller/` 基础结构。
- [x] 新增 `packaging/pyinstaller/BlueprintNormalizer.spec` 初版占位或计划说明。
- [x] 阶段 1 非联网检查：`python -m py_compile` 覆盖新增包文件。
- [x] 阶段 1 非联网检查：`python -m blueprint_normalizer --help`。
- [x] 阶段 1 非联网检查：配置模板解析不读取真实 key。

### 阶段 2：收窄版 MVP 主线迁移

- [x] 用批判性和对抗性思维审核原阶段 2 全量迁移风险。
- [x] 规划阶段 2 收窄迁移细节和回滚点。
- [x] 更新阶段 2 执行前 RPD/TODO，确认只读审计边界。
- [x] 提交阶段 2 执行前文档回滚点。
- [x] 只读审计 `tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py` 的函数边界、全局变量、路径默认值、凭据读取、联网函数和外部命令。
- [x] 记录需要参数化的对象：`SCRIPT_DIR`、默认 `input/output/work`、`DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`、联网请求函数、Ghostscript 调用。
- [x] 规划包内 MVP 目录和无副作用 dry-run 的实施边界。
- [x] 提交包内 MVP dry-run 实施前回滚点。
- [x] 新增 `src/blueprint_normalizer/pdf_rotation_mvp/__init__.py`。
- [x] 新增 `src/blueprint_normalizer/pdf_rotation_mvp/cli.py`。
- [x] 新增 `src/blueprint_normalizer/pdf_rotation_mvp/pipeline.py`。
- [x] 新增 `src/blueprint_normalizer/pdf_rotation_mvp/legacy_adapter.py`。
- [x] 新增 `src/blueprint_normalizer/pdf_rotation_mvp/prompts/` 和 `schemas/` 占位。
- [x] 扩展配置适配层，将 TOML 模板转换为 MVP 运行配置。
- [x] 增加假 key 脱敏测试，确保 stdout/stderr 不泄露凭据。
- [x] 增加配置优先级测试：显式 `--config` 优先于默认候选。
- [x] 新增 `blueprint-normalizer pdf-rotation-mvp dry-run`，只做结构检查，不调用阿里云、不处理真实 PDF。
- [x] 阶段 2 dry-run 验证不读取 `.env/.env`。
- [x] 阶段 2 dry-run 验证不写入 `local_data/review_inbox/current/`。
- [x] 规划最小 MVP 主线第一批纯函数和数据结构迁移边界。
- [x] 提交纯逻辑迁移实施前回滚点。
- [x] 迁移第一批纯函数：文件名清洗、图号规范化、标题栏位置映射、响应解析和决策构建。
- [x] 增加纯函数单元测试，覆盖旧脚本关键行为。
- [x] 本轮纯逻辑迁移非联网验证通过：旧入口 py_compile、新包 compileall、CLI dry-run、unittest、禁区检查。
- [x] 规划路径参数和 MVP 运行配置对象适配边界。
- [x] 提交运行配置适配实施前回滚点。
- [x] 新增 MVP 运行配置对象，将 TOML 解析为包内结构。
- [x] 将 dry-run 改为复用运行配置对象，不直接散落解析 TOML。
- [x] 增加运行配置对象单元测试，覆盖相对路径、显式配置、缺失配置和脱敏。
- [x] 本轮运行配置适配非联网验证通过：旧入口 py_compile、新包 compileall、CLI dry-run、unittest、禁区检查。
- [x] 规划副作用边界对象实施边界：只建模 PDF 拆分、Ghostscript、VLM 请求和发布步骤，不执行。
- [x] 提交副作用边界对象实施前回滚点。
- [x] 新增 MVP 执行计划对象，描述未来 run 的步骤和副作用边界。
- [x] dry-run 输出执行计划摘要，仍保持不读 PDF、不联网、不调用 Ghostscript、不创建目录。
- [x] 增加执行计划对象单元测试，覆盖步骤顺序、路径来源和副作用标记。
- [x] 本轮副作用边界对象非联网验证通过：新包 compileall、CLI dry-run、unittest。
- [x] 规划最小 MVP 主线数据骨架迁移边界：只迁记录结构、图片记录派生和报告行组装，不执行副作用。
- [x] 提交最小 MVP 主线数据骨架迁移实施前回滚点。
- [x] 迁移 `PageRecord`、`ImageRecord` 和主线报告组装纯逻辑到包内模块。
- [x] 增加主线数据骨架单元测试，覆盖图片记录派生、报告字段合并和缺失行兜底。
- [x] 本轮主线数据骨架非联网验证通过：旧入口 py_compile、新包 compileall、CLI dry-run、unittest、禁区检查。
- [x] 规划输入收集和目录安全守门迁移边界：只枚举 PDF 路径、校验受控目录和创建受控目录，不读 PDF 内容、不删除目录。
- [x] 提交输入收集和目录安全守门迁移实施前回滚点。
- [x] 迁移 `collect_input_pdfs()` 到包内模块，只枚举目录下 `.pdf` 文件并稳定排序。
- [x] 新增受控目录安全 helper，拒绝越界路径和根目录自身，暂不迁移旧脚本的目录清空逻辑。
- [x] 增加输入收集和目录安全单元测试，覆盖缺失目录、空目录、大小写后缀、越界路径和根路径拒绝。
- [x] 本轮输入收集和目录安全守门非联网验证通过：旧入口 py_compile、新包 compileall、CLI dry-run、unittest、禁区检查。
- [x] 规划报告写出工具迁移边界：只迁移 JSON/JSONL/CSV 序列化工具，在测试临时目录验证，不接入真实运行目录。
- [x] 提交报告写出工具迁移实施前回滚点。
- [x] 迁移 `write_json()`、`write_jsonl()`、`write_csv()` 到包内模块。
- [x] 增加报告写出工具单元测试，覆盖 UTF-8 JSON、JSONL 行格式、UTF-8-SIG CSV 和空行表头行为。
- [x] 本轮报告写出工具非联网验证通过：旧入口 py_compile、新包 compileall、CLI dry-run、unittest、禁区检查。
- [x] 规划 MVP prompt 资产迁移边界：只迁移旧脚本中的方向判断和图号提取提示词，不调用模型。
- [x] 提交 MVP prompt 资产迁移实施前回滚点。
- [x] 将方向判断和图号提取 prompt 迁移到包内 `prompts/` 资源文件。
- [x] 新增 prompt 读取 helper，并确保打包配置包含 prompt 资源。
- [x] 增加 prompt 资源单元测试，覆盖资源存在、中文内容和关键 JSON 字段约束。
- [x] 本轮 prompt 资产迁移非联网验证通过：旧入口 py_compile、新包 compileall、CLI dry-run、unittest、禁区检查。
- [x] 规划 VLM 请求构造迁移边界：只迁 endpoint 归一化、data URL、request body 和脱敏行，不迁 HTTP 调用。
- [x] 提交 VLM 请求构造迁移实施前回滚点。
- [x] 迁移 `endpoint_from_base_url()`、`data_url_for()`、`build_request_body()` 到包内模块。
- [x] 迁移 `redacted_request_row()` 和 `public_raw_row()`，保持图片 data URL 脱敏。
- [x] 增加 VLM 请求构造单元测试，覆盖 endpoint 兼容路径、base64 data URL、请求体结构和脱敏输出。
- [x] 本轮 VLM 请求构造非联网验证通过：旧入口 py_compile、新包 compileall、CLI dry-run、unittest、禁区检查。
- [x] 规划 MVP run summary 主线骨架迁移边界：只迁移旧 `run()` 末尾 summary 聚合和输出清单构造，不执行副作用步骤。
- [x] 提交 MVP run summary 主线骨架迁移实施前回滚点。
- [x] 迁移 `build_run_summary()` 到包内模块，聚合路径、模型、计数、env 状态和输出清单。
- [x] 增加 MVP run summary 单元测试，覆盖成功计数、needs review 计数、输出路径清单和 root 相对路径。
- [x] 本轮 MVP run summary 非联网验证通过：旧入口 py_compile、新包 compileall、CLI dry-run、unittest、禁区检查。
- [x] 规划 MVP run orchestrator 守门骨架：新增包内真实运行入口报告，但默认拒绝执行副作用步骤。
- [x] 提交 MVP run orchestrator 守门骨架实施前回滚点。
- [x] 新增 `build_run_disabled_report()`，复用运行配置和执行计划，明确列出真实运行尚未启用。
- [x] 增加 MVP run orchestrator 单元测试，覆盖默认不执行副作用、配置错误透传和未来步骤清单。
- [x] 本轮 MVP run orchestrator 非联网验证通过：旧入口 py_compile、新包 compileall、CLI dry-run、unittest、禁区检查。
- [ ] 迁移最小 MVP 主线到包内模块，逐步接入拆页渲染、模型请求、旋转发布和报告写出。
- [x] 暂时保留 `tools/pdf_rotation_mvp/run_pdf_rotation_mvp.py` 旧入口作为回归对照或薄 wrapper。
- [x] 阶段 2 非联网检查：旧入口 `py_compile` 通过。
- [x] 阶段 2 非联网检查：新 `pdf_rotation_mvp` 包 `py_compile` 通过。
- [x] 阶段 2 非联网检查：CLI help/config check/dry-run 通过。
- [x] 阶段 2 禁区检查：`git ls-files local_data .env outputs runs blueprint-normalizer.toml` 无输出。
- [x] 将 `scripts/*` 历史实验脚本迁移后置到单独阶段，不作为阶段 2 当前执行项。
- [x] 规划 PDF 旋转/复制输出迁移边界：只迁移 `rotate_or_copy_pdf()`，使用单元测试临时合成 PDF 验证。
- [x] 提交 PDF 旋转/复制输出迁移实施前回滚点。
- [x] 迁移 `rotate_or_copy_pdf()` 到包内模块，支持 corrected 与 copied_needs_review 两类输出。
- [x] 增加 PDF 旋转/复制输出单元测试，覆盖成功旋转、dry-run 复制、模型/解析/schema 阻断和路径报告。
- [x] 本轮 PDF 旋转/复制输出非联网验证通过：旧入口 py_compile、新包 compileall、CLI dry-run、unittest、禁区检查。
- [x] 规划最终 PDF 发布迁移边界：只迁移 `publish_final_pdfs()`，使用单元测试临时合成 PDF 验证。
- [x] 提交最终 PDF 发布迁移实施前回滚点。
- [x] 迁移 `publish_final_pdfs()` 到包内模块，支持 published 与 needs_review 两类最终状态。
- [x] 增加最终 PDF 发布单元测试，覆盖成功发布、dry-run 阻断、重复图号、缺失图号和路径报告。
- [x] 本轮最终 PDF 发布非联网验证通过：旧入口 py_compile、新包 compileall、CLI dry-run、unittest、禁区检查。
- [x] 规划标题栏裁剪候选图迁移边界：只迁移 `crop_title_block_candidate()`，使用单元测试临时合成 PNG 验证。
- [x] 提交标题栏裁剪候选图迁移实施前回滚点。
- [x] 迁移 `crop_title_block_candidate()` 到包内模块，保留横图/竖图裁剪比例和 crop 元数据。
- [x] 增加标题栏裁剪候选图单元测试，覆盖横向图、竖向图、输出尺寸、crop_box 和路径报告。
- [x] 本轮标题栏裁剪候选图非联网验证通过：旧入口 py_compile、新包 compileall、CLI dry-run、unittest、禁区检查。

### 阶段 3：CLI、运行目录和配置加载

- [ ] 规划阶段 3 CLI、运行目录和配置加载细节。
- [ ] 实现 `blueprint-normalizer config init`。
- [ ] 实现 `blueprint-normalizer config check`，不打印 API key。
- [ ] 实现 `blueprint-normalizer pdf-rotation-mvp dry-run`。
- [ ] 实现 `blueprint-normalizer pdf-rotation-mvp run`。
- [ ] 将配置加载优先级改为 `--config`、EXE 同级、开发根目录，再考虑兼容旧 `.env/.env`。
- [ ] 阶段 3 非联网 dry-run 验证不调用阿里云、不上传图纸。

### 阶段 4：文档目录迁移和入口更新

- [ ] 规划阶段 4 文档目录迁移和文档入口更新。
- [x] 刷新根目录 `HANDOFF.md`，供 2026-07-08 账号切换后继续接手。
- [ ] 用 `git mv` 将 `reports/` 迁入 `docs/reports/`。
- [ ] 用 `git mv` 将 `rules/` 迁入 `docs/rules/`。
- [ ] 用 `git mv` 将 `references/` 迁入 `docs/references/`。
- [ ] 更新根 README，加入 `AI Quick Context`。
- [ ] 更新 `HANDOFF.md` 中当前路径、remote、入口命令和下一步。
- [ ] 更新 `docs/README.md`、`docs/reports/README.md`、`docs/rules/README.md`、`docs/references/README.md`。
- [ ] 更新 `tools/pdf_rotation_mvp/README.md` 或迁移其内容到正式文档。
- [ ] 更新所有当前说明中的旧命令 `python tools\pdf_rotation_mvp\run_pdf_rotation_mvp.py`。
- [ ] 更新所有当前说明中的旧命令 `python -m scripts...`。
- [ ] 更新阿里云联网执行规则中的旧批准命令前缀说明。
- [ ] 删除或标注历史计划中不应机械替换的旧路径语境。

### 阶段 5：测试与验证

- [ ] 规划阶段 5 测试与验证细节。
- [ ] 增加包导入测试。
- [ ] 增加配置解析测试。
- [ ] 增加路径解析测试。
- [ ] 增加图号文件名规则测试。
- [ ] 增加 dry-run 不联网测试。
- [ ] 运行迁移后的 `python -m py_compile`。
- [ ] 运行迁移后的 CLI help/config check/dry-run 非联网验证。

### 阶段 6：EXE 打包准备

- [ ] 规划阶段 6 EXE 打包准备细节。
- [ ] 完善 PyInstaller spec。
- [ ] 生成发布包目录模板说明：`input/`、`output/`、`work/`、`logs/`。
- [ ] 确认发布包不包含真实 `blueprint-normalizer.toml` 和 API key。
- [ ] 清理迁移后遗留空目录、旧入口说明和过期 TODO。

## 后续业务待办

- [ ] 将无图号页 `待人工复核_XX` 命名规则落实到 MVP 输出。
- [ ] 分析第 22 页方向未摆正问题并决定 MVP 修正策略。
- [ ] 对浅字标题栏样本执行 OCR 图像预处理小实验。
- [ ] 重新生成 63 条图号命名人工审核包。
- [ ] 用户审核重建后的 63 条图号命名人工审核包。
- [ ] 归档重建后的 63 条图号命名人工审核结果。
- [ ] 设计本地 VLM 梯度测试方案。
- [ ] 批量处理完整 PDF。
- [ ] 生成校正后的 PDF 输出方案。
