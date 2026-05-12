# Style Adapter Training

## 当前定位

当前 BS 主链路已经实现：

- `style_prompt -> style_emb -> So-VITS-SVC internal_film`
- 真实 `internal_film` smoke 可执行
- `conditioning_report.json` 可证明 `executed_internal_film=true`

但这不等于“强文本风格控制模型已训练完成”。

当前阶段更准确的口径是：

- 已实现文本条件注入机制
- 已补齐 lightweight adapter / deterministic fallback encoder / small-scale dry-run 训练入口
- 强文本风格控制仍需要更大规模、带风格标注的数据继续训练

## 数据组织格式

推荐元数据文件：`data/style_adapter_pairs/metadata.jsonl`

每行至少包含：

```json
{
  "id": "sample_001",
  "input_audio_path": "runtime/eval_samples/input/sample_001.wav",
  "target_audio_path": "runtime/eval_samples/target/sample_001.wav",
  "output_audio_path": "runtime/eval_samples/output/sample_001.wav",
  "style_prompt": "清亮、少年感、流行男声",
  "style_label": "bright,youth,male",
  "singer": "lain",
  "speaker": "lain",
  "split": "train",
  "notes": "small-sample engineering validation only"
}
```

说明：

- `target_audio_path` 与 `output_audio_path` 至少提供一个
- `style_prompt` 是训练和 dry-run 的核心字段
- `style_label` 用于构造 lightweight adapter 的目标控制标签
- `singer` / `speaker` 当前主要作为元数据与后续分层采样字段

## 数据准备脚本

```bash
cd /home/featurize/work/BS
python scripts/build_style_adapter_dataset.py \
  --metadata data/style_adapter_pairs/metadata.jsonl \
  --output-dir data/style_adapter_pairs/prepared
```

如只想检查入口是否可用：

```bash
python scripts/build_style_adapter_dataset.py \
  --metadata data/style_adapter_pairs/metadata.jsonl \
  --dry-run
```

## 训练入口

```bash
cd /home/featurize/work/BS
python scripts/train_text_style_adapter.py \
  --metadata data/style_adapter_pairs/metadata.jsonl \
  --output runtime/style_adapter/text_style_adapter_v1.pt \
  --epochs 40 \
  --batch-size 8 \
  --style-dim 256 \
  --device cpu
```

如当前只做工程验证，不声明已完成大规模训练：

```bash
python scripts/train_text_style_adapter.py \
  --dry-run \
  --metadata data/style_adapter_pairs/metadata.jsonl \
  --output runtime/style_adapter/text_style_adapter_v1.pt \
  --report-output runtime/eval_reports/text_style_adapter_dry_run.json
```

`--dry-run` 会验证：

- 元数据读取
- prompt embedding 生成
- 输出路径与日志路径
- 训练入口参数
- 当前样本数是否足以进入真实训练

## 当前结论边界

- 可以说：训练入口、数据规范和 dry-run 验证已经补齐
- 可以说：当前工程已经具备后续训练 `text_style_adapter_v1.pt` 的基础
- 不能说：已经完成基于大规模风格标注数据的强文本风格控制训练
- 不能说：现有 small-scale dry-run 已经证明文本提示词可稳定强控制歌声风格

## 后续工作

后续如果补充更多标注样本，可以继续：

1. 扩大 prompt-style pair 数据规模
2. 在更稳定的 train/val/test 划分下训练 `text_style_adapter_v1.pt`
3. 比较 external adapter 与 internal FiLM 的分工边界
4. 结合主观听评验证 prompt-control 是否真的可感知
