# 论文材料包说明

## 1. 材料包用途

本目录用于支撑本科毕业论文《基于文本提示词控制的歌声风格转换系统》的**正文写作**、**系统实现描述**、**接口设计**、**实验与客观指标说明**、**系统测试与异常说明**、**部署与模型资产说明**以及**答辩材料整理**（含截图清单、异步与主观听评证据指引）。

材料内容均来自仓库内已有文档、脚本与审计记录整理，**不替代**你对学校模板、参考文献真实性及 Word 终稿的全文校对；标有「需人工补充」的项在补齐前**不宜**写成已定结论。

---

## 2. 文件索引

| 文件名 | 内容说明 | 可用于论文章节 | 是否可直接使用 | 是否仍需人工补充 |
| --- | --- | --- | --- | --- |
| `README.md` | 本材料包总目录与使用说明（当前文件） | 写作导航、组内交接 | 是 | 随材料增删可更新本表 |
| `thesis_ready_sections.md` | 可写入论文的段落口径与禁忌摘要 | 摘要、绪论、系统概述 | 是（需按需删减并与终稿统一） | 若涉及 prompt 与音色关系，建议按 `final_thesis_material_review.md` 补全边界句 |
| `final_project_tree.txt` | 项目目录树导出（排除大目录） | 系统总体结构、附录 | 是 | 目录结构变更后需重新导出 |
| `codex_audit_report.md` | 路由前缀、接口清单、StyleSinger/Demucs/Adapter、测试实跑摘要等审计结论 | 系统实现、接口真实性、测试与边界 | 是 | 重大代码变更后建议重跑审计命令并更新数字与日期 |
| `api_examples.md` | 核心 REST 接口的请求/响应示例与代码位置 | 接口设计、系统实现 | 是 | 接口契约变更时需同步改示例 |
| `api_runtime_examples.md` | 基于 TestClient 等的运行示例与部分实测标注 | 接口设计、附录、答辩演示说明 | 部分（已标注实测与未测） | 未实测路径以实际运行结果为准；健康检查 JSON 中服务名字段勿误读为主链路名称 |
| `exception_handling_table.md` | 常见异常、HTTP 状态码与代码位置索引 | 系统测试、异常处理、鲁棒性 | 是 | 代码行号随重构可能变化，引用前可抽查 |
| `feature_boundary_report.md` | Demucs、StyleSinger、waveform 能力边界专项说明 | 系统实现、限制与展望、风险说明 | 是 | Demucs 真分离、waveform 若未来实现需另补证据并改口径 |
| `async_task_evidence_checklist.md` | FastAPI + Redis + Celery 异步链路证据项与建议截图编号 | 异步任务设计、部署运行、答辩流程 | 是 | 终端与任务界面截图需按清单采集 |
| `model_assets_for_thesis.md` | 默认 preset/speaker、资产类型、环境变量、为何不提交 Git | 部署与复现、模型与配置说明 | 是 | 本地 `local_models` 与权重路径需自备；与 `svc_model_presets.json` 不一致时以配置为准 |
| `objective_metrics_table.md` | 基于 `objective_metrics_1000` 的指标对照表与结论边界 | 实验结果、客观评价小节 | 是（须同时写明 case 规模与「趋势证据」边界） | 若更换评估产物需更新表格数据与说明 |
| `experiment_artifact_index.md` | `docs/` 与 `runtime/eval_reports/` 等实验相关文件索引 | 实验设计、附录、材料来源 | 是 | `runtime/` 产物未必随仓库提交；答辩前需确认文件存在并归档快照 |
| `audio_sample_index.md` | 评估用音频样例命名规则与条件标签说明 | 实验附录、听评材料编号 | 是 | 实际 wav 文件与路径需自备 |
| `subjective_eval_template.md` | 主观听评维度、评分制与样例条件模板 | 主观评价方法、附录 | 是（方法模板） | **评分数据与统计结论需人工填写后才能写入正文结论** |
| `test_case_table.md` | 后端/前端测试命令、结果来源与接口手工测试状态 | 系统测试章节 | 是 | 接口与流程的手工验证截图、以及重跑后的计数更新 |
| `screenshot_checklist.md` | 建议截图编号、文件名、用途与是否已采集 | 系统界面、部署运行、实验与边界展示 | 是（作清单） | **绝大多数截图为待采集**；勿在未采集时写「见图×」为已完成 |
| `screenshot_capture_guide.md` | 截图保存路径、命名规则与采集顺序建议 | 与清单配合使用 | 是 | 按环境实际采集 |
| `reference_audit_todo.md` | 参考文献与正文引用的人工核查待办（摘录自草稿，不编造元数据） | 参考文献整理、答辩前核对 | 仅作核查清单使用 | **须人工联网核对**每条文献与角标对应关系 |
| `final_thesis_material_review.md` | 材料包内部一致性审查结论与风险项 | 定稿前自检、与导师对齐口径 | 是 | 重大变更后建议重读并视需要更新审查报告本身 |

---

## 3. 推荐写作顺序

1. **先使用 `thesis_ready_sections.md`**：统一摘要、绪论与系统概述口径，并记下禁忌表述。  
2. **再使用 `final_project_tree.txt`**：撰写系统总体结构、模块划分或附录目录说明。  
3. **再使用 `api_examples.md`**（必要时结合 `api_runtime_examples.md`、`exception_handling_table.md`）：撰写接口设计与关键交互流程。  
4. **再使用 `model_assets_for_thesis.md`**（可配合 `async_task_evidence_checklist.md`）：撰写模型资产、环境变量、部署与复现说明。  
5. **再使用 `objective_metrics_table.md`**（可配合 `experiment_artifact_index.md`、`audio_sample_index.md`）：撰写客观实验与指标说明，**务必**保留材料中关于样本规模与「趋势证据」的边界。  
6. **再使用 `test_case_table.md`**：撰写系统测试与质量保障；区分自动化测试结果与待补手工/截图证据。  
7. **最后使用 `final_thesis_material_review.md`**：对照风险项与禁止表述做一次定稿前排查；参考文献执行 `reference_audit_todo.md`；截图与主观材料按第 4 节补齐后再写相关结论句。

---

## 4. 不能直接写成结论的材料

以下内容在材料包中均**定位为待补充、待核查或边界说明**，**不得**在未补齐证据前写成已定结论：

| 类别 | 说明 |
| --- | --- |
| **主观听评** | 模板与索引已备，真实打分与统计未齐前，不能写「主观评价证明效果好」等。 |
| **截图** | 清单与指南仅为「待采集」规划；未采集并插入论文前，不能写已完成插图或虚构文件名。 |
| **参考文献** | `reference_audit_todo.md` 为人工核查待办，不视为文献已核验。 |
| **waveform 专用接口** | 多份材料一致说明：未发现已注册 `GET /api/waveform` 或 `GET /api/v1/waveform`，不能写已实现该后端接口。 |
| **Demucs 正式主流程** | 材料说明默认 mock/fallback；不能写「默认已完成真实 Demucs 分离并作为主流程稳定环节」除非另附严格配置下的运行证据。 |
| **客观指标 → 听感** | 不能把客观数值直接写成主观听感显著更优或风格控制「已充分证明」。 |
| **runtime 产物与本地模型** | 依赖本机路径与未入库文件；不能写「克隆仓库即可无步骤获得全部权重与实验表」。 |

---

## 5. 最终论文口径（与材料包一致）

- 前端：**React + Vite + TypeScript**  
- 后端：**FastAPI**  
- 异步任务：**Celery + Redis**  
- 歌声转换主链路：**So-VITS-SVC**  
- 文本条件控制：**TextStyleAdapter + internal_film**  
- 默认模型预设：**final_primary**  
- 默认说话人：**lain**  
- **StyleSinger**：高级实验模式或技术参考入口，**不是**当前默认稳定主转换链路  
- **客观指标**（含 `objective_metrics_1000` 等）：仅作**趋势与可复现记录**，不替代主观听感结论  
- **主观听评**：需**人工补充**评分与统计后，方可在结论中谨慎表述  

---

*材料包路径：`docs/thesis_materials/`。若新增或重命名材料文件，请同步更新本 `README.md` 第 2 节表格。*
