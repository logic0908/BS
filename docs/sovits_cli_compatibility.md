# So-VITS-SVC CLI Compatibility

生成日期：2026-05-06

## 当前 So-VITS-SVC 版本与入口

- 本地仓库：`/home/featurize/work/BS/so-vits-svc`
- 当前推理入口：`so-vits-svc/inference_main.py`
- 当前 wrapper：`backend/app/models_svc/sovits_wrapper.py`
- 当前调用方式：将输入音频复制/重编码到 `so-vits-svc/raw/<task_id>.wav`，再调用 `inference_main.py`，最后从 `so-vits-svc/results/` 发现新输出。

## `inference_main.py` 支持的主要参数

从当前文件的 `argparse` 定义读取到：

| CLI 参数 | 含义 | 当前 wrapper 是否透传 |
| --- | --- | --- |
| `-m / --model_path` | 模型权重路径 | 是 |
| `-c / --config_path` | 配置路径 | 是 |
| `-cl / --clip` | 强制切片秒数 | 否 |
| `-n / --clean_names` | `raw/` 下输入 wav 文件名 | 是 |
| `-t / --trans` | 半音转调 | 是 |
| `-s / --spk_list` | 目标 speaker | 是 |
| `-a / --auto_predict_f0` | 自动预测 F0 | 否 |
| `-cm / --cluster_model_path` | 聚类/检索索引路径 | 否 |
| `-cr / --cluster_infer_ratio` | 聚类/检索比例 | 否 |
| `-lg / --linear_gradient` | 切片交叉淡入长度 | 否 |
| `-f0p / --f0_predictor` | F0 预测器，如 `pm/dio/harvest/rmvpe/fcpe` | 否 |
| `-eh / --enhance` | NSF-HIFIGAN 增强器 | 否 |
| `-shd / --shallow_diffusion` | 浅扩散 | 否 |
| `-usm / --use_spk_mix` | 角色融合 | 否 |
| `-lea / --loudness_envelope_adjustment` | 响度包络融合比例 | 否 |
| `-fr / --feature_retrieval` | 特征检索 | 否 |
| `-dm / --diffusion_model_path` | 扩散模型路径 | 否 |
| `-dc / --diffusion_config_path` | 扩散配置路径 | 否 |
| `-ks / --k_step` | 扩散步数 | 否 |
| `-se / --second_encoding` | 二次编码 | 否 |
| `-od / --only_diffusion` | 纯扩散模式 | 否 |
| `-sd / --slice_db` | 自动切片阈值 | 否 |
| `-d / --device` | 推理设备 | 是 |
| `-ns / --noice_scale` | 噪声尺度 | 否 |
| `-p / --pad_seconds` | 推理 pad 秒数 | 否 |
| `-wf / --wav_format` | 输出格式 | 否，默认使用 So-VITS-SVC 自身默认 |
| `-lgr / --linear_gradient_retain` | 自动切片交叉保留比例 | 否 |
| `-eak / --enhancer_adaptive_key` | 增强器适配音域 | 否 |
| `-ft / --f0_filter_threshold` | crepe F0 过滤阈值 | 否 |

## 当前 wrapper 实际透传的参数

`SoVitsSvcEngine._build_command()` 当前只构造：

```bash
python inference_main.py \
  -m <model_path> \
  -c <config_path> \
  -n <clean_name>.wav \
  -t <transpose> \
  -s <speaker> \
  -d <device>
```

这是一条保守路径，优点是最小化与 So-VITS-SVC 版本差异相关的风险；缺点是前端/后端已经记录的一些高级参数尚未真实影响 CLI。

## 参数透传状态

| 参数 | 当前状态 | 说明 |
| --- | --- | --- |
| `transpose` | 真实透传 | 通过 `-t` 传给 CLI。 |
| `f0_method` | 仅记录，不透传 | 当前记录为 `f0_method`，理论对应 `-f0p/--f0_predictor`。需要先确认 `rmvpe.pt`、依赖与模型兼容性。 |
| `auto_predict_f0` | 仅记录，不透传 | 理论对应 `-a`。歌声转换中开启可能严重跑调，应作为显式高级实验项。 |
| `slice_db` | 仅记录，不透传 | 理论对应 `-sd`。可安全加入，但需要验证输出命名和结果发现逻辑。 |
| `clip_seconds` | 仅记录，不透传 | 理论对应 `-cl`。强制切片可能改变音频连续性，建议先 smoke test。 |
| `pad_seconds` | 仅记录，不透传 | 理论对应 `-p`。相对低风险，但仍需按 preset smoke test。 |

## 哪些参数只能先记录，不能传

当前不建议立即透传：

- `shallow_diffusion`、`diffusion_model_path`、`diffusion_config_path`：需要每个模型都有匹配扩散权重，否则会制造新失败点。
- `feature_retrieval`、`cluster_model_path`、`cluster_infer_ratio`：需要每个模型有对应索引或聚类文件。
- `enhance`：需要 NSF-HIFIGAN 预训练资产，并且部分训练充分模型可能被增强器劣化。
- `auto_predict_f0`：So-VITS-SVC README 明确提示歌声转换中不宜随意开启，容易跑调。

## 为什么不恢复 `-i/-o`

当前本地 `inference_main.py` 没有 `-i/--input` 或 `-o/--output` 参数。它沿用 So-VITS-SVC 4.x 的 `raw/` 输入目录和 `results/` 输出目录约定：

- 输入通过 `-n clean_name.wav` 指向 `raw/clean_name.wav`；
- 输出由脚本写入 `results/`，文件名包含 key、speaker、f0 predictor 和格式；
- wrapper 使用“运行前已有文件集合 + 运行后新增文件集合”来定位输出。

因此恢复 `-i/-o` 会与当前 CLI 不兼容，并且会掩盖真实失败原因。正确路线是继续使用 `raw/results` 约定，必要时只新增当前 CLI 实际支持的参数。

## 与当前 wrapper 的差距

- `conversion_params.json` 和前端高级参数已经能记录 `f0_method/auto_predict_f0/slice_db/clip_seconds/pad_seconds`，但 CLI 只接收 `transpose`。
- 文档和 UI 必须明确“部分参数为实验记录，尚未透传”，不能说这些参数已经真实控制 So-VITS-SVC。
- 后续最小改动路线：先透传 `slice_db`、`pad_seconds`、`clip_seconds`，每项都用 `SOVITS_MOCK=false`、`SOVITS_DEVICE=cuda`、单 preset smoke test 验证；`f0_method=rmvpe` 需先确认 RMVPE 资产存在；`auto_predict_f0` 保持高级实验开关。
