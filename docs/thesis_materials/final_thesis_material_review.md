# 论文材料最终一致性审查报告

- 审查日期：2026-05-13  
- 审查对象：`/home/featurize/work/BS/docs/thesis_materials/` 下全部论文材料文件（与任务 13 项检查清单对照）  
- 审查方法：通读材料目录内 Markdown/文本，辅以关键词检索（技术栈、接口路径、Mock、waveform、StyleSinger、Demucs、主观/客观结论等）；**未**修改 `backend/`、`frontend/`、`scripts/` 核心代码。

---

## 1. 审查范围

下列文件已纳入本轮一致性审查：

| 文件 |
| --- |
| `api_examples.md` |
| `api_runtime_examples.md` |
| `async_task_evidence_checklist.md` |
| `audio_sample_index.md` |
| `codex_audit_report.md` |
| `exception_handling_table.md` |
| `experiment_artifact_index.md` |
| `feature_boundary_report.md` |
| `final_project_tree.txt` |
| `model_assets_for_thesis.md` |
| `objective_metrics_table.md` |
| `reference_audit_todo.md` |
| `screenshot_capture_guide.md` |
| `screenshot_checklist.md` |
| `subjective_eval_template.md` |
| `test_case_table.md` |
| `thesis_ready_sections.md` |

**未纳入本目录但可能被论文引用的文件（提醒）：**`docs/undergraduate_thesis_draft.md`、`README.md` 等不在本轮逐字核对范围内；若终稿引用其中测试数字或表述，需与 `codex_audit_report.md` / `test_case_table.md` **自行对齐**，避免与材料包不一致。

---

## 2. 通过项

下列要点在**材料包内部**整体一致，且与 AGENTS.md / `codex_audit_report.md` 所反映的工程口径相容，可作为论文写作基础：

1. **技术栈**：多份材料统一为 **React + Vite + TypeScript**、**FastAPI**、**Celery + Redis**、主链路 **So-VITS-SVC**、文本条件 **TextStyleAdapter + internal_film**（见 `thesis_ready_sections.md`、`model_assets_for_thesis.md`、`codex_audit_report.md` 等）。**未发现** Vue、Element Plus 等历史前端栈表述。
2. **核心接口路径**：材料中主任务链路统一为 `POST /api/v1/upload`、`POST /api/v1/convert`、`GET /api/v1/tasks/{task_id}`、`GET /api/v1/tasks/{task_id}/result`、`POST /api/v1/style-analysis/compare`。**未发现**将 `/api/upload`、`/api/convert`（无 `v1`）写成当前已确认主路径的表述。
3. **waveform 边界**：`feature_boundary_report.md`、`api_examples.md`、`thesis_ready_sections.md`、`codex_audit_report.md` 均明确 **未发现已注册** `GET /api/waveform` 或 `GET /api/v1/waveform`，并禁止写成已上线生产接口。
4. **StyleSinger 边界**：统一为高级/实验入口，**非**默认稳定主链路；与 So-VITS-SVC 主链路区分清晰。
5. **Demucs 边界**：`feature_boundary_report.md`、`codex_audit_report.md` 写明代码路径存在但默认 `DEMUCS_MOCK`、fallback 等，**未**将 Demucs 写成「默认主流程已稳定完成真实分离」。
6. **TextStyleAdapter / internal_film**：强调训练对象为轻量适配器、internal_film 为可执行链路与元数据证据，**避免**「完整强文本风格控制大模型已训练完成」类结论；与 `experiment_artifact_index.md`、`objective_metrics_table.md` 边界一致。
7. **客观指标**：`objective_metrics_table.md`、`thesis_ready_sections.md`、`experiment_artifact_index.md` 明确 `objective_metrics_1000` **case_count=1**、指标为趋势/启发式，**不等价**主观听感。
8. **主观听评**：`subjective_eval_template.md`、`codex_audit_report.md`、`screenshot_checklist.md`（图4-16）等与「待人工填写」「不能写已证明效果好」一致。
9. **模型资产**：`model_assets_for_thesis.md` 写明默认 **final_primary / lain**、权重与 `runtime` 不随仓库提交、依赖本地 `local_models` 等。
10. **截图清单**：`screenshot_checklist.md` 明确为建议清单，「是否已存在」列均为「否」，**未**伪造已存在截图。
11. **测试材料**：`test_case_table.md` 区分接口手工测试（待补截图）与 pytest/npm 实跑；与 `codex_audit_report.md` 第 9 节数字一致（**127 passed, 20 warnings**；前端 **5 passed**）。
12. **参考文献待办**：`reference_audit_todo.md` 为摘录与核查清单，**未**在审计文档中编造新的 DOI/页码/会议信息；全文强调**需人工联网核查**，符合边界要求。

---

## 3. 风险项

| 风险编号 | 所在文件 | 原表述或问题 | 风险原因 | 建议修改方式 | 是否必须修改 |
| --- | --- | --- | --- | --- | --- |
| R01 | `thesis_ready_sections.md`、`model_assets_for_thesis.md` 等 | 材料强调默认 `final_primary`/`lain`，但**未**在「可答辩口径」段落中集中写出「提示词中的男声≠自动切换 speaker」 | 读者易从自然语言推断错误因果；`codex_audit_report.md` 已列为禁止表述的反例 | 在 `thesis_ready_sections.md`（或论文绪论/系统设计）增加一句与 `codex_audit_report.md` 第 12 节一致的正面说明 | **若论文正文讨论 prompt 与音色关系则必须**；否则建议仍补一句防误解 |
| R02 | `api_runtime_examples.md`（健康检查 JSON 示例） | 返回体含 `"service": "stylesinger-backend"` | 与「主链路 So-VITS-SVC」并列阅读时，可能被误读为后端即 StyleSinger 主服务 | 论文中若引用该 JSON，加脚注说明为**历史/兼容字段名**，不代表主业务链路；或仅引用字段语义不写服务名 | 建议（非必须，视是否引用该示例） |
| R03 | `test_case_table.md` / `codex_audit_report.md` ↔ 仓库外 `docs/undergraduate_thesis_draft.md`（若使用） | 材料包为 **127 passed**（后端）、**5 passed**（前端）；旧草稿曾出现其他计数 | 终稿若混用来源，答辩材料数字矛盾 | 以 `codex_audit_report.md` 审计日期对应实跑为准；改 Word 后删除旧数字 | **若论文仍引用旧草稿数字则必须** |
| R04 | `objective_metrics_1000` 命名 | 文件名含 `1000`，易被扫读成「1000 个测试用例/样本」 | 材料已写 `case_count=1`，但命名本身有误导性 | 论文中首次出现写全称：「基于 1000 条训练相关配置的客观评估套件，当前汇总 **case 数=1**」 | 建议 |
| R05 | `api_runtime_examples.md`、`codex_audit_report.md` | 除 5 个核心接口外，还列 `GET /api/v1/health`、`/system/*`、`POST /api/v1/synthesize` 等 | 无错误，但若论文「只实现五个接口」写绝对化易被质疑 | 论文写「核心演示接口为…」并视需要列「健康检查/能力查询/高级实验接口另列」 | 可选 |
| R06 | `feature_boundary_report.md` | 「已存在主流程代码接入点」描述 Demucs | 若论文摘句不当，可能弱化为「主流程已集成 Demucs」 | 论文沿用材料中下半句：**默认 mock/fallback，不能写真实分离已验证** | 建议核对摘句 |
| R07 | `test_case_table.md` 第 2 节 | 「可写本次审计实跑通过」指向固定日期审计 | 之后代码变更未重跑时，表述过时 | 答辩前重跑命令并更新 `codex_audit_report.md` / 本表或增加审计日期 | 建议（重大改代码后必须） |
| R08 | `screenshot_capture_guide.md` | 建议截图目录 `docs/thesis_materials/screenshots/` | 目录可能尚未创建或尚未入库 | 采图前创建目录；Git 是否提交大图按学校/仓库策略 | 按需 |

---

## 4. 建议统一表述（终稿推荐）

以下段落可直接作为论文「口径段」或答辩口径的合并母版（与材料包一致）：

- **技术栈**：前端采用 **React + Vite + TypeScript**；后端采用 **FastAPI**；异步推理任务由 **Celery** 消费、**Redis** 作为 broker/结果后端（具体配置以运行环境为准）。  
- **系统主链路**：默认歌声转换主链路为 **So-VITS-SVC**；任务创建、状态查询与结果下载以 **`/api/v1/upload` → `/api/v1/convert` → `/api/v1/tasks/{task_id}` → `/api/v1/tasks/{task_id}/result`** 为主证据链；风格客观对比为 **`POST /api/v1/style-analysis/compare`**。  
- **StyleSinger 边界**：StyleSinger 相关接口保留为**高级实验/技术对照**入口，**不是**默认稳定主转换链路；主结论与实验应以 **`/api/v1/convert`** 及 So-VITS-SVC 任务证据为准。  
- **Demucs 边界**：上传预处理链路中**存在** Demucs 相关代码分支，但默认配置含 **mock 与 fallback**；除非提供 `DEMUCS_MOCK=false` 等严格实跑日志与产物，**不得**写「默认已完成真实 Demucs 人声分离并作为主流程稳定环节」。  
- **TextStyleAdapter 边界**：当前训练与在线加载对象为**轻量级 TextStyleAdapter**（提示词 embedding → 控制参数 / preset 等），**不得**写成「已完成 So-VITS-SVC 全网络端到端重训」或「强泛化通用风格理解大模型」。  
- **internal_film 边界**：`internal_film` 用于证明 **文本条件进入 So-VITS-SVC 推理链路且可记录执行状态**；执行成功**不等于**听感一定优于 baseline 或无 artifact。  
- **客观指标边界**：`objective_metrics_1000` 等文件仅作**趋势与可复现记录**；`speaker_embedding_similarity`、`brightness_delta` 等**不得**直接等同于主观质量或「提示词匹配度已量化得证」。  
- **主观听评边界**：在获得真实评分表与统计前，**不得**写主观评价已证明系统效果较好或显著优于某 baseline。  
- **模型资产边界**：`local_models/`、权重、`runtime/` 调试与评估产物**不随源码仓库完整提供**；复现需本地补齐；默认 **preset=`final_primary`**、**speaker=`lain`**（与 `svc_model_presets.json` 一致前提下）。

---

## 5. 禁止写入论文的表述（类型与原因）

| 类型 | 原因 |
| --- | --- |
| 「后端已实现并上线 **`GET /api/waveform`**」 | 材料包与代码审计一致：**无该路由注册证据** |
| 「**StyleSinger** 为当前默认/稳定生产主链路」 | 与工程事实及材料包结论相反 |
| 「**Demucs** 已在默认配置下稳定完成真实人声分离并通过全面验证」 | 默认 mock/fallback；缺严格实证 |
| 「**主观听评**已证明系统效果很好 / internal_film 显著优于 baseline」 | 主观材料仍为 pending / 模板状态 |
| 「客观指标已证明**文本风格控制效果显著** / 模型具备**强泛化**」 | 客观表为单 case 趋势；Adapter 为小规模训练对象 |
| 「生成音频质量**优于所有 baseline**」 | 无全覆盖对比与统计检验支撑 |
| 「提示词写**男声**即**自动切换**男声 speaker」 | `codex_audit_report.md` 明确禁止（除非另附严格证据） |
| 「模型权重与数据集**随仓库一键克隆即可完整复现**」 | 与 `.gitignore` 及 `model_assets_for_thesis.md` 相悖 |

---

## 6. 可以直接进入论文的材料清单

| 建议引用文件 | 建议进入的论文章节/用途 |
| --- | --- |
| `thesis_ready_sections.md` | 摘要/绪论口径、系统总体说明（需按需压缩，并补 R01 若涉及 prompt） |
| `codex_audit_report.md` | 系统实现与接口真实性、测试与构建、禁止/可写表述清单（附录或脚注） |
| `api_examples.md` | 系统接口设计、请求/响应示例 |
| `api_runtime_examples.md` | 与 `TestClient` 实测相关的接口证据（注意 R02 字段名） |
| `exception_handling_table.md` | 异常处理与鲁棒性、HTTP 状态码说明 |
| `final_project_tree.txt` | 系统结构、模块划分（附录） |
| `feature_boundary_report.md` | Demucs / StyleSinger / waveform 专项边界（第 4 章风险与限制） |
| `async_task_evidence_checklist.md` | Celery+Redis 异步流程与答辩演示顺序 |
| `model_assets_for_thesis.md` | 部署与复现、模型与 preset 说明 |
| `objective_metrics_table.md` | 实验结果中的客观指标小节（**必须**带 case_count=1 说明） |
| `experiment_artifact_index.md` | 实验材料来源索引、附录文件列表 |
| `audio_sample_index.md` | 听评或样例音频编号规则（附录） |
| `subjective_eval_template.md` | 主观评价方法附录（在填写前不写结论） |
| `test_case_table.md` | 系统测试章节（区分自动测试与待补手工截图） |
| `screenshot_checklist.md`、`screenshot_capture_guide.md` | 截图目录与采集规范（不冒充已完成插图） |
| `reference_audit_todo.md` | 参考文献与正文引用的人工核查工作说明（不作为已核验文献列表） |

---

## 7. 仍需人工补充的材料

1. **真实截图**：`screenshot_checklist.md` 所列图4-1～图4-20 等，当前「是否已存在」均为否。  
2. **主观听评**：原始打分、统计汇总、`subjective_eval_results.md` 填写。  
3. **参考文献真实性核查**：按 `reference_audit_todo.md` 执行联网核对与 GB/T 格式统一。  
4. **音频样例编号**：按 `audio_sample_index.md` 与听评表对齐命名。  
5. **模型资产本地路径**：可选截图证明 `local_models/` 已按 `model_assets_setup.md` 放置（注意脱敏）。  
6. **异步任务终端截图**：Redis / FastAPI / Celery 启动日志等（清单图4-9～4-11）。  
7. **（可选）Demucs 真分离证据**：若论文要写真实分离，需按 `feature_boundary_report.md` 所列配置与日志补证。

---

## 8. 最终结论

当前 `docs/thesis_materials/` 材料包在**技术栈、主接口前缀与核心路径、StyleSinger/Demucs/waveform 边界、客观/主观结论克制、截图与测试表述、参考文献待办性质**等方面**整体可作为本科论文写作与答辩口径的基础**，且相互之间**无发现**与上述边界严重冲突的夸大结论。主要缺口在于：**截图与主观听评仍为待办**；**提示词与 speaker 因果关系**建议在面向读者的综述段**显式写清**（R01）；若终稿仍引用仓库外旧草稿中的测试统计，须与 `codex_audit_report.md` **对齐**。在上述人工材料补齐前，论文**结论部分**应限定为「工程闭环可复现、客观趋势可展示、听感与泛化未定论」层级，不写终局性效果评价。

---

*本报告仅覆盖 `docs/thesis_materials/`；不替代对 Word 终稿或校模板的全文校对。*
