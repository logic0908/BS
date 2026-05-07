# TextStyleAdapter v1.2-real-multi-style-preset-review Experiment Report

## Scope

本报告汇总当前 `TextStyleAdapter v1.2-real-multi-style-preset-review` 的数据扩展、训练、评估与真实 Celery 任务结果，重点覆盖：

- `data/style_adapter_pairs/metadata.jsonl` 数据规模与覆盖范围
- `build/train/eval` 训练设置与指标
- 前端四区工作台与 `WaveSurfer.js` A/B 对比接入
- `/api/v1/upload` 的 `input_quality_summary` 与 `input_quality_report.json`
- 默认 So-VITS-SVC 的高级转换参数入口
- 多模型 preset 边界与“未配置 preset 不伪装推理”约束
- `final_male_powerful` 的真实 smoke test 通过记录与当前剩余阻塞点
- 3 个真实 Celery 任务的 `audio_quality`
- 主观评价表模板与导出方式

当前系统仍然是“参数级/旁路控制”的 TextStyleAdapter，不是 So-VITS-SVC 网络内部 Bias/Scale 条件注入。

## 当前已完成数据快照

- backend pytest：`109 passed, 9 warnings`
- frontend build：`passed`
- frontend test：`9 passed`
- `final_male_powerful` smoke test：`success=true`
- style-analysis sidecar：已实现，并由后端/前端测试覆盖
- 当前 Node 版本：`20.16.0`
- Vite 推荐 Node：`20.19+` 或 `22.12+`

## Frontend Demo Workbench

- 当前前端已重构为 `Header / Demo Workspace / Audio Compare / Advanced Details` 四区正式演示工作台。
- `WaveSurfer.js` 已接入原始音频与转换音频的波形显示与 A/B 切换。
- 若 `WaveSurfer.js` 初始化失败，自动 fallback 到原生 `audio` 播放器，不阻断上传、转换与下载主流程。
- 默认主链路仍然是 So-VITS-SVC，StyleSinger 仅保留在折叠高级实验区。

## Upload Input Quality Gate

`/api/v1/upload` 当前会返回 `input_quality_summary`，并在上传目录中生成 `input_quality_report.json`。前端会基于该结果显示“输入质量：良好 / 一般 / 较差”和风险提示。

当前输入质量字段包括：

- `duration`
- `sample_rate`
- `channels`
- `rms`
- `peak`
- `low_energy_ratio`
- `clipping_ratio`
- `silence_ratio`
- `is_too_short`
- `is_probably_silent`
- `quality_level`
- `warnings`

## Advanced Conversion Params

默认 So-VITS-SVC 转换请求当前支持以下高级参数：

- `transpose`
- `style_strength`
- `model_preset_id`
- `f0_method`
- `auto_predict_f0`
- `slice_db`
- `clip_seconds`
- `pad_seconds`

前端高级参数区允许显式选择 `final_primary`、各风格占位 preset 与 `tech_villager fallback`，但默认不会改成 `tech_villager`。

## Model Preset Boundary

- `final_primary / lain` 仍是当前默认演示模型。
- `final_male_youth` 当前已接入 `Kuugo/Nova-Adult_So-Vits-SVC` 并通过本地真实 smoke test，可作为内部复核/本地技术演示候选使用：`speaker=Nova_Adult`，`speech_encoder=vec768l12`，`source_repo=Kuugo/Nova-Adult_So-Vits-SVC`，`license=license_unknown`。
- `final_male_powerful` 当前已通过本地真实 smoke test，可作为专用男声 preset 使用：`speaker=AY`，`speech_encoder=vec256l9`，`source_repo=andreyaniv/andre-yaniv-so-vits-svc`，`license=license_unknown`。
- `final_female_soft / final_female_clear` 当前仍未绑定真实模型；已检索到部分候选，但公开演示授权链路不够清晰，本轮不强行接入。
- 若 prompt 命中未配置 preset，系统会返回 `SVC_MODEL_PRESET_NOT_CONFIGURED`，并在前端说明“该风格尚未绑定目标模型”。
- 只有显式开启 `allow_preset_fallback=true` 时，才允许回退到 `final_primary/lain`，并且会同时显示 requested/effective preset 与 fallback reason。
- `final_male_youth` 与 `final_male_powerful` 当前 smoke test 通过只代表推理链路可运行，不代表主观风格效果已经优于默认演示模型；仍需 license 复核、人工听评与 A/B 对比。

## Effect Gap Analysis

当前系统与参考 SVC 示例仍有差距，主要来自三类因素：

1. 目标模型域差异：`final_primary / lain` 不是多风格全覆盖模型。
2. 控制层级差异：当前 Adapter 是参数级控制，不是 So-VITS-SVC 网络内部 Bias/Scale 注入。
3. 信号处理差异：输入干净程度、F0 方法、人声分离质量与转调设置都会显著影响自然度与风格贴合度。

对应的答辩口径是：当前系统已经具备“可演示、可复现、可解释”的真实链路，但效果提升仍依赖更匹配的目标模型 preset、稳定的 F0 方法与人工主观评价证据。

## Specialized Preset Smoke Evidence

| preset_id | speaker | model_file | speech_encoder | task_id | output_readable | duration_seconds | command_matches_preset | result |
| --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| `final_male_youth` | `Nova_Adult` | `G_10000.pth` | `vec768l12` | `smoke-final_male_youth-1778076531` | `true` | `12.007` | `true` | `passed` |
| `final_male_powerful` | `AY` | `G_15000.pth` | `vec256l9` | `smoke-final_male_powerful-1777912011` | `true` | `12.007` | `true` | `passed` |

补充说明：

- `final_male_youth selected_output=/home/featurize/work/BS/so-vits-svc/results/smoke-final_male_youth-1778076531.wav_0key_Nova_Adult_sovits_pm.flac`
- `final_male_youth output_path=/tmp/final_male_youth_smoke_test.wav`
- `final_male_powerful selected_output=/home/featurize/work/BS/so-vits-svc/results/smoke-final_male_powerful-1777912011.wav_0key_AY_sovits_pm.flac`
- `final_male_powerful output_path=/tmp/final_male_powerful_smoke_test.wav`
- `called_inference_main=true`
- `speaker_matches_preset=true`
- `return_code=0`

## Dataset

- 数据集文件：`data/style_adapter_pairs/metadata.jsonl`
- 当前人工样例数：`56`
- 样例 schema：
  - `id`
  - `audio_path`
  - `prompt`
  - `style_tags`
  - `model_preset_id`
  - `transpose`
  - `style_strength`
  - `notes`
- 当前覆盖重点：
  - 清亮 / 明亮 / 清澈
  - 厚重 / 有力 / 摇滚
  - 温柔 / 气声 / 抒情
  - 少年感 / 男声
  - 女声 / 流行
  - 低沉 / 成熟
- 额外保留：
  - `technical` 样例，用于 `tech_villager` 技术验收分支

## Training Setup

- 预处理脚本：`python scripts/build_style_adapter_dataset.py`
- 训练脚本：`python scripts/train_text_style_adapter.py`
- 评估脚本：`python scripts/eval_text_style_adapter.py`
- 文本编码器：`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- 输入维度：`384`
- MLP hidden dims：`[128, 64]`
- 输出控制维度：`6`
  - `brightness`
  - `power`
  - `breathiness`
  - `youthfulness`
  - `transpose`
  - `style_strength`
- 训练 epochs：`80`
- learning rate：`1e-3`
- final loss：`0.02664913423359394`
- runtime checkpoint：`runtime/style_adapter/text_style_adapter_v1.pt`
- 在线配置：
  - `STYLE_ADAPTER_USE_TRAINED=true`
  - `STYLE_ADAPTER_CHECKPOINT_PATH=/home/featurize/work/BS/runtime/style_adapter/text_style_adapter_v1.pt`
- 在线策略：
  - 优先加载训练型 Adapter
  - checkpoint 缺失、加载失败、维度不匹配时回退到 rule-based
  - 前端显示 `adapter_mode: trained / rule_based / fallback`

## Eval Metrics

评估摘要来源：`runtime/style_adapter/eval_summary.json`

- records：`56`
- tag_accuracy：`0.952381`
- mse_for_numeric_controls：`0.026125`

说明：

- `tag_accuracy` 是当前受支持标签维度上的逐标签准确率近似统计
- `mse_for_numeric_controls` 是训练目标控制向量上的均方误差
- 当前指标用于说明“训练型 Adapter 已可在线加载并稳定输出控制参数”，不代表终版论文泛化上限

## Real Celery Tasks

以下 3 个任务均为：

- `task_backend_mode=celery`
- `inference_mode=real`
- `adapter_mode=trained`
- `model_preset_id=final_primary`
- `speaker=lain`

| task_id | prompt | adapter_mode | inference_mode | model_preset_id | speaker |
| --- | --- | --- | --- | --- | --- |
| `b7c03828-e10d-4552-ac51-63f9dececfba` | 清亮、少年感、男声 | `trained` | `real` | `final_primary` | `lain` |
| `1a9d1b8b-a090-448e-b6e8-1252dc2ff5d3` | 温柔、气声、抒情女声 | `trained` | `real` | `final_primary` | `lain` |
| `4e703d1d-4af6-475b-9c29-a7a8fd0f8b3b` | 低沉、成熟、厚重男声 | `trained` | `real` | `final_primary` | `lain` |

## Audio Quality Table

| task_id | duration_consistency | low_energy_ratio | possible_dropouts |
| --- | ---: | ---: | --- |
| `b7c03828-e10d-4552-ac51-63f9dececfba` | `1.0` | `0.277992` | `false` |
| `1a9d1b8b-a090-448e-b6e8-1252dc2ff5d3` | `1.0` | `0.26834` | `false` |
| `4e703d1d-4af6-475b-9c29-a7a8fd0f8b3b` | `1.0` | `0.262548` | `false` |

当前报告展示的是前端最常用的 `audio_quality` 摘要指标。底层报告仍会在 debug 目录保留更完整的 `duration / sample_rate / channels / rms / peak / low_energy_ratio / duration_mismatch_ratio`。

## Subjective Evaluation

- 固定模板文档：`docs/subjective_eval_form.md`
- 当前结果文档：`docs/subjective_eval_results.md`
- 自动导出脚本：`python scripts/export_subjective_eval_pack.py`
- 最新导出包：`runtime/eval_reports/latest_subjective_eval_pack.md`
- 新的正式评价规划文档：`docs/subjective_evaluation_plan.md`
- 主观聚合脚本：`python scripts/aggregate_subjective_scores.py`

当前 `docs/subjective_eval_results.md` 已写入 3 个真实任务的基础信息，但评分列保持为空，待人工填写。

建议主观打分维度：

- 风格符合度
- 自然度
- 歌词可懂度
- 原旋律保持
- 总体满意度

### Subjective Evaluation Table Template

| task_id | prompt | 风格符合度 1-5 | 自然度 1-5 | 歌词可懂度 1-5 | 原旋律保持 1-5 | 总体满意度 1-5 | 备注 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `b7c03828-e10d-4552-ac51-63f9dececfba` | 清亮、少年感、男声 |  |  |  |  |  |  |
| `1a9d1b8b-a090-448e-b6e8-1252dc2ff5d3` | 温柔、气声、抒情女声 |  |  |  |  |  |  |
| `4e703d1d-4af6-475b-9c29-a7a8fd0f8b3b` | 低沉、成熟、厚重男声 |  |  |  |  |  |  |

## Limitations

- 当前 56 条样例仍然属于小规模人工数据，只能支撑原型验证
- 当前 Adapter 仍是参数级控制，不是 So-VITS-SVC 网络内部条件注入
- 当前多风格 preset 仍有多个占位项未绑定真实模型
- 主观评分模板和导出包已经具备，但人工听评结果还需要继续填写和汇总
- style-analysis 客观指标是启发式辅助证据，不能直接等价为主观听感或论文中的最终听感结论

## Evaluation Workflow

当前新增了一套更适合论文/答辩使用的评价闭环：

- 总体方案：`docs/evaluation_plan.md`
- 客观评价报告：`docs/objective_evaluation_report.md`
- 主观评价方案：`docs/subjective_evaluation_plan.md`
- 性能评价：`docs/performance_report.md`
- 客观评价脚本：`python scripts/run_objective_evaluation.py`
- 主观聚合脚本：`python scripts/aggregate_subjective_scores.py`
- 客观结果 JSON：`evaluation/objective_results.json`
- 主观模板 CSV：`evaluation/subjective_template.csv`

## Validation Snapshot

- backend pytest：`109 passed, 9 warnings`
- frontend build：通过
- frontend test：`9 passed`
- 当前 Node 版本：`20.16.0`
- Vite 推荐 Node：`20.19+` 或 `22.12+`
- 当前结论：虽然 Node 版本低于推荐值，但前端构建仍已通过；后续建议升级 Node 以减少 Vite 环境 warning
