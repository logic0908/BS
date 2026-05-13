# Defense Claims

## A. 可以说

- 系统已经实现 `style_prompt -> style_emb -> So-VITS-SVC internal_film` 的条件注入链路。
- 真实 smoke 已验证 internal FiLM 链路可执行，并生成有效音频。
- 最新 smoke 证据已同时记录：`text_style_adapter_loaded=true`、`adapter_checkpoint=runtime/style_adapter/text_style_adapter_1000.pt`、`condition_mode=internal_film`、`executed_internal_film=true`。
- `film_strength` 的 `internal_film_0.05/0.10/0.15` 与 `condition_mode` 的 `internal_film` 组均已通过最终断言核验，且 `adapter_mode=trained`、`adapter_type=trained_mlp`。
- `final_primary / lain` 的模型资产已补齐，前端可展示 `condition_mode`、`film_strength`、`executed_internal_film`。
- 当前仓库已经补齐主观听评模板、客观指标脚本、prompt matrix 和 ablation 报告导出框架。
- `text_style_adapter_1000.pt` 已通过类加载与 checkpoint 结构校验，训练/验证/测试指标可复查。

## B. 谨慎说

- `internal_film` 在部分样例上可能带来可测的特征差异，但是否形成稳定、显著的主观优势仍需听评验证。
- 当前 1000 条训练指标和客观指标趋势是“工程可复现证据”，不是“主观显著更优”的充分证明。
- 文本提示词与输出风格之间已经建立了工程链路，但风格区分是否足够明显仍需更多样本、更多 prompt 和更多人工听评支持。
- `external_preset` 当前更多是逻辑层外部预设/参数路径；若未绑定独立真实专模，不应直接用作效果优越性的结论。

## C. 不要说

- 已训练完成强文本风格控制模型。
- `internal_film` 一定显著优于 baseline `none`。
- 系统可以稳定复刻任意歌手风格。
- 当前模型与权重可以直接商用。
