# OBB 标注工具选择记录

日期：2026-06-25

## 一、需求

用户没有标注工具，需要为 YOLO/OBB 标题栏冒烟实验选择一个本地标注方案。

约束：

- 图纸不能上传。
- 当前只标注 16 张冒烟样本。
- 需要支持旋转框或四点多边形。
- 最终要得到 Ultralytics OBB 标签。
- 用户界面必须减少不必要信息，图像排列要方便查看。

## 二、结论

原推荐使用：

```text
Labelme + 项目内转换脚本
```

不推荐当前直接使用 CVAT，原因是它更适合团队、大批量和长期平台化标注；本项目现在只是 16 张冒烟样本，Docker/Web 平台成本偏高。

## 三、工具对比

| 工具 | 本地运行 | OBB/多边形能力 | 导出到 YOLO OBB | 当前适配度 |
| --- | --- | --- | --- | --- |
| Labelme | 是 | 支持 polygon | 需转换脚本 | 高 |
| CVAT Community | 是，自托管 | 支持多种标注形状 | 支持多种格式，但配置较重 | 中，后期再考虑 |
| Label Studio | 是，自托管 | 可做图像标注 | OBB 链路需额外配置 | 中低 |

## 四、推荐工作流

1. 安装或启动 Labelme。
2. 打开 smoke 样本图片目录。
3. 每张图只画一个 `title_block` 四点 polygon。
4. 保存 Labelme JSON 到 `local_data/yolo_obb_annotation_pack/smoke/labelme_json/`。
5. 运行 `scripts/yolo_obb/convert_labelme_to_yolo_obb.py` 生成 YOLO OBB 标签。
6. 运行 `scripts/yolo_obb/validate_obb_dataset.py` 校验。
7. 运行 `scripts/yolo_obb/visualize_obb_labels.py` 生成 overlay。
8. 人工查看 overlay，确认框住标题栏主体。

## 五、人工界面规则

本次新增 `rules/human-review-interface.md`，作为长期规则：

- 需要用户填写的内容只呈现必要字段。
- 技术字段、路径、调试分数放到机器报告，不放到人工填写表。
- 图像排列必须优先考虑用户查看便利。
- 大图必须避免裁切标题栏。

## 六、参考

- Labelme GitHub：https://github.com/wkentaro/labelme
- CVAT GitHub：https://github.com/cvat-ai/cvat
- Label Studio 文档：https://labelstud.io/

## 七、2026-06-26 补充：ISAT 调研后修正

经补充调研，当前推荐调整为：

```text
ISAT 优先，Labelme 备用
```

原因：

- ISAT 支持手动 polygon。
- ISAT 支持 Shift 约束水平、垂直和 45 度线，适合标题栏这类规则形状。
- ISAT 支持预览、快速浏览和细节检查，人工复核体验更好。
- ISAT 可在本地运行，并支持 ISAT/COCO/YOLO/LABELME/VOC 等格式转换。

保留 Labelme 作为备用，原因是 Labelme 更轻，且现有转换脚本已经可用。

