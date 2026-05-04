#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models_svc.sovits_assets import extract_speaker_list, summarize_sovits_config  # noqa: E402

try:
    from huggingface_hub import hf_hub_download
except Exception as exc:  # pragma: no cover
    hf_hub_download = None  # type: ignore[assignment]
    HF_IMPORT_ERROR = exc
else:
    HF_IMPORT_ERROR = None


PRESETS_PATH = PROJECT_ROOT / "backend" / "app" / "config" / "svc_model_presets.json"
LOCAL_PRESET_ROOT = PROJECT_ROOT / "local_models" / "sovits-final"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install or bind a real So-VITS-SVC model preset.")
    parser.add_argument("--preset-id", required=True)
    parser.add_argument("--display-name", default="")
    parser.add_argument("--description", default="")
    parser.add_argument("--speaker", default="")
    parser.add_argument("--repo-id", default="", help="Optional Hugging Face repo id.")
    parser.add_argument("--model-file", default="", help="Model filename inside the HF repo.")
    parser.add_argument("--config-file", default="", help="Config filename inside the HF repo.")
    parser.add_argument("--model-path", default="", help="Existing local model path.")
    parser.add_argument("--config-path", default="", help="Existing local config path.")
    parser.add_argument("--source-repo", default="")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--license", default="")
    parser.add_argument("--style-tag", action="append", default=[])
    parser.add_argument("--notes", default="")
    parser.add_argument("--smoke-test-status", default="pending")
    parser.add_argument("--smoke-test-output-path", default="")
    parser.add_argument("--mark-configured", action="store_true")
    parser.add_argument("--smoke-test-passed", action="store_true")
    parser.add_argument("--demo-quality", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    target_dir = LOCAL_PRESET_ROOT / args.preset_id
    target_dir.mkdir(parents=True, exist_ok=True)

    source_repo = args.source_repo.strip() or args.repo_id.strip()
    source_url = args.source_url.strip() or _default_source_url(args.repo_id.strip())
    license_name = (args.license or "").strip() or "license_unknown"

    model_target, config_target, install_mode = _materialize_assets(args, target_dir)
    config_payload = json.loads(config_target.read_text(encoding="utf-8"))
    config_summary = summarize_sovits_config(config_payload)
    speakers = extract_speaker_list(config_payload)
    speaker = args.speaker.strip() or (speakers[0] if speakers else "")

    report = {
        "preset_id": args.preset_id,
        "source_repo": source_repo,
        "source_url": source_url,
        "install_mode": install_mode,
        "model_filename": model_target.name,
        "config_filename": config_target.name,
        "speaker": speaker,
        "sampling_rate": config_summary.get("sampling_rate"),
        "speech_encoder": config_summary.get("speech_encoder"),
        "license": license_name,
        "sha256": _sha256(model_target),
        "downloaded_at": _now(),
        "smoke_test_status": args.smoke_test_status.strip() or "pending",
        "smoke_test_output_path": args.smoke_test_output_path.strip(),
        "notes": args.notes.strip(),
    }
    install_report_path = target_dir / "install_report.json"
    install_report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _update_preset_config(
        preset_id=args.preset_id,
        display_name=args.display_name.strip(),
        description=args.description.strip(),
        style_tags=args.style_tag,
        model_target=model_target,
        config_target=config_target,
        speaker=speaker,
        source_repo=source_repo,
        source_url=source_url,
        license_name=license_name,
        notes=args.notes.strip(),
        install_report_path=install_report_path,
        mark_configured=args.mark_configured,
        smoke_test_passed=args.smoke_test_passed,
        demo_quality=args.demo_quality,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _materialize_assets(args: argparse.Namespace, target_dir: Path) -> tuple[Path, Path, str]:
    if args.model_path and args.config_path:
        model_source = Path(args.model_path).expanduser().resolve()
        config_source = Path(args.config_path).expanduser().resolve()
        if not model_source.exists():
            raise SystemExit(f"model path not found: {model_source}")
        if not config_source.exists():
            raise SystemExit(f"config path not found: {config_source}")
        model_target = target_dir / model_source.name
        config_target = target_dir / "config.json"
        shutil.copy2(model_source, model_target)
        shutil.copy2(config_source, config_target)
        return model_target, config_target, "local_bind"

    if not (args.repo_id and args.model_file and args.config_file):
        raise SystemExit("provide either --model-path/--config-path or --repo-id/--model-file/--config-file")
    if hf_hub_download is None:
        raise SystemExit(f"huggingface_hub import failed: {HF_IMPORT_ERROR}")

    model_cache = Path(hf_hub_download(repo_id=args.repo_id, filename=args.model_file, repo_type="model"))
    config_cache = Path(hf_hub_download(repo_id=args.repo_id, filename=args.config_file, repo_type="model"))
    model_target = target_dir / Path(args.model_file).name
    config_target = target_dir / "config.json"
    shutil.copy2(model_cache, model_target)
    shutil.copy2(config_cache, config_target)
    for optional_name in ("README.md", "LICENSE", "LICENSE.txt", "license.txt"):
        try:
            optional_cache = Path(hf_hub_download(repo_id=args.repo_id, filename=optional_name, repo_type="model"))
        except Exception:
            continue
        mapped_name = "model_card.md" if optional_name.lower() == "readme.md" else optional_name
        shutil.copy2(optional_cache, target_dir / mapped_name)
    return model_target, config_target, "huggingface_download"


def _update_preset_config(
    *,
    preset_id: str,
    display_name: str,
    description: str,
    style_tags: list[str],
    model_target: Path,
    config_target: Path,
    speaker: str,
    source_repo: str,
    source_url: str,
    license_name: str,
    notes: str,
    install_report_path: Path,
    mark_configured: bool,
    smoke_test_passed: bool,
    demo_quality: bool,
) -> None:
    payload = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    presets = list(payload.get("presets") or [])
    updated = False
    for preset in presets:
        if str(preset.get("preset_id") or "") != preset_id:
            continue
        preset["display_name"] = display_name or preset.get("display_name") or preset_id
        preset["description"] = description or preset.get("description") or ""
        if style_tags:
            preset["style_tags"] = style_tags
        preset["model_path"] = str(model_target)
        preset["config_path"] = str(config_target)
        preset["speaker"] = speaker
        preset["source_repo"] = source_repo
        preset["source_url"] = source_url
        preset["license"] = license_name
        preset["install_report_path"] = str(install_report_path)
        preset["notes"] = notes
        preset["is_configured"] = bool(mark_configured and smoke_test_passed)
        preset["smoke_test_passed"] = bool(smoke_test_passed)
        preset["is_demo_quality"] = bool(demo_quality and mark_configured and smoke_test_passed)
        updated = True
        break

    if not updated:
        presets.append(
            {
                "preset_id": preset_id,
                "display_name": display_name or preset_id,
                "description": description,
                "style_tags": style_tags,
                "model_path": str(model_target),
                "config_path": str(config_target),
                "speaker": speaker,
                "device": "cuda",
                "is_configured": bool(mark_configured and smoke_test_passed),
                "is_demo_quality": bool(demo_quality and mark_configured and smoke_test_passed),
                "smoke_test_passed": bool(smoke_test_passed),
                "is_technical_validation_only": False,
                "source_repo": source_repo,
                "source_url": source_url,
                "license": license_name,
                "install_report_path": str(install_report_path),
                "notes": notes,
            }
        )

    payload["presets"] = presets
    PRESETS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _default_source_url(repo_id: str) -> str:
    return f"https://huggingface.co/{repo_id}" if repo_id else ""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
