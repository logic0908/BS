# Defense Claims

## A. 可以说

- 系统已经实现 `style_prompt -> style_emb -> So-VITS-SVC internal Bias/Scale / FiLM` 的条件注入链路。
- 真实 smoke 已验证 internal FiLM 链路可执行，并生成有效音频。
- `final_primary / lain` 的模型资产已补齐，前端可展示 `condition_mode`、`film_strength`、`executed_internal_film`。
- 当前仓库已经补齐主观听评模板、客观指标脚本、prompt matrix 和 ablation 报告导出框架。

## B. 谨慎说

- `internal_film` 在部分样例上可能带来可测的特征差异，但是否形成稳定、显著的主观优势仍需听评验证。
- 文本提示词与输出风格之间已经建立了工程链路，但风格区分是否足够明显仍需更多样本、更多 prompt 和更多人工听评支持。
- `external_preset` 当前更多是逻辑层外部预设/参数路径；若未绑定独立真实专模，不应直接用作效果优越性的结论。

## C. 不要说

- 已训练完成强文本风格控制模型。
- `internal_film` 一定显著优于 baseline `none`。
- 系统可以稳定复刻任意歌手风格。
- 当前模型与权重可以直接商用。
