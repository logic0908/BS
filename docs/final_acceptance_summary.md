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
- 客观指标（1000 对齐版）：已刷新 `runtime/eval_reports/objective_metrics_1000.{json,csv,md}`
- condition-mode ablation（1000）：已通过最终断言核验
- film-strength ablation（1000）：已通过最终断言核验
- 1000 条训练：已生成 `runtime/eval_reports/text_style_adapter_1000_train_report.json`
- 1000 adapter checkpoint：`runtime/style_adapter/text_style_adapter_1000.pt`
- 1000 曲线图：`runtime/figures/training_loss_curve_1000.png`

## 已确认的工程事实

- `style_prompt -> style_emb -> So-VITS-SVC internal_film` 已实现
- 真实 smoke 已生成有效音频，并记录 `executed_internal_film=true`
- 真实 smoke 已记录 `text_style_adapter_loaded=true` 与 `adapter_checkpoint=runtime/style_adapter/text_style_adapter_1000.pt`
- `film_strength` 的 `internal_film_0.05/0.10/0.15` 全部满足：`executed_internal_film=true`、`text_style_adapter_loaded=true`、`adapter_mode=trained`、`adapter_type=trained_mlp`
- `condition_mode` 的 `internal_film` 组满足：`executed_internal_film=true`、`text_style_adapter_loaded=true`、`adapter_mode=trained`、`adapter_type=trained_mlp`
- `TextStyleEncoder` 可生成 `style_embedding.pt`
- `StyleFiLMAdapter` 可执行调制
- 前端能够展示 `condition_mode / film_strength / executed_internal_film`
- `TextStyleAdapter` 训练型 checkpoint 已可被类加载（`adapter_mode=trained`，无 fallback）

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
