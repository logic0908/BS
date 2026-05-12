# Effect Ablation Report

## 目标

当前消融实验不用于夸大“强文本风格控制已完成”，而是用于补齐三类证据：

1. `film_strength` 多档配置是否已经形成可复现的实验框架
2. `none / external_preset / internal_film` 是否已经在工程上分离记录
3. 实验记录是否已经能导出为论文表格和答辩展示材料

## A. Film Strength Ablation

推荐实验组：

1. `none` 或 `internal_film strength=0`
2. `internal_film strength=0.05`
3. `internal_film strength=0.10`
4. `internal_film strength=0.15`

脚本：

```bash
python scripts/run_film_strength_ablation.py \
  --dry-run \
  --input /path/to/vocals.wav \
  --prompt "温柔、明亮、流行感更强的女声风格" \
  --strengths 0 0.05 0.10 0.15 \
  --preset final_primary
```

输出：

- `runtime/eval_reports/film_strength_ablation.json`
- `runtime/eval_reports/film_strength_ablation.md`

当前口径：

- 已补齐多档实验配置、字段记录和 dry-run 报告
- 若没有真实批量推理样本，只能说“实验框架已补齐”

## B. Condition Mode Ablation

实验组：

1. `none`
2. `external_preset`
3. `internal_film`
4. `external_preset + internal_film` 可选

脚本：

```bash
python scripts/run_condition_mode_ablation.py \
  --dry-run \
  --input /path/to/vocals.wav \
  --prompt "温柔、明亮、流行感更强的女声风格" \
  --preset final_primary
```

输出：

- `runtime/eval_reports/condition_mode_ablation.json`
- `runtime/eval_reports/condition_mode_ablation.md`

当前口径：

- `external_preset` 若只是逻辑层外部预设、未绑定真实独立专用模型，不能伪装成“真实专模效果”
- 显式 `final_primary` 手动 override 时，需要记录 `requested_model_preset_id / effective_model_preset_id / preset_fallback_used`

## C. 当前已成立与未成立结论

可以成立：

- internal FiLM 工程链路已打通并通过真实 smoke
- ablation 脚本与导出报告框架已补齐

还不能成立：

- `internal_film` 一定显著优于 `baseline none`
- 所有 prompt 都能稳定产生明显风格差异
- `external_preset` 已经等价于真实专用模型效果
