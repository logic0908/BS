# Effect Ablation Report

本报告用于解释当前系统与参考 SVC 示例之间仍存在的效果差距，并给出一个可复现的消融实验入口。`v1.2` 的目标是继续补真实多风格 preset，而不是用 fallback 假装已经拥有专用模型效果。

## 当前差距的主要来源

1. 目标模型域仍有限。
当前默认 `final_primary / lain` 是可运行的演示模型，但不是多风格全覆盖目标模型。当前已经新增 `final_male_youth / Nova_Adult` 与 `final_male_powerful / AY` 作为通过真实 smoke test 的专用男声 preset；但女声方向仍未落地，两个新增男声 preset 也仍需 license 复核与人工听评，因此系统仍不能声称“所有风格都已覆盖”。

2. Adapter 仍是参数级控制。
当前 `TextStyleAdapter` 会把提示词语义映射到 `model_preset_id / transpose / style_strength` 等轻量控制参数。它还不是 So-VITS-SVC 网络内部 Bias/Scale 注入，因此无法像网络级条件控制那样深度改变 timbre/style manifold。

3. F0 与输入质量会显著放大差异。
输入是否纯净干声、F0 提取方法、转调参数、人声分离质量都会影响最终自然度、旋律稳定性和歌词可懂度。当前系统已开始记录 `f0_method / auto_predict_f0 / slice_db / clip_seconds / pad_seconds`，但现阶段除 `transpose` 外，部分参数仍只记录为系统实验参数，尚未直接透传到当前 So-VITS-SVC 4.1 CLI。

4. 真实专用 preset 仍未完全落地。
`final_male_youth / Nova_Adult` 与 `final_male_powerful / AY` 已通过本地真实 smoke test，证明系统已经具备两个可运行的专用男声 preset；但二者均为 `license_unknown`，不能标成公开 demo quality，`final_female_soft / final_female_clear` 仍因公开演示授权链路不够清晰而保持未配置。因此，这一进展只证明男声方向的目标模型域开始落地，不代表多风格覆盖已经完成。

## 消融实验脚本

```bash
python scripts/run_conversion_ablation.py \
  --input /path/to/dry_vocal.wav \
  --prompt "少年感、男声、清亮" \
  --case 'final_primary+trained_adapter|final_primary|trained_adapter|false' \
  --case 'final_male_youth+trained_adapter|final_male_youth|trained_adapter|false' \
  --case 'final_male_youth+no_adapter|final_male_youth|no_adapter|false' \
  --case 'final_male_youth+allow_preset_fallback=false|final_male_youth|trained_adapter|false' \
  --output runtime/eval_reports/effect_ablation_latest.json
```

脚本会记录：

- `task_id`
- `requested_model_preset_id`
- `effective_model_preset_id`
- `speaker`
- `requested_adapter_mode`
- `effective_adapter_mode`
- `duration_consistency`
- `low_energy_ratio`
- `possible_dropouts`
- `output_path`
- `task_config_path`
- `sovits_command_path`

音频产物仍保留在 `runtime/debug` 或运行目录中，不写入 Git。

同时，每个任务都会额外写出 `runtime/debug/<task_id>/task_config.json`，其中至少包含：

- `requested_adapter_mode`
- `effective_adapter_mode`
- `worker_pid`
- `cuda_visible_devices`
- `torch_cuda_available`
- `output_path`

## Invalid / Superseded 轮次

1. `2026-05-07` CUDA 不可用轮次：
当前文档里旧表格中的 `47eacb77-6ba5-4152-b6d8-dee5d63546b4`、`533ffb86-bfea-46d3-8ae1-6d310a82b619`、`f92ccf87-93e2-4db3-8192-ec61de8925c7`、`fb60ebdd-eb0e-4213-804d-7f0e9a4e2f3e` 都停在 `RuntimeError: No CUDA GPUs are available`，没有生成可听输出，必须视为 `invalid`。

2. 早先 Celery GPU worker 首次成功出音但 `no_adapter` 未生效的轮次：
该轮虽然成功出音，但 `final_male_youth + no_adapter` 实际记录为 `adapter_runtime_mode=trained`，说明任务参数没有完整透传到 worker，不能用于正式实验结论，现统一标记为 `superseded`。

## 2026-05-07 有效轮次设置

- 统一输入：`/home/featurize/work/BS/backend/app/data/uploads/d510ec4d-8ed3-4e9f-8c59-e77b45f048ae/vocals.wav`
- 输入侧证据：`12.007s`、`44100 Hz`、`mono`、`PCM_16`
- 统一 prompt：`少年感、男声、清亮`
- 统一 `style_strength=0.65`
- 结果汇总文件：`runtime/eval_reports/effect_ablation_20260507_rerun.json`
- worker 证据：`task_config.json` 记录 `worker_pid=11469`、`CUDA_VISIBLE_DEVICES=0`、`torch_cuda_available=true`
- 本轮请求了 `f0_method=rmvpe`，但当前运行环境仍返回 `RMVPE_UNAVAILABLE`，因此四条任务实际都回退记录为 `f0_method=system_default`

## 2026-05-07 有效任务记录

| case | task_id | requested_model_preset_id | effective_model_preset_id | speaker | requested_adapter_mode | effective_adapter_mode | duration_consistency | low_energy_ratio | possible_dropouts | valid_audio | output_path |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `final_primary+trained_adapter` | `94a8b6ee-6f68-4032-bf78-992f8cb3cfbf` | `final_primary` | `final_primary` | `lain` | `trained_adapter` | `trained` | `1.0` | `0.277992` | `false` | `true` | `/home/featurize/work/BS/runtime/debug/94a8b6ee-6f68-4032-bf78-992f8cb3cfbf/converted.wav` |
| `final_male_youth+trained_adapter` | `1768b6ce-6f3c-4673-874c-d986b3ac4579` | `final_male_youth` | `final_male_youth` | `Nova_Adult` | `trained_adapter` | `trained` | `1.0` | `0.142857` | `false` | `true` | `/home/featurize/work/BS/runtime/debug/1768b6ce-6f3c-4673-874c-d986b3ac4579/converted.wav` |
| `final_male_youth+no_adapter` | `d4cddc4b-9945-46b5-8347-28bbc67bb84d` | `final_male_youth` | `final_male_youth` | `Nova_Adult` | `no_adapter` | `no_adapter` | `1.0` | `0.144788` | `false` | `true` | `/home/featurize/work/BS/runtime/debug/d4cddc4b-9945-46b5-8347-28bbc67bb84d/converted.wav` |
| `final_male_youth+allow_preset_fallback=false` | `19331294-d7ec-4b65-87f7-818ae7b0e0c6` | `final_male_youth` | `final_male_youth` | `Nova_Adult` | `trained_adapter` | `trained` | `1.0` | `0.142857` | `false` | `true` | `/home/featurize/work/BS/runtime/debug/19331294-d7ec-4b65-87f7-818ae7b0e0c6/converted.wav` |

## 2026-05-07 rerun 有效性检查

- 已检查 4 个 case 的 `status`、`task_id`、`requested_model_preset_id`、`effective_model_preset_id`、`requested_adapter_mode`、`effective_adapter_mode`、`speaker`、`output_path`、`output_exists`、`soundfile` 可读性、`duration_consistency`、`low_energy_ratio`、`possible_dropouts` 与 `sovits_command_debug_path`。
- 4 个 `output_path` 都存在，且 `soundfile` 可正常读取，因此 4 个 case 当前均为 `valid_audio=true`。
- 4 个输出文件的采样率均为 `44100 Hz`，时长均为 `12.00737s`，与统一输入长度一致，没有出现“文件存在但不可读”的情况。
- `final_male_youth+no_adapter` 的 [task_config.json](/home/featurize/work/BS/runtime/debug/d4cddc4b-9945-46b5-8347-28bbc67bb84d/task_config.json) 明确记录 `requested_adapter_mode=no_adapter`、`effective_adapter_mode=no_adapter`、`CUDA_VISIBLE_DEVICES=0`、`torch_cuda_available=true`。
- `final_male_youth+no_adapter` 的 [style_adapter_output.json](/home/featurize/work/BS/runtime/debug/d4cddc4b-9945-46b5-8347-28bbc67bb84d/style_adapter_output.json) 记录 `adapter_enabled=false`、`adapter_type=disabled`，并写明 `requested_adapter_mode=no_adapter; skipped TextStyleAdapter control injection`。
- `final_male_youth+trained_adapter` 的 [task_config.json](/home/featurize/work/BS/runtime/debug/1768b6ce-6f3c-4673-874c-d986b3ac4579/task_config.json) 仍记录 `effective_adapter_mode=trained`，可作为本轮链路对照。

## 模型效果对比候选表

仅 `valid_audio=true` 的 case 允许进入此表。本轮 4 个 case 均满足该条件。

| case | task_id | preset | speaker | adapter_mode | duration_consistency | low_energy_ratio | possible_dropouts | valid_audio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `final_primary+trained_adapter` | `94a8b6ee-6f68-4032-bf78-992f8cb3cfbf` | `final_primary` | `lain` | `trained_adapter -> trained` | `1.0` | `0.277992` | `false` | `true` |
| `final_male_youth+trained_adapter` | `1768b6ce-6f3c-4673-874c-d986b3ac4579` | `final_male_youth` | `Nova_Adult` | `trained_adapter -> trained` | `1.0` | `0.142857` | `false` | `true` |
| `final_male_youth+no_adapter` | `d4cddc4b-9945-46b5-8347-28bbc67bb84d` | `final_male_youth` | `Nova_Adult` | `no_adapter -> no_adapter` | `1.0` | `0.144788` | `false` | `true` |
| `final_male_youth+allow_preset_fallback=false` | `19331294-d7ec-4b65-87f7-818ae7b0e0c6` | `final_male_youth` | `Nova_Adult` | `trained_adapter -> trained` | `1.0` | `0.142857` | `false` | `true` |

## v1.2 当前执行结论

| 项目 | 当前状态 |
| --- | --- |
| 已配置 preset | `final_primary`、`final_male_youth`、`final_male_powerful`、`tech_villager` |
| 已筛到候选但未完成 smoke test | 暂无 |
| 仍未配置 | `final_female_soft`、`final_female_clear` |
| fallback 任务说明 | 只有显式开启 `allow_preset_fallback=true` 才允许回退到 `final_primary/lain`，且结果不能被表述成专用风格真实效果 |
| 真实专用模型推理任务 | 已新增 `final_male_youth / Nova_Adult` 与 `final_male_powerful / AY` 作为通过真实 smoke test 的专用男声 preset，但这只证明链路可运行，不代表所有风格覆盖完成 |
| Bias/Scale 注入结论 | 仍不能证明已完成 So-VITS-SVC 网络内部 Bias/Scale 注入 |

## 本轮实验结论

| 维度 | 当前结论 |
| --- | --- |
| `final_primary/lain` vs `final_male_youth/Nova_Adult` | 现在已经得到真实可听输出。首条实际执行 `final_primary / lain`，后三条实际执行 `final_male_youth / Nova_Adult`，且都 `return_code=0`。 |
| `trained_adapter` vs `no_adapter` | 已验证 `no_adapter` 控制链路真实跳过 Adapter。当前还没有人工评分，因此这里不对 `no_adapter` 与 `trained` 的听感优劣下结论。 |
| `allow_preset_fallback=false` 影响 | 在 `final_male_youth` 已 `ready` 的前提下，显式 `allow_preset_fallback=false` 与普通 `trained_adapter` case 的 `requested/effective preset` 一致，均未发生 preset fallback。 |
| `final_primary` 边界 | 当前可跑通、可演示，但不是全风格覆盖目标模型 |
| `specialized preset` 边界 | 当前已新增 `final_male_youth / Nova_Adult` 与 `final_male_powerful / AY` 作为通过本地真实 smoke test 的专用男声 preset，但女声方向、license 复核与人工听评仍未完成 |
| `f0_method` 影响 | 本轮原计划固定 `rmvpe`，但当前会话缺少可用 RMVPE 运行条件，四条任务都统一回退记录为 `system_default`，因此本次不能比较 F0 路径差异。 |
| 主要改进方向 | 当前 GPU worker 已恢复可用；下一步重点从“修链路”转为“补 RMVPE 条件、做人工听评、扩展更多专用 preset 对比”。 |

## 主观评价说明

- `docs/subjective_eval_results.md` 目前只保留真实任务样本与空白评分列。
- 还没有人工评分时，不应伪造结论；`scripts/summarize_subjective_eval.py` 会输出“待人工评价”。 
