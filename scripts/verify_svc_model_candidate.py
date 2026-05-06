#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a local So-VITS-SVC candidate directory without running inference.")
    parser.add_argument("candidate_dir", help="Directory expected to contain config.json and G_*.pth or model*.pth.")
    parser.add_argument("--speaker", default="", help="Optional expected speaker name.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only.")
    return parser.parse_args()


def inspect_candidate(candidate_dir: Path, expected_speaker: str = "") -> dict[str, Any]:
    config_files = sorted(candidate_dir.rglob("config.json"))
    weight_files = sorted(candidate_dir.rglob("G_*.pth")) + sorted(candidate_dir.rglob("model*.pth"))
    config_payload: dict[str, Any] = {}
    config_error = ""
    if config_files:
        try:
            config_payload = json.loads(config_files[0].read_text(encoding="utf-8"))
        except Exception as exc:
            config_error = str(exc)
    speakers = [str(key) for key in dict(config_payload.get("spk") or {}).keys()]
    model = dict(config_payload.get("model") or {})
    data = dict(config_payload.get("data") or {})
    expected_ok = not expected_speaker or expected_speaker in speakers
    valid = bool(weight_files and config_files and speakers and expected_ok and not config_error)
    return {
        "candidate_dir": str(candidate_dir),
        "valid": valid,
        "has_model_weight": bool(weight_files),
        "has_config_json": bool(config_files),
        "possible_weight_files": [str(path) for path in weight_files],
        "possible_config_files": [str(path) for path in config_files],
        "speaker_candidates": speakers,
        "expected_speaker": expected_speaker,
        "expected_speaker_found": expected_ok,
        "speech_encoder": model.get("speech_encoder"),
        "ssl_dim": model.get("ssl_dim"),
        "sampling_rate": data.get("sampling_rate"),
        "config_error": config_error,
        "recommended_action": "run smoke test before enabling preset" if valid else "do not enable preset",
    }


def main() -> int:
    args = parse_args()
    report = inspect_candidate(Path(args.candidate_dir).expanduser(), expected_speaker=args.speaker.strip())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
