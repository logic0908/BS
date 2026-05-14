# 异步任务证据清单（FastAPI + Redis + Celery）

## 1. 目标

用于证明“任务创建 -> 入队 -> 执行 -> 查询 -> 结果下载”链路真实可复现。

## 2. 证据项清单

| 证据项 | 关键内容 | 代码/文档依据 | 建议截图编号 | 状态 |
| --- | --- | --- | --- | --- |
| FastAPI 服务启动 | 监听端口、启动成功 | `scripts/start_real_svc_demo.sh`，`README.md` | 图4-9 | 需补充截图 |
| Redis 服务启动 | Redis 进程可用 | `docs/celery_redis_runbook.md` | 图4-10 | 需补充截图 |
| Celery Worker 启动 | 队列 `svc`，worker 在线 | `scripts/start_celery_worker.sh` | 图4-11 | 需补充截图 |
| 任务入队 | `/api/v1/convert` 返回 `task_id` 且 `status=queued` | `backend/app/api/endpoints/synthesis.py` | 图4-4 | 需补充截图 |
| 任务执行完成 | `/api/v1/tasks/{task_id}` 返回 `succeeded` | `backend/app/api/endpoints/synthesis.py` | 图4-5 | 需补充截图 |
| 结果下载 | `/api/v1/tasks/{task_id}/result` 返回 wav 文件流 | `backend/app/api/endpoints/synthesis.py` | 图4-5 | 需补充截图 |
| metadata 可解释字段 | `model_preset_id/speaker/condition_mode/executed_internal_film` | `synthesis.py` 返回结构 | 图4-7 | 需补充截图 |

## 3. 建议运行命令（不伪造结果）

```bash
# 1) Redis
redis-server --daemonize yes

# 2) FastAPI
cd /home/featurize/work/BS
bash scripts/start_real_svc_demo.sh

# 3) Celery Worker
cd /home/featurize/work/BS
bash scripts/start_celery_worker.sh
```

可选：如果做前端联调，另开终端

```bash
cd /home/featurize/work/BS/frontend
npm run dev -- --host 0.0.0.0
```

## 4. API 证据采集建议

1. 调用 `POST /api/v1/upload`，记录 `vocals_id`。
2. 调用 `POST /api/v1/convert`，记录 `task_id`。
3. 轮询 `GET /api/v1/tasks/{task_id}`，记录状态变化（queued -> running -> succeeded/failed）。
4. 成功后调用 `GET /api/v1/tasks/{task_id}/result`，保存输出音频。
5. 对应保存 `runtime/debug/<task_id>/` 下的 `prompt.json`、`task_config.json`、`sovits_command.txt`、`converted.wav`。

## 5. 需补充截图编号汇总

- 图4-9（FastAPI 启动日志）
- 图4-10（Redis 启动日志）
- 图4-11（Celery Worker 启动日志）
- 图4-4（任务处理中）
- 图4-5（任务成功与结果播放）
- 图4-7（metadata 字段展示）
