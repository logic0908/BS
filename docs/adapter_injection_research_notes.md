# Adapter Injection Research Notes

生成日期：2026-05-06

## 当前项目边界

当前项目已经有：

- `TextStyleEncoder`：把自然语言 prompt 编码为固定维度 embedding。
- `TextStyleAdapter`：用训练型 MLP / rule-based fallback 将 prompt 语义映射为 `model_preset_id`、`transpose`、`style_strength`、`brightness`、`power`、`breathiness`、`youthfulness` 等参数级控制。
- 在线链路：`prompt -> SentenceTransformer -> TextStyleAdapter -> style_library/preset/转换参数 -> So-VITS-SVC wrapper`。

当前项目尚未完成：

- Adapter 输出 Bias/Scale。
- Bias/Scale 注入 So-VITS-SVC prior encoder、flow 或 generator 中间层。
- 冻结 So-VITS-SVC 大部分权重、只训练网络内部 Adapter 的端到端训练流程。

因此，论文和答辩中应说“当前是参数级 TextStyleAdapter 原型；Bias/Scale 中间层注入是后续研究项”，不能声称已经完成网络内部条件调制。

## 调研依据

- FiLM（Feature-wise Linear Modulation）提出用条件信号生成逐特征 affine 变换，即类似 `y = gamma(z) * x + beta(z)` 的调制方式，适合作为“文本向量 -> Bias/Scale”的理论依据。
- Temporal FiLM 将 feature-wise modulation 扩展到序列/卷积场景，说明调制并不限于视觉模型。
- VITS 架构本身包含 prior encoder、flow、posterior encoder、decoder/generator、speaker embedding 等模块；So-VITS-SVC 以 SoftVC 内容编码器特征和 F0 替代原 TTS 文本输入，仍保留 VITS/flow/generator 类结构。
- So-VITS-SVC 4.1 配置里常见 `gin_channels`、`ssl_dim`、`speech_encoder`、`n_flow_layer`、`use_transformer_flow`、`speaker_embedding` 等字段，说明 speaker/style 条件通道已经是可扩展的天然切入点。

## 可选注入位置

| 位置 | 可行性 | 风险 | 建议 |
| --- | --- | --- | --- |
| speaker/style embedding 融合层 | 高 | 低 | 最低风险入口。把文本风格向量投影到与 speaker embedding 兼容的条件向量，先做加法/门控融合。 |
| prior encoder | 中 | 中 | 对内容表征和音高/风格映射影响明显，但可能破坏内容保持。适合第二阶段实验。 |
| flow | 中 | 中高 | 可改变隐空间分布，风格控制潜力强，但训练稳定性和调试难度更高。 |
| generator / decoder | 中 | 高 | 直接影响音色和质感，但最容易引入伪影、噪声和音质退化。建议最后尝试。 |

## 最低风险实现路线

1. 新建实验分支，不改默认 SVC 主链路。
2. 在 So-VITS-SVC 模型加载后增加一个小型 `TextFiLMAdapter`，输入 prompt embedding，输出 `gamma/beta`。
3. 先只在 speaker/style 条件融合处做 `condition = condition + adapter_projection(prompt_embedding)` 或门控融合，不碰 generator。
4. 冻结 So-VITS-SVC 大部分权重，只训练 Adapter 和必要的投影层。
5. 使用 `data/style_adapter_pairs/` 扩充到至少数百条 `{干声音频, 风格描述文本, 目标风格标签/目标模型}` 配对样本。
6. 先做离线训练和离线推理脚本，不接默认 API。
7. smoke test 通过后再增加一个显式 `SVC_ADAPTER_INJECTION_EXPERIMENT=true` 开关。
8. 加入消融：无 Adapter、参数级 Adapter、speaker 融合 Adapter、prior/flow Adapter。

## 不在本轮执行的事项

- 不直接修改 `so-vits-svc` 网络结构。
- 不重训 So-VITS-SVC 主模型。
- 不把参数级 Adapter 文案改成已经完成 Bias/Scale 注入。
- 不把 experimental Adapter 注入接入默认 `/api/v1/convert`。

## 未来验收标准

- 训练日志能证明 So-VITS-SVC 主干大部分权重被冻结。
- Adapter checkpoint 独立保存，并能在无 Adapter / 有 Adapter 条件下复现差异。
- `sovits_command.txt` 或等价 debug 文件记录 Adapter 注入开关、checkpoint、注入位置、prompt embedding 摘要。
- 主观评价表至少包含风格符合度、自然度、歌词可懂度、原旋律保持和总体满意度。
