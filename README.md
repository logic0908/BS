# 基于文本提示词控制的歌声风格转换系统

## 1. 项目简介

本项目是一个面向本科毕业设计的 B/S 架构歌声风格转换系统。用户上传清唱人声或干声音频，输入自然语言风格提示词，系统通过 So-VITS-SVC 完成歌声转换，并在前端提供任务状态、波形对比、结果下载和调试证据查看能力。

项目的工程重点不是“生成任意歌手声音”，也不是“完美复刻音色”，而是验证文本提示词与 So-VITS-SVC 转换过程之间的工程连接方式：系统通过文本风格编码器生成 `style_emb`，再将其注入 So-VITS-SVC 推理阶段的中间隐空间，实现文本条件驱动的内部 Bias/Scale / FiLM 调制机制。

当前仓库的准确表述应为：

- 已实现文本提示词驱动的 So-VITS-SVC 内部条件调制机制；
- 已完成真实 GPU smoke 验证；
- 该机制证明“内部条件注入链路可执行”，不等于“已经训练完成强文本风格控制模型”。

旧阶段的方案说明中曾出现 Vue 3 / Element Plus 描述；当前维护中的主前端已经是 **React + Vite + TypeScript**，入口文件为 [frontend/src/main.tsx](frontend/src/main.tsx) 和 [frontend/src/App.tsx](frontend/src/App.tsx)。

## 2. 核心功能

- 音频上传与管理
- 歌声 / 人声转换任务提交
- 文本风格提示词输入
- So-VITS-SVC 真实推理
- 文本向量生成（`TextStyleEncoder`）
- 内部 Bias/Scale / FiLM 条件注入（`StyleFiLMAdapter`）
- 任务状态查询
- 转换结果下载
- A/B 波形播放与结果预览
- `none / external_preset / internal_film` 消融实验支持
- `style_embedding.pt`、`conditioning_report.json`、`sovits_command.txt` 等 debug metadata 记录

## 3. 系统架构

### 前端

- React
- Vite
- TypeScript
- 主要入口文件：
  - [frontend/src/main.tsx](frontend/src/main.tsx)
  - [frontend/src/App.tsx](frontend/src/App.tsx)

### 后端

- FastAPI
- Celery
- Redis
- PyTorch
- So-VITS-SVC

### 模型链路

- `TextStyleEncoder`
- `StyleFiLMAdapter`
- `SoVitsSvcEngine` / `sovits_wrapper.py`
- `inference_conditioned.py`

### 架构图（文字版）

```text
用户浏览器
  -> React 前端
  -> FastAPI 后端
  -> Celery Worker
  -> TextStyleEncoder
  -> So-VITS-SVC conditioned inference
  -> converted.wav
  -> 前端播放 / 下载
```

## 4. 文本条件内部注入机制

这是当前项目最重要的工程亮点。

- 输入：`style_prompt`
- 文本编码：`style_emb`
- 调制模块：`StyleFiLMAdapter`
- 调制公式：

```text
h_cond = h * (1 + gamma(c)) + beta(c)
```

- 当前真实注入点：
  So-VITS-SVC 推理阶段，`SynthesizerTrn.infer()` 中 `flow` 输出隐变量 `z` 之后、`decoder / generator` 输入之前。
- 当前证据：
  在 `internal_film` 模式下，`runtime/debug/<task_id>/conditioning_report.json` 中可见 `executed_internal_film=true`。

实现文件：

- [backend/app/services/text_style_encoder.py](backend/app/services/text_style_encoder.py)
- [backend/app/models_svc/style_film.py](backend/app/models_svc/style_film.py)
- [backend/app/models_svc/sovits_wrapper.py](backend/app/models_svc/sovits_wrapper.py)
- [backend/app/models_svc/inference_conditioned.py](backend/app/models_svc/inference_conditioned.py)

需要强调：

- 这里证明的是“内部条件注入机制可执行”；
- 不是“已训练完成强文本风格控制模型”；
- 后续仍需要更多主观听感与客观指标实验来评估控制效果。

## 5. 目录结构

当前仓库的真实主结构如下：

```text
backend/
  app/
    api/
    config/
    models_svc/
    services/
    workers/
  requirements-core.txt
  requirements-dev.txt
  requirements-enhanced.txt
  requirements.txt
  tests/
frontend/
  src/
docs/
scripts/
data/                  # 默认不提交数据，仅保留说明文件/占位符
runtime/               # ignored
local_models/          # ignored
so-vits-svc/           # 本地第三方依赖，默认 ignored
StyleSinger/           # 保留的高级实验分支
```

说明：

- 当前配置文件不在顶层 `config/`，而是在：
  - `backend/app/config/style_library.json`
  - `backend/app/config/svc_model_presets.json`
- 当前主前端不在 Vue 子目录，真实入口是 `frontend/src/main.tsx` 和 `frontend/src/App.tsx`。

默认不应上传到 GitHub 的目录 / 文件包括：

- `runtime/`
- `local_models/`
- `datasets/`
- `checkpoints/`
- `data/`
- `*.pth`
- `*.ckpt`
- `*.pt`
- `*.onnx`
- `*.safetensors`
- `*.wav`
- `*.mp3`
- `*.flac`
- `node_modules/`

## 6. 环境要求

- Python：推荐 **3.11**
- Node.js：当前在 **20.16.0** 下已验证可以 `build`，但 Vite 会提示推荐 **20.19+** 或 **22.12+**
- Redis：用于 Celery broker / result backend
- FFmpeg：音频处理建议安装
- PyTorch：真实推理需要
- So-VITS-SVC：需要本地仓库和本地模型权重
- CUDA / GPU：可选，但真实 So-VITS-SVC 推理强烈建议使用 GPU

## 7. 安装步骤

### 7.1 克隆仓库

```bash
git clone <your-repo-url>
cd BS
```

### 7.2 后端依赖

推荐使用 conda：

```bash
conda create -n bs-svc python=3.11 -y
conda activate bs-svc
pip install -r requirements.txt
pip install -r backend/requirements-dev.txt
```

如果需要附加实验依赖：

```bash
pip install -r backend/requirements-enhanced.txt
```

说明：

- 顶层 `requirements.txt` 只是便捷入口，实际指向 `backend/requirements.txt`
- `backend/requirements.txt` 当前对应 `backend/requirements-core.txt`

### 7.3 前端依赖

```bash
cd frontend
npm install
npm run dev
```

构建命令：

```bash
cd frontend
npm run build
```

### 7.4 Redis / Celery / FastAPI

启动 Redis：

```bash
redis-server --daemonize yes
```

启动 FastAPI：

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

启动 Celery worker：

```bash
export PYTHONPATH="$(pwd)/backend"
celery -A app.core.celery_app.celery_app worker --loglevel=info -Q svc
```

项目内也提供了辅助脚本：

- [scripts/start_real_svc_demo.sh](scripts/start_real_svc_demo.sh)
- [scripts/start_celery_worker.sh](scripts/start_celery_worker.sh)
- [scripts/start_celery_gpu_worker.sh](scripts/start_celery_gpu_worker.sh)
- [scripts/start_frontend_demo.sh](scripts/start_frontend_demo.sh)

## 8. 环境变量

### 基础 So-VITS-SVC 相关

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
```

### 文本条件内部注入相关

```bash
SOVITS_CONDITION_MODE=internal_film
SOVITS_STYLE_DIM=256
SOVITS_FILM_STRENGTH=0.10
SOVITS_FILM_TARGET=pre_decoder
SOVITS_STYLE_EMB_FORMAT=pt
```

解释：

- `SOVITS_CONDITION_MODE=internal_film`：启用文本内部条件注入
- `SOVITS_CONDITION_MODE=none`：关闭内部条件注入，使用原始 So-VITS-SVC
- `SOVITS_MOCK=true`：使用 Mock 路径，适合无模型环境
- `SOVITS_MOCK=false`：使用真实 So-VITS-SVC

## 9. 启动方式

### 推荐本地启动顺序

1. 启动 Redis
2. 启动 Celery worker
3. 启动 FastAPI
4. 启动前端
5. 浏览器访问前端地址

当前默认端口：

- FastAPI：`http://127.0.0.1:8000`
- Vite：`http://127.0.0.1:3001`

前端通过 Vite 代理 `/api` 到本地 FastAPI。

## 10. API 示例

### 10.1 上传音频

```http
POST /api/v1/upload
```

### 10.2 创建转换任务

```http
POST /api/v1/convert
Content-Type: application/json
```

请求体示例（以真实代码字段为准）：

```json
{
  "vocals_id": "your-vocals-id",
  "prompt_text": "温柔、明亮、流行感更强的女声风格",
  "style_prompt": "温柔、明亮、流行感更强的女声风格",
  "style_strength": 0.65,
  "model_preset_id": "final_primary",
  "transpose": 0,
  "engine": "sovits"
}
```

### 10.3 查询任务状态

```http
GET /api/v1/tasks/{task_id}
```

### 10.4 下载结果

```http
GET /api/v1/tasks/{task_id}/result
```

更多接口说明见：

- [backend/app/api/endpoints/synthesis.py](backend/app/api/endpoints/synthesis.py)
- [docs/demo_runbook.md](docs/demo_runbook.md)

## 11. Smoke 验证结果

当前已经完成一轮真实 GPU smoke 验证，摘要如下：

- GPU：`NVIDIA GeForce RTX 3080`
- 输入音频：`44100 Hz`，`8.18s`
- baseline `none` 输出：可读，`44100 Hz`，`8.18s`，无 `NaN/Inf`
- `internal_film` 输出：可读，`44100 Hz`，`8.18s`，无 `NaN/Inf`
- `conditioning_report.json`：存在
- `executed_internal_film=true`
- `style_embedding.pt`：存在

详细记录已同步写入文档与 debug 证据文件，适合作为“机制已接入并已完成真实 smoke 验证”的论文实验前置证据，但不应直接上升为完整效果结论。

## 12. 消融实验设计

当前建议至少保留三组：

- `none`：无内部文本条件注入
- `external_preset`：只使用外部风格预设 / 参数映射
- `internal_film`：文本向量内部 Bias/Scale 注入

同时建议比较不同 `film_strength`：

- `0.05`
- `0.10`
- `0.15`

当前状态说明：

- 已完成 `film_strength=0.10` 的真实 smoke
- `0.05 / 0.15` 可作为后续实验配置

参考文档：

- [docs/effect_ablation_report.md](docs/effect_ablation_report.md)
- [docs/experiment_report.md](docs/experiment_report.md)

## 13. 测试

后端：

```bash
PYTHONPATH=$(pwd)/backend pytest backend/tests -q
```

前端：

```bash
cd frontend
npm run test -- --run
npm run build
```

注意：

- 当前前端在 Node `20.16.0` 下已验证可以通过 `test` 和 `build`
- 但 Vite 仍可能提示推荐更高 Node 版本

## 14. 已知限制

- 当前系统已实现内部条件注入机制，但没有基于大规模风格标注数据完成强文本控制训练
- 文本提示词控制效果仍需要进一步主观听感和客观指标验证
- 不建议将本项目表述为商业级声音克隆系统
- 模型文件和数据集不随仓库发布
- 真实推理依赖本地 So-VITS-SVC 模型权重和配置文件
- GPU、CUDA、第三方依赖版本差异会影响运行稳定性
- `StyleSinger` 仍保留在仓库中，但当前默认主链路是 So-VITS-SVC

## 15. 伦理与使用说明

- 不应用于未经授权的声音模仿
- 不上传含隐私或版权争议的音频
- 不将本项目直接用于商业声音克隆或身份冒充
- 本项目主要用于学习、科研和本科毕业设计展示

## 16. License

本仓库当前采用 [MIT License](LICENSE)。

补充说明：

- 第三方 So-VITS-SVC、StyleSinger、模型权重、数据集遵循其各自原始许可证
- 本仓库不重新分发受限模型权重
- `license_unknown` 的本地模型 preset 仅适合内部复核或毕业设计技术演示，不应被当作已完成公开授权清理的发布资产

## 相关文档

- [So-VITS-SVC 真实推理说明](docs/sovits_real_inference.md)
- [消融实验报告](docs/effect_ablation_report.md)
- [实验报告](docs/experiment_report.md)
- [演示运行手册](docs/demo_runbook.md)
- [模型预设说明](docs/model_preset_guide.md)
- [GitHub 发布检查清单](docs/github_release_checklist.md)
