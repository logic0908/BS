#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

try:
    import torch
    from torch import nn
except ModuleNotFoundError:
    torch = None
    nn = None

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


DATASET_DIR = PROJECT_ROOT / "data" / "style_adapter_pairs" / "prepared"
RUNTIME_DIR = PROJECT_ROOT / "runtime" / "style_adapter"
CHECKPOINT_PATH = RUNTIME_DIR / "text_style_adapter_v1.pt"
SUMMARY_PATH = RUNTIME_DIR / "training_summary.json"


def main() -> int:
    records_path = DATASET_DIR / "records.jsonl"
    embeddings_path = DATASET_DIR / "embeddings.npy"
    if not records_path.exists() or not embeddings_path.exists():
        print("[style-adapter] prepared dataset missing. Run python scripts/build_style_adapter_dataset.py first.")
        return 0
    if torch is None or nn is None:
        print("[style-adapter] torch is not available. Use the current environment with torch preinstalled.")
        return 0

    rows = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        print("[style-adapter] no prepared rows found.")
        return 0

    embeddings = np.load(embeddings_path)
    if embeddings.ndim != 2 or embeddings.shape[0] != len(rows):
        print("[style-adapter] embeddings.npy shape does not match records.jsonl.")
        return 0

    control_rows = [build_training_target(row) for row in rows]
    x = torch.tensor(embeddings, dtype=torch.float32)
    y = torch.tensor([numeric_target_vector(control_row) for control_row in control_rows], dtype=torch.float32)

    model = AdapterMLP(input_dim=x.shape[1], output_dim=y.shape[1], hidden_dims=[128, 64])
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    model.train()
    epochs = 80 if len(rows) >= 20 else 40
    final_loss = 0.0
    for _ in range(epochs):
        optimizer.zero_grad()
        pred = model(x)
        loss = loss_fn(pred, y)
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().cpu().item())

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_payload = {
        "adapter_version": "v0.7_trained_mlp_with_rule_based_fallback",
        "adapter_type": "trained_mlp",
        "input_dim": int(x.shape[1]),
        "output_dim": int(y.shape[1]),
        "hidden_dims": [128, 64],
        "target_keys": list(TRAINED_TARGET_KEYS),
        "records": len(rows),
        "epochs": epochs,
        "learning_rate": 1e-3,
        "final_loss": final_loss,
        "model_state_dict": model.state_dict(),
        "sample_embeddings": embeddings.astype(np.float32).tolist(),
        "sample_records": [
            {
                "id": row.get("id"),
                "prompt": row.get("prompt"),
                "style_tags": row.get("style_tags", []),
                "model_preset_id": control_row["model_preset_id"],
                "gender_hint": control_row["gender_hint"],
                "control_params": control_row,
            }
            for row, control_row in zip(rows, control_rows)
        ],
    }
    torch.save(checkpoint_payload, CHECKPOINT_PATH)

    SUMMARY_PATH.write_text(
        json.dumps(
            {
                "records": len(rows),
                "epochs": epochs,
                "learning_rate": 1e-3,
                "hidden_dims": [128, 64],
                "input_dim": int(x.shape[1]),
                "output_dim": int(y.shape[1]),
                "target_keys": list(TRAINED_TARGET_KEYS),
                "final_loss": final_loss,
                "checkpoint_path": str(CHECKPOINT_PATH),
                "dataset_path": str(records_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[style-adapter] checkpoint written to {CHECKPOINT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
