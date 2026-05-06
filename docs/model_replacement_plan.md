# Model Replacement Plan

生成日期：2026-05-06

## 1. 当前模型现状

- `final_primary / lain`：当前可用默认模型，`is_configured=true`，`smoke_test_passed=true`，可用于默认演示；它不代表所有专用风格均已覆盖。
- `tech_villager / villager`：仅技术验收 fallback，证明真实 So-VITS-SVC CUDA 推理链路可用，不作为默认演示模型。
- `final_male_powerful / AY`：已绑定本地模型并通过真实 smoke test，`is_configured=true`，但 `license=license_unknown`，只能作为本地技术演示候选，不能标成授权边界清晰的 demo quality。
- `final_male_youth / Nova_Adult`：已下载并通过真实 smoke test，`is_configured=true`，但 `license=license_unknown`，只能作为内部复核/本地技术演示候选，不能标成授权边界清晰的 demo quality。
- `final_female_soft`：待配置。已找到技术兼容候选，但授权/来源风险较高。
- `final_female_clear`：待配置。已找到技术兼容候选，但授权/来源风险较高。
- `allow_preset_fallback`：已完成，默认关闭；开启后也必须明确展示 requested/effective preset，不能把 fallback 说成专用风格真实效果。

## 2. 候选模型筛选结果

候选原始报告位于：

- `runtime/model_search_v1_1/candidates_raw.json`
- `runtime/model_search_v1_1/candidates_filtered.json`
- `runtime/model_search_v1_1/candidates.md`

这些文件位于 `runtime/`，不提交 Git。

本轮检索来源包括 Hugging Face API / model search、GitHub repository/code search，以及公开页面线索；模型资产必须最终落到 Hugging Face 或 GitHub 可下载文件，并满足 `权重 + config.json + speaker`。

| preset | 推荐级别 | 候选 | 是否允许下载 | license 风险 | 处理建议 |
| --- | --- | --- | --- | --- | --- |
| `final_female_soft` | 备用/暂不推荐 | `chjn/so-vits-svc4.1-CopanoRickey` | 暂不建议，除非用户确认非商用/授权边界可接受 | 高，`cc-by-nc-4.0` 且游戏角色音源 | 技术兼容，但不设为 demo quality；如下载需授权确认与 smoke test。 |
| `final_female_soft` | 排除 | `Sucial/so-vits-svc4.1-sanwu` | 不建议 | 高，可能涉及真实歌手/声音来源风险 | 不作为公开答辩默认候选。 |
| `final_female_soft` | 排除 | `Shinku0721/Shinku_Yuuki_so-vits-svc_4.1_model` | 不建议 | 高，`cc-by-nc-sa-4.0` 且来源需复核 | 可留作研究线索，不接默认。 |
| `final_female_clear` | 备用/暂不推荐 | `Sucial/so-vits-svc4.1-sanwu` | 不建议 | 高，来源/肖像声音风险 | 技术兼容但不适合作为默认公开演示。 |
| `final_female_clear` | 备用/暂不推荐 | `Shinku0721/Shinku_Yuuki_so-vits-svc_4.1_model` | 暂不建议 | 高，非商用 + SA，日语音色 | 只可在用户确认后下载并本地 smoke test。 |
| `final_female_clear` | 当前默认基线 | `SuCicada/Lain-so-vits-svc-4.1` | 已存在 | 中，`gpl` | 继续作为 `final_primary`，不能冒充专用清亮女声。 |
| `final_male_youth` | 已复核 | `Kuugo/Nova-Adult_So-Vits-SVC` | 已授权下载并本地 smoke test 通过 | 中，`license_unknown` | 结构匹配：`G_10000.pth`、`config.json`、`speaker=Nova_Adult`、`vec768l12`；可 `is_configured=true`，但保持 `is_demo_quality=false`。 |
| `final_male_youth` | 备用 | `None1145/So-VITS-SVC-Lappland` | 暂不建议 | 高，角色音源和数据集版权风险 | 技术兼容但不贴“少年男声”，不建议主推。 |
| `final_male_youth` | 排除 | 政治人物/真人 So-VITS-SVC 模型 | 不允许 | 高 | 不接入。 |
| `final_male_powerful` | 当前保留 | `andreyaniv/andre-yaniv-so-vits-svc` | 已存在 | 中，`license_unknown` | 已 smoke test，可保留 configured；license 未清晰前不标 `is_demo_quality=true`。 |
| `final_male_powerful` | 备用 | `Kuugo/Nova-Adult_So-Vits-SVC` | 需要授权下载 | 中 | 更偏 youth，不作为 powerful 首选。 |
| `final_male_powerful` | 排除 | `tech_villager` | 不作为风格模型 | 中，技术 fallback | 仅技术验收，不替代男声风格模型。 |

## 3. 替换原则

- 只有 smoke test 通过才允许 `is_configured=true`。
- 只有 license 可接受且来源风险可解释，才允许 `is_demo_quality=true`。
- 不用 `final_primary/lain` 冒充未配置风格。
- fallback 必须显式提示，必须展示 `requested_model_preset_id` 与 `effective_model_preset_id`。
- 不提交模型文件、音频文件、`runtime/`、`local_models/`、`so-vits-svc/`。
- 下载必须显式授权：`scripts/install_svc_model_preset.py` 默认 dry-run；远端下载必须加 `--apply --confirm-download` 或 `CONFIRM_DOWNLOAD=1 --apply`。

## 4. 执行顺序

1. 先处理 `final_female_soft` 或 `final_female_clear`：继续寻找 license 更清晰、非真人/非名人的女声模型；当前候选风险偏高，不建议马上下载。
2. 继续处理 `final_male_youth`：当前已 smoke test 通过，下一步只做 license 说明和主观听评，不再把它当作未下载候选。
3. 再复核 `final_male_powerful`：已可运行，但需要 license 说明和主观听评。
4. 每接入一个模型就运行 smoke test。
5. 每接入一个模型就更新 `docs/effect_ablation_report.md` 和 `docs/subjective_eval_results.md`。

## 5. Smoke Test 标准

每个模型必须满足：

- `SOVITS_MOCK=false`
- `SOVITS_DEVICE=cuda`
- `return_code=0`
- output wav 可读
- speaker 与 config/preset 一致
- `runtime/debug/<task_id>/sovits_command.txt` 指向该 preset 的 model/config/speaker
- result metadata 显示 `effective_model_preset_id`
- 未配置 preset 不误用 `final_primary`
- `allow_preset_fallback=false` 时，未配置 preset 返回 `SVC_MODEL_PRESET_NOT_CONFIGURED`

## 6. v1.2 已完成的授权下载复核

本轮已按用户授权复核 `Kuugo/Nova-Adult_So-Vits-SVC`，并落盘到 `local_models/sovits-final/final_male_youth/`：

```bash
bash scripts/smoke_test_final_svc_model.sh --preset-id final_male_youth
```

smoke test 结果：`return_code=0`，`speaker=Nova_Adult`，`soundfile_readable=true`，`command_matches_preset=true`。由于 license 仍为 `license_unknown`，该 preset 只允许 `is_configured=true / smoke_test_passed=true / is_demo_quality=false`。

当前建议仍先不下载女声高风险候选。若继续推进女声 preset，需要先找到授权边界更清晰的候选，或由用户明确授权仅做内部复核。
