# Subjective Evaluation Plan

## 1. 评价目的

本轮主观评价用于回答以下问题：

1. 转换后音频是否自然。
2. 转换后音频是否与提示词目标相匹配。
3. 转换前后风格变化是否足够明显。
4. 听评者是否更偏好转换后音频。

## 2. 评价方式

本项目参考 MOS / SMOS 与 MUSHRA 的思想，但采用轻量化小规模听评，不把当前方案表述成严格完整的 MUSHRA 实验。

推荐流程：

1. 听评者看到原始音频 A、转换后音频 B 和提示词。
2. 听评者先试听 A，再试听 B。
3. 听评者分别给出若干 1-5 分评价，并填写偏好。
4. 多名听评者独立完成问卷，避免互相讨论后统一意见。

## 3. 评分项

每条样本记录以下字段：

- `naturalness_score`：自然度，`1-5`
- `prompt_match_score`：提示词匹配度，`1-5`
- `style_change_score`：风格变化明显度，`1-5`
- `audio_quality_score`：音质可接受度，`1-5`
- `preference`：`before / after / no_difference`
- `comments`：主观意见

建议分值解释：

- `1`：明显较差 / 基本不符合
- `2`：较差 / 偏差较大
- `3`：一般 / 有一定体现
- `4`：较好 / 基本符合
- `5`：很好 / 表现明显

## 4. 参与人数建议

- 最小：`10` 人
- 较好：`15-20` 人
- 当前建议口径：计划采集 `10-15` 名听评者

## 5. 样本设计建议

建议至少准备 `3-5` 个 case：

1. `final_primary` 默认演示 case
2. `final_male_powerful` 厚重男声 case
3. fallback 场景 case
4. 如有稳定可复查样本，可补充 `final_male_youth` 内部复核 case

说明：

- `final_female_soft`、`final_female_clear` 当前未配置真实模型，不参与正式音频质量评分。
- 未配置女声 prompt 的失败或禁用场景，可以在论文中作为系统鲁棒性说明，但不应与成功转换样本混入同一听感评分表。

## 6. 问卷说明

听评者每次需要看到：

- 原始音频 A
- 转换后音频 B
- 提示词

然后完成：

- 自然度评分
- 提示词匹配度评分
- 风格变化明显度评分
- 音质可接受度评分
- A/B 偏好选择
- 主观备注

## 7. 数据文件

模板文件：

- `evaluation/subjective_template.csv`

真实数据文件约定：

- `evaluation/subjective_scores.csv`

聚合脚本：

- `python scripts/aggregate_subjective_scores.py`

## 8. 当前边界

- 当前仓库中没有真实问卷 CSV 或真实听评分数。
- 因此当前不能写平均分、标准差或偏好比例结论。
- 当前只能给出模板、采集方案和统计方法。
- 若展示表格样例，只能明确标注为“示例格式”，不能伪装成正式实验结果。
