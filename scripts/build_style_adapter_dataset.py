#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.text_style_encoder import TextStyleEncoderError, text_style_encoder


DATASET_DIR = PROJECT_ROOT / "data" / "style_adapter_pairs"
METADATA_PATH = DATASET_DIR / "metadata.jsonl"
OUTPUT_DIR = DATASET_DIR / "prepared"


def main() -> int:
    if not METADATA_PATH.exists():
        print(f"[style-adapter] dataset metadata not found: {METADATA_PATH}")
        print("[style-adapter] create data/style_adapter_pairs/metadata.jsonl first.")
        return 0

    rows = []
    for line in METADATA_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    if not rows:
        print("[style-adapter] metadata.jsonl is empty. Add prompt/style rows before building embeddings.")
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    embeddings = []
    prepared_rows = []
    for row in rows:
        prompt = str(row.get("prompt") or "").strip()
        if not prompt:
            continue
        try:
            embedding = text_style_encoder.encode_prompt(prompt)
        except TextStyleEncoderError as exc:
            print(f"[style-adapter] text encoder unavailable: {exc.code} - {exc}")
            return 0
        embeddings.append(np.asarray(embedding.embedding, dtype=np.float32))
        prepared_rows.append(
            {
                **row,
                "embedding_dim": embedding.embedding_dim,
                "embedding_norm": embedding.embedding_norm,
                "top_keywords": embedding.keywords[:5],
                "encoder_model_name": embedding.model_name,
            }
        )

    if not embeddings:
        print("[style-adapter] no valid rows with prompts were found.")
        return 0

    np.save(OUTPUT_DIR / "embeddings.npy", np.stack(embeddings, axis=0))
    with (OUTPUT_DIR / "records.jsonl").open("w", encoding="utf-8") as handle:
        for row in prepared_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[style-adapter] wrote {len(prepared_rows)} records to {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
