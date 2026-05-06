# 论文与答辩口径

## 1. 系统实现口径

当前系统实现了基于文本提示词的歌声风格转换演示链路。系统默认采用 So-VITS-SVC 作为真实转换引擎，用户上传干声音频后，后端完成输入音频合法性校验、格式标准化、风格提示词匹配、目标 preset 选择，并调用真实 So-VITS-SVC CUDA 推理生成转换结果。

## 2. 文本提示词控制的准确口径

现阶段文本提示词已经进入两级控制：

- 第一级：`style_library` 做关键词/规则匹配，选出基础 `style preset`
- 第二级：`TextStyleAdapter v1` 将提示词语义映射为 `model_preset_id / transpose / brightness / power / breathiness / youthfulness`

需要准确说明的是：当前 `TextStyleAdapter v1` 仍然是参数级/旁路控制模块，不是完整的 So-VITS-SVC 端到端神经网络条件注入。后续可进一步训练 Adapter，并把 Bias / Scale 注入 So-VITS-SVC 网络中间层，实现更细粒度的连续风格控制。

当前还需要进一步说明：系统虽然已经可以根据 prompt 匹配更接近的 `model_preset_id`，但默认稳定演示模型仍是 `final_primary / lain`。同时，系统已经新增两个通过本地真实 So-VITS-SVC smoke test 的专用男声 preset：`final_male_youth / Nova_Adult` 与 `final_male_powerful / AY`。二者当前均为 `license_unknown`，只能作为内部复核/本地技术演示候选，不应表述成授权边界清晰的公开 demo quality 模型。`final_female_soft / final_female_clear` 仍因为公开演示授权链路不够清晰而保持未配置。系统不会把未配置 preset 伪装成“已经拥有专用模型效果”。

## 3. So-VITS-SVC 技术原理口径

So-VITS-SVC 属于 Singing Voice Conversion，而不是文本到语音合成。该类模型首先从源音频中提取内容特征，再结合 F0、目标说话人或目标歌手模型以及声码器生成转换音频，因此更适合作为“保留原有旋律与内容、改变音色或演唱风格”的系统主链路。

## 4. 当前不足

- 当前 `TextStyleAdapter v1` 已完成小规模提示词-风格配对数据训练，但当前 `56` 条样本仍不足以支撑强泛化结论。
- 当前还没有把 Bias / Scale 注入 So-VITS-SVC 网络中间层。
- 当前 `final_primary / lain` 不是多风格目标模型；虽然 `final_male_youth / Nova_Adult` 与 `final_male_powerful / AY` 已通过本地真实 smoke test，但仍不能据此声称系统已经完成所有风格域覆盖。
- 当前真实多风格 preset 接入仍受大文件下载速度与公开演示授权边界约束，不应把“候选已找到”表述成“专用模型已全部可用”。
- 输入音频质量、F0 提取方式、人声分离质量与转调参数也会显著影响结果。
- 当前主观评价文档已经准备好，但真实人工评分仍待填写，效果归因证据还不完整。

## 5. 推荐答辩表述

- 可以说：本系统默认链路采用 `final_primary/lain` 保证稳定演示，同时新增 `final_male_youth/Nova_Adult` 与 `final_male_powerful/AY` 作为通过本地真实推理验证的专用男声 preset，用于展示系统从单模型演示向多模型风格 preset 扩展的能力。
- 可以说：`final_male_youth` 与 `final_male_powerful` 当前已经通过本地真实 So-VITS-SVC smoke test，但这只证明推理链路可运行，主观效果仍需人工听评，且 license_unknown 不适合公开传播。
- 不能说：所有风格都已真实覆盖。
- 不能说：女声 preset 已接入。
- 不能说：已完成 So-VITS-SVC 网络内部 Bias/Scale 注入。
- 不能说：`license_unknown` 模型的公开商用授权已经完全清晰。

## 6. 后续工作

- 收集提示词-风格配对数据。
- 训练 TextStyleAdapter。
- 将 Adapter 输出的 Bias / Scale 注入 So-VITS-SVC 网络中间层。
- 扩展并 smoke test 多风格模型 preset。
- 增加更丰富的客观与主观评价指标。
