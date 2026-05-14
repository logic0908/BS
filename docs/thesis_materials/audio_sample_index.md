# 音频样例索引与命名规范

## 1. 命名规则建议

建议统一命名：

`<sample_id>_<condition>_<preset>_<speaker>.wav`

示例：

- `S001_input_source.wav`
- `S001_baseline_none_final_primary_lain.wav`
- `S001_internal_film_0.05_final_primary_lain.wav`
- `S001_internal_film_0.10_final_primary_lain.wav`
- `S001_internal_film_0.15_final_primary_lain.wav`

## 2. 条件命名规范

- `input`：原始输入音频
- `baseline_none`：`condition_mode=none`
- `external_preset`：`condition_mode=external_preset`
- `internal_film_0.05`：`condition_mode=internal_film, film_strength=0.05`
- `internal_film_0.10`：`condition_mode=internal_film, film_strength=0.10`
- `internal_film_0.15`：`condition_mode=internal_film, film_strength=0.15`

## 3. 当前仓库可扫描到的真实样例路径

### 3.1 eval_samples（结构化样例）

- `/home/featurize/work/BS/runtime/eval_samples/condition_mode/none/converted.wav`
- `/home/featurize/work/BS/runtime/eval_samples/condition_mode/external_preset/converted.wav`
- `/home/featurize/work/BS/runtime/eval_samples/condition_mode/internal_film/converted.wav`
- `/home/featurize/work/BS/runtime/eval_samples/film_strength/none/converted.wav`
- `/home/featurize/work/BS/runtime/eval_samples/film_strength/internal_film_0.05/converted.wav`
- `/home/featurize/work/BS/runtime/eval_samples/film_strength/internal_film_0.10/converted.wav`
- `/home/featurize/work/BS/runtime/eval_samples/film_strength/internal_film_0.15/converted.wav`

### 3.2 任务调试目录（大量真实任务产物）

- `/home/featurize/work/BS/runtime/debug/<task_id>/input.wav`
- `/home/featurize/work/BS/runtime/debug/<task_id>/vocals.wav`
- `/home/featurize/work/BS/runtime/debug/<task_id>/converted.wav`

说明：`runtime/debug` 下文件量较大，建议论文阶段挑选固定任务 ID 建立“小样例白名单”并复制到专门归档目录。

## 4. 仍需补充材料

1. 样例与 prompt 的一一对应清单（当前仅有部分报告记录，未统一索引表）。
2. 每个样例的 `model_preset_id`、`speaker`、`adapter_mode` 对照表。
3. 主观听评实际播放清单（若用于问卷实验）。
