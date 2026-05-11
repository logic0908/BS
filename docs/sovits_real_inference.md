# So-VITS-SVC 真实推理说明

本文档说明当前仓库中 So-VITS-SVC 真实推理链路、`internal_film` 条件推理入口、调试证据文件以及常见问题排查方式。

## 1. 当前真实链路

当前主系统默认链路：

```text
style_prompt
-> TextStyleEncoder
-> style_embedding.pt / .json / .npy
-> SoVitsSvcEngine
-> inference_conditioned.py
-> SynthesizerTrn.infer()
-> pre_decoder internal FiLM
-> converted.wav
```

默认说明：

- 默认主链路是 So-VITS-SVC
- StyleSinger 仍保留在仓库中，但不是默认内容保持型转换主链路
- `SOVITS_MOCK=true` 时只走 mock 验证路径
- `SOVITS_MOCK=false` 且 `SOVITS_CONDITION_MODE=internal_film` 时，真实推理会走内部 FiLM 注入入口

## 2. 原始推理与 conditioned 推理

### 2.1 原始 So-VITS-SVC 推理

当 `SOVITS_CONDITION_MODE=none` 时，wrapper 会调用原始入口：

```text
so-vits-svc/inference_main.py
```

这条路径不加载 `style_emb`，也不会写出 `conditioning_report.json`。

### 2.2 conditioned inference 推理

当 `SOVITS_CONDITION_MODE=internal_film` 时，wrapper 会切换到：

```text
backend/app/models_svc/inference_conditioned.py
```

该脚本会额外接收：

- `--style-emb-path`
- `--style-emb-format`
- `--condition-mode internal_film`
- `--film-strength`
- `--film-target`
- `--conditioning-report-path`

## 3. internal_film 注入机制

### 3.1 注入输入

- 用户输入：`style_prompt`
- 文本编码器：`TextStyleEncoder`
- 向量文件：`style_embedding.pt`

### 3.2 调制模块

实现文件：

- [backend/app/models_svc/style_film.py](../backend/app/models_svc/style_film.py)

调制形式：

```text
h_cond = h * (1 + gamma(style_emb)) + beta(style_emb)
```

### 3.3 注入点

当前真实注入点位于：

- `SynthesizerTrn.infer()`
- `self.flow(...)` 输出隐变量 `z` 之后
- `self.dec(...)` 消费 `z * c_mask` 之前

这也是当前 `SOVITS_FILM_TARGET=pre_decoder` 的含义。

## 4. 关键环境变量

```bash
SOVITS_MOCK=false
SOVITS_REPO_DIR=/path/to/so-vits-svc
SOVITS_INFER_SCRIPT=/path/to/so-vits-svc/inference_main.py
SOVITS_MODEL_PATH=/path/to/model.pth
SOVITS_CONFIG_PATH=/path/to/config.json
SOVITS_SPEAKER=lain
SOVITS_DEVICE=cuda
SOVITS_TRANSPOSE=0
SOVITS_TIMEOUT_SECONDS=300

SOVITS_CONDITION_MODE=internal_film
SOVITS_STYLE_DIM=256
SOVITS_FILM_STRENGTH=0.10
SOVITS_FILM_TARGET=pre_decoder
SOVITS_STYLE_EMB_FORMAT=pt
```

关闭内部注入的方法：

```bash
export SOVITS_CONDITION_MODE=none
```

或：

```bash
export SOVITS_MOCK=true
```

## 5. 调试证据文件

每次真实任务都会在：

```text
runtime/debug/<task_id>/
```

写出调试证据。重点查看：

- `style_embedding.pt`
- `style_embedding.json`
- `style_embedding.npy`
- `conditioning_report.json`
- `sovits_command.txt`
- `sovits_debug.json`
- `converted.wav`

其中常见关键字段包括：

- `condition_mode`
- `style_prompt`
- `style_emb_path`
- `style_dim`
- `film_strength`
- `film_target`
- `injection_target`
- `executed_internal_film`
- `called_conditioned_inference`

## 6. 真实 smoke 摘要

最新一次真实 GPU smoke 摘要如下：

- GPU：`NVIDIA GeForce RTX 3080`
- 输入音频：`44100 Hz`，`8.18s`
- baseline `none`：可读，`44100 Hz`，`8.18s`，无 `NaN/Inf`
- `internal_film`：可读，`44100 Hz`，`8.18s`，无 `NaN/Inf`
- `conditioning_report.json`：存在
- `executed_internal_film=true`
- `style_embedding.pt`：存在

这组结果证明当前工程链路已经完成“文本向量 -> So-VITS-SVC 内部 Bias/Scale 注入 -> 真实 wav 输出”的跑通验证，但不等于已经得到充分的主观效果结论。

## 7. 常见错误排查

### 7.1 `style_emb_path` 缺失

现象：

- `internal_film` 模式启动，但报错缺少 `style_emb_path`

排查：

- 确认 `TextStyleEncoder` 已在任务前写出 `style_embedding.pt`
- 确认 `sovits_wrapper.py` 传入了 `style_emb_path`

### 7.2 `conditioning_report.json` 不存在

现象：

- 输出 wav 已生成，但没有 `conditioning_report.json`

排查：

- 查看实际命令是否走了 `inference_conditioned.py`
- 查看 `condition_mode` 是否误设为 `none`

### 7.3 GPU 不可见

现象：

- `torch.cuda.is_available() == False`
- `No CUDA GPUs are available`

排查：

- 确认当前会话是否真在 GPU 环境中
- 确认 `SOVITS_DEVICE=cuda`
- 检查 `nvidia-smi`

### 7.4 模型权重或配置缺失

现象：

- `SOVITS_MODEL_PATH` / `SOVITS_CONFIG_PATH` 不存在

排查：

- 检查 `backend/app/config/svc_model_presets.json`
- 检查本地 `local_models/` 是否就绪

### 7.5 当前效果不明显

需要如实说明：

- 当前系统已经接入内部条件注入机制
- 但尚未完成基于大规模风格标注数据的强文本控制训练
- 实际听感仍受目标模型、输入音频质量、F0 提取和分离质量影响
