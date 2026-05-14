# 论文正文整合前的最终证据补齐待办

> 依据：`docs/thesis_materials/final_thesis_material_review.md`、`docs/thesis_materials/README.md`。  
> 性质：**仅人工可完成**的证据与决策清单；不扩写材料包、不替代 Word 全文校对。

---

## 按优先级分列的待办

| 优先级 | 材料名称 | 对应论文位置 | 对应材料包文件 | 获取方式 | 是否必须补 | 不补会导致什么论文风险 |
| --- | --- | --- | --- | --- | --- | --- |
| **P0** | 系统运行界面截图（首页、上传、提示词、任务状态、结果播放/A-B、技术详情等） | 第 4 章系统实现与运行效果；答辩 PPT | `screenshot_checklist.md`、`screenshot_capture_guide.md` | 按清单启动前后端与一次完整任务流，在浏览器与页面状态下截图；命名见采集指南 | **强烈建议必补**（本科毕设展示类章节通常要求有图） | 易被质疑「仅有文字无运行证据」；不得虚构「见图×」 |
| **P0** | 异步任务链终端截图（Redis / FastAPI / Celery） | 第 4 章部署与运行；异步设计说明 | `async_task_evidence_checklist.md`、`screenshot_checklist.md`（图4-9～4-11） | 按 `README`/`runbook` 顺序启动：`redis-server`、后端脚本、Celery worker 脚本，截取关键日志行 | **强烈建议必补** | 难以证明「异步真实跑通」；与材料包主张的 Celery+Redis 口径不一致风险 |
| **P0** | 主观听评：**是否纳入正文结论**的明确决策 | 第 5 章实验与评价；结论章 | `subjective_eval_template.md`、`final_thesis_material_review.md` §5～§7 | 与导师确认二选一：**(A)** 纳入则按模板组织听评、填分、归档；**(B)** 不纳入则正文明确写「未开展/未统计」，且**不写**听感优劣结论 | **必须做决策**（补数据或明确不写） | 若未决策：易写成空洞评价或越界写「已证明效果好」（与材料禁止项冲突） |
| **P0** | 参考文献真实性核查与角标对应 | 参考文献章；正文引用 | `reference_audit_todo.md` | 按该文件表格逐条联网核对；处理 `[14]` 与正文是否引用、编号顺序等 | **必须补**（学校通常硬性要求） | 引用错误、答辩追问文献无法回答；学术不端风险 |
| **P0** | Word 终稿中**旧技术栈**与**旧接口路径**清理 | 全文（尤摘要、绪论、系统概述） | `final_thesis_material_review.md`（R03 等）、`README.md` §5、`codex_audit_report.md` | 在 Word 中全文检索：`Vue`、`Element`、`/api/upload`、`/api/convert`（无 `v1`）、过时测试计数等，对照材料包统一为 React+Vite+TS、`/api/v1/*` 与最新审计数字 | **强烈建议必补** | 与仓库及材料包矛盾（R03）；答辩被指出「论文与系统不一致」 |
| **P1** | 音频样例编号与文件对齐 | 实验附录、听评表、答辩附录 | `audio_sample_index.md`、`subjective_eval_template.md` | 按索引规则命名/列出 `S001…` 与各条件 wav；确保路径与 `runtime` 或本地归档一致 | 若写听评或贴附录音频则**必须**；否则可标「未使用」 | 样例与表格对不上；无法复现听评流程 |
| **P1** | 模型资产本地路径说明或截图（脱敏） | 部署与复现；系统实现 | `model_assets_for_thesis.md`、`docs/model_assets_setup.md`（仓库内说明，非本目录） | 整理 `local_models/`、`runtime/style_adapter/` 等实际路径；可选终端 `ls` 或资源管理器截图（隐去敏感账号路径） | **建议补充材料（非必填，按章节需求）** | 复现说明空泛；答辩问「模型在哪」难以举证 |
| **P1** | 答辩前测试命令重跑并更新论文中数字 | 系统测试章；摘要中若写测试统计 | `test_case_table.md`、`codex_audit_report.md` §9 | 执行表中命令；将新日期、新 `passed/warnings` 写入 Word 与（可选）更新审计报告 | **建议必做**（定稿前至少一次） | 论文数字与当前代码不一致（审查报告 R07）；「永久通过」误读 |
| **P1** | `objective_metrics_1000` 的 **case_count=1** 边界写入正文 | 第 5 章客观实验 | `objective_metrics_table.md`、`experiment_artifact_index.md` | 在表格标题或脚注中写明：文件名含 1000 系训练/套件命名，**当前汇总 case 数为 1**；指标仅趋势证据 | **若引用该表则必须** | 被误读为「1000 个独立用例」；夸大客观结论（审查报告 R04） |
| **P2** | Demucs 真实分离证据（命令、日志、输入输出、配置 `DEMUCS_MOCK`/`FALLBACK`） | 仅当正文要写「真实分离已验证」时 | `feature_boundary_report.md`、`codex_audit_report.md` §11 | 按边界报告「需补充材料」小节采集一组可复查实跑 | **仅论文要写 Demucs 实分离时必补** | 写成已验证则与材料边界冲突，属不实陈述 |
| **P2** | waveform 后端接口证据 | 仅当未来实现并要写进论文时 | `feature_boundary_report.md`、`api_examples.md` | 补路由注册、测试记录、前端调用证据后再改口径 | **当前不必补**（材料结论为未注册） | 无实现却写作「已实现」则直接违规 |
| **P2** | 更完整的主观听评统计（多样本、多评分人、显著性说明） | 增强第 5 章说服力（超出课程最低要求时） | `subjective_eval_template.md` | 扩大样本、填表、做简单统计；与导师确认统计方法 | **非必须** | 无风险于「不写」；若写「显著」而无统计则风险高 |

---

## P0 与任务要求的对应关系（自检）

| 任务要求 | 上表对应行 |
| --- | --- |
| 系统运行截图 | P0 第一行 |
| 异步任务终端截图 | P0 第二行 |
| 主观听评是否补充的决策 | P0 第三行 |
| 参考文献真实性核查 | P0 第四行 |
| Word 旧技术栈与旧接口路径清理 | P0 第五行 |

---

## 论文正文整合顺序（建议）

1. **系统概述**（摘要、绪论、需求概述）：口径以 `README.md` §5、`thesis_ready_sections.md` 为准。  
2. **系统架构**（总体结构、模块划分）：`final_project_tree.txt`，必要时 `codex_audit_report.md` 路由概览。  
3. **接口设计**（核心 API、请求响应）：`api_examples.md`，异常与状态码见 `exception_handling_table.md`。  
4. **模型资产与部署**（环境、preset、复现步骤）：`model_assets_for_thesis.md`、`async_task_evidence_checklist.md`。  
5. **系统测试**（自动化测试、手工/截图证据）：`test_case_table.md`，与重跑后的命令输出一致。  
6. **实验结果**（客观指标、可选主观）：`objective_metrics_table.md`、`experiment_artifact_index.md`；主观仅在有数据后撰写。  
7. **不足与展望**（边界、未做项）：`final_thesis_material_review.md` §5 禁止表述、`feature_boundary_report.md`（Demucs/StyleSinger/waveform）。

完成 P0 决策与证据后，再合并进 Word 终稿并统一图表编号与参考文献格式。

---

*本清单随证据补齐可勾选删除；不必提交到论文正文。*
