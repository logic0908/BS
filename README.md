# 基于文本提示词控制的歌声风格转换系统

## 1. 项目简介

本项目是一个 B/S 架构的歌声风格转换系统。用户通过浏览器上传人声或歌曲音频，输入自然语言风格提示词，系统在后端完成人声预处理、文本风格编码、Adapter 控制参数生成、So-VITS-SVC 歌声转换、音频质量评价，并在前端提供 A/B 对比播放与下载。

本项目不追求从零生成新歌曲，而是聚焦于对已有歌声或人声干声进行可控风格转换。当前默认主链路是 So-VITS-SVC；StyleSinger 仅作为高级实验模式保留，不是默认内容保持型 SVC 主链路。

当前系统已实现从文本提示词到风格控制参数的实验闭环：`prompt -> SentenceTransformer 文本编码 -> 训练型 TextStyleAdapter -> So-VITS-SVC 推理 -> 音频质量评价 -> 前端结果展示`。

当前系统已经实现真实 So-VITS-SVC CUDA 推理与 Redis/Celery 异步任务闭环。当前 TextStyleAdapter 将文本提示词语义映射为模型 preset 与转换参数；后续可扩展为 So-VITS-SVC 网络中间层 Bias/Scale 条件注入。当前系统不声称已完成端到端文本向量注入 So-VITS-SVC 网络内部。StyleSinger 高级模式是实验分支，不是默认内容保持型转换主链路。

## 2. 当前状态：v1.2-real-multi-style-preset-review + final_male_youth smoke passed

- 真实 So-VITS-SVC CUDA 推理已跑通。
- 默认演示模型 preset 仍为 `final_primary / lain`，它是当前可用默认模型，不代表所有专用风格均已覆盖。
- 默认演示模型文件为 `G_2400_infer.pth`。
- 默认演示模型来源为 `SuCicada/Lain-so-vits-svc-4.1`。
- `final_male_powerful / AY` 已成为一个通过本地真实 So-VITS-SVC smoke test 的专用男声 preset。
- `final_male_youth / Nova_Adult` 已完成首个授权下载复核候选的本地真实 smoke test；由于 `license=license_unknown`，仅作为内部复核/本地毕业设计技术演示候选，不建议用于公开传播素材，也不标记为 demo quality。
- `final_male_youth` 当前绑定：
  - `model_path=/home/featurize/work/BS/local_models/sovits-final/final_male_youth/G_10000.pth`
  - `config_path=/home/featurize/work/BS/local_models/sovits-final/final_male_youth/config.json`
  - `speaker=Nova_Adult`
  - `speech_encoder=vec768l12`
  - `source_repo=Kuugo/Nova-Adult_So-Vits-SVC`
- `final_male_youth` smoke test 证据摘要：
  - `task_id=smoke-final_male_youth-1778076531`
  - `selected_output=/home/featurize/work/BS/so-vits-svc/results/smoke-final_male_youth-1778076531.wav_0key_Nova_Adult_sovits_pm.flac`
  - `output_path=/tmp/final_male_youth_smoke_test.wav`
  - `duration_seconds=12.007`
  - `output_size=1059094`
  - `return_code=0`
  - `command_return_code=0`
  - `called_inference_main=true`
  - `command_matches_preset=true`
  - `speaker_matches_preset=true`
  - `soundfile_readable=true`
  - `success=true`
- `final_male_powerful` 当前绑定：
  - `model_path=/home/featurize/work/BS/local_models/sovits-final/final_male_powerful/G_15000.pth`
  - `config_path=/home/featurize/work/BS/local_models/sovits-final/final_male_powerful/config.json`
  - `speaker=AY`
  - `speech_encoder=vec256l9`
  - `source_repo=andreyaniv/andre-yaniv-so-vits-svc`
- `final_male_powerful` smoke test 证据摘要：
  - `task_id=smoke-final_male_powerful-1777912011`
  - `selected_output=/home/featurize/work/BS/so-vits-svc/results/smoke-final_male_powerful-1777912011.wav_0key_AY_sovits_pm.flac`
  - `output_path=/tmp/final_male_powerful_smoke_test.wav`
  - `duration_seconds=12.007`
  - `output_size=1059094`
  - `return_code=0`
  - `command_return_code=0`
  - `called_inference_main=true`
  - `command_matches_preset=true`
  - `speaker_matches_preset=true`
  - `soundfile_readable=true`
  - `success=true`
- `tech_villager` 仅作为技术验收 fallback，不是默认最终模型。
- Redis/Celery 已完成真实联调。
- TextStyleEncoder 已接入。
- 训练型 TextStyleAdapter 已接入，在线策略为 `trained` 优先、失败回退 `rule_based`。
- `style_adapter_pairs` 数据集已扩展到 `56` 条。
- `build/train/eval` 已跑通。
- 前端已重构为 `Header / Demo Workspace / Audio Compare / Advanced Details` 四区正式演示工作台。
- `WaveSurfer.js` 已接入 A/B 波形对比，初始化失败时会 fallback 到原生 `audio` 播放器。
- `/api/v1/upload` 现在返回 `input_quality_summary`，并在上传目录生成 `input_quality_report.json`。
- 默认 So-VITS-SVC 转换支持高级转换参数：`transpose`、`style_strength`、`model_preset_id`、`f0_method`、`auto_predict_f0`、`slice_db`、`clip_seconds`、`pad_seconds`。
- 新增多模型 preset 占位：`final_male_youth`、`final_male_powerful`、`final_female_soft`、`final_female_clear`。
- `allow_preset_fallback` 已完成，但仍保持默认关闭；只有显式开启时才允许回退到 `final_primary/lain`，且不能伪装成专用风格真实效果。
- 前端 `model_preset_id` 区域现在会显示每个 preset 的 `configured / smoke_test_passed / source_repo / license`，未配置 preset 明确显示“未绑定模型”。
- `final_male_youth` 已通过本地真实 smoke test 并进入已配置状态，但 `license=license_unknown`，只能用于内部复核/本地技术演示，不作为公开 demo quality 模型。
- `final_male_powerful` 已通过本地真实 smoke test，但这只代表推理链路可运行，不代表主观效果已经足够优秀；后续仍需人工听评或 A/B 对比评价。
- `final_female_soft`、`final_female_clear` 当前仍未绑定真实模型，主要原因是公开演示授权链路不够清晰，系统不会为了补齐 preset 数量强行接入来源可疑模型。
- 若 prompt 命中未配置的专用 preset，系统会明确返回 `SVC_MODEL_PRESET_NOT_CONFIGURED`，不会伪装为“已完成该风格转换”。
- `final_male_youth` 与 `final_male_powerful` 当前均为 `license=license_unknown`。它们可以用于本地毕业设计技术演示/内部复核，但不应被表述成“授权边界已完全清晰的公开商用模型”。
- 当前 `TextStyleAdapter` 仍是参数级/旁路控制，不应表述成已经完成 So-VITS-SVC 网络内部 Bias/Scale 条件注入。
- 主观评价结果文档为 `docs/subjective_eval_results.md`，当前评分待人工填写。
- 当前实验指标：
  - `records=56`
  - `final_loss=0.02664913423359394`
  - `tag_accuracy=0.952381`
  - `mse_for_numeric_controls=0.026125`
- 真实 Celery 任务已验证 3 个 prompt：
  - `清亮、少年感、男声`
  - `温柔、气声、抒情女声`
  - `低沉、成熟、厚重男声`
- 三个任务均满足：
  - `inference_mode=real`
  - `adapter_mode=trained`
  - `model_preset_id=final_primary`
  - `speaker=lain`
  - `duration_consistency=1.0`
  - `possible_dropouts=false`
- 后端测试：`PYTHONPATH=/home/featurize/work/BS/backend pytest backend/tests -q` 当前为 `102 passed`，并伴随环境级 warnings。
- 前端测试：`cd frontend && npm run test` 当前为 `6 passed`。
- 前端 `build` 已成功，但当前 Node `20.16.0` 低于 Vite 推荐版本 `20.19+` / `22.12+`，属于环境提示，不是功能失败；后续仍建议升级 Node。

## 3. 系统架构

前端采用 React + Vite，当前已重构为 `Header / Demo Workspace / Audio Compare / Advanced Details` 四区工作台。页面负责上传音频、输入 prompt、设置高级转换参数、触发默认 So-VITS-SVC 转换、执行基于 `WaveSurfer.js` 的 A/B 对比播放与下载，并把 `audio_quality`、Adapter、GPU telemetry 等技术字段收纳到默认折叠区。

后端采用 FastAPI + Celery + Redis，核心模块包括 `task_store`、So-VITS-SVC wrapper、`style_library`、`svc_model_presets`、`TextStyleEncoder`、`TextStyleAdapter`、`audio_quality` 与 GPU telemetry 记录。

```text
用户音频 + 文本提示词
-> /api/v1/upload
-> input_quality_summary + input_quality_report.json
-> vocals_id
-> /api/v1/convert
-> Celery task
-> style_library 匹配
-> SentenceTransformer 编码
-> TextStyleAdapter 生成控制参数
-> conversion_params.json 记录实际 F0 / slicing / padding 参数
-> So-VITS-SVC 推理
-> audio_quality + gpu_telemetry
-> /api/v1/tasks/{task_id}
-> /api/v1/tasks/{task_id}/result
```

## 3.1 当前与 SVC 示例效果差距的主要来源

- 当前 `final_primary / lain` 是可运行的默认演示模型，`final_male_youth / Nova_Adult` 与 `final_male_powerful / AY` 是已通过本地真实 smoke test 的专用男声 preset；这并不等于系统已经完成多风格全覆盖。
- `TextStyleAdapter` 目前仍是训练型参数级控制，不是 So-VITS-SVC 网络内部 Bias/Scale 注入。
- 输入音频质量、F0 提取方式、人声分离质量和转调参数会显著影响结果。
- 主观评价文档已经准备好，但人工评分仍待填写，因此当前效果归因证据还不完整。

下一步的主要提升方向是：为不同风格绑定更匹配的目标模型 preset，并结合消融实验与人工听评解释差距来源。

## 4. 功能特性

### 4.1 默认 SVC 主链路

- 支持上传音频。
- 可选择“输入已是纯人声/干声，跳过人声分离”。
- 完整歌曲可走人声分离与预处理。
- 纯人声可跳过分离。
- 上传阶段返回 `input_quality_summary`，用于提示输入质量与风险原因。
- 使用 `final_primary` 本地模型。
- 真实调用 `so-vits-svc/inference_main.py`。
- 支持 CUDA。
- 输出 `converted.wav`。

### 4.1.1 前端工作台与 WaveSurfer

- Header 区显示系统标题、真实 SVC、Celery、GPU、Adapter trained 状态徽章。
- Demo Workspace 区左侧负责上传音频与提示词，右侧负责任务状态与转换操作。
- Audio Compare 区基于 `WaveSurfer.js` 展示原始音频与转换音频波形。
- 若 `WaveSurfer.js` 初始化失败，前端自动 fallback 到原生 `audio controls`，不影响主流程。
- Advanced Details 默认折叠，用于集中展示 Adapter、输入质量、输出 `audio_quality`、GPU telemetry 和 StyleSinger 高级实验模式。

### 4.2 文本风格控制

- 使用 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`。
- 业务请求使用 `local_files_only=True`。
- 若本地文本编码器不存在，返回 `TEXT_ENCODER_MODEL_NOT_FOUND`，不会在业务请求中自动联网下载。
- 生成 `style_embedding.json` 和 `style_embedding.npy`。
- 前端只展示 embedding 摘要，不展示完整向量。

### 4.3 TextStyleAdapter

- 当前已接入训练型 TextStyleAdapter。
- 在线策略是 `trained` 优先，失败 `fallback` 到 `rule_based`。
- 输出控制参数：
  - `model_preset_id`
  - `transpose`
  - `brightness`
  - `power`
  - `breathiness`
  - `youthfulness`
  - `gender_hint`
  - `style_strength`
- 当前仍是参数级/旁路控制。
- 尚未完成 So-VITS-SVC 网络内部 Bias/Scale 条件注入。

### 4.3.1 高级转换参数

- 默认 So-VITS-SVC 转换请求支持：
  - `transpose`
  - `style_strength`
  - `model_preset_id`
- `f0_method`
- `auto_predict_f0`
- `slice_db`
- `clip_seconds`
- `pad_seconds`
- 前端高级参数区允许选择 `final_primary`、多风格占位 preset 与 `tech_villager fallback`。
- 默认仍使用 `final_primary`，不会自动切换到 `tech_villager`。
- 当前 So-VITS-SVC 4.1 集成里，除 `transpose` 外，其余参数会先记录进 `runtime/debug/<task_id>/conversion_params.json` 和 `sovits_command.txt`，不会强行透传到未知 CLI 参数位。

### 4.4 异步任务

- `SVC_USE_CELERY=true` 时，`/api/v1/convert` 只创建任务并返回 `task_id`。
- Celery worker 执行真实推理。
- Redis 用于 broker/result backend。
- `SVC_USE_CELERY=false` 时保留 `BackgroundTasks`/本地兼容模式。
- 任务状态同时落文件并同步 Redis。
- `/api/v1/tasks/{task_id}` 查询状态。
- `/api/v1/tasks/{task_id}/result` 下载结果。

### 4.5 音频质量评价

每次转换会生成 `runtime/debug/<task_id>/audio_quality_report.json`，指标包括：

- `duration`
- `sample_rate`
- `channels`
- `rms`
- `peak`
- `low_energy_ratio`
- `duration_mismatch_ratio`
- `duration_consistency`
- `possible_dropouts`

上传阶段还会生成 `input_quality_report.json` 并返回 `input_quality_summary`，当前输入质量字段包括：

- `duration`
- `sample_rate`
- `channels`
- `rms`
- `peak`
- `low_energy_ratio`
- `clipping_ratio`
- `silence_ratio`
- `is_too_short`
- `is_probably_silent`
- `quality_level`
- `warnings`

### 4.6 GPU telemetry

每次转换会生成 `runtime/debug/<task_id>/gpu_telemetry.txt`，并在 `sovits_command.txt` 中记录：

- `SOVITS_DEVICE`
- `CUDA_VISIBLE_DEVICES`
- `command_includes_d_cuda`
- 推理前/后 `nvidia-smi` 采样
- `query-compute-apps` 进程占用信息
- GPU 使用证据路径

当前实现以推理前后快照与命令参数、进程显存占用共同构成 GPU 使用证据。Featurize 平台图表中 CPU 占用高不等于未使用 GPU，因为音频预处理、F0、转码等阶段会大量使用 CPU；调试时应以 `sovits_command.txt` 与 `gpu_telemetry.txt` 为主。

### 4.7 StyleSinger 高级实验模式

- StyleSinger 不是默认主链路。
- 仅作为高级实验模式保留。
- 依赖 `ph/note/note_dur/note_type` 或可靠 metadata。
- 自动提取可能导致内容不一致。
- 不建议作为答辩默认演示链路。

## 5. 项目目录结构

```text
BS/
├── backend/
│   └── app/
│       ├── api/endpoints/synthesis.py
│       ├── core/celery_app.py
│       ├── config/
│       │   ├── svc_model_presets.json
│       │   └── style_adapter_config.json
│       ├── models_svc/
│       │   ├── sovits_wrapper.py
│       │   └── text_style_adapter.py
│       ├── services/
│       │   ├── audio_quality.py
│       │   ├── svc_task_service.py
│       │   └── text_style_encoder.py
│       └── workers/svc_tasks.py
├── frontend/
│   └── src/App.tsx
├── data/
│   └── style_adapter_pairs/metadata.jsonl
├── scripts/
│   ├── start_real_svc_demo.sh
│   ├── start_celery_worker.sh
│   ├── start_frontend_demo.sh
│   ├── prepare_text_encoder.py
│   ├── build_style_adapter_dataset.py
│   ├── train_text_style_adapter.py
│   ├── eval_text_style_adapter.py
│   ├── evaluate_audio_quality.py
│   ├── export_eval_report.py
│   └── export_subjective_eval_pack.py
└── docs/
    ├── celery_redis_runbook.md
    ├── style_adapter_training.md
    ├── evaluation_plan.md
    ├── experiment_report.md
    ├── subjective_eval_form.md
    └── subjective_eval_results.md
```

`runtime/`、`local_models/`、`so-vits-svc/` 不是需要提交到 Git 的源码目录，其中 `runtime/` 存放本地运行产物，`local_models/` 存放本地模型资产，`so-vits-svc/` 是第三方推理仓库，均受 `.gitignore` 管理。

## 6. 环境要求

- Linux / Featurize 服务器
- conda base
- Python 3.11
- `torch 2.8.0+cu128`
- CUDA 可用
- NVIDIA RTX 3060 已验证
- Node 当前是 `20.16.0`，Vite 推荐 `20.19+` 或 `22.12+`
- Redis
- Celery
- So-VITS-SVC 4.1 仓库
- ContentVec 预训练文件
- sentence-transformers 本地缓存模型

当前策略是使用服务器原有 conda base，不要求新建 conda/venv。

当前运行方式与后续 Docker 化需要区分：

- 当前答辩/Featurize 演示：使用服务器现有 conda base、Redis、Celery、FastAPI、Vite 前端和本地 `local_models/` 资产。
- 后续推荐部署产出：补充 Dockerfile / compose，将 CUDA、So-VITS-SVC、Redis/Celery、前后端启动流程容器化；当前仓库尚未实现 Docker 部署，不应把本机 base 运行方式描述成已 Docker 化。

## 7. 本地资产说明

以下目录或文件类型不提交 Git：

- `local_models/`
- `so-vits-svc/`
- `runtime/`
- `data/style_adapter_pairs/prepared/`
- `*.pth`
- `*.pt`
- `*.wav`
- `*.flac`
- `node_modules/`

说明：

- `local_models/sovits-final/final_primary/` 存放当前可用默认模型。
- `local_models/sovits-test/minecraft_villager/` 存放技术验收 fallback 模型。
- `runtime/debug/<task_id>/` 存放每次任务的 debug 产物。
- `runtime/style_adapter/` 存放训练 checkpoint 与评估摘要。
- `runtime/eval_reports/` 存放导出报告。

模型和音频文件不进入 GitHub。

## 8. 快速启动

当前 Featurize 服务器实际运行情况：

- 项目路径：`/home/featurize/work/BS`
- 后端 FastAPI 启动脚本：`bash scripts/start_real_svc_demo.sh`
- 后端 FastAPI 实际监听：`0.0.0.0:8000`
- API 前缀：`/api/v1`
- 前端 Vite 启动脚本：`bash scripts/start_frontend_demo.sh`
- 前端 Vite 实际监听：`0.0.0.0:3001`
- Redis 仅用于 Celery broker/backend
- Celery worker 仅为服务器内部后台进程

### 8.1 Featurize 推荐启动顺序

推荐使用 4 个终端，分别启动 Redis、Celery worker、FastAPI 后端和 Vite 前端。

#### 终端 1：Redis

```bash
cd /home/featurize/work/BS
redis-server --daemonize yes
redis-cli ping
```

预期输出：

```text
PONG
```

#### 终端 2：Celery worker

```bash
cd /home/featurize/work/BS
export PYTHONPATH=/home/featurize/work/BS/backend:$PYTHONPATH
export SVC_USE_CELERY=true
export SOVITS_MOCK=false
export SOVITS_DEVICE=cuda
export NUMBA_CACHE_DIR=/home/featurize/work/BS/runtime/numba_cache
celery -A app.core.celery_app.celery_app worker --loglevel=info -Q svc
```

预期看到：

- `[tasks]`
- 或 `svc.process_task`
- worker 正常 waiting for tasks

说明：

- 后端代码内部使用 `from app.xxx import ...`，所以 Celery worker 启动时必须把 `backend/` 加入 `PYTHONPATH`。
- 如果没有设置 `PYTHONPATH=/home/featurize/work/BS/backend:$PYTHONPATH`，常见报错是 `ModuleNotFoundError: No module named 'app'`。
- worker 和 FastAPI 必须使用同一套 `SOVITS_*` 环境变量，否则可能误走 mock 分支。

#### 终端 3：FastAPI 后端

```bash
cd /home/featurize/work/BS
bash scripts/start_real_svc_demo.sh
```

预期看到：

- `Uvicorn running on http://0.0.0.0:8000`
- `preset_id=final_primary`
- `speaker=lain`
- `SOVITS_DEVICE=cuda`

#### 终端 4：Vite 前端

```bash
cd /home/featurize/work/BS
bash scripts/start_frontend_demo.sh
```

预期看到：

- `Vite dev server running`
- `Network: http://...:3001`

前端必须监听 `0.0.0.0:3001`。如果输出只出现 `localhost` 或 `127.0.0.1`，需要检查 `scripts/start_frontend_demo.sh` 或 Vite 启动参数，确保包含：

```bash
--host 0.0.0.0
--port 3001
```

`start_real_svc_demo.sh` 会执行 fairseq Python 3.11 兼容 patch，读取 `svc_model_presets.json` 的 `active_preset_id`，并启动 FastAPI。

后端必须监听：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

也可以直接通过：

```bash
bash scripts/start_real_svc_demo.sh
```

启动，并确认输出：

- `Uvicorn running on http://0.0.0.0:8000`

为避免手工遗漏，也可以直接使用：

```bash
cd /home/featurize/work/BS
bash scripts/start_celery_worker.sh
```

详细步骤可参考：[Celery/Redis 运行手册](docs/celery_redis_runbook.md)、[So-VITS-SVC 真实推理说明](docs/sovits_real_inference.md)。

### 8.2 Featurize 公网端口暴露说明

Featurize 服务器内部进程与公网访问关系：

| 服务 | 本地端口 | 是否需要公网暴露 | 说明 |
|---|---:|---|---|
| Redis | 6379 | 否 | 仅 Celery broker/backend 内部使用，禁止暴露公网 |
| Celery worker | 无固定 HTTP 端口 | 否 | 后台任务进程，不对浏览器开放 |
| FastAPI 后端 | 8000 | 视情况 | 仅当前端不通过 Vite `/api` 代理时需要暴露 |
| Vite 前端 | 3001 | 是 | 浏览器访问演示页面 |

必须明确：

- 前端页面必须通过 Featurize 暴露的 `3001` 端口访问。
- 后端必须监听 `0.0.0.0:8000`。
- 前端必须监听 `0.0.0.0:3001`。
- Redis 和 Celery worker 不需要暴露公网。
- 不要把 Redis `6379` 暴露到公网。

补充说明：Vite 默认常见端口是 `5173`，但本项目当前实际前端端口为 `3001`。README 的快速启动和 Featurize 公网暴露说明均以 `3001` 为准。

### Featurize 端口暴露命令

本项目当前前端实际运行在 `3001` 端口。启动前端后，在服务器终端执行：

```bash
featurize port export 3001
```

命令会输出类似：

```text
Local port 3001 has been exported to 60623
You can visit http://workspace.featurize.cn:60623 if it's a http server
```

浏览器应访问 Featurize 输出的公网地址，例如：

```text
http://workspace.featurize.cn:60623
```

不要在本地浏览器访问：

- `http://0.0.0.0:3001`
- `http://127.0.0.1:3001`
- `http://localhost:3001`

这些地址只对服务器内部或本机环境有意义，不是公网访问地址。

每台 Featurize 服务器最多只能暴露 `10` 个端口。如果 `featurize port export` 失败，先查看已暴露端口：

```bash
featurize port list
```

删除不需要的端口暴露规则：

```bash
featurize port unexport <端口或规则编号>
```

具体参数以 `featurize port list` 输出和 Featurize 命令提示为准。

两种访问方式：

方式 A：推荐，只暴露前端 `3001`

- 条件：前端 Vite 已配置 `/api` 代理到 `http://127.0.0.1:8000`。
- 步骤：
  - 启动 Redis、Celery worker、FastAPI 后端、Vite 前端
  - 执行 `featurize port export 3001`
  - 复制 Featurize 输出的公网地址
  - 浏览器访问该公网地址
- 前端请求 `/api/v1/...`，由 Vite dev server 代理到服务器内部 `127.0.0.1:8000`。
- 这种方式只需要公网暴露 `3001`。

方式 B：同时暴露 `3001` 和 `8000`

- 适用于前端直接请求后端公网地址的情况。
- 步骤：
  - 暴露前端：`featurize port export 3001`
  - 暴露后端：`featurize port export 8000`
- 前端需要配置 API Base URL 指向 `8000` 公网地址。
- 如果浏览器中请求的是 `localhost:8000` 或 `127.0.0.1:8000`，它指向的是用户自己的电脑，不是 Featurize 服务器，因此会失败。

如果页面能打开但转换时报 API 连接失败，优先检查：

- 后端 `8000` 是否正在运行
- 前端是否通过 `/api` 代理到 `8000`
- Featurize 是否暴露了必要端口
- 浏览器 Network 里请求的 API 地址是否正确
- 是否错误请求了 `localhost:8000`

### 8.3 Featurize 端口暴露后的访问方式

1. 在 Featurize 控制台或端口转发/公网访问页面中添加端口：
   - `3001`：前端页面
   - `8000`：后端 API，仅当没有 Vite `/api` proxy 时需要
2. 复制 Featurize 给出的 `3001` 公网地址，在浏览器打开。
3. 不要在本地浏览器直接访问：
   - `http://0.0.0.0:3001`
   - `http://127.0.0.1:3001`
   - `http://localhost:3001`
   - `http://127.0.0.1:8000`
   因为这些地址只在服务器内部有效。
4. 服务器内部自检可以用：

```bash
curl http://127.0.0.1:8000/api/v1/system/health
curl http://127.0.0.1:8000/api/v1/system/sovits-check
```

### 8.4 Featurize 访问常见问题

1. 页面打不开
   - 检查前端是否启动
   - 检查前端是否监听 `0.0.0.0:3001`
   - 检查是否已执行 `featurize port export 3001`
   - 检查 Featurize 输出的公网端口是否正确
   - 检查是否误访问了 `0.0.0.0:3001`、`127.0.0.1:3001` 或 `localhost:3001`

2. 页面能打开，但上传/转换失败
   - 检查后端 `8000` 是否启动
   - 检查前端是否通过 `/api` 代理到 `127.0.0.1:8000`
   - 如果没有代理，检查是否执行 `featurize port export 8000`
   - 打开浏览器开发者工具 Network，确认 API 请求地址
   - 不应错误请求用户本机 `localhost:8000`

3. Celery 启动时报 `No module named app`
   - 使用正确命令：

```bash
export PYTHONPATH=/home/featurize/work/BS/backend:$PYTHONPATH
celery -A app.core.celery_app.celery_app worker --loglevel=info -Q svc
```

4. worker 启动后任务误走 mock
   - 确保 worker 启动前设置：

```bash
export SOVITS_MOCK=false
export SOVITS_DEVICE=cuda
```

   - worker 和 FastAPI 必须使用同一套 `SOVITS_*` 环境变量

5. GPU 图表看起来像 CPU 在跑
   - 音频预处理、F0、转码会使用 CPU
   - 判断 GPU 是否参与应看 `runtime/debug/<task_id>/sovits_command.txt` 和 `gpu_telemetry.txt`
   - 确认 `command_includes_d_cuda=true`

6. `8000` 端口占用
   - 使用：

```bash
ss -ltnp | grep ':8000'
```

   - 或：

```bash
pkill -f "uvicorn app.main:app"
```

   - 再重启后端

### 8.5 公网 API 自检命令

服务器内部检查：

```bash
curl http://127.0.0.1:8000/api/v1/system/health
curl http://127.0.0.1:8000/api/v1/system/sovits-check
```

公网检查：

如果 Featurize 暴露了 `8000`，把 `<BACKEND_PUBLIC_URL>` 替换为 Featurize 后端公网地址：

```bash
curl <BACKEND_PUBLIC_URL>/api/v1/system/health
curl <BACKEND_PUBLIC_URL>/api/v1/system/sovits-check
```

如果只暴露 `3001` 且使用 Vite proxy，则在浏览器开发者工具 Network 中确认 `/api/v1/system/health` 返回 `200`。

### 8.6 兼容：非 Celery 本地模式

设置 `SVC_USE_CELERY=false` 后，`/api/v1/convert` 会继续使用本地 `BackgroundTasks`/内存兼容模式，适合快速开发和单测。

## 9. API 说明

当前真实 API 如下：

- `GET /api/v1/system/health`
- `GET /api/v1/system/sovits-check`
- `POST /api/v1/upload`
- `POST /api/v1/convert`
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/tasks/{task_id}/result`
- `POST /api/v1/extract_features`
- `POST /api/v1/tasks`

`POST /api/v1/tasks` 属于 StyleSinger 高级实验模式，不是默认 SVC 主链路。默认 SVC 转换只走 `POST /api/v1/convert`。

最小 `curl` 示例：

1. 上传音频

```bash
curl -X POST http://127.0.0.1:8000/api/v1/upload \
  -F "file=@demo.wav"
```

2. 发起转换

```bash
curl -X POST http://127.0.0.1:8000/api/v1/convert \
  -H "Content-Type: application/json" \
  -d '{
    "vocals_id": "REPLACE_WITH_VOCALS_ID",
    "prompt_text": "清亮、少年感、男声",
    "style_strength": 0.8,
    "model_preset_id": "final_primary"
  }'
```

3. 查询任务

```bash
curl http://127.0.0.1:8000/api/v1/tasks/REPLACE_WITH_TASK_ID
```

4. 下载结果

```bash
curl -L http://127.0.0.1:8000/api/v1/tasks/REPLACE_WITH_TASK_ID/result \
  -o converted.wav
```

## 10. TextStyleAdapter 数据与训练

数据文件为 `data/style_adapter_pairs/metadata.jsonl`，当前规模为 `56` 条人工样例，覆盖风格包括：

- 清亮/明亮/清澈
- 厚重/有力/摇滚
- 温柔/气声/抒情
- 少年感/男声
- 女声/流行
- 低沉/成熟
- `tech_villager` 技术验收样例

训练命令：

```bash
python scripts/build_style_adapter_dataset.py
python scripts/train_text_style_adapter.py
python scripts/eval_text_style_adapter.py
```

当前结果：

- `records=56`
- `epochs=80`
- `final_loss=0.02664913423359394`
- `tag_accuracy=0.952381`
- `mse_for_numeric_controls=0.026125`

`runtime/style_adapter/text_style_adapter_v1.pt` 不提交 Git，仅作为本地训练产物。

更多说明可参考：[Adapter 训练说明](docs/style_adapter_training.md)。

## 11. 实验与评价

实验报告见：[实验报告](docs/experiment_report.md)。

主观评价模板见：[主观评价表](docs/subjective_eval_form.md)。

当前主观评价结果文档见：[主观评价结果](docs/subjective_eval_results.md)。

导出主观评价包：

```bash
python scripts/export_subjective_eval_pack.py
```

当前 3 个真实 Celery 任务如下：

- `b7c03828-e10d-4552-ac51-63f9dececfba`，prompt：`清亮、少年感、男声`
- `1a9d1b8b-a090-448e-b6e8-1252dc2ff5d3`，prompt：`温柔、气声、抒情女声`
- `4e703d1d-4af6-475b-9c29-a7a8fd0f8b3b`，prompt：`低沉、成熟、厚重男声`

共同结果：

- `inference_mode=real`
- `adapter_mode=trained`
- `model_preset_id=final_primary`
- `speaker=lain`
- `duration_consistency=1.0`
- `low_energy_ratio=0.277992 / 0.26834 / 0.262548`
- `possible_dropouts=false`

主观评价维度：

- 风格符合度
- 自然度
- 歌词可懂度
- 原旋律保持
- 总体满意度

目前 `docs/subjective_eval_results.md` 已预填这 3 个真实任务的基础信息，但主观评分仍待人工填写汇总。

## 12. 测试与验证

后端：

```bash
python -m compileall backend/app scripts/*.py
PYTHONPATH=/home/featurize/work/BS/backend pytest backend/tests -q
```

当前结果：`99 passed`

前端：

```bash
cd frontend
npm run build
npm run test
```

当前结果：`6 passed`

脚本语法检查：

```bash
bash -n scripts/start_real_svc_demo.sh
bash -n scripts/start_frontend_demo.sh
bash -n scripts/run_sovits_real_cuda_check.sh
bash -n scripts/export_demo_assets.sh
bash -n scripts/smoke_test_final_svc_model.sh
bash -n scripts/replace_with_final_svc_model.sh
```

## 13. 已知限制

1. 当前 TextStyleAdapter 是训练型参数级旁路控制，不是 So-VITS-SVC 网络内部 Bias/Scale 注入。
2. 当前 `56` 条样例仍是小规模原型数据，不足以支撑强泛化结论。
3. 当前 `final_primary/lain` 是可运行的默认演示模型，但不代表所有风格都能高度贴合。
4. StyleSinger 高级模式输出可能与原内容不一致，不作为默认演示。
5. 主观听评尚未正式完成。
6. Node 版本低于 Vite 推荐版本，但当前构建通过。
7. 训练产物和模型资产只保留在服务器本地，不提交 Git。

## 14. 后续工作

- 扩充 `style_adapter_pairs` 到更大规模。
- 填写并汇总主观听评结果。
- 增加更多 `final_*` model preset。
- 将 Adapter 输出扩展为 So-VITS-SVC 网络中间层 Bias/Scale 条件注入。
- 继续优化 WaveSurfer.js 交互与前端演示细节。
- 增加更系统的客观指标，如 F0 连续性、MCD、说话人相似度、MOS 等。
- 整理论文章节和答辩材料。

## 15. Git 与资产管理

不提交：

- `local_models/`
- `so-vits-svc/`
- `runtime/`
- `node_modules/`
- `*.pth`
- `*.pt`
- `*.wav`
- `*.flac`
- `data/style_adapter_pairs/prepared/`

提交：

- 源码
- 配置模板
- 脚本
- 文档
- 小规模 `metadata.jsonl`
- 测试代码

提交前执行：

```bash
git diff --cached --name-only | grep -E '(^runtime/|^local_models/|^so-vits-svc/|\.pth$|\.pt$|\.wav$|\.flac$|^data/style_adapter_pairs/prepared/)' || true
```

无输出再 commit。

## 相关文档

- [Celery/Redis 运行手册](docs/celery_redis_runbook.md)
- [Adapter 训练说明](docs/style_adapter_training.md)
- [实验报告](docs/experiment_report.md)
- [主观评价表](docs/subjective_eval_form.md)
- [主观评价结果](docs/subjective_eval_results.md)
- [So-VITS-SVC 真实推理说明](docs/sovits_real_inference.md)
- [评价计划](docs/evaluation_plan.md)
