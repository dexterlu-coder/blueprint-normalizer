# OBB 标注工具选择调研索引

本目录记录本地 OBB 标注工具选择的外部参照。

## 样本索引

| 工具 | 类型 | 来源 | 优点 | 不适合当前点 |
| --- | --- | --- | --- | --- |
| ISAT-SAM | 本地桌面 GUI | https://github.com/yatengLG/ISAT_with_segment_anything | 支持手动 polygon、SAM 辅助、Shift 约束规则形状、快速浏览/细节检查，并支持 ISAT/COCO/YOLO/LABELME/VOC 转换 | YOLO 转换不应直接假设为 Ultralytics OBB；安装可能比 Labelme 重 |
| Labelme | 本地桌面 GUI | https://github.com/wkentaro/labelme | Python/Qt 本地工具，支持 polygon/rectangle/circle/line/point，安装和使用轻，适合 16 张冒烟样本 | 不直接导出 Ultralytics OBB，需要项目内转换脚本 |
| CVAT Community | 自托管 Web 平台 | https://github.com/cvat-ai/cvat | 功能强，支持图像/视频/3D 标注、任务管理、导入导出多种格式、团队协作 | Docker 部署较重，不适合当前单人 16 张快速冒烟 |
| Label Studio | Web 标注平台 | https://labelstud.io/ | 可本地部署，适合多类型数据和项目管理 | 对当前 OBB 四点导出链路不如 Labelme 直接，配置复杂度较高 |

## 选择结论

当前推荐调整为：`ISAT 优先，Labelme 备用`。

原因：

1. 当前只需要标注 16 张图，但用户更需要顺手的人工界面。
2. ISAT 支持手动 polygon，并支持 Shift 约束水平、垂直和 45 度方向，更适合标题栏这类规则形状。
3. ISAT 提供预览、快速浏览和细节检查，对人工复核更友好。
4. ISAT 本地运行，不上传图纸。
5. ISAT 可转换到 Labelme，因此可以复用现有 `convert_labelme_to_yolo_obb.py`。
6. 如果 ISAT 安装或导出链路不顺，再回退 Labelme。

## 当前流程

```text
ISAT 画四点 polygon
  -> 导出/转换 Labelme JSON
  -> scripts/yolo_obb/convert_labelme_to_yolo_obb.py 转换为 YOLO OBB txt
  -> scripts/yolo_obb/validate_obb_dataset.py 校验
  -> scripts/yolo_obb/visualize_obb_labels.py 生成 overlay
  -> 人工看 overlay
```

