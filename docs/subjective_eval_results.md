# Subjective Evaluation Results

本表根据 [docs/subjective_eval_form.md](./subjective_eval_form.md) 整理，用于正式答辩前后的主观试听记录。

当前固定说明：

- 默认主链路：So-VITS-SVC
- 当前默认模型：`final_primary / lain`
- 异步执行：`Celery / Redis`
- TextStyleAdapter：训练型参数级控制，非 So-VITS-SVC 网络内部 Bias/Scale 注入

## 待评价样本清单

- `b7c03828-e10d-4552-ac51-63f9dececfba`：清亮、少年感、男声
- `1a9d1b8b-a090-448e-b6e8-1252dc2ff5d3`：温柔、气声、抒情女声
- `4e703d1d-4af6-475b-9c29-a7a8fd0f8b3b`：低沉、成熟、厚重男声
- `94a8b6ee-6f68-4032-bf78-992f8cb3cfbf`：`final_primary+trained_adapter`
- `1768b6ce-6f3c-4673-874c-d986b3ac4579`：`final_male_youth+trained_adapter`
- `d4cddc4b-9945-46b5-8347-28bbc67bb84d`：`final_male_youth+no_adapter`
- `19331294-d7ec-4b65-87f7-818ae7b0e0c6`：`final_male_youth+allow_preset_fallback=false`

## 待评价样本明细表

| task_id | case | prompt | preset | speaker | adapter_mode | output_path | audio_quality_summary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `94a8b6ee-6f68-4032-bf78-992f8cb3cfbf` | `final_primary+trained_adapter` | 少年感、男声、清亮 | `final_primary` | `lain` | `trained_adapter -> trained` | `/home/featurize/work/BS/runtime/debug/94a8b6ee-6f68-4032-bf78-992f8cb3cfbf/converted.wav` | `{"duration_consistency":1.0,"low_energy_ratio":0.277992,"possible_dropouts":false}` |
| `1768b6ce-6f3c-4673-874c-d986b3ac4579` | `final_male_youth+trained_adapter` | 少年感、男声、清亮 | `final_male_youth` | `Nova_Adult` | `trained_adapter -> trained` | `/home/featurize/work/BS/runtime/debug/1768b6ce-6f3c-4673-874c-d986b3ac4579/converted.wav` | `{"duration_consistency":1.0,"low_energy_ratio":0.142857,"possible_dropouts":false}` |
| `d4cddc4b-9945-46b5-8347-28bbc67bb84d` | `final_male_youth+no_adapter` | 少年感、男声、清亮 | `final_male_youth` | `Nova_Adult` | `no_adapter -> no_adapter` | `/home/featurize/work/BS/runtime/debug/d4cddc4b-9945-46b5-8347-28bbc67bb84d/converted.wav` | `{"duration_consistency":1.0,"low_energy_ratio":0.144788,"possible_dropouts":false}` |
| `19331294-d7ec-4b65-87f7-818ae7b0e0c6` | `final_male_youth+allow_preset_fallback=false` | 少年感、男声、清亮 | `final_male_youth` | `Nova_Adult` | `trained_adapter -> trained` | `/home/featurize/work/BS/runtime/debug/19331294-d7ec-4b65-87f7-818ae7b0e0c6/converted.wav` | `{"duration_consistency":1.0,"low_energy_ratio":0.142857,"possible_dropouts":false}` |

## 评分填写说明

- 每个维度使用 `1-5` 分：`1` 表示明显不符合或质量较差，`5` 表示表现优秀。
- 若尚未完成人工听评，请保持评分单元格为空，不要伪造分数。
- 如果当前样本命中了未配置的专用目标模型，请在备注中说明“待补模型后复评”。

## Evaluation Table

| task_id | prompt | inference_mode | model_preset_id | speaker | 风格符合度 1-5 | 自然度 1-5 | 歌词可懂度 1-5 | 原旋律保持 1-5 | 总体满意度 1-5 | 备注 |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `b7c03828-e10d-4552-ac51-63f9dececfba` | 清亮、少年感、男声 | `real` | `final_primary` | `lain` |  |  |  |  |  | 待人工评价 |
| `1a9d1b8b-a090-448e-b6e8-1252dc2ff5d3` | 温柔、气声、抒情女声 | `real` | `final_primary` | `lain` |  |  |  |  |  | 待人工评价 |
| `4e703d1d-4af6-475b-9c29-a7a8fd0f8b3b` | 低沉、成熟、厚重男声 | `real` | `final_primary` | `lain` |  |  |  |  |  | 待人工评价 |
| `94a8b6ee-6f68-4032-bf78-992f8cb3cfbf` | 少年感、男声、清亮 | `real` | `final_primary` | `lain` |  |  |  |  |  | 待人工评价 |
| `1768b6ce-6f3c-4673-874c-d986b3ac4579` | 少年感、男声、清亮 | `real` | `final_male_youth` | `Nova_Adult` |  |  |  |  |  | 待人工评价 |
| `d4cddc4b-9945-46b5-8347-28bbc67bb84d` | 少年感、男声、清亮 | `real` | `final_male_youth` | `Nova_Adult` |  |  |  |  |  | 待人工评价 |
| `19331294-d7ec-4b65-87f7-818ae7b0e0c6` | 少年感、男声、清亮 | `real` | `final_male_youth` | `Nova_Adult` |  |  |  |  |  | 待人工评价 |

## Fill-in Notes

- 若尚未完成真实人工听评，请保持评分列为空，并在备注中保留“待人工评价”。
- `scripts/summarize_subjective_eval.py` 会读取本文件；当评分仍为空时，只输出待评价提示，不会报错。

## 空白评分模板

| 评价维度 | 分值区间 | 当前填写 |
| --- | --- | --- |
| 风格符合度 | 1-5 |  |
| 自然度 | 1-5 |  |
| 歌词可懂度 | 1-5 |  |
| 原旋律保持 | 1-5 |  |
| 总体满意度 | 1-5 |  |
