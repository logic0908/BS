# 论文截图采集指南

- 适用项目根目录：`/home/featurize/work/BS`
- 目标：辅助人工采集论文截图，不伪造图片、不改业务代码。
- 建议截图保存目录：`/home/featurize/work/BS/docs/thesis_materials/screenshots/`

## 1. 启动命令（按顺序）

### 1.1 启动 Redis

```bash
redis-server --daemonize yes
```

### 1.2 启动后端 FastAPI

```bash
cd /home/featurize/work/BS
bash scripts/start_real_svc_demo.sh
```

等价命令（手动）：

```bash
cd /home/featurize/work/BS/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 1.3 启动 Celery Worker

```bash
cd /home/featurize/work/BS
bash scripts/start_celery_worker.sh
```

### 1.4 启动前端

```bash
cd /home/featurize/work/BS
bash scripts/start_frontend_demo.sh
```

等价命令（手动）：

```bash
cd /home/featurize/work/BS/frontend
npm run dev -- --host 0.0.0.0
```

## 2. 推荐浏览器访问地址

根据 `frontend/vite.config.ts` 当前配置：

- 前端页面：`http://127.0.0.1:3001`
- 后端 OpenAPI 文档：`http://127.0.0.1:8000/docs`

如在远程/端口映射环境中，请替换为对应公网或映射地址。

## 3. 每张论文截图建议截取位置

对应清单文件：

- `/home/featurize/work/BS/docs/thesis_materials/screenshot_checklist.md`

建议覆盖：

1. 系统首页整体布局（工作台三栏）
2. 上传区与输入质量提示
3. 提示词与高级参数
4. 任务处理中状态
5. 任务完成与结果播放/下载
6. 关键指标面板
7. 技术链路 metadata 面板
8. 字段说明折叠区
9. FastAPI 启动日志
10. Redis 启动日志
11. Celery Worker 启动日志
12. 前端启动日志
13. `runtime/eval_reports` 目录与关键文件
14. `runtime/figures/training_loss_curve_1000.png`
15. 主观听评空状态（pending_human_scores）
16. 接口代码位置截图（upload/convert/style-analysis）
17. waveform 未实现说明截图

## 4. 截图文件命名规则

建议统一：

`fig<章节>-<序号>-<slug>-<YYYYMMDD>.png`

例如：

- `fig4-1-home-overview-20260513.png`
- `fig4-9-fastapi-log-20260513.png`
- `fig4-15-training-loss-curve-20260513.png`

建议使用小写英文 slug，避免空格与中文文件名。

## 5. 截图插入论文位置建议

| 截图类型 | 建议章节 |
| --- | --- |
| 首页、上传、提示词、任务状态、结果播放 | 第4章“系统实现与功能展示” |
| 技术 metadata、字段说明 | 第4章“关键技术链路与可解释性” |
| FastAPI/Redis/Celery/前端日志 | 第4章“系统部署与运行流程”或附录 |
| objective_metrics、eval_reports、训练曲线 | 第5章“实验与结果分析” |
| 主观听评空状态说明 | 第5章“实验边界与不足” |
| waveform 未实现说明 | 第5章“功能边界说明”或附录“风险与限制” |

## 6. 自动化截图工具核查结论

已核查当前仓库：

- 未发现 Playwright 配置文件（`playwright.config.*`）
- 未发现 Cypress 配置文件（`cypress.config.*` / `cypress.json`）
- 前端当前测试框架为 Vitest（`frontend/package.json`）

因此本轮采用手动截图流程，不安装新依赖，不伪造截图文件。

## 7. 人工截图流程（建议）

1. 先运行 `bash scripts/collect_thesis_evidence.sh` 查看待截图清单与命令。
2. 按“服务日志截图 -> 页面交互截图 -> 实验材料截图 -> 代码证据截图”的顺序采集。
3. 每完成一张截图，在 `screenshot_checklist.md` 中把“是否已存在”改为“是”，并补充采集时间。
4. 若当日无法采集，保持“否/需补充材料”，不要放占位假图。
