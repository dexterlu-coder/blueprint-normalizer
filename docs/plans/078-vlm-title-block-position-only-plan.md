# VLM 只判断标题栏当前位置计划

日期：2026-07-02

## 背景

用户确认旋转判断应拆成两个稳定步骤：

1. 判断标题栏当前位置。
2. 根据机械制图规则推断图纸被旋转的角度。

机械制图中标题栏在正确阅读方向下位于图纸右下角。因此只要得到当前屏幕坐标下标题栏位置，旋转角度就应由程序按规则确定，不应交给 VLM 自由解释。

## 目标

- 修改阿里云 VLM prompt，明确只要求模型判断当前屏幕坐标下标题栏位置和图号。
- 不再要求模型输出 `current_clockwise_degrees` 和 `correction_clockwise_degrees`。
- 在本地程序中新增标题栏位置到角度的确定性映射。
- 输出中保留：
  - `title_block_position`
  - `derived_current_clockwise_degrees`
  - `derived_correction_clockwise_degrees`
- 双模型对比只比较模型直接判断的标题栏位置和图号；角度冲突只由派生位置冲突自然导致。
- 在受控多位置样本上重新 dry-run 和联网验证。

## 位置到角度规则

| 标题栏当前位置 | 当前图纸已顺时针旋转角度 | 建议顺时针校正角度 |
| --- | --- | --- |
| `bottom_right` / `bottom` | 0 | 0 |
| `bottom_left` / `left` | 90 | 270 |
| `top_left` / `top` | 180 | 180 |
| `top_right` / `right` | 270 | 90 |
| `unknown` | 空 | 空 |

## 非目标

- 不发布新的固定审核入口。
- 不生成正式旋正 PDF。
- 不重命名 PDF。
- 不把 `local_data/` 输出纳入 Git。
- 不删除历史烟测结果。

## 验证

1. 编译 VLM 请求包和烟测脚本。
2. dry-run 生成请求，确认 prompt 不再要求模型输出角度。
3. 使用 `local_data/aliyun_vlm_position_probe/position_probe_images/` 复测 4 张受控图片、2 个模型。
4. 检查 schema、派生角度和双模型对比结果。
5. 记录结果到 RPD 和 TODO。

## 回滚准备

实现前提交本计划、RPD 和 TODO，作为“标题栏位置优先”重构前回滚点。
