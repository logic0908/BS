# 论文截图清单（建议）

- 说明：截图编号从“图4-1”开始。
- 说明：以下为建议采集清单，不假设截图已存在。
- 建议存放目录：`/home/featurize/work/BS/docs/thesis_materials/screenshots/`

| 截图编号 | 建议文件名 | 截图内容 | 论文用途 | 获取方式 | 是否已存在 | 是否需要人工截图 | 推荐截图时机 | 对应论文小节 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 图4-1 | fig4-1-home-overview.png | 系统首页整体布局（Header + 工作台） | 系统总体实现界面 | 启动前端后全屏截图 | 否 | 是 | 前端启动成功后 | 4.1 系统总体界面 |
| 图4-2 | fig4-2-upload-panel.png | 上传音频区域与输入质量提示 | 输入模块说明 | 上传一个测试音频后截图 | 否 | 是 | 上传音频成功后 | 4.2 输入与预处理 |
| 图4-3 | fig4-3-prompt-input.png | 文本提示词输入与高级参数 | 提示词控制入口说明 | 输入示例 prompt 后截图 | 否 | 是 | 提交任务前 | 4.3 提示词控制 |
| 图4-4 | fig4-4-task-running.png | 任务处理中状态（queued/running） | 异步任务链路说明 | 提交转换后轮询阶段截图 | 否 | 是 | 任务状态为 running 时 | 4.4 异步任务流程 |
| 图4-5 | fig4-5-result-player.png | 转换结果播放器与下载按钮 | 结果输出能力说明 | 任务成功后截图 | 否 | 是 | 任务成功后 | 4.5 结果展示与下载 |
| 图4-6 | fig4-6-metrics-panel.png | 关键指标展示区域 | 客观指标展示能力 | 转换成功并加载指标后截图 | 否 | 是 | 结果页加载完成后 | 5.2 客观指标展示 |
| 图4-7 | fig4-7-tech-metadata.png | 技术链路 metadata（preset/speaker/adapter） | 可解释性说明 | 展开技术详情后截图 | 否 | 是 | 任务成功且 metadata 完整时 | 4.6 技术链路可解释性 |
| 图4-8 | fig4-8-field-help.png | 字段说明（中英对照术语） | 字段可解释性说明 | 展开字段说明后截图 | 否 | 是 | 技术详情展开后 | 4.6 技术链路可解释性 |
| 图4-9 | fig4-9-fastapi-log.png | FastAPI 启动日志与监听端口 | 后端服务运行证据 | 终端执行 `bash scripts/start_real_svc_demo.sh` | 否 | 是 | 后端刚启动成功时 | 4.7 系统部署与运行 |
| 图4-10 | fig4-10-redis-log.png | Redis 启动日志 | 异步基础设施证据 | 终端执行 `redis-server --daemonize yes` 或前台日志 | 否 | 是 | Redis 启动后 | 4.7 系统部署与运行 |
| 图4-11 | fig4-11-celery-log.png | Celery Worker 启动与队列信息 | 异步执行证据 | 终端执行 `bash scripts/start_celery_worker.sh` | 否 | 是 | Worker 进入 ready 状态时 | 4.7 系统部署与运行 |
| 图4-12 | fig4-12-frontend-log.png | 前端 dev 启动日志与访问地址 | 前端可运行证据 | 终端执行 `cd frontend && npm run dev -- --host 0.0.0.0` | 否 | 是 | Vite 显示 Local/Network 地址后 | 4.7 系统部署与运行 |
| 图4-13 | fig4-13-eval-reports-dir.png | `runtime/eval_reports/` 目录文件列表 | 实验材料归档证据 | 文件浏览器或 `ls` 输出截图 | 否 | 是 | 实验产物整理时 | 5.1 实验材料来源 |
| 图4-14 | fig4-14-objective-metrics-files.png | `objective_metrics_1000.{json,csv,md}` 文件 | 客观指标来源证据 | 文件浏览器或终端列表截图 | 否 | 是 | 写客观指标小节前 | 5.2 客观指标分析 |
| 图4-15 | fig4-15-training-loss-curve.png | `runtime/figures/training_loss_curve_1000.png` | 训练过程可视化证据 | 图片查看器打开并截图 | 否 | 是 | 写训练实验小节前 | 5.3 训练实验结果 |
| 图4-16 | fig4-16-subjective-empty.png | `subjective_eval_summary.json` 的 pending 状态 | 主观听评未完成边界说明 | 打开文件内容截图 | 否 | 是 | 写主观听评边界时 | 5.4 主观评价与边界 |
| 图4-17 | fig4-17-api-upload-code.png | `/api/v1/upload` 代码片段 | 接口真实性证据 | IDE 打开对应代码位置截图 | 否 | 是 | 写接口实现小节时 | 4.8 接口实现 |
| 图4-18 | fig4-18-api-convert-code.png | `/api/v1/convert` + `/tasks/{id}` 代码片段 | 任务接口真实性证据 | IDE 打开对应代码位置截图 | 否 | 是 | 写接口实现小节时 | 4.8 接口实现 |
| 图4-19 | fig4-19-style-analysis-code.png | `/api/v1/style-analysis/compare` 代码片段 | 风格证据接口真实性 | IDE 打开对应代码位置截图 | 否 | 是 | 写风格证据小节时 | 4.9 风格证据分析 |
| 图4-20 | fig4-20-waveform-no-api-note.png | “无 waveform API”核查说明（文档页） | 风险边界说明 | 引用 `api_examples.md` 相关节截图 | 否 | 是 | 写风险与边界小节时 | 5.5 风险与限制 |

## 采集建议

1. 统一浏览器窗口尺寸（建议 1920x1080），避免论文图比例差异过大。
2. 终端截图前先清屏，并保留关键命令与关键输出行。
3. 每张图采集后在文件名中加入日期，例如 `fig4-9-fastapi-log-20260513.png`。
4. 若某图当日无法采集，保留“需补充材料”状态，不用占位假图。

未采集项统一视为需补充材料，未实际截图并插入论文前，不得在正文中写作“见图×”或作为已完成截图证据。
