# 阿里云 VLM 标题栏不同位置复测计划

日期：2026-07-02

## 背景

用户核对首轮双模型烟测后反馈：

- `js2207_page_001` 的图号两个模型都识别正确。
- `js2207_page_001` 的标题栏位置应为 `top_right`。
- 需要再次测试标题栏处于不同位置时，`qwen3-vl-flash` 与 `qwen3-vl-plus` 的差异。
- 用户关注压缩后的图片是否导致小字模糊。

## 本轮判断

首轮烟测已证明阿里云百炼 OpenAI 兼容接口可用，但标题栏位置字段存在模型理解差异。继续只测真实 JS2207 前两页，无法区分差异来自模型能力、prompt 坐标定义，还是样本本身的旋转状态。因此本轮优先构造受控多位置样本。

## 目标

1. 以用户已核对的 `js2207_page_001.png` 为基准。
2. 生成四张受控旋转图：
   - 原图：预期标题栏位置 `top_right`。
   - 顺时针 90 度：预期标题栏位置 `bottom_right`。
   - 顺时针 180 度：预期标题栏位置 `bottom_left`。
   - 顺时针 270 度：预期标题栏位置 `top_left`。
3. 使用更高质量图像参数复测：
   - `--max-image-long-side 3200`
   - `--jpeg-quality 95`
4. 同时调用：
   - `qwen3-vl-flash`
   - `qwen3-vl-plus`
5. 生成双模型位置对比、旋转角度对比和图号对比。
6. 记录压缩图片的必要性、风险和下一步改进建议。

## 非目标

- 不覆盖当前 `local_data/review_inbox/current/`。
- 不发布新的固定审核入口。
- 不生成正式旋正 PDF。
- 不重命名单页 PDF。
- 不修改 JS2207 审核表中的人工反馈。
- 不将 `local_data/` 输出提交到 Git。

## 压缩图片说明

当前脚本上传压缩 JPEG 的原因：

- 阿里云官方限制要求控制图片尺寸和 Base64 请求体大小，Base64 编码后不得超过 `10MB`。
- 机械图纸整页 PNG 直接 Base64 上传容易导致请求体过大、网络慢或超时。
- 小批量烟测先使用整页图，需在可读性、请求稳定性和成本之间取平衡。

压缩的风险：

- 细小图号、浅色标题栏、小字号表格可能被 JPEG 压缩或缩放影响。
- 图号读取比方向判断更敏感。

本轮控制措施：

- 提高 JPEG 质量到 95。
- 将长边上限提高到 3200。
- 后续若图号仍受影响，应采用“两阶段输入”：整页高压缩图用于方向判断，标题栏 crop 或更高质量局部图用于图号读取。

## 输出

本地输出目录：

```text
local_data/aliyun_vlm_position_probe/
```

计划生成：

- `position_probe_images/`
- `position_probe_manifest.csv`
- `position_probe_manifest.json`
- `vlm_raw_responses.jsonl`
- `vlm_decisions.csv`
- `dual_model_comparison.csv`
- `needs_review.csv`
- `vlm_call_summary.json`

## 验证

- 编译新增脚本。
- 生成四张受控位置图片。
- 检查图片文件存在且尺寸合理。
- 联网调用 4 张图片、2 个模型，共 8 次请求。
- 检查 HTTP、JSON 解析和 schema 校验。
- 对比预期标题栏位置、模型输出和图号读取结果。

## 回滚准备

实现前提交本计划、RPD 和 TODO，作为多位置复测实现前的回滚点。
