# 实验材料索引

- 扫描范围：`docs/`、`runtime/eval_reports/`、`runtime/figures/`
- 结论口径：仅整理“已存在文件”，不推断未验证能力。

## A. docs 下的实验/评估文档

| 文件路径 | 用途 | 是否可直接写入论文 | 结论边界 |
| --- | --- | --- | --- |
| `/home/featurize/work/BS/docs/experiment_report.md` | 总体实验阶段摘要 | 可引用（需标注日期） | 不可外推为“所有场景稳定最优” |
| `/home/featurize/work/BS/docs/objective_evaluation_report.md` | 客观指标说明与表格 | 可引用 | 仅趋势证据，不等价主观优劣 |
| `/home/featurize/work/BS/docs/effect_ablation_report.md` | 消融实验设计与边界 | 可引用 | “框架已具备”不等于“效果已定论” |
| `/home/featurize/work/BS/docs/training_experiment_report.md` | 训练与内部核验摘要 | 可引用 | 训练对象为 TextStyleAdapter，不是整套主模型重训 |
| `/home/featurize/work/BS/docs/subjective_eval_results.md` | 主观听评结果页 | 可引用（空状态） | 主观听评为需补充材料，未补齐前不得用于效果优劣结论。 |
| `/home/featurize/work/BS/docs/subjective_eval_form.md` | 听评表模板 | 可引用（方法附录） | 模板不是结果 |

## B. runtime/eval_reports 下的结构化产物

### B1. 训练报告

| 文件路径 | 用途 | 是否可直接写入论文 | 结论边界 |
| --- | --- | --- | --- |
| `/home/featurize/work/BS/runtime/eval_reports/text_style_adapter_1000_train_report.json` | 1000 样本训练输出 | 可引用（建议转表格） | 指标仅针对当前数据切分 |
| `/home/featurize/work/BS/runtime/eval_reports/text_style_adapter_500_train_report.json` | 500 样本训练输出 | 可引用 | 不应与 1000 样本结果混为单一结论 |
| `/home/featurize/work/BS/runtime/eval_reports/text_style_adapter_300_train_report.json` | 300 样本训练输出 | 可引用 | 同上 |

### B2. 客观指标

| 文件路径 | 用途 | 是否可直接写入论文 | 结论边界 |
| --- | --- | --- | --- |
| `/home/featurize/work/BS/runtime/eval_reports/objective_metrics_1000.json` | 1000 套件客观指标明细 | 可引用 | 客观指标不替代听评 |
| `/home/featurize/work/BS/runtime/eval_reports/objective_metrics_1000.csv` | 1000 套件表格化指标 | 可转论文表格（**须**同时标注 `case_count=1`、数据来源路径与生成时间） | 样本数当前为 1 个 case |
| `/home/featurize/work/BS/runtime/eval_reports/objective_metrics_1000.md` | 可读版报告 | 可引用 | 需同时标注“case_count=1” |
| `/home/featurize/work/BS/runtime/eval_reports/objective_metrics.json` | 非 1000 套件客观指标 | 可引用 | 与 1000 套件需区分版本 |

### B3. 消融实验

| 文件路径 | 用途 | 是否可直接写入论文 | 结论边界 |
| --- | --- | --- | --- |
| `/home/featurize/work/BS/runtime/eval_reports/film_strength_ablation_1000.json` | `internal_film` 强度消融明细 | 可引用 | 当前不代表主观显著差异 |
| `/home/featurize/work/BS/runtime/eval_reports/film_strength_ablation_1000.md` | 强度消融可读报告 | 可引用 | 需结合 case 数与样本来源说明 |
| `/home/featurize/work/BS/runtime/eval_reports/condition_mode_ablation_1000.json` | `none/external/internal` 条件消融 | 可引用 | `external_preset` 不等价独立专模效果 |
| `/home/featurize/work/BS/runtime/eval_reports/condition_mode_ablation_1000.md` | 条件消融可读报告 | 可引用 | 同上 |

### B4. Prompt 与评估配置

| 文件路径 | 用途 | 是否可直接写入论文 | 结论边界 |
| --- | --- | --- | --- |
| `/home/featurize/work/BS/runtime/eval_reports/eval_prompt_matrix.json` | prompt 矩阵配置 | 可引用（方法说明） | 配置文件不是实验结果 |
| `/home/featurize/work/BS/runtime/eval_reports/eval_prompt_matrix.md` | prompt 矩阵可读说明 | 可引用 | 同上 |
| `/home/featurize/work/BS/runtime/eval_reports/eval_cases.json` | case 输入配置 | 可引用（可复现实验） | 需与实际输出文件配对说明 |

### B5. 主观听评空状态

| 文件路径 | 用途 | 是否可直接写入论文 | 结论边界 |
| --- | --- | --- | --- |
| `/home/featurize/work/BS/runtime/eval_reports/subjective_eval_summary.json` | 主观听评汇总状态 | 可引用 | 当前 `pending_human_scores` |
| `/home/featurize/work/BS/runtime/eval_reports/subjective_eval_summary.md` | 主观听评摘要 | 可引用 | 当前“模板已生成，暂无结论” |
| `/home/featurize/work/BS/runtime/eval_reports/subjective_eval_pack/subjective_eval_scores.template.csv` | 打分模板 | 可引用（附录） | 模板不构成结果 |

## C. runtime/figures 下的图像产物

| 文件路径 | 用途 | 是否可直接写入论文 | 结论边界 |
| --- | --- | --- | --- |
| `/home/featurize/work/BS/runtime/figures/training_loss_curve_1000.png` | 1000 样本训练 loss 曲线 | 可直接插图 | 仅说明该轮训练收敛过程 |
| `/home/featurize/work/BS/runtime/figures/training_loss_curve.png` | 训练曲线（默认） | 可引用 | 需核对对应实验版本 |
| `/home/featurize/work/BS/runtime/figures/training_loss_curve_500.png` | 500 样本训练曲线 | 可引用 | 与 1000 版本需分开描述 |
| `/home/featurize/work/BS/runtime/figures/training_loss_curve_300.png` | 300 样本训练曲线 | 可引用 | 同上 |

## D. 总体结论边界

1. 现有材料足以支撑“工程链路已打通、客观指标可复现、消融框架已建立”的论文表述。
2. 现有材料不足以支撑“主观听感显著优于 baseline”的结论。
3. `runtime/*` 为运行态产物，论文归档前建议人工复制到稳定归档目录并打时间戳。
