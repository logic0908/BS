# Subjective Evaluation Results

当前状态：待人工填写。

## 当前结论边界

- 已补齐听评模板、协议、导出脚本和汇总脚本
- 尚未在本文件中填写真实人工评分
- 因此当前不能声称 `internal_film` 在主观听感上显著优于 `baseline none`

## 样例清单模板

| sample_id | prompt | condition_a | condition_b | notes |
| --- | --- | --- | --- | --- |
| `case_001` | 温柔、明亮、流行感更强的女声风格 | `baseline none` | `internal_film strength=0.10` | 待人工填写 |
| `case_002` | 清亮、少年感、流行男声 | `baseline none` | `internal_film strength=0.10` | 待人工填写 |

## 汇总表模板

| condition | naturalness | clarity | content_preservation | prompt_match | style_change | overall_preference | notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `baseline none` | 待人工填写 | 待人工填写 | 待人工填写 | 待人工填写 | 待人工填写 | 待人工填写 | 待人工填写 |
| `internal_film strength=0.10` | 待人工填写 | 待人工填写 | 待人工填写 | 待人工填写 | 待人工填写 | 待人工填写 | 待人工填写 |

## 说明

- `scripts/export_subjective_eval_pack.py` 会导出样例清单和 CSV 模板
- `scripts/summarize_subjective_eval.py` 可对 CSV/JSON 结果做均值、标准差和样本数汇总
- 在没有人工数据时，`runtime/eval_reports/subjective_eval_summary.json` 和 `.md` 应输出“模板已生成，暂无结论”
