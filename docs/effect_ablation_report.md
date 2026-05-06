# Effect Ablation Report

本报告用于解释当前系统与参考 SVC 示例之间仍存在的效果差距，并给出一个可复现的消融实验入口。`v1.1` 的目标是优先补真实多风格 preset，而不是用 fallback 假装已经拥有专用模型效果。

## 当前差距的主要来源

1. 目标模型域仍有限。
当前默认 `final_primary / lain` 是可运行的演示模型，但不是多风格全覆盖目标模型。当前已经新增 `final_male_powerful / AY` 作为通过真实 smoke test 的专用男声 preset；但很多 prompt 仍可能更贴近 `final_male_youth / final_female_soft / final_female_clear` 等尚未完全落地的专用 preset，因此系统仍不能声称“所有风格都已覆盖”。

2. Adapter 仍是参数级控制。
当前 `TextStyleAdapter` 会把提示词语义映射到 `model_preset_id / transpose / style_strength` 等轻量控制参数。它还不是 So-VITS-SVC 网络内部 Bias/Scale 注入，因此无法像网络级条件控制那样深度改变 timbre/style manifold。

3. F0 与输入质量会显著放大差异。
输入是否纯净干声、F0 提取方法、转调参数、人声分离质量都会影响最终自然度、旋律稳定性和歌词可懂度。当前系统已开始记录 `f0_method / auto_predict_f0 / slice_db / clip_seconds / pad_seconds`，但现阶段除 `transpose` 外，部分参数仍只记录为系统实验参数，尚未直接透传到当前 So-VITS-SVC 4.1 CLI。

4. 真实专用 preset 仍未完全落地。
`final_male_powerful / AY` 已通过本地真实 smoke test，证明系统已经具备至少一个可运行的专用男声 preset；但 `final_male_youth` 仍未完成真实启用验证，`final_female_soft / final_female_clear` 仍因公开演示授权链路不够清晰而保持未配置。因此，这一进展只证明“厚重/有力/成熟男声”方向的目标模型域开始落地，不代表多风格覆盖已经完成。

## 消融实验脚本

```bash
python scripts/run_conversion_ablation.py \
  --input /path/to/dry_vocal.wav \
  --prompt "清亮、少年感、男声" \
  --model-preset-id final_primary \
  --adapter-mode no_adapter \
  --adapter-mode rule_based \
  --adapter-mode trained \
  --f0-method rmvpe \
  --f0-method system_default
```

脚本会记录：

- `task_id`
- `prompt`
- `model_preset_id`
- `adapter_mode`
- `f0_method`
- `auto_predict_f0`
- `duration_consistency`
- `low_energy_ratio`
- `possible_dropouts`
- `output_path`

音频产物仍保留在 `runtime/debug` 或运行目录中，不写入 Git。

## v1.1 当前执行结论

| 项目 | 当前状态 |
| --- | --- |
| 已配置 preset | `final_primary`、`final_male_powerful`、`tech_villager` |
| 已筛到候选但未完成 smoke test | `final_male_youth` |
| 仍未配置 | `final_female_soft`、`final_female_clear` |
| fallback 任务说明 | 只有显式开启 `allow_preset_fallback=true` 才允许回退到 `final_primary/lain`，且结果不能被表述成专用风格真实效果 |
| 真实专用模型推理任务 | 已新增 `final_male_powerful / AY` 作为通过真实 smoke test 的专用男声 preset，但这只证明链路可运行，不代表所有风格覆盖完成 |
| Bias/Scale 注入结论 | 仍不能证明已完成 So-VITS-SVC 网络内部 Bias/Scale 注入 |

## 当前实验结论模板

| 维度 | 当前结论 |
| --- | --- |
| `no_adapter` vs `rule_based_adapter` | 待运行脚本后填写 |
| `rule_based_adapter` vs `trained_adapter` | 待运行脚本后填写 |
| `final_primary` 边界 | 当前可跑通、可演示，但不是全风格覆盖目标模型 |
| `specialized preset` 边界 | 当前已新增 `final_male_powerful / AY` 作为通过本地真实 smoke test 的专用男声 preset，但女声、少年感等方向仍需后续模型与人工听评 |
| `f0_method` 影响 | 待结合运行环境与主观试听填写 |
| 主要改进方向 | 更匹配的目标模型域 + 更稳定的 F0 + 更纯净的输入音频 |

## 主观评价说明

- `docs/subjective_eval_results.md` 目前只保留真实任务样本与空白评分列。
- 还没有人工评分时，不应伪造结论；`scripts/summarize_subjective_eval.py` 会输出“待人工评价”。 
