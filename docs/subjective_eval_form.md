# Subjective Evaluation Form

用于 `baseline none` vs `internal_film strength=0.10` 的人工听评记录。

## 评分维度

每个条件都按 `1-5` 分填写：

1. 音质自然度
2. 人声清晰度
3. 原始歌词/旋律保持度
4. 与文本提示词匹配度
5. 风格变化明显程度
6. 综合偏好

分值建议：

- `1` 很差
- `2` 较差
- `3` 一般
- `4` 较好
- `5` 很好

## 单条件评分表

| listener_id | sample_id | prompt | condition | naturalness_score | clarity_score | content_preservation_score | prompt_match_score | style_change_score | overall_preference | comments |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
|  |  |  | baseline none |  |  |  |  |  |  |  |
|  |  |  | internal_film strength=0.10 |  |  |  |  |  |  |  |

## A/B 配对问题

| listener_id | sample_id | prompt | 哪个版本更符合提示词 | 哪个版本音质更自然 | 是否能听出风格差异 | 是否存在爆音/机械音/失真 | comments |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |

## 当前填写原则

- 没有真实人工听评时，保持空白，不要伪造分数
- 若差异不明显，可以直接在 `comments` 中写“风格差异不明显”
- 若出现爆音、机械音、失真，优先记录在 `comments`
