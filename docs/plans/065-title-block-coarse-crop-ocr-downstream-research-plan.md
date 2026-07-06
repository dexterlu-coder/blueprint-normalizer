# 标题栏粗 crop 对图号 OCR 影响调研计划

## 背景

用户已完成修复后标题栏 crop 复核表。63 条样本均判断为 `正确`，说明当前修复策略在“完整覆盖标题栏”上有效；但其中 31 条标注 `范围太大`，备注集中为“左半边不是标题栏，而是图纸”。

这暴露出新的设计矛盾：

- 粗 crop 简单、稳定、便于人工确认完整性。
- 粗 crop 会把图纸下部主体、尺寸标注、技术要求或印章一起送入 OCR，可能增加图号识别和候选排序复杂性。
- 若直接缩小 crop，又可能重新引入右侧图号栏截断或标题栏漏裁风险。

## 目标

1. 调研文档 OCR、表格识别、版面分析和工程图纸标题栏识别中处理“粗定位后细识别”的成熟方案。
2. 先归档当前已填写的修复后 crop 复核入口，生成低噪声人工摘要和机器摘要。
3. 判断“完整标题栏粗 crop”是否应该继续作为人工审核对象。
4. 判断图号 OCR 是否应使用另一个更小的二级 ROI，而不是直接使用人工审核 crop。
5. 给出本项目下一步建议，包括是否需要新增“完整性 crop”和“OCR 用细 crop”双轨产物。
6. 沉淀可追溯调研文档、样本索引和决策建议。

## 非目标

- 不修改 crop 生成脚本。
- 不生成新的命名审核包。
- 不运行 OCR 图像预处理实验。
- 不生成正式 PDF，不重命名 PDF。

## 调研问题

1. 粗框完整覆盖但包含噪声时，行业通常如何避免 OCR 被噪声干扰？
2. 是否常见先做文档/表格/标题栏粗定位，再做字段级细定位？
3. 对机械图纸标题栏，图号通常应从完整标题栏 crop 中抽取，还是从右侧图号单元格/字段 ROI 中抽取？
4. 表格线、关键词锚点、文本检测和版面模型分别适合承担哪一层任务？
5. 当前 31 条 `范围太大` 是否应视为阻断，还是作为“完整性审核通过、OCR 需二级裁剪”的输入？

## 输出

本轮调研至少输出：

```text
local_data/review_inbox/archive/title_block_crop_recovery_review_*/ 
local_data/title_block_crop_recovery_review/filled_review_summary.json
local_data/title_block_crop_recovery_review/filled_review_summary.csv
local_data/title_block_crop_recovery_review/human_summary.md
references/title-block-coarse-crop-ocr-downstream/README.md
docs/research/2026-06-30-title-block-coarse-crop-ocr-downstream-research.md
docs/decisions/title-block-crop-and-ocr-roi-strategy.md
```

## 验收标准

1. 调研来源优先使用论文、官方文档或高质量开源项目说明。
2. 至少横向比较 5 类方案：
   - 粗定位后字段级细定位。
   - 表格结构识别。
   - OCR 文本检测后过滤。
   - 关键词/字段锚点定位。
   - 多 crop 双轨策略。
3. 明确推荐方案和不推荐方案。
4. 明确当前审核结果如何进入下一步流程。
5. 当前固定审核入口完成归档后重置为无待审核任务。

## 回滚准备

本计划、RPD 和 TODO 提交后作为归档和调研前回滚点。若归档或调研结论不适合当前项目，可回退到该提交，重新从当前审核入口读取用户填写结果，并保留已提交的 crop 修复实现。
