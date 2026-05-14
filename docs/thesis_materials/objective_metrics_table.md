# 客观指标表（基于 objective_metrics_1000）

- 数据来源：
  - `/home/featurize/work/BS/runtime/eval_reports/objective_metrics_1000.csv`
  - `/home/featurize/work/BS/runtime/eval_reports/objective_metrics_1000.md`
- 当前样本：`ablation_1000_case_001`
- 提醒：当前 `case_count=1`，结论只能作为趋势证据。

## 1. 论文可用对照表（baseline vs internal_film）

| 指标名称 | baseline_none | internal_film | 指标含义 | 结论边界 |
| --- | ---: | ---: | --- | --- |
| `duration_seconds` | `8.18` | `8.18` | 输出音频时长 | 与输入一致性需结合 `duration_consistency`，不能单独评价质量 |
| `rms_energy` | `0.08897263` | `0.08897496` | 平均能量强度 | 能量接近不代表主观“更有力量” |
| `peak_amplitude` | `0.55737305` | `0.55734253` | 峰值幅度 | 峰值接近仅说明幅值层面变化小 |
| `clipping_ratio` | `0.0` | `0.0` | 裁剪失真比例 | 为 0 说明无明显削顶，不代表整体音质最佳 |
| `silence_ratio` | `0.145506` | `0.145506` | 低能量/静音占比 | 相同不代表听感相同 |
| `spectral_centroid_mean` | `3069.844238` | `3069.726807` | 频谱质心均值（亮度相关） | 差异很小，仅能作弱趋势观察 |
| `f0_mean` | `273.625417` | `273.625417` | 平均基频 | 相同不代表风格一致；需结合其他维度 |
| `mfcc_distance` | `47.253521` | `47.253956` | 与输入的谱特征差异 | 数值本身不等于“更好”，仅表示差异量 |
| `speaker_embedding_similarity` | `0.818377` | `0.816511` | 说话人嵌入相似度 | 相似度高通常表示音色保持，但不等于风格更符合 prompt |
| `brightness_delta` | `29.5` | `29.382569` | 亮度方向变化 | 为启发式方向指标，不是主观评分 |
| `energy_delta` | `0.03734826` | `0.03735059` | 能量方向变化 | 差异极小，不能下“显著提升”结论 |
| `pitch_height_delta` | `-10.237549` | `-10.237549` | 音高方向变化 | 与目标匹配度仍需听评验证 |

## 2. 解释建议（可入论文）

1. 当前 `objective_metrics_1000` 显示 baseline 与 internal_film 在部分指标上存在可量化差异，但幅度整体有限。
2. 客观指标可用于“趋势提示”和“可复现实验记录”，不能直接推导“主观听感显著更好”。
3. 论文中应同时注明：主观听评仍需人工补充，当前不能写“主观评价已证明效果较好”。
