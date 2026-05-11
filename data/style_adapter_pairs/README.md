# style_adapter_pairs

本目录用于存放 TextStyleAdapter 训练/评估所需的小规模提示词-风格配对数据。

请不要提交真实大音频文件到仓库。建议仅提交：

- `metadata.jsonl`
- 少量占位样例或脱敏路径
- 训练/评估输出的 schema 说明

`metadata.jsonl` 每行示例：

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

建议目录结构：

```text
data/style_adapter_pairs/
├── README.md
├── metadata.jsonl
└── audio/
    └── sample_001.wav
```
