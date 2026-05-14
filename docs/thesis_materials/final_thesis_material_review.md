# 论文材料最终一致性审查

审查时间：2026-05-14  
审查范围：`/home/featurize/work/BS/docs/thesis_materials/` 全部文件

## 0. 12 项检查结论总览

| 检查项 | 结论 | 证据（示例文件） |
| --- | --- | --- |
| 1. 技术栈统一为 React + Vite + TypeScript | 通过 | `thesis_ready_sections.md`、`README.md` |
| 2. 路由前缀统一为 `/api/v1` | 通过 | `api_examples.md`、`codex_audit_report.md` |
| 3. 主链路为 So-VITS-SVC + TextStyleAdapter + internal_film | 通过 | `thesis_ready_sections.md`、`feature_boundary_report.md` |
| 4. 未将 StyleSinger 写成稳定主链路 | 通过 | `feature_boundary_report.md`、`codex_audit_report.md` |
| 5. 未将 Demucs 写成默认已正式稳定集成 | 通过（有边界） | `feature_boundary_report.md` |
| 6. 未写“主观评价证明效果较好” | 通过 | `subjective_eval_template.md`、`thesis_ready_sections.md` |
| 7. 明确客观指标仅为趋势证据 | 通过 | `objective_metrics_table.md`、`experiment_artifact_index.md` |
| 8. 明确 prompt 不会自动切换 speaker | 通过 | `thesis_ready_sections.md` |
| 9. 明确权重/数据集/runtime 产物不随仓库提交 | 通过 | `model_assets_for_thesis.md`、`README.md` |
| 10. 截图未伪造 | 通过 | `screenshot_checklist.md`（是否已存在均为“否”） |
| 11. 接口示例有代码依据或运行验证标注 | 通过 | `api_examples.md`、`api_runtime_examples.md` |
| 12. 缺失材料标注“需补充材料” | 通过（本轮已统一） | `test_case_table.md`、`subjective_eval_template.md`、`next_manual_evidence_todo.md`、`experiment_artifact_index.md`、`codex_audit_report.md` |

## 1. 通过项

1. 材料包整体口径已统一到 React + Vite + TypeScript、FastAPI、Celery + Redis。
2. API 主路径口径统一为 `/api/v1/*`，核心五接口一致。
3. So-VITS-SVC + TextStyleAdapter + internal_film 被持续写作主链路。
4. StyleSinger、Demucs、waveform 三个边界均有单独约束文档，且与总审计口径一致。
5. 主观评价与客观指标边界表述谨慎，未出现“已显著更好”的越界结论。
6. 模型资产与运行产物不入库边界明确，默认 preset/speaker（`final_primary` / `lain`）明确。
7. 截图材料全部以“清单/待采集”呈现，未见伪造截图声称。
8. 接口示例文档区分了“代码结构示例”和“已实际运行验证”。

## 2. 风险项状态

| 风险编号 | 风险描述 | 当前状态 | 说明 |
| --- | --- | --- | --- |
| R1 | 缺失材料标注词不完全统一 | 已修正 | 本轮已统一替换为“需补充材料（待截图）”“需补充材料（待人工填写）”“建议补充材料（非必填，按章节需求）”。 |
| R2 | `thesis_ready_sections.md` 第 7 节重复编号 | 已修正 | 两个“5.”已合并为单条，且仅保留一次 prompt 与 speaker 边界说明。 |
| R3 | 最终审查报告版本冲突风险 | 已修正 | 本文件已更新为本轮最终版本，保留审查日期并同步风险状态。 |
| R4 | 论文引用旧测试数字的时效性风险 | 仍需人工补充 | 已在 `test_case_table.md` 标注“当次记录”边界；定稿前仍需你重跑或补日志截图。 |

## 3. 本轮已修改文件（文档口径）

1. `/home/featurize/work/BS/docs/thesis_materials/thesis_ready_sections.md`
2. `/home/featurize/work/BS/docs/thesis_materials/test_case_table.md`
3. `/home/featurize/work/BS/docs/thesis_materials/screenshot_checklist.md`
4. `/home/featurize/work/BS/docs/thesis_materials/subjective_eval_template.md`
5. `/home/featurize/work/BS/docs/thesis_materials/final_thesis_material_review.md`
6. `/home/featurize/work/BS/docs/thesis_materials/next_manual_evidence_todo.md`
7. `/home/featurize/work/BS/docs/thesis_materials/experiment_artifact_index.md`
8. `/home/featurize/work/BS/docs/thesis_materials/codex_audit_report.md`

## 4. 统一口径（当前采用）

1. `需补充材料（待截图）`
2. `需补充材料（待人工填写）`
3. `建议补充材料（非必填，按章节需求）`
4. `主观听评为需补充材料，未补齐前不得用于效果优劣结论。`
5. `Demucs 在上传预处理链路存在可调用分支；默认配置含 mock/fallback，未形成“默认真实分离已验证”结论。`

## 5. 最终论文可采用的材料清单

1. `thesis_ready_sections.md`（正文可引用段落，含边界）
2. `codex_audit_report.md`（全局审计证据）
3. `feature_boundary_report.md`（StyleSinger/Demucs/waveform 边界）
4. `api_examples.md`（接口定义与代码依据）
5. `api_runtime_examples.md`（最小运行验证与异常分支）
6. `exception_handling_table.md`（异常处理证据表）
7. `objective_metrics_table.md`（客观指标趋势表）
8. `experiment_artifact_index.md`（实验产物索引）
9. `model_assets_for_thesis.md`（模型资产与提交边界）
10. `test_case_table.md`（测试材料总表）
11. `screenshot_checklist.md` + `screenshot_capture_guide.md`（截图采集规范）
12. `reference_audit_todo.md`（参考文献与正文引用人工核查待办）

## 6. 结论

当前 `docs/thesis_materials/` 在主技术口径、接口口径、主链路与边界口径方面总体一致，可作为论文材料包直接使用。本轮修改仅涉及文档口径统一与表述修正，不涉及核心业务代码、模型代码、前端功能代码，也未改动模型推理逻辑。剩余工作主要为人工补证（截图采集、测试重跑或日志留档、主观听评真实评分统计）。
