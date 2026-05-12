from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parents[1]
BACKEND_ROOT = APP_DIR.parents[0]
PROJECT_ROOT = BACKEND_ROOT.parent

CONTENTVEC_REQUIRED_ENCODERS = {
    "vec768l12",
    "vec256l9",
    "contentvec",
}
HUBERT_REQUIRED_ENCODERS = {
    "hubertsoft",
}
SPEECH_ENCODER_REQUIRED_FILENAMES = {
    "vec768l12": ("checkpoint_best_legacy_500.pt", "hubert_base.pt"),
    "vec256l9": ("checkpoint_best_legacy_500.pt", "hubert_base.pt"),
    "contentvec": ("checkpoint_best_legacy_500.pt", "hubert_base.pt"),
    "hubertsoft": ("hubert-soft-0d54a1f4.pt", "hubert-soft.onnx"),
}
RMVPE_TARGET_RELATIVE_PATH = Path("pretrain") / "rmvpe.pt"
CONTENTVEC_TARGET_RELATIVE_PATH = Path("pretrain") / "checkpoint_best_legacy_500.pt"


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        normalized = str(path)
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(path)
    return deduped


def _candidate_env_path(*env_names: str) -> Path | None:
    for env_name in env_names:
        raw = os.environ.get(env_name, "").strip()
        if raw:
            return Path(raw)
    return None


def speech_encoder_requires_pretrain(speech_encoder: str | None) -> bool:
    normalized = str(speech_encoder or "").strip().lower()
    return normalized in CONTENTVEC_REQUIRED_ENCODERS or normalized in HUBERT_REQUIRED_ENCODERS


def resolve_config_f0_predictor(config_payload: dict[str, Any]) -> str | None:
    for section_name in ("model", "data", "train"):
        section = config_payload.get(section_name)
        if isinstance(section, dict):
            predictor = str(section.get("f0_predictor") or "").strip()
            if predictor:
                return predictor
    top_level = str(config_payload.get("f0_predictor") or "").strip()
    return top_level or None


def load_sovits_config(config_path: str) -> dict[str, Any]:
    with open(config_path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("So-VITS config.json root must be an object")
    return payload


def extract_speaker_list(config_payload: dict[str, Any]) -> list[str]:
    spk_section = config_payload.get("spk")
    if isinstance(spk_section, dict):
        return [str(name) for name in spk_section.keys()]

    speakers = config_payload.get("speakers")
    if isinstance(speakers, list):
        return [str(name) for name in speakers]
    if isinstance(speakers, dict):
        return [str(name) for name in speakers.keys()]
    return []


def summarize_sovits_config(config_payload: dict[str, Any]) -> dict[str, Any]:
    data_section = config_payload.get("data") if isinstance(config_payload.get("data"), dict) else {}
    model_section = config_payload.get("model") if isinstance(config_payload.get("model"), dict) else {}
    return {
        "speakers": extract_speaker_list(config_payload),
        "sampling_rate": data_section.get("sampling_rate"),
        "speech_encoder": model_section.get("speech_encoder"),
        "f0_predictor": resolve_config_f0_predictor(config_payload),
    }


def contentvec_candidate_paths(repo_dir: str, speech_encoder: str | None = None) -> list[Path]:
    pretrain_dir = Path(repo_dir) / "pretrain"
    encoder_name = str(speech_encoder or "").strip().lower()
    filenames = SPEECH_ENCODER_REQUIRED_FILENAMES.get(
        encoder_name,
        ("checkpoint_best_legacy_500.pt", "hubert_base.pt"),
    )
    env_override = _candidate_env_path("SOVITS_CONTENTVEC_PATH")
    candidates = []
    if env_override is not None:
        candidates.append(env_override)
    candidates.extend(
        [
            pretrain_dir / filename
            for filename in filenames
        ]
    )
    candidates.extend(
        [
            Path(repo_dir) / "hubert" / "checkpoint_best_legacy_500.pt",
            Path(repo_dir) / "pretrain" / "contentvec" / "checkpoint_best_legacy_500.pt",
            PROJECT_ROOT / "local_models" / "contentvec" / "checkpoint_best_legacy_500.pt",
            PROJECT_ROOT / "local_models" / "pretrained" / "checkpoint_best_legacy_500.pt",
        ]
    )
    return _dedupe_paths(candidates)


def rmvpe_candidate_paths(repo_dir: str) -> list[Path]:
    env_override = _candidate_env_path("SOVITS_RMVPE_MODEL_PATH", "RMVPE_MODEL_PATH")
    candidates = []
    if env_override is not None:
        candidates.append(env_override)
    candidates.extend(
        [
            BACKEND_ROOT / "models" / "rmvpe" / "rmvpe.pt",
            Path(repo_dir) / RMVPE_TARGET_RELATIVE_PATH,
            Path(repo_dir) / "rmvpe.pt",
            PROJECT_ROOT / "local_models" / "rmvpe" / "rmvpe.pt",
            PROJECT_ROOT / "rmvpe.pt",
        ]
    )
    return _dedupe_paths(candidates)


def preferred_contentvec_path(repo_dir: str, speech_encoder: str | None = None) -> Path:
    candidates = contentvec_candidate_paths(repo_dir, speech_encoder=speech_encoder)
    return candidates[0] if candidates else Path(repo_dir) / CONTENTVEC_TARGET_RELATIVE_PATH


def preferred_rmvpe_path(repo_dir: str) -> Path:
    candidates = rmvpe_candidate_paths(repo_dir)
    return candidates[0] if candidates else Path(repo_dir) / RMVPE_TARGET_RELATIVE_PATH


def _ensure_repo_symlink(target_path: Path, source_path: Path) -> bool:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        return True
    try:
        target_path.symlink_to(source_path)
    except OSError:
        return False
    return True


def ensure_repo_runtime_assets(repo_dir: str) -> list[dict[str, str]]:
    repo_path = Path(repo_dir)
    actions: list[dict[str, str]] = []
    env_asset_mappings = [
        (
            _candidate_env_path("SOVITS_CONTENTVEC_PATH"),
            repo_path / CONTENTVEC_TARGET_RELATIVE_PATH,
            "contentvec",
        ),
        (
            _candidate_env_path("SOVITS_RMVPE_MODEL_PATH", "RMVPE_MODEL_PATH"),
            repo_path / RMVPE_TARGET_RELATIVE_PATH,
            "rmvpe",
        ),
    ]
    for source_path, target_path, asset_name in env_asset_mappings:
        if source_path is None or target_path.exists() or not source_path.exists():
            continue
        if _ensure_repo_symlink(target_path, source_path):
            actions.append(
                {
                    "asset": asset_name,
                    "source_path": str(source_path),
                    "target_path": str(target_path),
                    "action": "symlinked",
                }
            )
    return actions


def inspect_sovits_assets(
    *,
    repo_dir: str,
    infer_script: str,
    model_path: str,
    config_path: str,
    speaker: str,
    f0_method: str | None = None,
) -> dict[str, Any]:
    repo_path = Path(repo_dir)
    script_path = Path(infer_script)
    model_file = Path(model_path) if model_path else None
    config_file = Path(config_path) if config_path else None
    report: dict[str, Any] = {
        "repo_exists": repo_path.exists(),
        "infer_script_exists": script_path.exists(),
        "model_exists": bool(model_file and model_file.exists()),
        "config_exists": bool(config_file and config_file.exists()),
        "config_parse_ok": False,
        "config_error": None,
        "config_summary": {
            "speakers": [],
            "sampling_rate": None,
            "speech_encoder": None,
            "f0_predictor": None,
        },
        "speaker_exists_in_config": None,
        "speech_encoder_pretrain_required": False,
        "speech_encoder_pretrain_type": None,
        "contentvec_required": False,
        "contentvec_candidate_paths": [],
        "contentvec_found_paths": [],
        "rmvpe_required": False,
        "rmvpe_candidate_paths": [str(path) for path in rmvpe_candidate_paths(repo_dir)],
        "rmvpe_found_paths": [],
        "validation_errors": [],
    }

    if not report["config_exists"]:
        return report

    try:
        config_payload = load_sovits_config(config_path)
    except Exception as exc:
        report["config_error"] = str(exc)
        report["validation_errors"].append(
            {
                "code": "SOVITS_CONFIG_INVALID",
                "message": f"Failed to parse So-VITS config.json: {exc}",
            }
        )
        return report

    report["config_parse_ok"] = True
    report["config_summary"] = summarize_sovits_config(config_payload)
    speakers = report["config_summary"]["speakers"]
    speech_encoder = report["config_summary"]["speech_encoder"]
    config_f0_predictor = report["config_summary"]["f0_predictor"]
    requested_f0_method = str(f0_method or "").strip().lower()
    effective_f0_predictor = requested_f0_method or str(config_f0_predictor or "").strip().lower()

    if speaker.strip():
        report["speaker_exists_in_config"] = speaker in speakers if speakers else None
        if speakers and speaker not in speakers:
            report["validation_errors"].append(
                {
                    "code": "SOVITS_SPEAKER_NOT_IN_CONFIG",
                    "message": f"Speaker '{speaker}' is not present in config speaker list",
                    "details": {
                        "speaker": speaker,
                        "available_speakers": speakers,
                    },
                }
            )

    if speech_encoder_requires_pretrain(speech_encoder):
        normalized_encoder = str(speech_encoder or "").strip().lower()
        report["speech_encoder_pretrain_required"] = True
        report["speech_encoder_pretrain_type"] = normalized_encoder
        report["contentvec_required"] = normalized_encoder in CONTENTVEC_REQUIRED_ENCODERS
        candidate_paths = contentvec_candidate_paths(repo_dir, speech_encoder=speech_encoder)
        report["contentvec_candidate_paths"] = [str(path) for path in candidate_paths]
        found_paths = [str(path) for path in candidate_paths if path.exists()]
        report["contentvec_found_paths"] = found_paths
        if not found_paths:
            expected_label = "ContentVec" if normalized_encoder in CONTENTVEC_REQUIRED_ENCODERS else "HuBERT"
            report["validation_errors"].append(
                {
                    "code": "CONTENTVEC_PRETRAIN_NOT_FOUND",
                    "message": (
                        f"speech_encoder={speech_encoder} requires a local {expected_label} checkpoint "
                        f"under {repo_path / 'pretrain'}"
                    ),
                    "details": {
                        "speech_encoder": speech_encoder,
                        "expected_paths": report["contentvec_candidate_paths"],
                        "preferred_path": str(preferred_contentvec_path(repo_dir, speech_encoder=speech_encoder)),
                        "supported_env_var": "SOVITS_CONTENTVEC_PATH",
                    },
                }
            )

    if effective_f0_predictor == "rmvpe":
        report["rmvpe_required"] = True
        found_paths = [str(path) for path in rmvpe_candidate_paths(repo_dir) if path.exists()]
        report["rmvpe_found_paths"] = found_paths
        if not found_paths:
            report["validation_errors"].append(
                {
                    "code": "RMVPE_MODEL_NOT_FOUND",
                    "message": "RMVPE was requested but no local rmvpe.pt checkpoint was found",
                    "details": {
                        "f0_method": effective_f0_predictor,
                        "expected_paths": report["rmvpe_candidate_paths"],
                        "preferred_path": str(preferred_rmvpe_path(repo_dir)),
                        "supported_env_var": "SOVITS_RMVPE_MODEL_PATH",
                    },
                }
            )

    return report


def build_sovits_env_exports(
    *,
    repo_dir: str,
    infer_script: str,
    model_path: str,
    config_path: str,
    speaker: str,
    device: str,
) -> list[str]:
    return [
        "export SOVITS_MOCK=false",
        f"export SOVITS_REPO_DIR={repo_dir}",
        f"export SOVITS_INFER_SCRIPT={infer_script}",
        f"export SOVITS_MODEL_PATH={model_path}",
        f"export SOVITS_CONFIG_PATH={config_path}",
        f"export SOVITS_SPEAKER={speaker}",
        f"export SOVITS_DEVICE={device}",
        "export SOVITS_TRANSPOSE=0",
        "export SOVITS_TIMEOUT_SECONDS=300",
        "export SOVITS_PYTHON=",
        "export SOVITS_VENDOR_PATH=",
    ]
