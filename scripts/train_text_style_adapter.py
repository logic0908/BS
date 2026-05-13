#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except ModuleNotFoundError:
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models_svc.text_style_adapter import (  # noqa: E402
    AdapterMLP,
    TRAINED_TARGET_KEYS,
    build_training_target,
    numeric_target_vector,
)
from app.services.text_style_encoder import TextStyleEncoder, TextStyleEncoderError  # noqa: E402


DEFAULT_METADATA = PROJECT_ROOT / "data" / "style_adapter_pairs" / "metadata.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "runtime" / "style_adapter" / "text_style_adapter_v1.pt"
DEFAULT_DRY_RUN_REPORT = PROJECT_ROOT / "runtime" / "eval_reports" / "text_style_adapter_dry_run.json"

REQUIRED_FIELDS = (
    "input_audio_path",
    "target_audio_path_or_output_audio_path",
    "style_prompt",
    "style_label",
    "singer_or_speaker",
    "split",
    "notes",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train or dry-run the lightweight TextStyleAdapter entrypoint without touching the internal FiLM main chain."
    )
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA, help="JSONL metadata for prompt/style pairs")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Checkpoint output path")
    parser.add_argument("--epochs", type=int, default=40, help="Training epochs for the lightweight adapter")
    parser.add_argument("--batch-size", type=int, default=8, help="Mini-batch size")
    parser.add_argument("--style-dim", type=int, default=256, help="Prompt embedding dimension")
    parser.add_argument("--device", default="cpu", help="Training device, e.g. cpu or cuda")
    parser.add_argument("--max-items", type=int, default=0, help="Cap usable rows for small-run smoke/sanity training. <=0 means no cap.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed used for temporary split assignment when val/test are missing.")
    parser.add_argument("--dry-run", action="store_true", help="Validate data loading, embedding, output path, and logs without training")
    parser.add_argument(
        "--report-output",
        type=Path,
        default=DEFAULT_DRY_RUN_REPORT,
        help="JSON report path. In dry-run mode this is the main artifact.",
    )
    parser.add_argument(
        "--minimum-train-samples",
        type=int,
        default=8,
        help="If fewer usable rows exist, write a report and skip weight training.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    max_items = int(getattr(args, "max_items", 0) or 0)
    seed = int(getattr(args, "seed", 42) or 42)
    rows = load_metadata_rows(args.metadata)
    encoder = TextStyleEncoder(style_dim=args.style_dim)
    normalized_rows, warnings = normalize_rows(rows)

    prepared_rows: list[dict[str, Any]] = []
    embeddings: list[np.ndarray] = []
    encoder_types: Counter[str] = Counter()
    skipped_missing_prompt = 0

    for row in normalized_rows:
        prompt = row["style_prompt"]
        if not prompt:
            skipped_missing_prompt += 1
            continue
        try:
            embedding = encoder.encode_prompt(prompt)
        except TextStyleEncoderError as exc:
            warnings.append(f"text_style_encoder_unavailable:{exc.code}")
            continue

        encoder_types[embedding.encoder_type] += 1
        control_params = build_training_target(
            {
                "prompt": prompt,
                "style_tags": row["style_tags"],
                "model_preset_id": row["model_preset_id"],
                "transpose": row["transpose"],
                "style_strength": row["style_strength"],
            }
        )
        prepared_rows.append(
            {
                **row,
                "embedding_dim": embedding.embedding_dim,
                "embedding_norm": round(embedding.embedding_norm, 6),
                "encoder_model_name": embedding.model_name,
                "encoder_type": embedding.encoder_type,
                "top_keywords": embedding.keywords[:5],
                "control_params": control_params,
            }
        )
        embeddings.append(embedding.to_numpy())

    if skipped_missing_prompt:
        warnings.append(f"skipped_missing_prompt:{skipped_missing_prompt}")
    if max_items > 0 and len(prepared_rows) > max_items:
        prepared_rows = prepared_rows[:max_items]
        embeddings = embeddings[:max_items]
        warnings.append(f"max_items_applied:{max_items}")

    split_fallback_applied = ensure_split_assignments(prepared_rows, seed=seed, warnings=warnings)

    can_train = (
        not args.dry_run
        and len(prepared_rows) >= max(args.minimum_train_samples, 1)
        and torch is not None
        and nn is not None
        and DataLoader is not None
        and TensorDataset is not None
    )
    report = build_report(
        args=args,
        raw_rows=rows,
        prepared_rows=prepared_rows,
        warnings=warnings,
        encoder_types=encoder_types,
        can_train=can_train,
        split_fallback_applied=split_fallback_applied,
    )

    if args.dry_run:
        write_json(args.report_output, report)
        print(f"[style-adapter] dry-run report written to {args.report_output}")
        return 0

    if len(prepared_rows) < max(args.minimum_train_samples, 1):
        report["status"] = "insufficient_data_for_training"
        report["message"] = (
            "Metadata and embedding entrypoint are ready, but the current usable sample count is below the training threshold. "
            "Keep this pass as framework validation, not as a claim of large-scale style-control training."
        )
        write_json(args.report_output, report)
        print(f"[style-adapter] insufficient data, wrote report to {args.report_output}")
        return 0

    if torch is None or nn is None or DataLoader is None or TensorDataset is None:
        report["status"] = "torch_unavailable"
        report["message"] = "Torch is unavailable in the current environment, so only the data/entrypoint validation was completed."
        write_json(args.report_output, report)
        print(f"[style-adapter] torch unavailable, wrote report to {args.report_output}")
        return 0

    checkpoint_summary = train_adapter(
        prepared_rows=prepared_rows,
        embeddings=np.stack(embeddings, axis=0),
        output_path=args.output,
        epochs=max(args.epochs, 1),
        batch_size=max(args.batch_size, 1),
        device=args.device,
        seed=seed,
    )
    report["status"] = "trained"
    report["training"] = checkpoint_summary
    write_json(args.report_output, report)
    print(f"[style-adapter] checkpoint written to {args.output}")
    print(f"[style-adapter] report written to {args.report_output}")
    return 0


def load_metadata_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"[style-adapter] metadata not found: {path}")
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise SystemExit(f"[style-adapter] metadata row {lineno} is not a JSON object")
        rows.append(payload)
    return rows


def normalize_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        input_audio_path = first_non_empty(
            row.get("input_audio_path"),
            row.get("input_path"),
            row.get("audio_path"),
        )
        target_audio_path = first_non_empty(
            row.get("target_audio_path"),
            row.get("output_audio_path"),
            row.get("target_path"),
        )
        style_prompt = first_non_empty(row.get("style_prompt"), row.get("prompt"))
        style_label = first_non_empty(row.get("style_label"), row.get("label"))
        singer = first_non_empty(row.get("singer"), row.get("speaker"))
        split = first_non_empty(row.get("split"), "unspecified")
        notes = first_non_empty(row.get("notes"))
        style_tags = normalize_tags(row.get("style_tags"), style_label)

        normalized.append(
            {
                "id": first_non_empty(row.get("id"), f"sample_{index:04d}"),
                "input_audio_path": input_audio_path,
                "target_audio_path": target_audio_path,
                "output_audio_path": first_non_empty(row.get("output_audio_path"), target_audio_path),
                "style_prompt": style_prompt,
                "style_label": style_label,
                "singer": singer,
                "speaker": singer,
                "split": split,
                "notes": notes,
                "style_tags": style_tags,
                "model_preset_id": first_non_empty(row.get("model_preset_id"), "final_primary"),
                "transpose": int(row.get("transpose", 0) or 0),
                "style_strength": float(row.get("style_strength", 0.65) or 0.65),
            }
        )

        missing = []
        if not input_audio_path:
            missing.append("input_audio_path")
        if not (target_audio_path or first_non_empty(row.get("output_audio_path"))):
            missing.append("target_audio_path/output_audio_path")
        if not style_prompt:
            missing.append("style_prompt")
        if not style_label:
            missing.append("style_label")
        if not singer:
            missing.append("singer/speaker")
        if missing:
            warnings.append(f"row_{index}_missing:{','.join(missing)}")
    return normalized, warnings


def normalize_tags(raw_tags: Any, style_label: str) -> list[str]:
    values: list[str] = []
    if isinstance(raw_tags, list):
        values.extend(str(item).strip() for item in raw_tags if str(item).strip())
    elif raw_tags:
        values.extend(part.strip() for part in str(raw_tags).replace("，", ",").split(",") if part.strip())
    if style_label:
        values.extend(part.strip() for part in style_label.replace("，", ",").split(",") if part.strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(value)
    return deduped


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value).strip() if value is not None else ""
        if text:
            return text
    return ""


def build_report(
    *,
    args: argparse.Namespace,
    raw_rows: list[dict[str, Any]],
    prepared_rows: list[dict[str, Any]],
    warnings: list[str],
    encoder_types: Counter[str],
    can_train: bool,
    split_fallback_applied: bool,
) -> dict[str, Any]:
    split_counter = Counter(row.get("split", "unspecified") for row in prepared_rows)
    speaker_counter = Counter(first_non_empty(row.get("singer"), row.get("speaker"), "unknown") for row in prepared_rows)
    preview_rows = [
        {
            "id": row["id"],
            "style_prompt": row["style_prompt"],
            "style_label": row["style_label"],
            "singer": row["singer"],
            "split": row["split"],
            "encoder_type": row["encoder_type"],
            "control_params": row["control_params"],
        }
        for row in prepared_rows[:5]
    ]
    return {
        "status": "dry_run_ready" if args.dry_run else "ready_to_train" if can_train else "framework_validated",
        "dry_run": bool(args.dry_run),
        "metadata_path": str(args.metadata),
        "output_path": str(args.output),
        "report_output": str(args.report_output),
        "required_fields": list(REQUIRED_FIELDS),
        "rows_total": len(raw_rows),
        "rows_usable": len(prepared_rows),
        "style_dim": int(args.style_dim),
        "epochs": int(args.epochs),
        "batch_size": int(args.batch_size),
        "max_items": int(getattr(args, "max_items", 0) or 0),
        "device": args.device,
        "seed": int(getattr(args, "seed", 42) or 42),
        "minimum_train_samples": int(args.minimum_train_samples),
        "can_train": can_train,
        "torch_available": torch is not None,
        "split_fallback_applied": split_fallback_applied,
        "encoder_types": dict(encoder_types),
        "splits": dict(split_counter),
        "speakers": dict(speaker_counter),
        "warnings": sorted(set(warnings)),
        "notes": [
            "Current BS has already implemented the text-prompt to internal FiLM injection path.",
            "This script only validates the lightweight adapter training entrypoint and metadata organization.",
            "Large-scale strong text style control still requires more annotated prompt-style data.",
        ],
        "preview_rows": preview_rows,
    }


def train_adapter(
    *,
    prepared_rows: list[dict[str, Any]],
    embeddings: np.ndarray,
    output_path: Path,
    epochs: int,
    batch_size: int,
    device: str,
    seed: int,
) -> dict[str, Any]:
    torch.manual_seed(seed)
    np.random.seed(seed)

    x = torch.tensor(embeddings, dtype=torch.float32)
    y = torch.tensor([numeric_target_vector(row["control_params"]) for row in prepared_rows], dtype=torch.float32)

    train_indices = [idx for idx, row in enumerate(prepared_rows) if str(row.get("split") or "").strip().lower() == "train"]
    val_indices = [idx for idx, row in enumerate(prepared_rows) if str(row.get("split") or "").strip().lower() == "val"]
    test_indices = [idx for idx, row in enumerate(prepared_rows) if str(row.get("split") or "").strip().lower() == "test"]
    if not train_indices:
        # Last-resort safety: keep training possible even if split labels were malformed.
        train_indices = list(range(len(prepared_rows)))
    train_x, train_y = x[train_indices], y[train_indices]
    val_x, val_y = (x[val_indices], y[val_indices]) if val_indices else (None, None)
    test_x, test_y = (x[test_indices], y[test_indices]) if test_indices else (None, None)

    train_dataset = TensorDataset(train_x, train_y)
    loader = DataLoader(train_dataset, batch_size=min(batch_size, len(train_dataset)), shuffle=True)

    requested_device = str(device).strip() or "cpu"
    effective_device, gpu_name, device_fallback_reason = resolve_device(requested_device)
    target_device = torch.device(effective_device)
    model = AdapterMLP(input_dim=x.shape[1], output_dim=y.shape[1], hidden_dims=[128, 64]).to(target_device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    train_history: list[float] = []
    val_history: list[float | None] = []
    started = time.perf_counter()
    model.train()
    for _ in range(epochs):
        epoch_losses: list[float] = []
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(target_device)
            batch_y = batch_y.to(target_device)
            optimizer.zero_grad()
            prediction = model(batch_x)
            loss = loss_fn(prediction, batch_y)
            loss.backward()
            optimizer.step()
            epoch_losses.append(float(loss.detach().cpu().item()))
        train_epoch_loss = round(sum(epoch_losses) / max(len(epoch_losses), 1), 8)
        train_history.append(train_epoch_loss)
        if val_x is not None and val_y is not None and val_x.shape[0] > 0:
            model.eval()
            with torch.no_grad():
                prediction = model(val_x.to(target_device))
                val_loss = float(loss_fn(prediction, val_y.to(target_device)).detach().cpu().item())
            val_history.append(round(val_loss, 8))
            model.train()
        else:
            val_history.append(None)

    best_epoch = 1
    best_val_loss: float | None = None
    if any(loss is not None for loss in val_history):
        best_epoch = min(
            ((idx + 1, loss) for idx, loss in enumerate(val_history) if loss is not None),
            key=lambda item: item[1],
        )[0]
        best_val_loss = val_history[best_epoch - 1]
    elif train_history:
        best_epoch = min(range(len(train_history)), key=lambda idx: train_history[idx]) + 1
        best_val_loss = None

    test_loss = None
    if test_x is not None and test_y is not None and test_x.shape[0] > 0:
        model.eval()
        with torch.no_grad():
            prediction = model(test_x.to(target_device))
            test_loss = float(loss_fn(prediction, test_y.to(target_device)).detach().cpu().item())
        model.train()
    total_seconds = round(time.perf_counter() - started, 6)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sample_records = [
        {
            "id": row.get("id"),
            "model_preset_id": row.get("model_preset_id", "final_primary"),
            "gender_hint": str((row.get("control_params") or {}).get("gender_hint") or "neutral"),
            "style_label": row.get("style_label", ""),
            "style_prompt": row.get("style_prompt", ""),
            "split": row.get("split", "unspecified"),
        }
        for row in prepared_rows
    ]
    checkpoint_payload = {
        "adapter_version": "text_style_adapter_v1_lightweight_entrypoint",
        "adapter_type": "trained_mlp",
        "checkpoint_format_version": 2,
        "input_dim": int(x.shape[1]),
        "output_dim": int(y.shape[1]),
        "hidden_dims": [128, 64],
        "target_keys": list(TRAINED_TARGET_KEYS),
        "records": len(prepared_rows),
        "train_size": len(train_indices),
        "val_size": len(val_indices),
        "test_size": len(test_indices),
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": 1e-3,
        "final_loss": train_history[-1] if train_history else math.nan,
        "train_loss_per_epoch": train_history,
        "val_loss_per_epoch": val_history,
        "best_epoch": best_epoch,
        "best_val_loss": best_val_loss,
        "final_train_loss": train_history[-1] if train_history else None,
        "test_loss": round(test_loss, 8) if test_loss is not None else None,
        "device": effective_device,
        "gpu_name": gpu_name,
        "device_fallback_reason": device_fallback_reason,
        "total_seconds": total_seconds,
        "model_state_dict": model.cpu().state_dict(),
        "sample_embeddings": embeddings.astype(np.float32).tolist(),
        "sample_records": sample_records,
    }
    torch.save(checkpoint_payload, output_path)
    return {
        "checkpoint_path": str(output_path),
        "records": len(prepared_rows),
        "train_size": len(train_indices),
        "val_size": len(val_indices),
        "test_size": len(test_indices),
        "epochs": epochs,
        "batch_size": batch_size,
        "input_dim": int(x.shape[1]),
        "output_dim": int(y.shape[1]),
        "train_loss_per_epoch": train_history,
        "val_loss_per_epoch": val_history,
        "best_epoch": best_epoch,
        "best_val_loss": best_val_loss,
        "final_train_loss": train_history[-1] if train_history else None,
        "final_loss": train_history[-1] if train_history else None,
        "test_loss": round(test_loss, 8) if test_loss is not None else None,
        "total_seconds": total_seconds,
        "device": effective_device,
        "gpu_name": gpu_name,
        "device_fallback_reason": device_fallback_reason,
    }


def ensure_split_assignments(rows: list[dict[str, Any]], seed: int, warnings: list[str]) -> bool:
    if not rows:
        return False
    normalized_splits = [str(row.get("split") or "").strip().lower() for row in rows]
    has_val_or_test = any(split in {"val", "test"} for split in normalized_splits)
    if has_val_or_test:
        return False
    indices = list(range(len(rows)))
    rng = np.random.default_rng(seed)
    rng.shuffle(indices)
    for rank, idx in enumerate(indices):
        frac = rank / max(len(indices), 1)
        if frac < 0.8:
            rows[idx]["split"] = "train"
        elif frac < 0.9:
            rows[idx]["split"] = "val"
        else:
            rows[idx]["split"] = "test"
    warnings.append("temporary_split_assignment:8_1_1")
    return True


def resolve_device(requested_device: str) -> tuple[str, str | None, str | None]:
    device_token = requested_device.lower()
    fallback_reason = None
    gpu_name = None
    if device_token.startswith("cuda"):
        if torch.cuda.is_available():
            effective = requested_device
            try:
                gpu_name = torch.cuda.get_device_name(torch.device(effective))
            except Exception:
                gpu_name = torch.cuda.get_device_name(0)
            return effective, gpu_name, fallback_reason
        fallback_reason = "cuda_requested_but_not_available"
        return "cpu", gpu_name, fallback_reason
    return requested_device, gpu_name, fallback_reason


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
