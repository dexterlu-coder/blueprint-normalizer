# 本地标题栏检测模型与本地 VLM 调研

日期：2026-06-25

## 一、问题

用户倾向使用专用标题栏检测模型检查标题栏，并关心：

- YOLO / OBB 是否可以运行在本地小模型上。
- 若公司不允许使用在线 VLM，是否有可本地运行的开源图像识别小模型。
- 这些本地小模型的配置压力如何，应该按什么顺序测试。
- 本地小模型在本项目中的合理位置。

## 二、结论

1. YOLO / OBB 可以作为本地小模型运行。
2. OBB 更适合“标题栏框检测”，不是直接替代旋转角度规则。
3. 对机械图纸方向识别来说，专用标题栏检测器比 OCR 更接近“第三类方向证据”。
4. 本地开源 VLM 可作为隐私友好的兜底分支，但不应默认替代 OpenCV 或标题栏检测器。
5. 当进入 VLM 兜底阶段时，第一轮应优先使用云端模型，先验证收益，再承担本地部署复杂度。
6. 本地 VLM 测试应从配置压力最小的模型开始，逐级寻找可用性和成本的最优点。

## 三、YOLO / OBB 是否可本地运行

Ultralytics OBB 文档显示，OBB 检测输出旋转框、类别和置信度；模型可以训练、预测、验证和导出。其 OBB 模型包含 nano/small 等小尺寸变体，并支持导出到 ONNX、OpenVINO、TensorRT、CoreML、TFLite、NCNN 等格式。

对本项目的意义：

- 可以训练一个本地 `title_block` 检测器。
- 输出标题栏旋转框后，再由框中心和页面边缘位置映射到 `bottom/left/top/right`。
- 不需要上传图纸到外部服务。
- 小模型可先用 YOLO nano/small 级别验证。

注意：

- OBB 旋转框角度本身不等于图纸旋转角度。
- 标题栏检测器需要标注数据。
- 现有 83 张样本可作为起点，但对训练深度模型偏少，更适合先做验证或微调实验。

## 四、本地模型配置压力

配置压力不是单看参数量，还受输入图片分辨率、推理精度、量化方式、batch size、CUDA/驱动和推理框架影响。下表用于决定测试顺序，不作为最终硬件承诺。

| 顺序 | 模型/路线 | 大致规模 | 配置压力 | 建议用途 | 测试判断 |
| --- | --- | --- | --- | --- | --- |
| 1 | YOLO OBB nano/small | 百万到千万级参数 | 低 | 本地 `title_block` 检测 | 优先做，最贴合标题栏定位 |
| 2 | SmolVLM-500M-Instruct | 500M 级 | 低到中 | 最轻量本地 VLM 验证 | 若结构化输出不稳，直接淘汰 |
| 3 | Florence-2-base | 约 0.2B 级 | 低到中 | 区域/OCR/视觉基础任务 | 作为工具模型，不当聊天式 VLM |
| 4 | InternVL2.5-1B | 1B 级 | 中 | 本地 VLM 兜底候选 | 若 1B 已足够，就不继续上大模型 |
| 5 | Qwen2.5-VL-3B-Instruct | 3B 级 | 中到高 | 中文能力更强的本地 VLM | 在 1B 不够时测试 |
| 6 | MiniCPM-V-2.6 | 8B 级附近 | 高 | 私有化 VLM 兜底候选 | 放到后期，不作为第一轮 |

当前结论：

- 标题栏检测优先测试 YOLO/OBB，因为它更小、更快，也更贴近任务。
- 本地 VLM 不是第一轮测试对象；它的价值应先由云端 VLM 快速验证。
- 本地 VLM 若要测试，应从 SmolVLM/Florence/InternVL 这类低压力候选开始，不应一上来就部署 3B/8B。

## 五、本地开源 VLM 候选

| 模型 | 特点 | 适合本项目的用途 | 风险 |
| --- | --- | --- | --- |
| Qwen2.5-VL-3B-Instruct | 小尺寸视觉语言模型，可本地推理 | 兜底判断标题栏位置、读取局部文字 | 对机械图纸稳定性需实测 |
| SmolVLM-500M-Instruct | 更小，适合轻量本地实验 | 快速验证本地 VLM 作为兜底是否有价值 | 能力可能不足以理解复杂图纸 |
| Florence-2-base | 本地视觉基础模型，支持 caption、OCR、区域相关任务 | 可作为非对话式视觉工具，辅助区域理解 | 不是专门的聊天式 VLM |
| MiniCPM-V 2.6 | 本地多模态模型，支持 Transformers、vLLM、SGLang、llama.cpp/Ollama 等部署路径 | 兜底视觉问答，适合私有化环境试验 | 模型体积和部署复杂度高于小 detector |
| InternVL2.5-1B | 1B 级开源多模态模型 | 本地 VLM 兜底候选，适合先做小样本验证 | 小参数版本对复杂工程图的稳定性需实测 |

部署判断：

- 这些 VLM 可以在本地机器或内网服务器运行，前提是先下载模型权重并满足许可条件。
- “本地可运行”不等于“适合主流程”。VLM 输出天然更偏语义解释，结构化稳定性需要用项目样本验证。
- 若公司禁止在线 VLM，应优先保留 OpenCV + 本地标题栏 detector；本地 VLM 放在疑难样本兜底层。

## 六、推荐架构修正

不建议把 OCR、YOLO/OBB、VLM 当成同权投票者。

更合理的证据层级：

1. OpenCV 几何主流程：当前已在 83 张联合集上达到 83/83。
2. 专用标题栏检测器：本地 detector，作为最接近方向判断的第三类证据。
3. OCR：文字证据，用来确认标题栏真实性，不主导方向。
4. 本地或在线 VLM：疑难样本兜底，用来解释非典型版式。

建议流程：

```text
OpenCV
  -> 高可信：接受
  -> 低可信/冲突：
       -> 本地 YOLO/OBB 标题栏检测
       -> OCR 辅助确认文字/标题栏真实性
       -> 本地/云端 VLM 兜底解释疑难样本
       -> 证据融合，不做简单同权投票
```

## 七、下一步建议

主线先做本地 YOLO/OBB 标题栏检测小实验。云端 VLM 可以降低 VLM 价值验证的复杂度，但不应排在标题栏 detector 之前。

下一步最小验证：

1. 建一个标题栏检测标注规范。
2. 选 83 张样本中的标题栏，标注 `title_block` 框。
3. 先用 YOLO OBB nano/small 做小实验。
4. detector 可用后，加入 OCR 辅助确认文字/标题栏真实性。
5. 若 OpenCV、YOLO/OBB、OCR 仍冲突，再选 4-8 张疑难样本跑云端 VLM 兜底小实验，要求输出固定 JSON。
6. 若云端 VLM 证明有增益，再按配置压力测试本地模型：SmolVLM/Florence -> InternVL2.5-1B -> Qwen2.5-VL-3B -> MiniCPM-V-2.6。
7. 比较：
   - detector 是否能稳定找到标题栏框。
   - 云端 VLM 是否能稳定输出结构化位置。
   - 本地小模型是否能接近云端 VLM 的效果。
   - OCR 是否只适合作为关键词证据。

## 八、参考

- Ultralytics OBB 文档：https://docs.ultralytics.com/tasks/obb/
- Ultralytics Export 文档：https://docs.ultralytics.com/modes/export/
- Qwen2.5-VL-3B-Instruct：https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct
- SmolVLM-500M-Instruct：https://huggingface.co/HuggingFaceTB/SmolVLM-500M-Instruct
- Florence-2-base：https://huggingface.co/microsoft/Florence-2-base
- MiniCPM-V-2_6：https://huggingface.co/openbmb/MiniCPM-V-2_6
- InternVL2.5-1B：https://huggingface.co/OpenGVLab/InternVL2_5-1B
