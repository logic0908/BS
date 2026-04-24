import json, os

meta_in  = "data/processed/style/metadata.json"
meta_out = "data/processed/style/metadata.abs.json"
AUDIO_ROOT = "/home/featurize/data"  # 你的服务器音频根目录（改成你自己的）

with open(meta_in, "r", encoding="utf-8") as f:
    data = json.load(f)

# 常见两种：list[dict] 或 dict(key->dict)。这里做兼容处理
items = data if isinstance(data, list) else list(data.values())

changed = 0
for it in items:
    if "wav_fn" not in it:
        continue
    old = it["wav_fn"]
    # 如果 old 已经是绝对路径就跳过；否则拼到 AUDIO_ROOT
    if not os.path.isabs(old):
        it["wav_fn"] = os.path.join(AUDIO_ROOT, old)
        changed += 1

with open(meta_out, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Done. changed={changed}, wrote={meta_out}")
