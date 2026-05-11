# 演示运行手册

## 1. 演示目标

当前演示目标是展示以下闭环：

1. 上传人声 / 干声音频
2. 输入 `style_prompt`
3. 创建 So-VITS-SVC 转换任务
4. 走真实 So-VITS-SVC 推理
5. 在 `internal_film` 模式下完成内部 Bias/Scale 注入
6. 前端查看结果、播放波形、下载音频
7. 查看 debug metadata 与 `conditioning_report.json`

## 2. 启动顺序

### 2.1 启动 Redis

```bash
redis-server --daemonize yes
```

### 2.2 启动 FastAPI

推荐方式一：

```bash
bash scripts/start_real_svc_demo.sh
```

推荐方式二：

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2.3 启动 Celery worker

```bash
bash scripts/start_celery_worker.sh
```

若需要更稳定的 GPU 演示 worker，可使用：

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

### 2.5 打开浏览器

- 前端：`http://127.0.0.1:3001`
- 后端：`http://127.0.0.1:8000`

## 3. 页面演示步骤

1. 打开前端工作台
2. 上传一个短的人声音频
3. 输入 `style_prompt`，例如：

```text
温柔、明亮、流行感更强的女声风格
```

4. 如需保持默认配置，可直接开始转换
5. 若要展示高级参数，可展开高级区域查看：
   - `transpose`
   - `style_strength`
   - `model_preset_id`
6. 等待任务完成
7. 在 A/B 波形区域查看原始音频与转换结果
8. 在技术详情区查看 `condition_mode`、`executed_internal_film` 等信息

## 4. 如何查看 debug metadata

每个任务都会在：

```text
runtime/debug/<task_id>/
```

写出调试文件。建议重点查看：

- `style_embedding.pt`
- `style_embedding.json`
- `conditioning_report.json`
- `sovits_command.txt`
- `sovits_debug.json`
- `converted.wav`

关键信息包括：

- `condition_mode`
- `style_prompt`
- `film_strength`
- `film_target`
- `injection_target`
- `executed_internal_film`

## 5. 演示中建议的表述

建议这样描述当前系统：

- 系统已实现文本提示词驱动的 So-VITS-SVC 内部条件调制机制
- 当前已完成真实 GPU smoke 验证
- 现阶段重点证明机制可执行，不夸大为强文本语义可控模型

避免这样描述：

- 任意歌手声音生成
- 完美复刻音色
- 商业级可用
- 已完成充分效果验证

## 6. 常见问题

### 6.1 页面显示 Mock

检查：

```bash
echo $SOVITS_MOCK
```

应为：

```bash
false
```

### 6.2 想确认是否走到 internal_film

查看：

- `runtime/debug/<task_id>/conditioning_report.json`
- `runtime/debug/<task_id>/sovits_command.txt`

应至少看到：

- `executed_internal_film=true`
- `--style-emb-path`
- `--condition-mode internal_film`

### 6.3 输出音频仍不理想

需要如实说明：

- 当前效果受目标模型、输入音频质量、F0 提取和人声分离质量影响
- 当前系统已证明机制接入，不代表效果结论已经完备
