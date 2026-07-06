# ISAT 标注 YOLO/OBB 标题栏操作流程

## 一、当前推荐

当前推荐优先使用 ISAT，Labelme 作为备用。

原因：ISAT 对 polygon 标注、规则形状约束、快速检查更友好，适合当前标题栏四点标注。

## 二、安装

推荐先新建环境，避免污染当前项目环境：

```powershell
conda create -n isat_env python=3.10
conda activate isat_env
pip install isat-sam
isat-sam
```

如果你不使用 conda，也可以先只试：

```powershell
pip install isat-sam
isat-sam
```

当前阶段先不启用 SAM 模型，只使用手动 polygon。

## 三、你只需要做什么

先只标注 1 张做兼容性验证，不要一次性标完 16 张。

建议第一张：

```text
sample_009
```

标注规则：

1. 类别名：`title_block`。
2. 使用 Draw Polygon。
3. 只画标题栏主体。
4. 只画 4 个角点。
5. 可以按住 Shift 约束水平/垂直/45 度线。

## 四、保存/导出

优先导出或转换为 Labelme JSON，放到：

```text
local_data/yolo_obb_annotation_pack/smoke/labelme_json/
```

文件名：

```text
sample_009.json
```

如果 ISAT 只能先保存为 ISAT JSON，也可以先保存，我会根据 JSON 结构补转换脚本。

## 五、标注后我来做什么

你完成 1 张后告诉我。我会：

```powershell
python scripts\yolo_obb\convert_labelme_to_yolo_obb.py --allow-missing
python scripts\yolo_obb\validate_obb_dataset.py
python scripts\yolo_obb\visualize_obb_labels.py
```

然后检查 overlay。确认链路没问题后，再标注剩余 15 张。

