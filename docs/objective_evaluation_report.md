# Objective Evaluation Report

本报告基于当前仓库内可复查的真实 smoke test 结果、已成功转换任务产物以及 `compare_audio_style` 生成的启发式客观指标自动整理。

## 当前范围

- 评估样本数：`4`
- 结果文件：`evaluation/objective_results.json`
- 生成脚本：`scripts/run_objective_evaluation.py`
- 说明：客观指标只用于辅助解释风格变化趋势，不能替代人工听评。

## 样本数量说明

- 当前可直接复查的真实样本数量有限，本报告只代表阶段性客观证据，不应外推为完整风格覆盖结论。
- `final_female_soft` 与 `final_female_clear` 仍未配置真实模型，因此不纳入本轮音频客观评价。

## 汇总表

| case_id | preset | duration_delta (s) | style_evidence_score | level | matched/total | f0_median_delta | rms_mean_delta | spectral_centroid_delta | style_analysis_time (s) |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |
| final_male_powerful_smoke | `final_male_powerful` | `0` | `0` | `weak` | `0/5` | `0` | `0.0608` | `372.8046` | `13.083` |
| final_primary_demo_b7c03828 | `final_primary` | `0` | `0.4` | `partial` | `2/5` | `-16.6736` | `-0.0048` | `-114.4727` | `6.26` |
| final_primary_demo_1a9d1b8b | `final_primary` | `0` | `0.2` | `weak` | `1/5` | `17.6651` | `-0.001` | `-29.8277` | `6.276` |
| final_primary_demo_4e703d1d | `final_primary` | `0` | `0.6` | `partial` | `3/5` | `-33.1737` | `-0.003` | `-140.1614` | `6.107` |

## 个案说明

### final_male_powerful_smoke

- prompt：`低沉、成熟、厚重男声`
- preset：`final_male_powerful`
- 输入音频：`test.wav`
- 输出音频：`smoke-final_male_powerful-1777912011.wav_0key_AY_sovits_pm.flac`
- style evidence：`0` / `weak`
- 总结：输出音频与输入相比变化有限，未能在多数可测指标上明显朝提示词目标方向移动。该结果可作为后续优化目标模型、提示词映射和条件控制强度的依据。
- 内容保持说明：So-VITS-SVC 类 SVC 更偏向保留源音频的旋律、节奏与语调骨架，因此前后差异通常不会像 TTS 重合成那样剧烈。
- 风格响应说明：客观指标显示本次输出的风格响应较弱，可作为后续优化 preset、提示词映射和控制强度的依据。
- warnings：`该分析为启发式客观指标，仅用于展示趋势，不能替代人工听评。`
- smoke 证据： `success=True` `command_return_code=0` `called_inference_main=True` `command_matches_preset=True` `speaker_matches_preset=True` `soundfile_readable=True` `duration_seconds=12.007` `license=license_unknown`

### final_primary_demo_b7c03828

- prompt：`清亮、少年感、男声`
- preset：`final_primary`
- 输入音频：`vocals.wav`
- 输出音频：`converted.wav`
- style evidence：`0.4` / `partial`
- 总结：输出音频在部分指标上向提示词目标方向移动，但仍有若干维度变化不明显，说明当前模型具备一定提示词响应趋势，但转换幅度有限。
- 内容保持说明：So-VITS-SVC 类 SVC 更偏向保留源音频的旋律、节奏与语调骨架，因此前后差异通常不会像 TTS 重合成那样剧烈。
- 风格响应说明：客观指标显示输出存在一定提示词响应趋势，但变化幅度有限，仍需结合主观试听判断是否足够明显。
- warnings：`该分析为启发式客观指标，仅用于展示趋势，不能替代人工听评。`

### final_primary_demo_1a9d1b8b

- prompt：`温柔、气声、抒情女声`
- preset：`final_primary`
- 输入音频：`vocals.wav`
- 输出音频：`converted.wav`
- style evidence：`0.2` / `weak`
- 总结：输出音频与输入相比变化有限，未能在多数可测指标上明显朝提示词目标方向移动。该结果可作为后续优化目标模型、提示词映射和条件控制强度的依据。
- 内容保持说明：So-VITS-SVC 类 SVC 更偏向保留源音频的旋律、节奏与语调骨架，因此前后差异通常不会像 TTS 重合成那样剧烈。
- 风格响应说明：客观指标显示本次输出的风格响应较弱，可作为后续优化 preset、提示词映射和控制强度的依据。
- warnings：`该分析为启发式客观指标，仅用于展示趋势，不能替代人工听评。`

### final_primary_demo_4e703d1d

- prompt：`低沉、成熟、厚重男声`
- preset：`final_primary`
- 输入音频：`vocals.wav`
- 输出音频：`converted.wav`
- style evidence：`0.6` / `partial`
- 总结：输出音频在部分指标上向提示词目标方向移动，但仍有若干维度变化不明显，说明当前模型具备一定提示词响应趋势，但转换幅度有限。
- 内容保持说明：So-VITS-SVC 类 SVC 更偏向保留源音频的旋律、节奏与语调骨架，因此前后差异通常不会像 TTS 重合成那样剧烈。
- 风格响应说明：客观指标显示输出存在一定提示词响应趋势，但变化幅度有限，仍需结合主观试听判断是否足够明显。
- warnings：`该分析为启发式客观指标，仅用于展示趋势，不能替代人工听评。`

## 结论边界

- 当前报告只说明：系统已经具备可复查的客观风格证据提取能力。
- 当前报告不能说明：系统已经完成全部风格覆盖，或客观指标等价于主观听感。
- `TextStyleAdapter` 当前仍是参数级控制，不是 So-VITS-SVC 网络内部 Bias/Scale 注入。
- `license_unknown` 模型只能按当前文档口径用于本地技术演示或内部复核，不能表述成授权边界完全清晰的公开商用模型。
