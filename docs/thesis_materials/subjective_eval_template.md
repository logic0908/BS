# 主观听评模板（论文材料）

- 当前状态：需补充材料（待人工填写）。
- 强制边界：未补充前，不能写“主观评价证明系统效果较好”。
- 强制边界：主观评分和统计结果未补齐前，不得写入效果优劣结论。

## 1. 评价维度

建议每条样例按以下维度打分：

1. 音质自然度（Naturalness）
2. 人声清晰度（Clarity）
3. 内容保持度（Content Preservation）
4. 提示词匹配度（Prompt Match）
5. 风格变化可感知度（Style Change）
6. 综合偏好（Overall Preference）

## 2. 评分范围

- 评分制：`1~5` 分
- 含义建议：
  - `1` 很差
  - `2` 较差
  - `3` 一般
  - `4` 较好
  - `5` 很好

## 3. 样例编号模板

建议样例编号：`S001, S002, S003 ...`

每个样例至少包含：

- `input`
- `baseline_none`
- `internal_film_0.10`

可扩展包含：

- `internal_film_0.05`
- `internal_film_0.15`
- `external_preset`

## 4. 被试人数建议

- 建议不少于 `10` 人（最低可用线）
- 推荐 `15~30` 人（答辩阶段更稳妥）
- 每位被试应覆盖全部样例，或采用均衡分组并在统计中注明。

## 5. 统计方式建议

1. 逐维度计算均值、标准差、样本数。
2. 按条件（baseline/internal_film）计算配对差值（可选配对 t 检验或 Wilcoxon，按课程要求）。
3. 统计“总体偏好票数”与“提示词匹配优选票数”。
4. 标注无效样本规则（如未听完整、空白评分）。

## 6. 记录表模板

| listener_id | sample_id | condition | naturalness | clarity | content_preservation | prompt_match | style_change | overall_preference | comments |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| L01 | S001 | baseline_none |  |  |  |  |  |  |  |
| L01 | S001 | internal_film_0.10 |  |  |  |  |  |  |  |

## 7. 结果声明模板（论文可用）

- 若尚未采集：
  - “主观听评模板与统计流程已准备完成，当前为需补充材料（待人工填写），故本文不对主观优劣做定论。”
- 若已采集：
  - “主观评分结果见附录 X，统计方法与显著性检验过程见附录 Y。”
