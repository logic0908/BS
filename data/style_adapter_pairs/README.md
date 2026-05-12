# style_adapter_pairs

本目录用于整理 TextStyleAdapter 训练入口、small-scale micro-tuning、dry-run 与后续大规模数据扩展所需的元数据。

当前原则：

- 不提交真实大音频
- 不提交训练权重
- 可以提交数据 schema、README 和少量脱敏示例

## 推荐目录

```text
data/style_adapter_pairs/
├── README.md
├── metadata.jsonl
└── prepared/
    ├── embeddings.npy
    └── records.jsonl
```

`prepared/` 为本地生成产物，不要求提交。

## metadata.jsonl 字段

每行一个 JSON object，至少包含：

```json
{
  "id": "sample_001",
  "input_audio_path": "runtime/eval_samples/input/sample_001.wav",
  "target_audio_path": "runtime/eval_samples/target/sample_001.wav",
  "output_audio_path": "runtime/eval_samples/output/sample_001.wav",
  "style_prompt": "温柔、明亮、流行感更强的女声风格",
  "style_label": "soft,bright,pop,female",
  "singer": "lain",
  "speaker": "lain",
  "split": "train",
  "notes": "engineering validation only"
}
```

字段说明：

- `input_audio_path`
- `target_audio_path` 或 `output_audio_path`
- `style_prompt`
- `style_label`
- `singer` 或 `speaker`
- `split`
- `notes`

可选字段：

- `model_preset_id`
- `transpose`
- `style_strength`
- `style_tags`

## 当前边界

当前仓库中补齐的是：

- 数据组织格式
- embedding 预处理入口
- lightweight adapter 训练入口
- dry-run report 机制

当前还没有完成：

- 基于大规模风格标注数据的强文本风格控制训练
- 能直接据此写成“文本强控制已完成”的充分实验结果
