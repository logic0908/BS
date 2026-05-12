#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.text_style_encoder import TextStyleEncoder, TextStyleEncoderError  # noqa: E402


DEFAULT_METADATA = PROJECT_ROOT / "data" / "style_adapter_pairs" / "metadata.jsonl"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "style_adapter_pairs" / "prepared"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare prompt embeddings for the lightweight TextStyleAdapter dataset.")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA, help="Input metadata JSONL")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Prepared output directory")
    parser.add_argument("--style-dim", type=int, default=256, help="Prompt embedding dimension")
    parser.add_argument("--dry-run", action="store_true", help="Validate metadata and prompt embedding without saving arrays")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.metadata.exists():
        print(f"[style-adapter] dataset metadata not found: {args.metadata}")
        return 0

    rows = []
    for line in args.metadata.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    if not rows:
        print("[style-adapter] metadata.jsonl is empty.")
        return 0

    encoder = TextStyleEncoder(style_dim=args.style_dim)
    embeddings: list[np.ndarray] = []
    prepared_rows: list[dict[str, Any]] = []
    for row in rows:
        prompt = first_non_empty(row.get("style_prompt"), row.get("prompt"))
        if not prompt:
            continue
        try:
            embedding = encoder.encode_prompt(prompt)
        except TextStyleEncoderError as exc:
            print(f"[style-adapter] text encoder unavailable: {exc.code} - {exc}")
            return 0
        embeddings.append(np.asarray(embedding.embedding, dtype=np.float32))
        prepared_rows.append(
            {
                **row,
                "input_audio_path": first_non_empty(row.get("input_audio_path"), row.get("input_path"), row.get("audio_path")),
                "target_audio_path": first_non_empty(
                    row.get("target_audio_path"),
                    row.get("output_audio_path"),
                    row.get("target_path"),
                ),
                "style_prompt": prompt,
                "style_label": first_non_empty(row.get("style_label"), row.get("label")),
                "singer": first_non_empty(row.get("singer"), row.get("speaker")),
                "speaker": first_non_empty(row.get("speaker"), row.get("singer")),
                "split": first_non_empty(row.get("split"), "unspecified"),
                "notes": first_non_empty(row.get("notes")),
                "embedding_dim": embedding.embedding_dim,
                "embedding_norm": embedding.embedding_norm,
                "top_keywords": embedding.keywords[:5],
                "encoder_model_name": embedding.model_name,
                "encoder_type": embedding.encoder_type,
            }
        )

    if not prepared_rows:
        print("[style-adapter] no valid rows with prompts were found.")
        return 0

    if args.dry_run:
        print(
            json.dumps(
                {
                    "status": "dry_run_ready",
                    "metadata_path": str(args.metadata),
                    "output_dir": str(args.output_dir),
                    "rows": len(prepared_rows),
                    "style_dim": args.style_dim,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    np.save(args.output_dir / "embeddings.npy", np.stack(embeddings, axis=0))
    with (args.output_dir / "records.jsonl").open("w", encoding="utf-8") as handle:
        for row in prepared_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[style-adapter] wrote {len(prepared_rows)} records to {args.output_dir}")
    return 0


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value).strip() if value is not None else ""
        if text:
            return text
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
