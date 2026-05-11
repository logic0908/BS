#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from sentence_transformers import SentenceTransformer
except ModuleNotFoundError:
    SentenceTransformer = None

from app.services.text_style_encoder import load_text_style_config


def main() -> int:
    if SentenceTransformer is None:
        print("[text-encoder] sentence-transformers is not installed in the current environment.")
        return 0

    config = load_text_style_config()
    model_name = str(config.get("encoder_model_name") or "").strip()
    cache_dir = Path(str(config.get("cache_dir") or "").strip())
    if not model_name or not cache_dir:
        print("[text-encoder] invalid text_style_config.json")
        return 1

    cache_dir.mkdir(parents=True, exist_ok=True)
    print(f"[text-encoder] preparing model={model_name}")
    print(f"[text-encoder] cache_dir={cache_dir}")
    try:
        model = SentenceTransformer(model_name, cache_folder=str(cache_dir), local_files_only=False)
    except Exception as exc:
        print(f"[text-encoder] prepare failed: {exc}")
        return 1

    sample = model.encode(["清亮、少年感、男声"], normalize_embeddings=True)[0]
    summary = {
        "model_name": model_name,
        "cache_dir": str(cache_dir),
        "embedding_dim": int(len(sample)),
    }
    summary_path = cache_dir / "prepare_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[text-encoder] prepared successfully: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
