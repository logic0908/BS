# 本地模型资产补齐说明

## 目录结构

```text
local_models/
  sovits-final/
    final_primary/
      G_2400_infer.pth
      config.json
  contentvec/
    checkpoint_best_legacy_500.pt
  rmvpe/
    rmvpe.pt

runtime/
  style_adapter/
    text_style_adapter_v1.pt  # 可选
```

当前仓库里的真实默认 preset 是 `final_primary / lain`。实际运行时优先读取：

- `backend/app/config/svc_model_presets.json`
- `backend/.env.example` 中对应的 `SVC_MODEL_PRESET_ID` / `SOVITS_*` 配置

## 每个文件的作用

- `G_2400_infer.pth`：So-VITS-SVC 生成器权重。
- `config.json`：So-VITS-SVC 模型结构、speaker 列表、speech encoder 配置。
- `checkpoint_best_legacy_500.pt`：`vec768l12` / `vec256l9` 等 ContentVec 语音内容编码器所需预训练权重。
- `rmvpe.pt`：RMVPE F0 提取模型。
- `text_style_adapter_v1.pt`：可选增强型文本风格 Adapter 权重；缺失时不会阻断主链路，系统会回退到本地 deterministic fallback encoder。

## 为什么不提交权重

- 模型文件通常较大，不适合直接放进普通 GitHub 仓库。
- 不同公开模型的许可证边界不一定允许再分发。
- 推理与实验会产生大量本地音频/中间产物，应该和源码分离。
- 仓库已通过 `.gitignore` 排除 `local_models/`、`runtime/`、`*.pth`、`*.pt`、`*.wav` 等大文件与产物。

## 路径与环境变量

默认真实主链路使用：

```env
SVC_MODEL_PRESET_ID=final_primary
SOVITS_REPO_DIR=/home/featurize/work/BS/so-vits-svc
SOVITS_INFER_SCRIPT=/home/featurize/work/BS/so-vits-svc/inference_main.py
SOVITS_CONDITIONED_INFER_SCRIPT=/home/featurize/work/BS/backend/app/models_svc/inference_conditioned.py
SOVITS_MODEL_PATH=/home/featurize/work/BS/local_models/sovits-final/final_primary/G_2400_infer.pth
SOVITS_CONFIG_PATH=/home/featurize/work/BS/local_models/sovits-final/final_primary/config.json
SOVITS_SPEAKER=lain
SOVITS_DEVICE=cuda
SOVITS_CONDITION_MODE=internal_film
SOVITS_STYLE_DIM=256
SOVITS_FILM_STRENGTH=0.10
SOVITS_FILM_TARGET=pre_decoder
SOVITS_STYLE_EMB_FORMAT=pt
SOVITS_CONTENTVEC_PATH=/home/featurize/work/BS/so-vits-svc/pretrain/checkpoint_best_legacy_500.pt
SOVITS_RMVPE_MODEL_PATH=/home/featurize/work/BS/backend/models/rmvpe/rmvpe.pt
```

说明：

- So-VITS-SVC 第三方仓库本身主要按固定相对路径读取 `pretrain/` 下的预训练文件。
- 当前仓库的检查层支持 `SOVITS_CONTENTVEC_PATH` 与 `SOVITS_RMVPE_MODEL_PATH`，必要时会把它们软链接到 `so-vits-svc/pretrain/` 里供本地推理使用。
- 如果缺少 `checkpoint_best_legacy_500.pt`，请优先放到 `so-vits-svc/pretrain/checkpoint_best_legacy_500.pt`，或者在 `.env` 中配置 `SOVITS_CONTENTVEC_PATH`。
- 如果缺少 `rmvpe.pt`，请优先放到 `so-vits-svc/pretrain/rmvpe.pt`、`backend/models/rmvpe/rmvpe.pt` 或 `local_models/rmvpe/rmvpe.pt`，或者在 `.env` 中配置 `SOVITS_RMVPE_MODEL_PATH`。

## 快速检查命令

```bash
PYTHONPATH=$(pwd)/backend python scripts/check_models_ready.py --preset final_primary
```

## 真实 smoke 命令

```bash
bash scripts/smoke_internal_film_conversion.sh --input /path/to/test.wav
```

脚本会在 `runtime/debug/smoke-internal_film-*/` 下生成：

- `converted_internal_film.wav`
- `converted.wav`
- `style_embedding.pt`
- `conditioning_report.json`
- `smoke_summary.json`
- `sovits_command.txt`
