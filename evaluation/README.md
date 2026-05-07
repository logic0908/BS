# Evaluation Assets

本目录用于整理毕业设计中的主客观评价输入、模板和脚本输出。

## 文件说明

- `objective_pairs.json`
  - 客观评价输入对列表。
  - 每条记录描述一组 `input_path` / `output_path` / `prompt_text` / `model_preset_id`。
- `objective_results.json`
  - `python scripts/run_objective_evaluation.py` 自动生成的客观评价结果。
- `subjective_template.csv`
  - 主观听评模板，只提供表头，不包含真实评分。
- `subjective_scores.csv`
  - 若后续完成真实问卷整理，可将听评结果保存为此文件，再运行聚合脚本。
- `subjective_summary.json`
  - `python scripts/aggregate_subjective_scores.py` 在有真实 CSV 时自动生成。

## 运行方式

```bash
python scripts/run_objective_evaluation.py
python scripts/aggregate_subjective_scores.py
```

## 重要边界

- 不要把 `runtime/`、`local_models/`、`so-vits-svc/` 中的大文件产物复制进本目录。
- 若没有真实主观听评数据，只保留模板和统计脚本，不填写平均分。
- 客观指标用于辅助解释转换趋势，不能替代人工听评。
