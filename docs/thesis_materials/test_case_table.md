# 测试用例总表

- 说明：本表包含「已有文档记录」与「`codex_audit_report.md` 所载审计日期下的当次实跑结果」；重跑后须同步更新本表与审计报告。
- 说明：已有测试数字仅代表当次记录，论文定稿前应重新运行或保留日志截图作为最新证据。

## 1. 功能/接口/异常/构建测试清单

| 类别 | 测试目标 | 命令或方式 | 结果来源 | 当前状态 |
| --- | --- | --- | --- | --- |
| 后端单元测试 | 核验后端服务、接口、任务流程、风格分析等测试集 | `PYTHONPATH=$(pwd)/backend:$PYTHONPATH pytest backend/tests -q` | `codex_audit_report.md` 记载的当次实跑 | 通过（127 passed, 20 warnings） |
| 前端测试 | 核验主界面流程与文案边界 | `cd frontend && npm run test -- --run` | `codex_audit_report.md` 记载的当次实跑 | 通过（5 passed） |
| 前端构建测试 | 核验生产构建链路 | `cd frontend && npm run build` | `codex_audit_report.md` 记载的当次实跑 | 通过（构建成功，含 Node 版本提示） |
| 上传接口测试 | `POST /api/v1/upload` 能返回 `vocals_id` | API 调用（手工或脚本） | 代码结构 + 需补充材料（待截图） | 需补充材料 |
| 转换任务创建测试 | `POST /api/v1/convert` 返回 `task_id` | API 调用 | 代码结构 + 需补充材料（待截图） | 需补充材料 |
| 任务状态查询测试 | `GET /api/v1/tasks/{task_id}` 返回状态变化 | API 调用轮询 | 代码结构 + 需补充材料（待截图） | 需补充材料 |
| 结果下载测试 | `GET /api/v1/tasks/{task_id}/result` 返回 wav 文件 | API 调用 | 代码结构 + 需补充材料（待截图） | 需补充材料 |
| 风格分析接口测试 | `POST /api/v1/style-analysis/compare` 路径与参数边界 | API 调用 + 后端 tests | 代码结构 + `backend/tests/test_audio_style_analysis.py` + 需补充材料（待截图） | 需补充材料 |
| 异常输入测试 | 无效 `vocals_id`、空 prompt、路径越界等 | API 调用 | 代码结构（HTTPException 分支）+ 需补充材料（待截图） | 需补充材料 |

## 2. 可引用的已有记录

| 记录项 | 记录位置 | 可引用写法 |
| --- | --- | --- |
| 后端 `127 passed, 20 warnings` | `/home/featurize/work/BS/docs/thesis_materials/codex_audit_report.md` | 可写为：在审计报告所载日期与命令下，后端测试集曾得到该计数（**非**永久结论；定稿前建议重跑并更新）。 |
| 前端 `5 passed` | `/home/featurize/work/BS/docs/thesis_materials/codex_audit_report.md` | 同上，注明为单次实跑记录。 |
| 前端 build 成功 | `/home/featurize/work/BS/docs/thesis_materials/codex_audit_report.md` | 可写为：同次审计中构建成功并存在 Node 版本提示（以当时日志为准）。 |

## 3. 失败记录策略

若后续复测失败，建议按以下格式记录：

- 命令：
- 失败时间：
- 报错摘要：
- 可能原因：
- 是否阻塞论文结论：是/否
- 处理建议：

当前状态：在写入 `codex_audit_report.md` 对应条目的那次运行中未记录失败用例；若你本地重跑出现失败，应在本表与审计报告中更新状态，不得沿用旧表述。
