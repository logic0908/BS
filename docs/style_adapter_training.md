# TextStyleAdapter 训练说明

## 当前状态

当前仓库中的 `TextStyleAdapter v1` 是旁路参数控制原型：

- 输入：提示词 embedding、`style_strength`、`selected_style`
- 输出：`model_preset_id`、`transpose`、`brightness`、`power`、`breathiness`、`youthfulness`

它还不是 So-VITS-SVC 网络内部的端到端神经注入模块。

## 数据准备

在 `data/style_adapter_pairs/metadata.jsonl` 中按如下 schema 准备样本：

```json
{
  "id": "sample_001",
  "audio_path": "audio/sample_001.wav",
  "prompt": "清亮、少年感、男声",
  "style_tags": ["bright", "youth", "male"],
  "model_preset_id": "final_primary",
  "transpose": 0,
  "style_strength": 0.8,
  "notes": ""
}
```

不要提交真实大音频文件到仓库。

## 构建 embedding 数据

```bash
cd /home/featurize/work/BS
python scripts/build_style_adapter_dataset.py
```

输出：

- `data/style_adapter_pairs/prepared/embeddings.npy`
- `data/style_adapter_pairs/prepared/records.jsonl`

## 训练最小 MLP 骨架

```bash
cd /home/featurize/work/BS
python scripts/train_text_style_adapter.py
```

输出：

- `runtime/style_adapter/text_style_adapter_v1.pt`
- `runtime/style_adapter/training_summary.json`

## 评估

```bash
cd /home/featurize/work/BS
python scripts/eval_text_style_adapter.py
```

当前 eval 会输出：

- `tag accuracy`
- `mse for numeric controls`
- `sample predictions`

## 后续工作

- 收集更稳定的提示词-风格配对数据
- 训练真正的 Adapter 参数网络
- 将 Adapter 输出的 Bias / Scale 注入 So-VITS-SVC 中间层
- 扩展多风格模型 preset 与更细粒度控制参数
