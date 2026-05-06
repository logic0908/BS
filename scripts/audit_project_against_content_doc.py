#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


CHECKS = [
    ("browser_bs", ["frontend/src/App.tsx", "frontend/vite.config.ts"]),
    ("upload_audio", ["backend/app/api/endpoints/synthesis.py", "frontend/src/components/FileUpload.tsx"]),
    ("wavesurfer", ["frontend/src/components/WaveformPlayer.tsx"]),
    ("ab_compare", ["frontend/src/components/AudioComparePanel.tsx"]),
    ("download_result", ["frontend/src/components/AudioComparePanel.tsx", "backend/app/api/endpoints/synthesis.py"]),
    ("fastapi", ["backend/app/main.py", "backend/app/api/endpoints/synthesis.py"]),
    ("celery_redis", ["backend/app/core/celery_app.py", "backend/app/workers/svc_tasks.py"]),
    ("demucs_uvr", ["backend/app/services/separation_service.py"]),
    ("sovits_real", ["backend/app/models_svc/sovits_wrapper.py", "backend/app/config/svc_model_presets.json"]),
    ("sentence_transformer", ["backend/app/services/text_style_encoder.py"]),
    ("text_style_adapter", ["backend/app/models_svc/text_style_adapter.py"]),
    ("style_data", ["data/style_adapter_pairs/metadata.jsonl"]),
    ("docker", ["Dockerfile", "docker-compose.yml", "README.md"]),
    ("gitignore_large_assets", [".gitignore"]),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lightweight requirement audit helper for 内容.doc alignment.")
    parser.add_argument("--content-doc", default=str(PROJECT_ROOT / "内容.doc"))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def extract_doc_text(path: Path) -> str:
    data = path.read_bytes()
    decoded = data.decode("utf-16le", errors="ignore")
    chunks = re.findall(r"[\u4e00-\u9fffA-Za-z0-9，。、；：！？（）《》/\-+ .:_]{6,}", decoded)
    return "\n".join(chunks)


def file_contains(path: Path, patterns: list[str]) -> bool:
    if not path.exists() or not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    return all(pattern in text for pattern in patterns)


def run_checks(content_doc: Path) -> dict[str, Any]:
    doc_text = extract_doc_text(content_doc)
    checks: dict[str, Any] = {}
    for check_id, relative_paths in CHECKS:
        existing = [str(path) for path in relative_paths if (PROJECT_ROOT / path).exists()]
        checks[check_id] = {
            "files_checked": relative_paths,
            "existing_files": existing,
            "has_any_file": bool(existing),
        }
    checks["content_doc_summary"] = {
        "has_title": "基于文本提示词控制的歌声风格转换系统" in doc_text,
        "mentions_wavesurfer": "WaveSurfer.js" in doc_text,
        "mentions_celery_redis": "celery+redis" in doc_text or ("Celery" in doc_text and "Redis" in doc_text),
        "mentions_bias_scale": "Bias" in doc_text and "Scale" in doc_text,
        "mentions_docker": "Docker" in doc_text,
    }
    checks["gitignore_large_assets"] = {
        **checks["gitignore_large_assets"],
        "runtime_ignored": file_contains(PROJECT_ROOT / ".gitignore", ["runtime/"]),
        "local_models_ignored": file_contains(PROJECT_ROOT / ".gitignore", ["local_models/"]),
        "sovits_repo_ignored": file_contains(PROJECT_ROOT / ".gitignore", ["so-vits-svc/"]),
        "weights_ignored": file_contains(PROJECT_ROOT / ".gitignore", ["*.pth", "*.pt"]),
        "audio_ignored": file_contains(PROJECT_ROOT / ".gitignore", ["*.wav", "*.flac"]),
    }
    return checks


def main() -> int:
    args = parse_args()
    report = run_checks(Path(args.content_doc))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
