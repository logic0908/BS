# 演示运行手册

## 1. 演示目标

当前演示目标是展示以下闭环：

1. 上传干声音频
2. 输入风格提示词
3. 创建 So-VITS-SVC 转换任务
4. 在 `internal_film` 条件模式下完成真实推理
5. 在前端查看任务状态、转换结果、关键指标和技术链路
6. 下载输出音频

## 2. 启动顺序

### 2.1 启动 Redis

```bash
redis-server --daemonize yes
```

### 2.2 启动 FastAPI

推荐：

```bash
bash scripts/start_real_svc_demo.sh
```

或：

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2.3 启动 Celery worker

```bash
bash scripts/start_celery_worker.sh
```

如需 GPU worker：

```bash
bash scripts/start_celery_gpu_worker.sh
```

### 2.4 启动前端

```bash
bash scripts/start_frontend_demo.sh
```

或：

```bash
cd frontend
npm run dev -- --host 0.0.0.0
```

## 3. 页面演示步骤（当前三栏工作台）

1. 打开前端工作台
2. 上传短时长人声音频
3. 输入提示词，例如：`温柔、明亮、流行感更强的女声风格`
4. 点击“开始风格转换”
5. 观察中栏任务状态与进度
6. 查看中栏转换结果卡片（输出播放器 + 下载）
7. 查看右栏关键指标对比与技术链路
8. 展开“字段说明”查看中英字段对应关系

说明：主页面已删除重复的“转换前后音频对比”大卡片，避免答辩展示时纵向堆叠过长。

## 4. 如何查看 debug metadata

每个任务都会在：

```text
runtime/debug/<task_id>/
```

写出调试文件。建议重点查看：

- `conditioning_report.json`
- `sovits_command.txt`
- `sovits_debug.json`
- `converted.wav`

重点字段：

- `condition_mode`
- `film_strength`
- `executed_internal_film`
- `text_style_adapter_loaded`
- `adapter_mode`
- `adapter_type`
- `adapter_checkpoint`

## 5. 推荐答辩表述

建议：

- 系统已实现文本提示词驱动的 So-VITS-SVC 条件调制链路
- 当前已完成真实链路可执行性验证
- 当前训练对象是 TextStyleAdapter，核心结论是“链路可复现、可验证”

边界：

- 文本提示词会影响风格调制，不会自动切换目标音色
- 当前默认目标音色由 `final_primary / lain` 决定
- 主观听评结论仍需人工补充

## 6. 常见问题

### 6.1 页面显示 Mock

检查：

```bash
echo $SOVITS_MOCK
```

应为 `false`。

### 6.2 想确认是否走到 internal_film

查看：

- `runtime/debug/<task_id>/conditioning_report.json`
- `runtime/debug/<task_id>/sovits_command.txt`

应至少出现：

- `executed_internal_film=true`
- `--condition-mode internal_film`

### 6.3 prompt 写“男声”但输出仍偏向 lain

这是当前设计边界：目标音色仍由当前模型预设与目标音色配置决定。若需要真正男声音色输出，需要接入男声模型预设或男声目标音色并切换配置。
