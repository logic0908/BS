# Model Preset Guide

当前系统仍以 `So-VITS-SVC` 为默认主链路，默认模型为 `final_primary / lain`。`v1.2` 已把 `final_male_youth / Nova_Adult` 与 `final_male_powerful / AY` 推进到“本地真实 smoke test 通过”的专用男声 preset 状态；其余 preset 仍按真实验证进度分别管理，而不是用 fallback 伪装成“全风格都已接入”。

## 当前 preset 状态

| preset_id | display_name | style_tags | is_configured | smoke_test_passed | source_repo | 说明 |
| --- | --- | --- | --- | --- | --- |
| `final_primary` | 当前可用默认 So-VITS-SVC 模型 | `baseline, demo, general` | 是 | 是 | `SuCicada/Lain-so-vits-svc-4.1` | 当前默认模型，`speaker=lain`，不代表所有专用风格均已覆盖 |
| `final_male_youth` | 少年感男声目标模型 | `male, youth, bright` | 是 | 是 | `Kuugo/Nova-Adult_So-Vits-SVC` | 已通过本地真实 smoke test；`speaker=Nova_Adult`，`speech_encoder=vec768l12`，输出文件可读；`license=license_unknown`，仅内部复核/本地技术演示，不标 demo quality |
| `final_male_powerful` | 力量感男声目标模型 | `male, powerful, thick` | 是 | 是 | `andreyaniv/andre-yaniv-so-vits-svc` | 已通过本地真实 smoke test；`speaker=AY`，`speech_encoder=vec256l9`，输出文件可读；`license=license_unknown`，仅建议用于本地毕业设计技术演示 |
| `final_female_soft` | 温柔女声目标模型 | `female, soft, breathy` | 否 | 否 | `n/a` | 已检索到若干真实女声候选，但公开演示授权链路不够清晰，本轮保持未配置 |
| `final_female_clear` | 清亮女声目标模型 | `female, clear, bright` | 否 | 否 | `n/a` | 已检索到若干清亮女声候选，但来源或授权不适合毕业设计公开演示，本轮保持未配置 |
| `tech_villager` | 技术验收模型：Minecraft Villager | `technical, validation, fallback` | 是 | 是 | `Sucial/so-vits-svc4.1-Minecraft_villager` | 仅用于技术链路验证，不是默认演示模型 |

## 设计边界

- `final_primary / lain` 当前只代表“已验证可跑通的默认演示模型”，不代表所有男女声/多风格都已被真实覆盖。
- `final_male_youth / Nova_Adult` 与 `final_male_powerful / AY` 当前已经通过本地真实 smoke test，但这只证明推理链路可运行，不代表主观效果已经足够优秀；后续仍需要人工听评或 A/B 对比评价。
- 两个新增男声 preset 目前均为 `license_unknown`，只能作为内部复核/本地毕业设计技术演示候选；公开演示或传播前必须补齐授权说明。
- `style_library` 会先按 prompt 做风格匹配；当多个 preset 得分接近时，会优先选择 `ready=true` 的 preset。若命中的是未配置 preset，严格模式下仍返回 `SVC_MODEL_PRESET_NOT_CONFIGURED`。
- `allow_preset_fallback` 仍保持上一轮语义不变：仅在显式开启时才允许回退到 `final_primary/lain`，并且必须显示 requested/effective preset 与 fallback reason。
- `TextStyleAdapter` 目前仍是训练型参数级控制：它可以帮助选择 preset、微调 `transpose/style_strength` 等参数，但不是 So-VITS-SVC 网络内部 Bias/Scale 注入。

## 常用脚本

- 查看当前 prompt 更接近哪个 preset：
  `python scripts/find_svc_models_by_style.py --style "清亮、少年感、男声"`
- 查看当前 prompt 对应的本地占位与远端候选：
  `python scripts/find_svc_models_by_style.py --style "厚重、摇滚、男声" --include-remote-candidates`
- 扫描本地候选目录：
  `python scripts/find_svc_models_by_style.py --style "温柔、气声、女声" --search-root /home/featurize/work/BS/local_models`
- 将真实模型下载/绑定到某个 preset，但默认不直接标成 ready：
  `python scripts/install_svc_model_preset.py --preset-id final_male_youth --repo-id Kuugo/Nova-Adult_So-Vits-SVC --model-file G_10000.pth --config-file config.json --speaker Nova_Adult --source-repo Kuugo/Nova-Adult_So-Vits-SVC --source-url https://huggingface.co/Kuugo/Nova-Adult_So-Vits-SVC --license license_unknown --style-tag male --style-tag youth`
- smoke test 通过后，再把 preset 标成 configured：
  `python scripts/install_svc_model_preset.py --preset-id final_male_youth --model-path /home/featurize/work/BS/local_models/sovits-final/final_male_youth/G_10000.pth --config-path /home/featurize/work/BS/local_models/sovits-final/final_male_youth/config.json --speaker Nova_Adult --source-repo Kuugo/Nova-Adult_So-Vits-SVC --source-url https://huggingface.co/Kuugo/Nova-Adult_So-Vits-SVC --license license_unknown --style-tag male --style-tag youth --mark-configured --smoke-test-passed`
- 真实 smoke test：
  `bash scripts/smoke_test_final_svc_model.sh --preset-id final_male_youth`
- 复验 `final_male_powerful`：
  `bash scripts/smoke_test_final_svc_model.sh --preset-id final_male_powerful --input /home/featurize/work/BS/StyleSinger/test/test.wav --output /tmp/final_male_powerful_smoke_test.wav`

## 下一步提升方向

- 继续对 `final_male_youth` 做听感验证与 license 复核；license 未清晰前保持 `is_demo_quality=false`。
- 继续寻找授权边界更清楚的 `female_soft / female_clear` 候选，而不是为了补齐四个 preset 强行绑定来源可疑模型。
- 继续在 `final_male_powerful` 已通过 smoke 的基础上运行 `python scripts/run_conversion_ablation.py` 做可复现对比与主观听评。

## 2026-05-06 候选检索摘要

完整原始候选报告写入 `runtime/model_search_v1_1/`，该目录不提交 Git。

| preset | 当前候选 | 结论 |
| --- | --- | --- |
| `final_male_youth` | `Kuugo/Nova-Adult_So-Vits-SVC` | 已授权下载复核并通过本地真实 smoke test；`license_unknown`，仅内部复核/本地技术演示，不标 demo quality。 |
| `final_male_powerful` | `andreyaniv/andre-yaniv-so-vits-svc` | 已本地 smoke test 通过，license 仍未知，暂不标 demo quality。 |
| `final_female_soft` | `chjn/so-vits-svc4.1-CopanoRickey` | 技术兼容但来源/非商用风险较高，暂不推荐默认下载。 |
| `final_female_clear` | `Sucial/so-vits-svc4.1-sanwu`、`Shinku0721/Shinku_Yuuki_so-vits-svc_4.1_model` | 技术兼容但 license/source 风险较高，继续寻找更安全候选。 |
