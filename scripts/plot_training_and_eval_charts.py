#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = PROJECT_ROOT / "runtime" / "eval_reports" / "text_style_adapter_1000_train_report.json"
DEFAULT_FIGURE = PROJECT_ROOT / "runtime" / "figures" / "training_loss_curve_1000.png"
DEFAULT_INDEX = PROJECT_ROOT / "runtime" / "eval_reports" / "figure_index.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot training/eval curves from style-adapter train report.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Path to training report json")
    parser.add_argument("--figure-output", type=Path, default=DEFAULT_FIGURE, help="Output PNG path")
    parser.add_argument("--index-output", type=Path, default=DEFAULT_INDEX, help="Output markdown index path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.report.exists():
        raise SystemExit(f"[plot] report not found: {args.report}")
    payload = json.loads(args.report.read_text(encoding="utf-8"))
    training = payload.get("training", {}) if isinstance(payload, dict) else {}
    train_loss = training.get("train_loss_per_epoch") or []
    val_loss = training.get("val_loss_per_epoch") or []
    if not train_loss:
        raise SystemExit("[plot] train_loss_per_epoch is empty, nothing to draw.")

    epochs = list(range(1, len(train_loss) + 1))
    val_points = [point for point in val_loss if point is not None]

    args.figure_output.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(8, 5))
    plt.plot(epochs, train_loss, marker="o", label="train_loss")
    if val_points:
        filtered_epochs = [idx + 1 for idx, point in enumerate(val_loss) if point is not None]
        plt.plot(filtered_epochs, val_points, marker="s", label="val_loss")
    plt.title("TextStyleAdapter Training Curve")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(args.figure_output, dpi=150)
    plt.close()

    write_index(args.index_output, args.figure_output, args.report, payload)
    print(f"[plot] figure written to {args.figure_output}")
    print(f"[plot] index written to {args.index_output}")
    return 0


def write_index(index_path: Path, figure_path: Path, report_path: Path, payload: dict) -> None:
    training = payload.get("training", {}) if isinstance(payload, dict) else {}
    figure_label = "training_loss_curve_1000" if "1000" in figure_path.stem else "training_loss_curve"
    lines = [
        "# Figure Index",
        "",
        f"- generated_at: `{datetime.now(timezone.utc).isoformat()}`",
        f"- report: `{report_path}`",
        f"- figure: `{figure_path}`",
        f"- epochs: `{training.get('epochs')}`",
        f"- best_epoch: `{training.get('best_epoch')}`",
        f"- best_val_loss: `{training.get('best_val_loss')}`",
        f"- final_train_loss: `{training.get('final_train_loss')}`",
        "",
        "## Files",
        "",
        f"- {figure_label}: `{figure_path}`",
    ]
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
