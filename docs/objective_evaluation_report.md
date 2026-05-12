# Objective Evaluation Report

本报告汇总 `baseline none`、`external_preset`、`internal_film` 的可量化参考指标，用于论文和答辩中的辅助说明。

## 边界说明

- 指标只用于量化参考，不直接证明主观听感更好。
- 歌声转换场景下，若没有 clean reference 或可用许可实现，不强制计算 PESQ/POLQA/STOI。
- `speaker_embedding_similarity`、`f0`、`mfcc_distance` 等指标在依赖缺失时只输出 warning，不中断整体报告。

- 当前状态：`ok`
- 当前 case 数：`1`

## 汇总表

| sample_id | condition | rms_energy | clipping_ratio | silence_ratio | spectral_centroid_mean | f0_mean | mfcc_distance | speaker_similarity | brightness_delta | energy_delta | pitch_height_delta |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `condition_mode_case_001` | `baseline_none` | `0.0886408` | `0.0` | `0.1398` | `3068.660889` | `270.748048` | `23.935169` | `0.949915` | `826.338379` | `0.00637772` | `-3.377609` |
| `condition_mode_case_001` | `external_preset` | `0.0886408` | `0.0` | `0.1398` | `3068.660889` | `270.748048` | `23.935169` | `0.949915` | `826.338379` | `0.00637772` | `-3.377609` |
| `condition_mode_case_001` | `internal_film` | `0.08864222` | `0.0` | `0.1398` | `3068.56665` | `270.748048` | `23.935965` | `0.949919` | `826.24414` | `0.00637914` | `-3.377609` |

## 解释方式

- `brightness_delta / energy_delta / pitch_height_delta / softness_delta / thickness_delta` 为启发式风格方向指标。
- 它们只能说明输出是否朝 prompt 预期方向发生变化，不能替代人工听评或证明“显著更优”。

## 当前结论边界

- 可以说：系统已经具备对 baseline / external / internal 条件的批量客观统计框架。
- 不能说：仅凭本报告就能证明 internal FiLM 一定显著优于 baseline none。
