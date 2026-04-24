import json, os
meta = json.load(open("data/processed/style/metadata.json","r",encoding="utf-8"))
items = meta if isinstance(meta, list) else list(meta.values())
bad = []
for i,it in enumerate(items[:2000]):  # 先抽查前2000条
    p = it.get("wav_fn","")
    if not p or not os.path.exists(p):
        bad.append((i,p))
print("bad count:", len(bad))
print("example:", bad[:5])