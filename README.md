# 基于文本提示词控制的歌声风格转换系统

## 项目简介

本项目是面向本科毕业设计的 B/S 架构歌声风格转换系统。用户上传干声音频、输入文本风格提示词，系统在真实 So-VITS-SVC 链路上执行转换，并展示任务状态、结果下载、关键指标和技术链路元数据。

当前阶段的核心目标是验证“文本提示词 -> 风格调制 -> 歌声转换”的工程可执行性与可复现性。

## 当前技术栈

- 前端：React + Vite + TypeScript
- 后端：FastAPI
- 异步任务：Celery + Redis
- 推理主链路：So-VITS-SVC
- 文本条件控制：TextStyleAdapter + internal_film

## 当前核心功能

- 音频上传与基础质量检查
- 文本风格提示词输入
- So-VITS-SVC 真实转换任务提交与轮询
- internal_film 条件注入执行
- 训练型 TextStyleAdapter 加载状态展示
- 关键指标对比（输入/输出/变化）
- 技术链路 metadata 展示
- 转换结果播放器与下载

## 当前模型与配置状态

- 默认模型预设：`final_primary`
- 默认目标音色：`lain`
- 训练适配器 checkpoint：`runtime/style_adapter/text_style_adapter_1000.pt`
- 当前链路可在任务 metadata 中看到：
  - `condition_mode=internal_film`
  - `executed_internal_film=true`
  - `text_style_adapter_loaded=true`
  - `adapter_mode=trained`
  - `adapter_type=trained_mlp`

说明：`text_style_adapter_1000.pt` 属于本地运行产物，不提交仓库。

## 训练实验摘要（1000 样本）

- 数据来源：GTSinger 配对样本 1000 条
- 数据划分：`train/val/test = 800/100/100`
- 训练轮次：`epochs=15`
- 最优轮次：`best_epoch=15`
- 验证损失：`best_val_loss=4.209e-05`
- 测试损失：`test_loss=1.559e-05`
- checkpoint 核验：
  - `missing=[]`
  - `has_model_state_dict=true`
  - `has_sample_embeddings=true`

## 前端当前展示形态

- 宽屏三栏工作台布局（左：上传/提示词；中：状态/结果；右：指标/技术链路）
- 主页面已删除重复的“转换前后音频对比”大卡片
- 主界面字段中文化展示
- 英文工程字段仅保留在折叠“字段说明”中

## 运行方式

### 1) 启动后端（真实链路）

```bash
bash scripts/start_real_svc_demo.sh
```

或：

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2) 启动 Celery Worker

```bash
bash scripts/start_celery_worker.sh
```

等价核心命令：

```bash
PYTHONPATH=$(pwd)/backend:$PYTHONPATH celery -A app.core.celery_app.celery_app worker --loglevel=info -Q svc
```

### 3) 启动前端

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

## 测试与构建命令

后端：

```bash
PYTHONPATH=$(pwd)/backend:$PYTHONPATH pytest backend/tests -q
```

前端测试：

```bash
cd frontend
npm run test -- --run
```

前端构建：

```bash
cd frontend
npm run build
```

## 已知限制与边界

- 文本提示词中的“男声”仅是风格方向提示，不会自动切换目标音色。
- 当前默认模型预设与目标音色是 `final_primary / lain`，输出主音色仍由该组合决定。
- 当前训练对象是轻量 TextStyleAdapter，不是从头训练完整 So-VITS-SVC 主模型。
- internal_film 结果用于证明链路可执行，不代表主观听感结论已经完成。
- 主观听评仍需人工补充。
- 模型权重、数据集和运行时音频产物不随仓库提交。
- Node `20.16.0` 可能出现 Vite 版本提示；Vite 推荐 Node `20.19+` 或 `22.12+`。

## 数据与模型资产说明

以下目录或文件类型不提交仓库：

- `runtime/`
- `datasets/`
- `local_models/`
- `*.pt` `*.pth` `*.ckpt` `*.onnx` `*.safetensors`
- `*.wav` `*.mp3` `*.flac` `*.npy`

本项目运行前需在本地准备 So-VITS-SVC 模型资产与依赖。

## 相关文档

- [最终验收摘要](docs/final_acceptance_summary.md)
- [训练实验报告](docs/training_experiment_report.md)
- [真实推理说明](docs/sovits_real_inference.md)
- [演示运行手册](docs/demo_runbook.md)
- [模型资产说明](docs/model_assets_setup.md)
- [模型预设说明](docs/model_preset_guide.md)
