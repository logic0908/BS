# 毕设论文材料审计报告（Codex）

- 审计时间：2026-05-13（UTC）
- 审计范围：`/home/featurize/work/BS`
- 审计目标：基于仓库真实内容核查论文可引用材料，不修改核心业务代码与模型推理逻辑。

## 0. 审计边界与证据来源

本报告仅使用以下真实来源：

- `README` 与 `docs/*`
- `backend/app/*`、`frontend/src/*`、`scripts/*`
- `runtime/eval_reports/*`、`evaluation/*`
- `backend/tests/*`、`frontend/src/App.test.tsx`
- 本次现场命令实跑结果（pytest / 前端 test / 前端 build）

若某项证据不足，统一标注“需补充材料”。

## 1. 项目结构导出（按排除规则）

已按要求导出目录树（排除 `.git`、`runtime`、`local_models`、`datasets`、`node_modules`、`frontend/node_modules`）：

- `/home/featurize/work/BS/docs/thesis_materials/final_project_tree.txt`

说明：该文件由命令生成并保存，当前共 975 行。

## 2. `backend/app/main.py` 路由前缀核查

核查文件：`/home/featurize/work/BS/backend/app/main.py`

确认结果：

- `app.include_router(synthesis.router, prefix="/api/v1", tags=["synthesis"])`
- `app.include_router(style_analysis.router, prefix="/api/v1", tags=["style-analysis"])`
- 另有根路由 `GET /`

结论：当前后端 API 主前缀为 `/api/v1`。

## 3. `backend/app/api/endpoints/` 真实接口清单

核查目录：`/home/featurize/work/BS/backend/app/api/endpoints/`

当前真实端点源码文件：

- `/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py`
- `/home/featurize/work/BS/backend/app/api/endpoints/style_analysis.py`

已注册接口（带完整路径）：

1. `GET /api/v1/health`
2. `GET /api/v1/system/health`
3. `GET /api/v1/system/sovits-check`
4. `GET /api/v1/capabilities`
5. `POST /api/v1/upload`
6. `POST /api/v1/convert`
7. `POST /api/v1/synthesize`（StyleSinger 高级实验入口）
8. `POST /api/v1/extract_features`（StyleSinger 特征提取入口）
9. `POST /api/v1/analyze_audio`（StyleSinger 音频分析入口）
10. `POST /api/v1/tasks`（StyleSinger 旧任务入口）
11. `GET /api/v1/tasks/{task_id}`
12. `GET /api/v1/tasks/{task_id}/result`
13. `POST /api/v1/style-analysis/compare`

## 4. 指定关键接口核查

核查项：

1. `POST /api/v1/upload`：存在（`synthesis.py`）
2. `POST /api/v1/convert`：存在（`synthesis.py`）
3. `GET /api/v1/tasks/{task_id}`：存在（`synthesis.py`）
4. `GET /api/v1/tasks/{task_id}/result`：存在（`synthesis.py`）
5. `POST /api/v1/style-analysis/compare`：存在（`style_analysis.py`）
6. `GET /api/waveform` 或 `GET /api/v1/waveform`：未发现

强制结论（按用户要求原文）：

- 当前仓库未发现已注册 waveform 接口，论文中不应写为已实现功能。

## 5. StyleSinger / Demucs / TextStyleAdapter / internal_film 真实边界

### 5.1 StyleSinger

证据：

- `/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py`
  - 存在 `POST /api/v1/synthesize`、`POST /api/v1/extract_features`、`POST /api/v1/analyze_audio`、`POST /api/v1/tasks`
- `/home/featurize/work/BS/backend/app/main.py`
  - 服务描述为“默认主链路 So-VITS-SVC，StyleSinger 仅高级实验模式保留”

结论：

- StyleSinger 在代码中仍可调用，但属于高级/实验分支入口；默认主链路不是 StyleSinger。

### 5.2 Demucs

证据：

- `/home/featurize/work/BS/backend/app/services/separation_service.py`
  - 有真实 `demucs --two-stems vocals` 命令路径
  - 默认 `DEMUCS_MOCK=true`
  - 默认 `DEMUCS_ALLOW_FALLBACK=true`

结论：

- 代码具备 Demucs 调用能力，但默认配置是 mock + fallback，不应在论文中写成“默认已完成真实 Demucs 分离验证”。
- 若论文要写“真实分离已验证”，需补充 `DEMUCS_MOCK=false` 且 `DEMUCS_ALLOW_FALLBACK=false` 的实跑证据。当前为“需补充材料”。

### 5.3 TextStyleAdapter

证据：

- `/home/featurize/work/BS/backend/app/models_svc/text_style_adapter.py`
- `/home/featurize/work/BS/backend/app/services/svc_task_service.py`

结论：

- TextStyleAdapter 已在主链路中真实调用，支持 `trained/rule_based/no_adapter` 模式。
- 其作用在当前实现里是“提示词到 preset/参数控制”的可执行模块，论文表述应避免过度泛化。

### 5.4 internal_film

证据：

- `/home/featurize/work/BS/backend/app/models_svc/sovits_wrapper.py`
  - 默认 `SOVITS_CONDITION_MODE=internal_film`
  - 存在 conditioned 推理分支与 `executed_internal_film` 相关元数据输出
- `/home/featurize/work/BS/backend/app/models_svc/inference_conditioned.py`
  - 显式支持 `--condition-mode internal_film`

结论：

- internal_film 在 So-VITS-SVC 路径有真实代码入口与状态记录。
- 但“效果优劣”仍需主观听评，不可仅凭客观指标推导显著主观结论。

## 6. Celery + Redis 异步任务链路核查

关键证据：

- 路由分发：`/home/featurize/work/BS/backend/app/api/endpoints/synthesis.py`
  - `POST /api/v1/convert` 中，`svc_task_service.use_celery()` 为真时走 `process_svc_task.apply_async(queue="svc")`
- Celery 配置：`/home/featurize/work/BS/backend/app/core/celery_app.py`
  - broker/backend 默认 `redis://localhost:6379/0`
  - 任务名 `svc.process_task`，默认队列 `svc`
- Worker 任务：`/home/featurize/work/BS/backend/app/workers/svc_tasks.py`
  - `process_svc_task` 转调 `svc_task_service.process_task`
- 任务存储：`/home/featurize/work/BS/backend/app/services/task_store.py`
  - Redis + 文件双写回退（`runtime/task_store`）
- 启动脚本与 runbook：
  - `/home/featurize/work/BS/scripts/start_celery_worker.sh`
  - `/home/featurize/work/BS/docs/celery_redis_runbook.md`

结论：

- Celery + Redis 异步链路在代码层与脚本层完整存在，可复现。

## 7. docs 与 runtime/eval_reports 的实验材料核查

### 7.1 已发现材料（可引用）

文档类（示例）：

- `/home/featurize/work/BS/docs/experiment_report.md`
- `/home/featurize/work/BS/docs/objective_evaluation_report.md`
- `/home/featurize/work/BS/docs/effect_ablation_report.md`
- `/home/featurize/work/BS/docs/training_experiment_report.md`
- `/home/featurize/work/BS/docs/subjective_eval_results.md`

运行产物类（示例）：

- `/home/featurize/work/BS/runtime/eval_reports/objective_metrics.json`
- `/home/featurize/work/BS/runtime/eval_reports/objective_metrics_1000.json`
- `/home/featurize/work/BS/runtime/eval_reports/film_strength_ablation_1000.json`
- `/home/featurize/work/BS/runtime/eval_reports/condition_mode_ablation_1000.json`
- `/home/featurize/work/BS/runtime/eval_reports/text_style_adapter_1000_train_report.json`

结论：

- 训练、客观指标、消融实验的“文档+JSON/CSV”材料存在，可做论文引用底稿。

### 7.2 需谨慎引用/需补充材料

- `runtime/eval_reports/*` 多为运行时产物，不随仓库稳定提交；论文归档需人工整理并固化快照。需补充材料。
- 训练报告中的具体指标（如准确率、loss）可引用，但应标注来源文件与时间，不可扩展为超出证据范围的结论。

## 8. 主观听评结果核查

关键证据：

- `/home/featurize/work/BS/docs/subjective_eval_results.md`：表格为“需补充材料（待人工填写）”
- `/home/featurize/work/BS/runtime/eval_reports/subjective_eval_summary.json`
  - `"status": "pending_human_scores"`
  - `"scored_rows": 0`
  - `"message": "模板已生成，暂无结论。"`

结论（强制）：

- 主观听评需补充，不能写成已证明效果较好。

## 9. 测试与构建材料核查（审计当次实跑记录）

本次现场命令结果（**仅对审计当时环境与提交快照有效**）：

1. 后端测试
   - 命令：`PYTHONPATH=$(pwd)/backend:$PYTHONPATH pytest backend/tests -q`
   - 结果：`127 passed, 20 warnings in 45.84s`

2. 前端测试
   - 命令：`cd frontend && npm run test -- --run`
   - 结果：`5 passed (1 test file)`

3. 前端构建
   - 命令：`cd frontend && npm run build`
   - 结果：构建成功
   - 附注：出现 Node 版本提示（当前 `20.16.0`，Vite 提示推荐 `20.19+` 或 `22.12+`）

结论：

- 测试与构建命令可重跑；在本文档所载审计时间与环境下，当次运行结果为通过（含 warnings / version warning）。**不保证**此后任意提交或任意环境仍相同。

## 10. 基于仓库审查的结论要点（非终局证明）

1. API 主前缀 `/api/v1` 及核心任务接口在**所审查源码快照**中存在。
2. `POST /api/v1/style-analysis/compare` 在所审查路由中已注册。
3. 默认歌声转换主链路为 So-VITS-SVC，StyleSinger 为保留的高级/实验入口（依据 `main.py` 描述与路由分工）。
4. Celery + Redis 异步链路在代码、配置、脚本与 runbook 层可追溯。
5. 训练/客观/消融相关文档与 `runtime/eval_reports` 路径在材料整理时可索引；**文件是否存在于你本机**以实际目录为准。
6. 本文档第 9 节记录的 pytest / 前端测试 / 构建结果为**该次实跑日志**，论文引用时应附带日期或提示「见审计报告重跑记录」。

## 11. 缺失材料

1. 主观听评真实评分与统计（当前为模板状态）。需补充材料。
2. waveform API 的已实现证据（当前未注册该接口）。
3. 若要声称“真实 Demucs 分离已完成”，需补 `DEMUCS_MOCK=false` 且禁 fallback 的实跑证据。需补充材料。
4. 论文最终截图清单、截图文件名与采集时环境说明。需补充材料。

## 12. 不能写进论文的风险表述

1. “当前仓库已经实现 waveform 后端接口并用于前端波形请求。”
2. “主观听评已证明 internal_film 显著优于 baseline。”
3. “Demucs 默认链路已稳定完成真实人声分离验证。”
4. “StyleSinger 是当前稳定主链路。”
5. “提示词中的‘男声’会自动切换到男声音色 speaker。”（除非另有严格证据）

## 13. 可以写进论文的谨慎表述

1. “系统后端采用 FastAPI，主 API 前缀为 `/api/v1`，包含上传、转换、任务查询、结果下载与风格证据分析接口。”
2. “默认转换链路为 So-VITS-SVC；StyleSinger 作为高级实验能力保留。”
3. “异步任务链路由 Celery + Redis 实现，`/api/v1/convert` 在 Celery 模式下返回 `task_id` 并由 worker 执行转换。”
4. “TextStyleAdapter 与 internal_film 在工程中均有对应实现与元数据记录，客观指标用于辅助展示，不替代人工听评。”
5. “当前主观听评材料仍待人工补充，论文结论宜限于已有可追溯的客观与工程记录，不扩展到未采集的主观定论。”

## 14. 需要用户手动补充的材料

1. 主观听评原始打分表（含评分人、样本、条件、时间）与统计汇总表。
2. 论文用截图与编号清单（页面、接口、任务状态、结果展示、告警场景）。
3. 如需写 Demucs 真实验证，请补充一组可复现命令、日志、输入输出路径与失败/成功判据。
4. 论文最终引用的实验快照归档（建议将 `runtime/eval_reports` 关键文件复制到可长期保留目录并加时间戳）。

## 15. 关键提醒

- 当前仓库未发现已注册 waveform 接口，论文中不应写为已实现功能。
- 主观听评需补充，不能写成已证明效果较好。
