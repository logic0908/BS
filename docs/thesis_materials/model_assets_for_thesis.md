# 论文模型资产说明

## 1. 证据来源

- `/home/featurize/work/BS/docs/model_assets_setup.md`
- `/home/featurize/work/BS/backend/app/config/svc_model_presets.json`
- `/home/featurize/work/BS/backend/.env.example`
- `/home/featurize/work/BS/README.md`

## 2. 默认配置（论文统一口径）

- 默认 preset：`final_primary`
- 默认 speaker：`lain`
- 主链路：So-VITS-SVC

## 3. 关键模型资产类别

| 资产类别 | 典型文件 | 作用 | 本地放置路径（示例） |
| --- | --- | --- | --- |
| So-VITS-SVC 权重 | `G_*.pth` | 执行歌声转换推理 | `/home/featurize/work/BS/local_models/sovits-final/...` |
| So-VITS-SVC 配置 | `config.json` | 定义 speaker、网络参数、编码器配置 | `/home/featurize/work/BS/local_models/sovits-final/...` |
| ContentVec | `checkpoint_best_legacy_500.pt` | 语音内容特征编码 | `/home/featurize/work/BS/so-vits-svc/pretrain/` 或环境变量路径 |
| RMVPE | `rmvpe.pt` | F0 提取相关模型 | `/home/featurize/work/BS/backend/models/rmvpe/` 或环境变量路径 |
| TextStyleAdapter | `text_style_adapter_1000.pt` | 文本风格控制参数映射 | `/home/featurize/work/BS/runtime/style_adapter/` |

## 4. 预设与 speaker（来自 presets 配置）

| preset_id | speaker | 状态摘要 |
| --- | --- | --- |
| `final_primary` | `lain` | 默认演示 preset，已配置 |
| `final_male_youth` | `Nova_Adult` | 已配置，`license_unknown`，非默认 demo quality |
| `final_male_powerful` | `AY` | 已配置，`license_unknown`，非默认 demo quality |
| `tech_villager` | `villager` | 技术验收 fallback，不是默认 |

说明：上述数据来自 `backend/app/config/svc_model_presets.json`。

## 5. 环境变量要点（示例）

来自 `backend/.env.example`：

- `SVC_MODEL_PRESET_ID=final_primary`
- `SOVITS_SPEAKER=lain`
- `SOVITS_MODEL_PATH=.../local_models/sovits-final/final_primary/G_2400_infer.pth`
- `SOVITS_CONFIG_PATH=.../local_models/sovits-final/final_primary/config.json`
- `SOVITS_CONDITION_MODE=internal_film`
- `STYLE_ADAPTER_CHECKPOINT_PATH=.../runtime/style_adapter/text_style_adapter_1000.pt`

## 6. 为什么不提交到 GitHub

1. 模型权重和音频产物体积大，不适合源码仓库存储。
2. 部分公开模型许可证/授权边界不适合二次分发。
3. 本地运行产物（`runtime/*`）频繁变化，不应作为源码版本控制对象。
4. 仓库 `.gitignore` 已明确排除模型与音频产物类别。

## 7. 论文写作边界

- 可以写：系统依赖本地模型资产与配置文件完成真实推理。
- 不应写：模型资产随仓库一键完整提供。
- 必须写明：默认 preset 为 `final_primary`，默认 speaker 为 `lain`，模型资产不随仓库提交。
