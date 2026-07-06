# YOLO/OBB 训练规划依据

日期：2026-06-26

## 一、问题

当前项目已完成第二轮 40 张标题栏 OBB 标注、转换、校验和人工 overlay 复查。用户询问下一步训练计划依据是什么，是否有调研结论支撑。

本文件记录训练前规划依据，避免后续把“小样本链路验证”误说成“工业级模型训练完成”。

## 二、依据来源

### 外部调研

主要记录在：

- `docs/research/2026-06-25-yolo-obb-debugging-research.md`
- `references/yolo-obb-debugging-research/README.md`

调研样本包括：

- Ultralytics OBB Dataset Format。
- Ultralytics Train Mode。
- Ultralytics Performance Metrics。
- Ultralytics Model Testing。
- Ultralytics Data Collection and Annotation。
- 工程图纸 OBB + Donut 解析论文。
- 多阶段工程图纸 VLM 框架论文。

### 项目内路线

主要记录在：

- `docs/plans/013-yolo-obb-title-block-experiment-plan.md`
- `docs/plans/012-yolo-obb-smoke-training-plan.md`

项目路线是：

```text
OpenCV 基线
  -> 本地 YOLO/OBB 标题栏检测
  -> OCR 文字证据
  -> 本地/云端 VLM 兜底解释疑难样本
  -> 证据融合，不做简单同权投票
```

## 三、调研结论

1. YOLO/OBB 训练不能直接从标注跳到训练结果，必须先做标签格式校验、overlay 可视化和人工复查。
2. OBB 标签必须使用 `class_index x1 y1 x2 y2 x3 y3 x4 y4`，坐标归一化；仅检查 `.txt` 存在不足以证明可训练。
3. 小样本阶段应先验证训练链路和过拟合能力，不应宣称泛化能力。
4. 训练/验证/测试拆分必须按 `source_sample` 分组，避免原图和增强图跨 split 泄漏。
5. 指标不能只看 mAP，还必须看 recall、定位质量、预测图、错误样本和后处理映射是否正确。
6. 错误必须分层为 `label_error`、`format_error`、`false_negative`、`false_positive`、`localization_error`、`postprocess_error`、`data_leakage`。
7. 工程图纸场景适合 detector-first：先检测标题栏，再让 OCR/VLM 做辅助或兜底。

## 四、当前质量门状态

当前已完成：

- 第二轮标注样本：40。
- 数据来源：`original` 8，`augmented_90` 20，`augmented_90_unclear` 12。
- ISAT JSON 转 YOLO/OBB：40/40。
- 标签校验：0 错误，0 警告。
- overlay 生成：40/40。
- 人工 overlay 复查：40/40 正确。
- 训练前数据集：`local_data/yolo_obb_dataset_round2/`。
- train/val/test：26/7/7。
- `source_sample` 跨 split 泄漏：0。

## 五、下一步训练计划原则

下一步若安装 Ultralytics 并训练，应按以下原则执行：

1. 先记录训练命令、模型、参数、输出目录和回滚点。
2. 首轮使用 nano 级 OBB 模型，优先降低配置压力。
3. 开启 `plots=True`，保留训练曲线、验证图和预测图。
4. 先验证模型能否学习训练集，再看 val/test。
5. 训练后必须生成预测 overlay，并放入固定审核入口复查。
6. 如果训练集也检测失败，优先检查标签、YAML、路径和点序，不急着调参。
7. 如果训练集好但 val/test 差，优先补样本和检查版式覆盖。

## 六、边界声明

当前 40 张数据集足以支撑标题栏检测链路验证，但不足以支撑工业级泛化结论。

任何训练结果只能表述为：

- 小样本标题栏 OBB detector 原型。
- 本地训练链路验证。
- OpenCV 之外的候选证据来源。

不得表述为：

- 已达到工业级稳定。
- 可无人复核处理所有图纸。
- 可替代 OpenCV 主流程。

## 七、后续验收

训练阶段至少需要输出：

- 训练命令和环境记录。
- `data.yaml`。
- 训练日志与 plots。
- val/test 预测结果。
- 预测 overlay。
- 错误样本分层表。
- 框位置到标题栏方向的映射评估。
