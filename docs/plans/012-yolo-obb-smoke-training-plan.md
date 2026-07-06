# YOLO/OBB 冒烟训练准备计划

## 背景

ISAT 标注的 16 张 smoke 样本已经完成转换、校验和 overlay 抽查：

- YOLO/OBB 标签：16/16。
- 校验错误：0。
- 校验警告：0。
- overlay 抽查通过。

下一步应进入 YOLO/OBB 冒烟训练准备。但当前环境尚未安装 Ultralytics，因此本阶段先准备本地数据集结构，不直接训练。

## 目标

生成一个可被 Ultralytics OBB 训练命令读取的本地数据集包。

输出位置：

```text
local_data/yolo_obb_dataset_smoke/
```

包含：

- `images/train/`
- `images/val/`
- `labels/train/`
- `labels/val/`
- `data.yaml`
- `dataset_summary.json`

## 冒烟训练策略

本阶段先采用“过拟合链路验证”数据集：

```text
train = 16 张 smoke 样本
val   = 16 张 smoke 样本
```

这不是泛化评估，而是故意验证：

- 图片和标签路径是否正确。
- Ultralytics OBB 能否加载数据。
- 模型是否能在极小样本上学到标题栏。
- 输出预测图和指标文件是否可用于后续调试。

泛化评估必须等后续扩展到更多标注样本后再做。

## 本轮不做

- 不安装 Ultralytics。
- 不下载 YOLO 权重。
- 不启动训练。
- 不上传图纸和标签。
- 不把 `local_data/` 产物提交到 Git。

## 验收标准

- 数据集构建脚本可重复运行。
- 生成 16 张 train 图片和 16 个 train 标签。
- 生成 16 张 val 图片和 16 个 val 标签。
- `data.yaml` 指向本地数据集目录。
- 类别只有一个：`title_block`。
- 所有标签仍通过基础格式校验。

## 后续训练命令草案

待用户同意安装 Ultralytics 后，训练命令可类似：

```powershell
yolo obb train model=yolo11n-obb.pt data=local_data/yolo_obb_dataset_smoke/data.yaml epochs=30 imgsz=1024 batch=2 plots=True
```

实际参数需根据显存、CPU/GPU 环境和首轮结果调整。
