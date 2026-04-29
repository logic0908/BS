#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models_svc.sovits_assets import extract_speaker_list, inspect_sovits_assets, summarize_sovits_config  # noqa: E402

try:
    from huggingface_hub import HfApi, hf_hub_download
except Exception as exc:  # pragma: no cover
    HfApi = None  # type: ignore[assignment]
    hf_hub_download = None  # type: ignore[assignment]
    HF_IMPORT_ERROR = exc
else:
    HF_IMPORT_ERROR = None


CANDIDATES_PATH = PROJECT_ROOT / "runtime" / "model_search" / "candidates.json"
PRESETS_PATH = PROJECT_ROOT / "backend" / "app" / "config" / "svc_model_presets.json"
SUPPORTED_ENCODERS = {"vec768l12", "vec256l9", "hubertsoft", "cnhubertlarge"}
CONTENTVEC_ENCODERS = {"vec768l12", "vec256l9"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install the selected final So-VITS-SVC model preset.")
    parser.add_argument("--repo-id", default="")
    parser.add_argument("--model-file", default="")
    parser.add_argument("--config-file", default="")
    parser.add_argument("--speaker", default="")
    parser.add_argument("--preset-id", default="final_primary")
    parser.add_argument("--candidate-rank", type=int, default=1, help="1-based rank among non-rejected candidates.")
    parser.add_argument("--activate", action="store_true", help="Also switch active_preset_id to the installed preset.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if HfApi is None:
        print(f"huggingface_hub import failed: {HF_IMPORT_ERROR}", file=sys.stderr)
        return 2

    selection = _select_candidate(args)
    preset_id = args.preset_id
    target_dir = PROJECT_ROOT / "local_models" / "sovits-final" / preset_id
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"[install] repo={selection['repo_id']} model={selection['model_file']} config={selection['config_file']}")
    model_cache = hf_hub_download(repo_id=selection["repo_id"], filename=selection["model_file"], repo_type="model")
    config_cache = hf_hub_download(repo_id=selection["repo_id"], filename=selection["config_file"], repo_type="model")

    model_target = target_dir / Path(selection["model_file"]).name
    config_target = target_dir / "config.json"
    shutil.copy2(model_cache, model_target)
    shutil.copy2(config_cache, config_target)
    _copy_optional_docs(selection["repo_id"], target_dir)

    config_payload = _load_json(config_target)
    config_summary = summarize_sovits_config(config_payload)
    speakers = extract_speaker_list(config_payload)
    speaker = args.speaker.strip() or selection.get("speaker") or (speakers[0] if speakers else "")
    validation = _validate_install(
        model_target=model_target,
        config_target=config_target,
        speaker=speaker,
        config_summary=config_summary,
        speakers=speakers,
    )
    if not validation["ok"]:
        _write_install_report(
            target_dir=target_dir,
            selection=selection,
            model_target=model_target,
            config_target=config_target,
            speaker=speaker,
            config_summary=config_summary,
            validation=validation,
        )
        print(json.dumps(validation, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    report = _write_install_report(
        target_dir=target_dir,
        selection=selection,
        model_target=model_target,
        config_target=config_target,
        speaker=speaker,
        config_summary=config_summary,
        validation=validation,
    )
    _update_preset_config(
        preset_id=preset_id,
        model_target=model_target,
        config_target=config_target,
        speaker=speaker,
        selection=selection,
        activate=args.activate,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _select_candidate(args: argparse.Namespace) -> dict[str, Any]:
    if args.repo_id and args.model_file and args.config_file:
        return {
            "repo_id": args.repo_id,
            "model_file": args.model_file,
            "config_file": args.config_file,
            "speaker": args.speaker,
            "license": _fetch_repo_license(args.repo_id),
            "source": "manual_args",
        }

    payload = _load_json(CANDIDATES_PATH)
    accepted = [candidate for candidate in payload.get("candidates", []) if not candidate.get("rejection_reason")]
    if not accepted:
        raise SystemExit(f"No accepted candidates found in {CANDIDATES_PATH}")
    index = max(0, args.candidate_rank - 1)
    if index >= len(accepted):
        raise SystemExit(f"candidate-rank {args.candidate_rank} is out of range; accepted candidates={len(accepted)}")
    selected = dict(accepted[index])
    speakers = list(selected.get("speaker_candidates") or [])
    selected["speaker"] = args.speaker.strip() or (speakers[0] if speakers else "")
    selected["source"] = str(CANDIDATES_PATH)
    return selected


def _copy_optional_docs(repo_id: str, target_dir: Path) -> None:
    for filename in ("README.md", "model_card.md", "LICENSE", "LICENSE.txt", "license.txt"):
        try:
            cached = hf_hub_download(repo_id=repo_id, filename=filename, repo_type="model")
        except Exception:
            continue
        target_name = "model_card.md" if filename.lower() in {"readme.md", "model_card.md"} else Path(filename).name
        shutil.copy2(cached, target_dir / target_name)


def _validate_install(
    *,
    model_target: Path,
    config_target: Path,
    speaker: str,
    config_summary: dict[str, Any],
    speakers: list[str],
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    speech_encoder = config_summary.get("speech_encoder")
    if not model_target.exists() or model_target.stat().st_size <= 1024 * 1024:
        errors.append({"code": "MODEL_FILE_TOO_SMALL", "message": "model file must exist and be larger than 1MB"})
    if not config_target.exists():
        errors.append({"code": "CONFIG_MISSING", "message": "config.json missing"})
    if speaker not in speakers:
        errors.append({"code": "SPEAKER_NOT_FOUND", "message": f"speaker={speaker!r} not found in config", "available_speakers": speakers})
    if speech_encoder not in SUPPORTED_ENCODERS:
        errors.append({"code": "UNSUPPORTED_SPEECH_ENCODER", "message": f"speech_encoder={speech_encoder} is not supported"})
    if speech_encoder in CONTENTVEC_ENCODERS and not _contentvec_ready():
        _run_prepare_sovits_assets()
        if not _contentvec_ready():
            errors.append({"code": "CONTENTVEC_PRETRAIN_NOT_FOUND", "message": "required ContentVec pretrain file is missing"})

    asset_report = inspect_sovits_assets(
        repo_dir=str(PROJECT_ROOT / "so-vits-svc"),
        infer_script=str(PROJECT_ROOT / "so-vits-svc" / "inference_main.py"),
        model_path=str(model_target),
        config_path=str(config_target),
        speaker=speaker,
    )
    errors.extend(asset_report.get("validation_errors", []))
    return {
        "ok": not errors,
        "errors": errors,
        "asset_report": asset_report,
    }


def _contentvec_ready() -> bool:
    pretrain = PROJECT_ROOT / "so-vits-svc" / "pretrain"
    return any((pretrain / name).exists() for name in ("checkpoint_best_legacy_500.pt", "hubert_base.pt"))


def _run_prepare_sovits_assets() -> None:
    subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "prepare_sovits_assets.py")], cwd=PROJECT_ROOT)


def _write_install_report(
    *,
    target_dir: Path,
    selection: dict[str, Any],
    model_target: Path,
    config_target: Path,
    speaker: str,
    config_summary: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    report = {
        "repo_id": selection["repo_id"],
        "model_path": str(model_target),
        "config_path": str(config_target),
        "speaker": speaker,
        "license": selection.get("license", ""),
        "downloaded_at": _now(),
        "sha256": _sha256(model_target),
        "config_sha256": _sha256(config_target),
        "speech_encoder": config_summary.get("speech_encoder"),
        "sampling_rate": config_summary.get("sampling_rate"),
        "validation_result": validation,
    }
    (target_dir / "install_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _update_preset_config(
    *,
    preset_id: str,
    model_target: Path,
    config_target: Path,
    speaker: str,
    selection: dict[str, Any],
    activate: bool,
) -> None:
    payload = _load_json(PRESETS_PATH) if PRESETS_PATH.exists() else {"presets": []}
    payload.setdefault("active_preset_id", "tech_villager")
    payload.setdefault("fallback_preset_id", "tech_villager")
    presets = [item for item in payload.get("presets", []) if item.get("preset_id") != preset_id]
    presets.insert(
        0,
        {
            "preset_id": preset_id,
            "display_name": "最终演示 So-VITS-SVC 模型",
            "description": "用于毕业设计默认演示的目标歌声转换模型。",
            "model_path": str(model_target),
            "config_path": str(config_target),
            "speaker": speaker,
            "device": "cuda",
            "is_demo_quality": True,
            "is_technical_validation_only": False,
            "source_repo": selection["repo_id"],
            "license": selection.get("license", ""),
        },
    )
    payload["presets"] = presets
    if activate:
        payload["active_preset_id"] = preset_id
    PRESETS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _fetch_repo_license(repo_id: str) -> str:
    try:
        info = HfApi().model_info(repo_id)
    except Exception:
        return ""
    for tag in getattr(info, "tags", []) or []:
        if str(tag).startswith("license:"):
            return str(tag).split(":", 1)[1]
    card_data = getattr(info, "cardData", None)
    if isinstance(card_data, dict):
        return str(card_data.get("license") or "")
    return str(getattr(card_data, "license", "") or "")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


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
