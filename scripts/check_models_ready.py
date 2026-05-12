#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models_svc.model_readiness import collect_model_readiness  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check whether the real internal FiLM So-VITS-SVC path is locally ready.")
    parser.add_argument("--preset", default="final_primary", help="Model preset id to validate.")
    parser.add_argument("--prompt-text", default="温柔、明亮、流行感更强的女声风格", help="Prompt used for TextStyleEncoder readiness.")
    parser.add_argument("--json", action="store_true", help="Emit the full readiness payload as JSON.")
    parser.add_argument(
        "--allow-mock",
        action="store_true",
        help="Do not fail the readiness script when the current runtime is in Mock mode.",
    )
    return parser


def render_check_line(check: dict[str, object]) -> str:
    level = str(check.get("level") or "ok").upper()
    message = str(check.get("message") or "")
    details = check.get("details") or {}
    suffix = ""
    if isinstance(details, dict):
        expected_path = details.get("expected_path") or details.get("preferred_path")
        if expected_path:
            suffix = f": expected {expected_path}"
    return f"[{level}] {message}{suffix}"


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    readiness = collect_model_readiness(
        preset_id=args.preset,
        prompt_text=args.prompt_text,
        require_real_assets=not args.allow_mock,
        skip_real_checks_if_mock=args.allow_mock,
    )

    if args.json:
        print(json.dumps(readiness, ensure_ascii=False, indent=2))
    else:
        for check in readiness["checks"]:
            print(render_check_line(check))

    return 0 if readiness["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
