# Training Experiment Report

## 1. 1000 条阶段训练结论

- 数据规模：`readable_audio_count=1000`，`data/style_adapter_pairs/metadata.small.jsonl=1000` 行。
- 数据划分：`train/val/test=800/100/100`。
- 训练命令：
  - `python scripts/train_text_style_adapter.py --metadata data/style_adapter_pairs/metadata.small.jsonl --output runtime/style_adapter/text_style_adapter_1000.pt --epochs 15 --batch-size 16 --style-dim 256 --device cuda --max-items 1000 --report-output runtime/eval_reports/text_style_adapter_1000_train_report.json`
- 训练设备：`cuda`（`NVIDIA RTX A4000`）。
- 关键指标：
  - `best_epoch=15`
  - `best_val_loss=4.209e-05`
  - `test_loss=1.559e-05`
  - `final_train_loss=2.124e-05`

## 2. Checkpoint 可加载性验证

- 主 checkpoint：`runtime/style_adapter/text_style_adapter_1000.pt`
- 通过 `TextStyleAdapter` 类真实调用验证：
  - `adapter_mode=trained`
  - `adapter_fallback_reason=None`
  - `adapter_checkpoint_path=/home/featurize/work/BS/runtime/style_adapter/text_style_adapter_1000.pt`
- 通过 `torch.load` 验证 checkpoint 字段完整，包含：
  - `model_state_dict`
  - `sample_embeddings`
  - `train_size / val_size / test_size`
  - `best_epoch / best_val_loss / test_loss`
  - `device / gpu_name`

## 3. internal_film Smoke 结果

- 脚本：`bash scripts/smoke_internal_film_conversion.sh --input <input.wav> --preset final_primary`
- 最新 smoke 摘要：
  - `condition_mode=internal_film`
  - `executed_internal_film=true`
  - `text_style_adapter_loaded=true`
  - `adapter_checkpoint=runtime/style_adapter/text_style_adapter_1000.pt`
- 结论：internal FiLM 实际执行，且任务 metadata 已显式记录 1000 adapter 的加载路径。

## 4. 消融实验与客观指标

### 4.1 film_strength 消融（0 / 0.05 / 0.10 / 0.15）

- 报告：`runtime/eval_reports/film_strength_ablation_1000.json` 与 `.md`
- 现象：
  - `strength=0` 时 `condition_mode=none`，`executed_internal_film=false`
  - `internal_film_0.05 / 0.10 / 0.15` 均满足：
    `executed_internal_film=true`、`text_style_adapter_loaded=true`、`adapter_mode=trained`、`adapter_type=trained_mlp`、`adapter_checkpoint=runtime/style_adapter/text_style_adapter_1000.pt`
  - 各组输出音频可读（`44100 Hz`，约 `12.007s`，无 `NaN/Inf`）

### 4.2 condition_mode 消融（none / external_preset / internal_film）

- 报告：`runtime/eval_reports/condition_mode_ablation_1000.json` 与 `.md`
- 现象：
  - `none`：`executed_internal_film=false`
  - `external_preset`：`executed_internal_film=false`
  - `internal_film`：`executed_internal_film=true`、`text_style_adapter_loaded=true`、`adapter_mode=trained`、`adapter_type=trained_mlp`、`adapter_checkpoint=runtime/style_adapter/text_style_adapter_1000.pt`
  - 本次固定 `final_primary`，`requested_model_preset_id` 与 `effective_model_preset_id` 一致，`preset_fallback_used=false`

### 4.3 客观指标统计

- 命令：
  - `python scripts/evaluate_audio_quality.py --cases runtime/eval_reports/objective_cases_1000.json --output runtime/eval_reports/objective_metrics_1000.json`
- 产物：
  - `runtime/eval_reports/objective_metrics_1000.json`
  - `runtime/eval_reports/objective_metrics_1000.csv`
  - `runtime/eval_reports/objective_metrics_1000.md`
- 样例趋势（同一输入）：
  - `speaker_embedding_similarity`：`baseline_none=0.905602`，`internal_film=0.906717`
  - `brightness_delta`：`baseline_none=23.530762`，`internal_film=26.608887`
- 边界：客观指标仅是辅助趋势证据，不等价于主观听感显著性结论。

## 5. 回归测试

- 命令：`PYTHONPATH=$(pwd)/backend:$PYTHONPATH pytest backend/tests -q`
- 结果：`127 passed, 20 warnings`
