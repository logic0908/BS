# Prompt Case Study

## 目的

本文件用于说明为什么当前评估 prompt 采用多维方向描述，而不是直接宣称“任意自然语言都可稳定强控制歌声风格”。

## Prompt 设计原则

当前 prompt 以风格方向为主，而不是以具体歌手复刻为主，重点覆盖：

- 明亮度 `brightness`
- 能量感 `energy`
- 音高走向 `pitch_height`
- 柔和度 `softness`
- 厚度 `thickness`
- 情绪强度 `emotion_intensity`

这样做的原因是：

- 当前 internal FiLM 已证明能注入文本条件
- 但还没有足够数据证明复杂自然语言语义能够稳定映射为强感知风格
- 因此更适合先做“方向性验证”和“小样本听评”

## 当前 prompt matrix

标准配置见：`config/eval_prompts.json`

关键边界：

- `final_primary` 记为 `available`
- `final_male_youth` 记为 `available_but_license_unknown`
- `final_male_powerful` 记为 `available_but_specialized`
- `final_female_soft / final_female_clear` 当前记为 `unavailable`

## 如何用于后续批量评估

1. 用同一个输入音频逐个跑 prompt
2. 保持同一个 `requested_model_preset_id`
3. 先做 `none vs internal_film`
4. 再做 `film_strength` 多档对照
5. 最后把主观听评和客观指标一起解释

## 论文可用口径

可以写：

> 当前 prompt 设计以可测风格方向为主，包括 brightness、energy、pitch height、softness、thickness 与 emotion intensity 等维度，用于验证文本条件注入是否会在输出音频中带来可观测变化趋势。

不应写：

> 系统已经能够稳定、显著地复刻任意自然语言描述的歌声风格。
