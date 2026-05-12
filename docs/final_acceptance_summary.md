# Final Acceptance Summary

## 基线实现状态

- 基线 commit：`05ed291`
- 当前主链路：So-VITS-SVC + internal FiLM
- 当前默认 preset：`final_primary / lain`
- 模型检查：`scripts/check_models_ready.py --preset final_primary` 通过

## 最新验证快照

- 后端：`127 passed, 20 warnings`
- 前端测试：`9 passed`
- 前端 build：成功
- Node 提示：`20.16.0` 低于 Vite 推荐版本，但本次 build 仍成功
- text style adapter dry-run：已生成 `runtime/eval_reports/text_style_adapter_dry_run.json`
- 主观听评汇总：已生成空状态 `runtime/eval_reports/subjective_eval_summary.json`
- prompt matrix：已生成 `runtime/eval_reports/eval_prompt_matrix.json`
- 客观指标：已生成 `runtime/eval_reports/objective_metrics.json`
- condition-mode ablation：已生成真实单样例报告
- film-strength ablation：已生成真实单样例报告

## 已确认的工程事实

- `style_prompt -> style_emb -> So-VITS-SVC internal_film` 已实现
- 真实 smoke 已生成有效音频，并记录 `executed_internal_film=true`
- `TextStyleEncoder` 可生成 `style_embedding.pt`
- `StyleFiLMAdapter` 可执行调制
- 前端能够展示 `condition_mode / film_strength / executed_internal_film`

## 本轮补充的材料方向

- 训练入口与 dry-run 报告
- 主观听评模板与统计脚本
- 客观指标统计脚本
- `film_strength` / `condition_mode` 消融实验框架
- prompt matrix 与答辩材料索引
- 真实单样例 ablation 导出物与可复现说明

## 当前限制

- 不能声称“强文本风格控制模型已训练完成”
- 不能声称“internal_film 已显著优于 baseline none”
- `external_preset` 若未绑定真实独立专用模型，不能表述成真实专模效果
- 真实大规模听评和更多样本仍是后续工作
- 当前客观指标显示的是可量化差异趋势，不等价于主观优劣结论
