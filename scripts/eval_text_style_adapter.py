#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

try:
    import torch
except ModuleNotFoundError:
    torch = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models_svc.text_style_adapter import (
    AdapterMLP,
    TRAINED_TARGET_KEYS,
    build_training_target,
    numeric_target_vector,
)


PREPARED_DIR = PROJECT_ROOT / "data" / "style_adapter_pairs" / "prepared"
RUNTIME_DIR = PROJECT_ROOT / "runtime" / "style_adapter"
CHECKPOINT_PATH = RUNTIME_DIR / "text_style_adapter_v1.pt"
OUTPUT_PATH = RUNTIME_DIR / "eval_summary.json"


def main() -> int:
    records_path = PREPARED_DIR / "records.jsonl"
    embeddings_path = PREPARED_DIR / "embeddings.npy"
    if not records_path.exists() or not embeddings_path.exists():
        print("[style-adapter] no prepared dataset found. Run build_style_adapter_dataset.py first.")
        return 0
    if not CHECKPOINT_PATH.exists():
        print("[style-adapter] no adapter checkpoint found. Run train_text_style_adapter.py first.")
        return 0
    if torch is None:
        print("[style-adapter] torch is not available. Use the current environment with torch preinstalled.")
        return 0

    rows = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        print("[style-adapter] no prepared rows found.")
        return 0

    embeddings = np.load(embeddings_path)
    checkpoint = torch.load(str(CHECKPOINT_PATH), map_location="cpu")
    model = AdapterMLP(
        input_dim=int(checkpoint.get("input_dim", 0)),
        output_dim=int(checkpoint.get("output_dim", 0)),
        hidden_dims=list(checkpoint.get("hidden_dims") or [128, 64]),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    with torch.no_grad():
        predicted = model(torch.tensor(embeddings, dtype=torch.float32)).detach().cpu().numpy()

    targets = np.asarray(
        [numeric_target_vector(build_training_target(row)) for row in rows],
        dtype=np.float32,
    )
    numeric_mse = float(np.mean(np.square(predicted - targets)))

    supported_tags = ("bright", "power", "breathy", "youth", "male", "female")
    per_label_hits = 0
    per_label_total = 0
    sample_predictions = []
    for index, row in enumerate(rows):
        pred_vec = predicted[index]
        pred_controls = {
            key: float(value)
            for key, value in zip(checkpoint.get("target_keys") or TRAINED_TARGET_KEYS, pred_vec)
        }
        gender_hint = "female" if row_has_tag(row, "female") else "male" if row_has_tag(row, "male") else "neutral"
        predicted_tags = {
            "bright": pred_controls.get("brightness", 0.0) >= 0.55,
            "power": pred_controls.get("power", 0.0) >= 0.55,
            "breathy": pred_controls.get("breathiness", 0.0) >= 0.55,
            "youth": pred_controls.get("youthfulness", 0.0) >= 0.55,
            "male": gender_hint == "male",
            "female": gender_hint == "female",
        }
        for tag in supported_tags:
            per_label_hits += int(predicted_tags[tag] == row_has_tag(row, tag))
            per_label_total += 1
        sample_predictions.append(
            {
                "id": row.get("id"),
                "prompt": row.get("prompt"),
                "predicted_controls": {
                    "brightness": round(float(pred_controls.get("brightness", 0.0)), 4),
                    "power": round(float(pred_controls.get("power", 0.0)), 4),
                    "breathiness": round(float(pred_controls.get("breathiness", 0.0)), 4),
                    "youthfulness": round(float(pred_controls.get("youthfulness", 0.0)), 4),
                    "transpose": round(float(pred_controls.get("transpose", 0.0)), 4),
                    "style_strength": round(float(pred_controls.get("style_strength", 0.0)), 4),
                },
                "target_tags": sorted(row.get("style_tags") or []),
            }
        )

    payload = {
        "records": len(rows),
        "tag_accuracy": round(per_label_hits / max(per_label_total, 1), 6),
        "mse_for_numeric_controls": round(numeric_mse, 6),
        "checkpoint_path": str(CHECKPOINT_PATH),
        "target_keys": list(checkpoint.get("target_keys") or TRAINED_TARGET_KEYS),
        "sample_predictions": sample_predictions[:5],
    }
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def row_has_tag(row: dict[str, object], tag: str) -> bool:
    return tag in {str(item).strip().lower() for item in (row.get("style_tags") or []) if str(item).strip()}


if __name__ == "__main__":
    raise SystemExit(main())
