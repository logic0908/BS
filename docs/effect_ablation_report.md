# Effect Ablation Report

本文档用于整理当前项目的消融实验设计、真实 smoke 对照和论文中可引用的实验边界说明。

## 1. 实验目标

当前项目的实验重点不是直接证明“强文本语义可控的高质量歌声转换效果”，而是验证：

1. 文本提示词是否能稳定生成确定性 `style_emb`
2. `style_emb` 是否能进入 So-VITS-SVC 真实推理链路
3. 内部 Bias/Scale / FiLM 注入机制是否在真实 GPU 环境中执行
4. baseline 与 `internal_film` 是否都能生成有效音频输出

## 2. 三组核心对照

### 2.1 `none`

- 含义：关闭内部文本条件注入
- 配置：`SOVITS_CONDITION_MODE=none`
- 入口：原始 `inference_main.py`

### 2.2 `external_preset`

- 含义：保留 `style_library` 与 `TextStyleAdapter` 的外部 preset / 参数控制
- 配置：通常仍使用 `SOVITS_CONDITION_MODE=none`
- 重点：比较只有外部控制时的表现

### 2.3 `internal_film`

- 含义：启用 `TextStyleEncoder -> style_emb -> pre_decoder FiLM`
- 配置：`SOVITS_CONDITION_MODE=internal_film`
- 入口：`backend/app/models_svc/inference_conditioned.py`

## 3. film_strength 对比建议

建议预留三档：

- `0.05`
- `0.10`
- `0.15`

当前状态：

- 已完成 `0.10` 的真实 smoke
- `0.05 / 0.15` 为后续实验配置，尚未形成正式对比结论

## 4. 最新 smoke 对照

### 4.1 输入音频

- 输入类型：本地短人声片段
- 采样率：`44100 Hz`
- 时长：`8.18s`
- 可读性：`soundfile` 可读
- 数值检查：无 `NaN/Inf`

### 4.2 baseline `none`

- 输出：有效 wav
- 采样率：`44100 Hz`
- 时长：`8.18s`
- `soundfile`：可读
- `NaN/Inf`：无
- 推理入口：原始 `inference_main.py`
- `executed_internal_film=false`

### 4.3 `internal_film`

- 输出：有效 wav
- 采样率：`44100 Hz`
- 时长：`8.18s`
- `soundfile`：可读
- `NaN/Inf`：无
- `style_embedding.pt`：存在
- `conditioning_report.json`：存在
- `executed_internal_film=true`
- 注入目标：`pre_decoder`

## 5. 建议记录字段

每组实验建议至少记录：

- 输入音频路径
- `style_prompt`
- 输出音频路径
- `condition_mode`
- `film_strength`
- `film_target`
- `injection_target`
- 是否成功生成有效 wav
- `soundfile` 可读性
- 采样率
- 时长
- 是否有 `NaN/Inf`
- 主观听感备注
- 可选客观指标

## 6. 建议保留的证据文件

```text
runtime/debug/<task_id>/
  style_embedding.pt
  style_embedding.json
  conditioning_report.json
  sovits_command.txt
  sovits_debug.json
  converted.wav
```

其中，论文和答辩阶段最关键的证据是：

- `conditioning_report.json` 中的 `executed_internal_film=true`
- `sovits_command.txt` 中带有：
  - `--style-emb-path`
  - `--condition-mode internal_film`
  - `--film-strength`

## 7. 当前可得结论

当前可以成立的结论：

- 文本条件内部注入机制已经在真实 GPU 环境中接入并跑通
- baseline `none` 与 `internal_film` 都可生成有效 wav
- `internal_film` 路径可以写出完整调试证据

当前还不能直接成立的结论：

- 文本提示词已经实现强语义级风格控制
- `internal_film` 一定优于 `none`
- 当前系统已经完成充分的主观效果验证

## 8. 后续实验建议

后续可在不扩大系统功能的前提下继续补充：

1. `0.05 / 0.10 / 0.15` 的 `film_strength` 对照
2. 相同输入音频下的人工听评表
3. 不同 preset 与相同 prompt 的对照
4. `external_preset` 与 `internal_film` 的分离对比
