# YOLO/OBB 第二轮首训计划

## 背景

第二轮人工确认数据集已经完成：

- 数据集目录：`local_data/yolo_obb_dataset_round2/`
- 样本总数：40。
- train / val / test：26 / 7 / 7。
- source_sample 跨 split 泄漏：0。
- 标签校验问题：0。
- overlay 人工复查：40/40 正确。

本计划依据：

- `docs/research/2026-06-26-yolo-obb-training-basis.md`
- `docs/research/2026-06-25-yolo-obb-debugging-research.md`
- `references/yolo-obb-debugging-research/README.md`

## 目标

首轮训练只验证本地 YOLO/OBB 标题栏 detector 链路：

1. Ultralytics OBB 是否能正常加载本项目数据集。
2. 模型是否能在小样本训练集上学到 `title_block`。
3. val/test 预测图是否能稳定框住标题栏。
4. 预测框是否能作为 OpenCV 之外的方向判断证据。

## 非目标

本轮不做：

- 不宣称工业级泛化能力。
- 不替代 OpenCV 主流程。
- 不接入 OCR/VLM。
- 不调复杂超参数。
- 不上传图纸、标签或训练数据。
- 不把训练产物提交到 Git。

## 模型选择

首轮使用 nano 级 OBB 模型，优先降低配置压力：

```text
yolo11n-obb.pt
```

理由：

- 符合调研结论中的“小样本先验证链路”。
- 下载和训练成本最低。
- 若 nano 模型无法在训练集学习标题栏，优先排查数据、标签、路径和配置，而不是直接换大模型。

## 数据集

使用：

```text
local_data/yolo_obb_dataset_round2/data.yaml
```

当前内容：

```text
train: images/train
val: images/val
test: images/test
class 0: title_block
```

划分策略：

- 按 `source_sample` 分组，避免原图、清晰 90 度增强、不清晰 90 度增强跨 split 泄漏。
- `test` 固定包含 `sample_001`、`sample_010`、`sample_042` 等关键难例来源。
- `val` 固定包含 `sample_009`、`sample_020`、`sample_034`、`sample_040` 等代表来源。

## 训练命令草案

安装 Ultralytics 后，首轮命令草案：

```powershell
yolo obb train model=yolo11n-obb.pt data=local_data/yolo_obb_dataset_round2/data.yaml epochs=40 imgsz=1024 batch=2 plots=True project=local_data/yolo_runs name=round2_yolo11n_obb
```

如果本机无 GPU 或显存不足：

```powershell
yolo obb train model=yolo11n-obb.pt data=local_data/yolo_obb_dataset_round2/data.yaml epochs=30 imgsz=768 batch=1 plots=True project=local_data/yolo_runs name=round2_yolo11n_obb_cpu
```

参数说明：

- `model=yolo11n-obb.pt`：最低配置压力。
- `epochs=30-40`：先验证链路，不做长时间调参。
- `imgsz=1024`：图纸细线较多，优先保留细节。
- `batch=1-2`：降低显存压力。
- `plots=True`：必须保留训练曲线和验证图。
- `project=local_data/yolo_runs`：训练产物留在 ignored 本地目录。

## 训练前检查

训练前必须确认：

1. `python -m pip show ultralytics` 是否已安装。
2. `local_data/yolo_obb_dataset_round2/data.yaml` 存在。
3. train/val/test 图片和标签数量分别为 26/7/7。
4. `dataset_validation.json` 中 `issues=0`。
5. `local_data/` 仍被 `.gitignore` 排除。

## 训练后质量门

训练结束后必须执行：

1. 保存训练命令、环境、模型和输出目录。
2. 检查训练日志和 plots。
3. 对 train、val、test 运行 predict。
4. 生成预测 overlay。
5. 将预测 overlay 发布到固定审核入口：

```text
local_data/review_inbox/current/
```

6. 用户复查预测框是否准确框住标题栏。
7. 对错误样本做错误分层。

## 指标观察

本轮重点看：

- train 是否能稳定学到标题栏。
- val/test recall。
- val/test 预测框定位质量。
- false negative：漏检标题栏。
- false positive：误检明细表、技术要求表或相似表格。
- localization error：检测到标题栏但框偏。
- postprocess error：框正确但位置映射错误。

mAP 只能作为参考，不作为唯一验收指标。

## 通过标准

首轮训练可进入下一阶段的最低标准：

1. 训练流程完成，没有路径、标签格式或数据加载错误。
2. train 预测大部分能检出标题栏。
3. val/test 预测图能生成并可复查。
4. 错误样本已分层，不静默接受失败结果。
5. 至少能判断 YOLO/OBB 是否值得继续作为 OpenCV 之外的证据分支。

## 失败处理

若训练失败：

- 数据加载失败：检查 `data.yaml`、目录、图片/标签匹配。
- 标签异常：回到转换脚本和 overlay 校验。
- train 也检不出：检查 OBB 点序、标注一致性、类别配置。
- train 好但 val/test 差：补样本、检查 split、增加真实 90 度或难例，不先调大模型。
- 误检相似表格：补负例或增加困难样本，并更新错误分层记录。

## 回滚点

本计划、RPD 和 TODO 提交后作为训练前回滚点。若安装或训练不可用，可回退到该提交，保留已通过质量门的数据集和规划。
