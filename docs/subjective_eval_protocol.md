# Subjective Evaluation Protocol

## 目的

本轮主观听评用于回答两个更谨慎的问题：

1. `internal_film` 是否在部分样例上表现出可感知的风格差异
2. 这种差异是否能在不明显牺牲自然度与内容保持的情况下被听到

本协议不预设结论，也不允许在没有人工数据时声称 `internal_film` 显著优于 baseline `none`。

## 对比组

- `baseline none`
- `internal_film strength=0.10`

必要时可在后续扩展：

- `internal_film strength=0.05`
- `internal_film strength=0.15`
- `external_preset`

## 评分维度

每个条件独立打分，范围 `1-5`：

1. 音质自然度
2. 人声清晰度
3. 原始歌词/旋律保持度
4. 与文本提示词匹配度
5. 风格变化明显程度
6. 综合偏好

## 配对问题

每个样例还要回答：

- 哪个版本更符合提示词
- 哪个版本音质更自然
- 是否能听出风格差异
- 是否存在爆音、机械音、失真

## 样例选择建议

- 同一个输入音频
- 同一个 prompt
- 同一个 `requested_model_preset_id`
- 相同的基础参数，只有 `condition_mode` / `film_strength` 变化

## 结果解释原则

- 若评分为空：明确写“待人工填写”
- 若样本量小：只能写“小样本听评趋势”
- 若不同听评人分歧大：不能写“显著优于”
- 若有风格变化但自然度下降：要如实记录 trade-off
