from __future__ import annotations

from pathlib import Path
from typing import Any

import torch

from app.models_svc.sovits_assets import (
    ensure_repo_runtime_assets,
    inspect_sovits_assets,
    preferred_contentvec_path,
    preferred_rmvpe_path,
)
from app.models_svc.style_film import StyleFiLMAdapter
from app.models_svc.sovits_wrapper import SoVitsSvcEngine, load_conversion_params_config
from app.models_svc.text_style_adapter import load_style_adapter_config
from app.services.text_style_encoder import TextStyleEncoder

PROJECT_ROOT = Path(__file__).resolve().parents[3]
APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PROMPT = "温柔、明亮、流行感更强的女声风格"
WEIGHT_GLOBS = ("*.pth", "*.pt", "*.ckpt", "*.onnx", "*.safetensors", "*.npy")


def _basename(path: str | None) -> str | None:
    if not path:
        return None
    return Path(path).name


def _normalize_level(level: str) -> str:
    return str(level or "ok").strip().lower()


def _append_check(
    checks: list[dict[str, Any]],
    level: str,
    message: str,
    *,
    code: str,
    details: dict[str, Any] | None = None,
) -> None:
    checks.append(
        {
            "level": _normalize_level(level),
            "code": code,
            "message": message,
            "details": details or {},
        }
    )


def _gitignore_covers_weights(project_root: Path) -> bool:
    gitignore_path = project_root / ".gitignore"
    if not gitignore_path.exists():
        return False
    content = gitignore_path.read_text(encoding="utf-8")
    patterns = {line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")}
    return all(pattern in patterns for pattern in WEIGHT_GLOBS)


def _text_encoder_check(style_dim: int, prompt_text: str) -> dict[str, Any]:
    encoder = TextStyleEncoder(style_dim=style_dim)
    embedding = encoder.encode_prompt(prompt_text)
    summary = embedding.to_summary()
    summary["encoder_model_name"] = embedding.model_name
    summary["encoder_type"] = embedding.encoder_type
    summary["embedding_dim"] = embedding.embedding_dim
    return summary


def _style_film_check(style_dim: int, film_strength: float) -> dict[str, Any]:
    adapter = StyleFiLMAdapter(style_dim=style_dim, hidden_channels=8, strength=film_strength)
    hidden = torch.randn(1, 8, 12, dtype=torch.float32)
    style_emb = torch.randn(1, style_dim, dtype=torch.float32)
    modulated = adapter(hidden, style_emb)
    return {
        "shape": list(modulated.shape),
        "dtype": str(modulated.dtype),
        "finite": bool(torch.isfinite(modulated).all().item()),
    }


def _optional_adapter_check() -> dict[str, Any]:
    config = load_style_adapter_config()
    checkpoint_path = str(config.get("adapter_checkpoint_path") or "")
    return {
        "checkpoint_path": checkpoint_path,
        "checkpoint_basename": _basename(checkpoint_path),
        "exists": bool(checkpoint_path and Path(checkpoint_path).exists()),
        "enabled": bool(config.get("enabled", True)),
        "use_trained": bool(config.get("use_trained", True)),
    }


def _device_check(device: str, require_real_assets: bool) -> dict[str, Any]:
    normalized = str(device or "").strip().lower() or "cpu"
    if normalized == "cuda":
        available = bool(torch.cuda.is_available())
        return {
            "requested_device": device,
            "available": available,
            "device_count": int(torch.cuda.device_count()) if available else 0,
            "required": require_real_assets,
        }
    return {
        "requested_device": device,
        "available": True,
        "device_count": 0,
        "required": False,
    }


def build_runtime_status_summary(*, runtime_config: Any, asset_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "mock": bool(runtime_config.mock_enabled),
        "preset": runtime_config.model_preset_id or runtime_config.effective_model_preset_id or None,
        "model_exists": bool(asset_report.get("model_exists")),
        "config_exists": bool(asset_report.get("config_exists")),
        "model_basename": _basename(runtime_config.model_path),
        "config_basename": _basename(runtime_config.config_path),
        "speaker": runtime_config.speaker,
        "device": runtime_config.device,
        "condition_mode": runtime_config.condition_mode,
        "conditioned_infer_exists": Path(runtime_config.infer_script).exists() if runtime_config.called_conditioned_inference else False,
        "called_conditioned_inference": bool(runtime_config.called_conditioned_inference),
        "style_dim": int(runtime_config.style_dim),
        "film_strength": float(runtime_config.film_strength),
        "film_target": runtime_config.film_target,
        "style_emb_format": runtime_config.style_emb_format,
        "speech_encoder": asset_report.get("config_summary", {}).get("speech_encoder"),
        "f0_predictor": asset_report.get("config_summary", {}).get("f0_predictor"),
    }


def build_text_conditioning_summary(*, runtime_config: Any, text_encoder: dict[str, Any]) -> dict[str, Any]:
    return {
        "enabled": runtime_config.condition_mode == "internal_film",
        "style_dim": int(runtime_config.style_dim),
        "film_strength": float(runtime_config.film_strength),
        "film_target": runtime_config.film_target,
        "style_emb_format": runtime_config.style_emb_format,
        "encoder_status": text_encoder.get("status"),
        "encoder_type": text_encoder.get("encoder_type"),
    }


def collect_model_readiness(
    *,
    preset_id: str | None = None,
    prompt_text: str = DEFAULT_PROMPT,
    require_real_assets: bool = True,
    skip_real_checks_if_mock: bool = False,
) -> dict[str, Any]:
    engine = SoVitsSvcEngine()
    style_preset = {"model_preset_id": preset_id} if preset_id else {}
    runtime_config = engine.resolve_runtime_config(style_preset)
    ensure_actions = ensure_repo_runtime_assets(runtime_config.repo_dir)
    conversion_defaults = load_conversion_params_config().get("defaults", {})
    requested_f0_method = str(conversion_defaults.get("f0_method") or runtime_config.f0_method or "").strip().lower()
    asset_report = inspect_sovits_assets(
        repo_dir=runtime_config.repo_dir,
        infer_script=runtime_config.base_infer_script,
        model_path=runtime_config.model_path,
        config_path=runtime_config.config_path,
        speaker=runtime_config.speaker,
        f0_method=requested_f0_method if requested_f0_method == "rmvpe" else None,
    )

    checks: list[dict[str, Any]] = []
    real_checks_required = require_real_assets and not (runtime_config.mock_enabled and skip_real_checks_if_mock)

    if runtime_config.mock_enabled:
        _append_check(
            checks,
            "warn" if skip_real_checks_if_mock else "error",
            "Current runtime is in Mock mode.",
            code="SOVITS_MOCK_ENABLED",
            details={"mock_enabled": True},
        )
    else:
        _append_check(checks, "ok", "Real So-VITS-SVC mode is enabled.", code="SOVITS_REAL_MODE")

    if asset_report.get("repo_exists"):
        _append_check(checks, "ok", "So-VITS-SVC repo found.", code="SOVITS_REPO_FOUND")
    else:
        _append_check(
            checks,
            "error" if real_checks_required else "warn",
            "So-VITS-SVC repo missing.",
            code="SOVITS_REPO_NOT_FOUND",
            details={"expected_path": runtime_config.repo_dir},
        )

    if Path(runtime_config.base_infer_script).exists():
        _append_check(checks, "ok", "inference_main.py found.", code="SOVITS_INFER_SCRIPT_FOUND")
    else:
        _append_check(
            checks,
            "error" if real_checks_required else "warn",
            "inference_main.py missing.",
            code="SOVITS_SCRIPT_NOT_FOUND",
            details={"expected_path": runtime_config.base_infer_script},
        )

    if Path(runtime_config.infer_script).exists() and runtime_config.called_conditioned_inference:
        _append_check(checks, "ok", "Conditioned internal FiLM inference found.", code="SOVITS_CONDITIONED_INFER_FOUND")
    elif runtime_config.called_conditioned_inference:
        _append_check(
            checks,
            "error" if real_checks_required else "warn",
            "Conditioned internal FiLM inference missing.",
            code="SOVITS_CONDITIONED_SCRIPT_NOT_FOUND",
            details={"expected_path": runtime_config.infer_script},
        )

    if asset_report.get("model_exists"):
        _append_check(checks, "ok", "final_primary model found.", code="SOVITS_MODEL_FOUND")
    else:
        _append_check(
            checks,
            "error" if real_checks_required else "warn",
            "Model checkpoint missing.",
            code="SOVITS_MODEL_NOT_FOUND",
            details={"expected_path": runtime_config.model_path},
        )

    if asset_report.get("config_exists"):
        _append_check(checks, "ok", "config.json found.", code="SOVITS_CONFIG_FOUND")
    else:
        _append_check(
            checks,
            "error" if real_checks_required else "warn",
            "config.json missing.",
            code="SOVITS_CONFIG_NOT_FOUND",
            details={"expected_path": runtime_config.config_path},
        )

    if asset_report.get("config_parse_ok"):
        _append_check(checks, "ok", "config.json parsed.", code="SOVITS_CONFIG_PARSED")
    elif asset_report.get("config_exists"):
        _append_check(
            checks,
            "error" if real_checks_required else "warn",
            "config.json could not be parsed.",
            code="SOVITS_CONFIG_INVALID",
            details={"error": asset_report.get("config_error")},
        )

    speaker_exists = asset_report.get("speaker_exists_in_config")
    if speaker_exists is True:
        _append_check(checks, "ok", f"speaker {runtime_config.speaker} found.", code="SOVITS_SPEAKER_FOUND")
    elif runtime_config.speaker:
        _append_check(
            checks,
            "error" if real_checks_required else "warn",
            f"speaker {runtime_config.speaker} not found in config.",
            code="SOVITS_SPEAKER_NOT_IN_CONFIG",
            details={
                "speaker": runtime_config.speaker,
                "available_speakers": asset_report.get("config_summary", {}).get("speakers", []),
            },
        )
    else:
        _append_check(
            checks,
            "error" if real_checks_required else "warn",
            "speaker is empty.",
            code="SOVITS_SPEAKER_MISSING",
        )

    if asset_report.get("speech_encoder_pretrain_required"):
        found_paths = asset_report.get("contentvec_found_paths") or []
        if found_paths:
            _append_check(
                checks,
                "ok",
                "Speech encoder pretrain found.",
                code="SOVITS_CONTENTVEC_FOUND",
                details={"resolved_path": found_paths[0]},
            )
        else:
            _append_check(
                checks,
                "error" if real_checks_required else "warn",
                "ContentVec / HuBERT checkpoint missing.",
                code="CONTENTVEC_PRETRAIN_NOT_FOUND",
                details={
                    "speech_encoder": asset_report.get("config_summary", {}).get("speech_encoder"),
                    "expected_paths": asset_report.get("contentvec_candidate_paths", []),
                    "preferred_path": str(
                        preferred_contentvec_path(
                            runtime_config.repo_dir,
                            speech_encoder=asset_report.get("config_summary", {}).get("speech_encoder"),
                        )
                    ),
                    "supported_env_var": "SOVITS_CONTENTVEC_PATH",
                },
            )

    rmvpe_required = bool(asset_report.get("rmvpe_required"))
    if rmvpe_required:
        found_paths = asset_report.get("rmvpe_found_paths") or []
        if found_paths:
            _append_check(
                checks,
                "ok",
                "RMVPE model found.",
                code="RMVPE_MODEL_FOUND",
                details={"resolved_path": found_paths[0]},
            )
        else:
            _append_check(
                checks,
                "error" if real_checks_required else "warn",
                "RMVPE model missing.",
                code="RMVPE_MODEL_NOT_FOUND",
                details={
                    "expected_paths": asset_report.get("rmvpe_candidate_paths", []),
                    "preferred_path": str(preferred_rmvpe_path(runtime_config.repo_dir)),
                    "supported_env_var": "SOVITS_RMVPE_MODEL_PATH",
                },
            )
    else:
        _append_check(
            checks,
            "warn",
            "Current CLI passthrough does not require RMVPE for this smoke path; RMVPE is not a hard blocker here.",
            code="RMVPE_NOT_REQUIRED",
            details={
                "f0_method_requested": requested_f0_method or None,
                "f0_method_effective": runtime_config.f0_method,
                "cli_passthrough": runtime_config.cli_passthrough or {},
            },
        )

    device_status = _device_check(runtime_config.device, real_checks_required)
    if device_status["available"]:
        _append_check(
            checks,
            "ok",
            f"device {runtime_config.device} is available.",
            code="SOVITS_DEVICE_READY",
            details=device_status,
        )
    else:
        _append_check(
            checks,
            "error" if real_checks_required else "warn",
            f"device {runtime_config.device} is unavailable.",
            code="SOVITS_DEVICE_UNAVAILABLE",
            details=device_status,
        )

    text_encoder_status = _text_encoder_check(runtime_config.style_dim, prompt_text)
    _append_check(
        checks,
        "ok",
        f"TextStyleEncoder generated style_emb via {text_encoder_status.get('encoder_type')}.",
        code="TEXT_STYLE_ENCODER_READY",
        details=text_encoder_status,
    )

    film_status = _style_film_check(runtime_config.style_dim, runtime_config.film_strength)
    _append_check(
        checks,
        "ok" if film_status["finite"] else "error",
        "StyleFiLMAdapter modulated a dummy tensor.",
        code="STYLE_FILM_READY",
        details=film_status,
    )

    optional_adapter = _optional_adapter_check()
    if optional_adapter["exists"]:
        _append_check(
            checks,
            "ok",
            "Optional trained text style adapter found.",
            code="OPTIONAL_TEXT_STYLE_ADAPTER_FOUND",
            details=optional_adapter,
        )
    else:
        _append_check(
            checks,
            "warn",
            "Optional text style adapter not found, fallback encoder will be used.",
            code="OPTIONAL_TEXT_STYLE_ADAPTER_MISSING",
            details=optional_adapter,
        )

    if _gitignore_covers_weights(PROJECT_ROOT):
        _append_check(checks, "ok", ".gitignore covers model weight suffixes.", code="GITIGNORE_WEIGHTS_OK")
    else:
        _append_check(
            checks,
            "error",
            ".gitignore is missing one or more model weight suffix patterns.",
            code="GITIGNORE_WEIGHTS_MISSING",
        )

    for action in ensure_actions:
        _append_check(
            checks,
            "ok",
            f"{action['asset']} runtime asset linked into repo pretrain/ for local inference.",
            code=f"{action['asset'].upper()}_SYMLINKED",
            details=action,
        )

    has_error = any(check["level"] == "error" for check in checks)
    return {
        "ok": not has_error,
        "preset_id": runtime_config.model_preset_id or preset_id or None,
        "runtime_config": runtime_config.to_public_dict(),
        "asset_report": asset_report,
        "checks": checks,
        "sovits": build_runtime_status_summary(runtime_config=runtime_config, asset_report=asset_report),
        "text_conditioning": build_text_conditioning_summary(runtime_config=runtime_config, text_encoder=text_encoder_status),
    }
