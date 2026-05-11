#!/usr/bin/env python
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = PROJECT_ROOT / "runtime" / "debug"
OUTPUT_DIR = PROJECT_ROOT / "runtime" / "eval_reports"
OUTPUT_PATH = OUTPUT_DIR / "latest_eval_report.md"


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reports = []
    for path in sorted(DEBUG_DIR.glob("*/audio_quality_report.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        reports.append((path, payload))

    if not reports:
        OUTPUT_PATH.write_text(
            "# Evaluation Report\n\nNo audio_quality_report.json files were found under runtime/debug.\n",
            encoding="utf-8",
        )
        print(f"[eval-report] wrote empty report to {OUTPUT_PATH}")
        return 0

    lines = ["# Evaluation Report", ""]
    for path, payload in reports[-10:]:
        summary = payload.get("summary", {})
        lines.extend(
            [
                f"## {path.parent.name}",
                f"- source: `{path}`",
                f"- duration_consistency: `{summary.get('duration_consistency', 'n/a')}`",
                f"- low_energy_ratio: `{summary.get('low_energy_ratio', 'n/a')}`",
                f"- possible_dropouts: `{summary.get('possible_dropouts', 'n/a')}`",
                "",
            ]
        )
    OUTPUT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"[eval-report] wrote report to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
