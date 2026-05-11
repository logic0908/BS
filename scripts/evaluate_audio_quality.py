#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.audio_quality import analyze_audio_pair, write_audio_quality_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate audio quality for SVC input/output pairs.")
    parser.add_argument("--input", dest="input_path", help="Input vocals path")
    parser.add_argument("--output", dest="output_path", help="Converted output path")
    parser.add_argument("--debug-dir", dest="debug_dir", default=str(PROJECT_ROOT / "runtime" / "debug" / "manual_eval"))
    args = parser.parse_args()

    if not args.input_path or not args.output_path:
        print("[audio-quality] provide --input and --output to evaluate a pair.")
        return 0

    report = analyze_audio_pair(args.input_path, args.output_path)
    report_path = write_audio_quality_report(args.debug_dir, report)
    print(json.dumps({"report_path": report_path, "summary": report.get("summary", {})}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
