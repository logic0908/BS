# Defense Claims

## A. 可以说

- 系统已经实现 `style_prompt -> style_emb -> So-VITS-SVC internal_film` 条件注入链路。
- 真实 smoke 已验证 internal FiLM 链路可执行，并生成有效音频。
- 最新 1000 版证据已记录：`text_style_adapter_loaded=true`、`adapter_checkpoint=runtime/style_adapter/text_style_adapter_1000.pt`、`condition_mode=internal_film`、`executed_internal_film=true`。
- `film_strength` 的 `internal_film_0.05/0.10/0.15` 与 `condition_mode` 的 `internal_film` 组均通过断言核验，且 `adapter_mode=trained`、`adapter_type=trained_mlp`。
- 当前默认模型预设与目标音色是 `final_primary / lain`，前端可展示关键技术字段。
- 当前仓库已补齐主观听评模板、客观指标脚本、ablation 报告与索引。

## B. 谨慎说

- internal_film 在部分样例上可观察到客观指标差异趋势，但主观听感结论仍需人工听评支持。
- 当前 1000 条训练和客观指标是“工程可复现证据”，不是“主观质量结论”的充分证明。
- 文本提示词可以调制风格方向，但不会自动切换目标音色。
- 当前训练对象是 TextStyleAdapter，不是从头训练完整 So-VITS-SVC 主模型。

## C. 不应表述

- 不应把当前结果描述为“已经完成完整强文本风格控制模型训练”。
- 不应把当前结果描述为“提示词可直接保证目标音色切换”。
- 不应把当前结果描述为“主观听感结论已经充分成立”。
- 不应把当前模型资产描述为“已完成公开发布授权清理”。
