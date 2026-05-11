# 异步任务工作进程与 Redis 运行手册

## 1. 启动 Redis

```bash
redis-server --daemonize yes
```

Redis 只用于本机 Celery broker/backend，不暴露公网。

## 2. 启动 Celery 工作进程

普通启动方式仍保留：

```bash
cd /home/featurize/work/BS
export PYTHONPATH=/home/featurize/work/BS/backend:$PYTHONPATH
export SVC_USE_CELERY=true
export SOVITS_MOCK=false
export SOVITS_DEVICE=cuda
export NUMBA_CACHE_DIR=/home/featurize/work/BS/runtime/numba_cache
celery -A app.core.celery_app.celery_app worker --loglevel=info -Q svc
```

也可以直接使用：

```bash
cd /home/featurize/work/BS
bash scripts/start_celery_worker.sh
```

如果任务是 GPU 实时推理、真实 So-VITS-SVC 冒烟测试或 v1.3 消融实验，推荐使用专用 `solo` GPU 工作进程：

```bash
cd /home/featurize/work/BS
bash scripts/start_celery_gpu_worker.sh
```

该脚本会固定：

- `SVC_USE_CELERY=true`
- `SOVITS_MOCK=false`
- `SOVITS_DEVICE=cuda`
- `CUDA_VISIBLE_DEVICES=0`
- `NVIDIA_VISIBLE_DEVICES=0`
- `PYTORCH_NVML_BASED_CUDA_CHECK=1`
- `--pool=solo --concurrency=1`

## 3. 启动 FastAPI

```bash
cd /home/featurize/work/BS
bash scripts/start_real_svc_demo.sh
```

建议在 `backend/.env` 中确认：

```bash
REDIS_URL=redis://localhost:6379/0
CELERY_TASK_ALWAYS_EAGER=false
SVC_USE_CELERY=true
```

重要说明：

- Celery 工作进程必须与 FastAPI 使用同一套 conda base 环境。
- Celery 工作进程必须与 FastAPI 使用同一组 `SOVITS_*` 环境变量。
- GPU 工作进程必须与 FastAPI 使用同一套 `SOVITS_REPO_DIR`、`SOVITS_INFER_SCRIPT`、`SOVITS_DEVICE`、`CUDA_VISIBLE_DEVICES`、`NUMBA_CACHE_DIR` 等运行时变量。
- 如果工作进程没有把 `/home/featurize/work/BS/backend` 放入 `PYTHONPATH`，可能出现 `ModuleNotFoundError: No module named 'app'`。
- 如果工作进程没有继承与 FastAPI 一致的 `SOVITS_MOCK`、`SOVITS_DEVICE`、`SOVITS_REPO_DIR`、`SOVITS_INFER_SCRIPT` 等变量，可能误走 mock，或者加载到错误的推理配置。
- Redis 不暴露公网。
- Celery 工作进程不暴露公网。
- 如果使用 `prefork`，真实 So-VITS-SVC CUDA 推理可能在 `ForkPoolWorker` 子进程里出现 GPU 不可见或多任务争用问题。
- 因此，GPU 推理与消融实验推荐 `solo` 工作进程，而不是默认 `prefork`。

## 4. 启动前端

```bash
cd /home/featurize/work/BS
bash scripts/start_frontend_demo.sh
```

## 5. 说明

- 默认 SVC 按钮仍然只调用 `POST /api/v1/convert`。
- 当前 `POST /api/v1/convert` 会创建任务并返回 `task_id`，真实 So-VITS-SVC 转换由 Celery 工作进程执行。
- 如果需要兼容旧的本地模式，可设置 `SVC_USE_CELERY=false`，系统会回退到 FastAPI `BackgroundTasks` + 内存任务模式。
- 普通 Celery 启动方式继续保留，但 GPU 推理/消融实验优先使用 `bash scripts/start_celery_gpu_worker.sh`。
- 默认演示模型仍是 `final_primary / lain`。
- `final_male_powerful / AY` 当前已通过本地真实冒烟测试，可作为专用男声模型预设使用，但不是默认演示模型。
- `tech_villager` 仍只是技术验收回退模型。
- `allow_preset_fallback` 默认关闭；只有显式开启时才允许回退到 `final_primary/lain`，并且必须展示 requested/effective preset 与 fallback reason。
