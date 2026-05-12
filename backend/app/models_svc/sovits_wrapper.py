from __future__ import annotations

import json
import importlib.util
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import soundfile as sf

from app.models_svc.sovits_assets import ensure_repo_runtime_assets, inspect_sovits_assets
from app.models_svc.svc_base import VoiceConversionEngine
from app.services import svc_model_presets

logger = logging.getLogger(__name__)
RESULT_AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".ogg", ".m4a"}
GPU_QUERY_COMMAND = [
    "nvidia-smi",
    "--query-gpu=timestamp,name,utilization.gpu,memory.used,memory.total",
    "--format=csv",
]
GPU_COMPUTE_APPS_COMMAND = [
    "nvidia-smi",
    "--query-compute-apps=pid,process_name,used_memory",
    "--format=csv",
]
APP_DIR = Path(__file__).resolve().parents[1]
CONVERSION_PARAMS_PATH = Path(
    os.environ.get(
        "SVC_CONVERSION_PARAMS_PATH",
        str(APP_DIR / "config" / "conversion_params.json"),
    )
)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_condition_mode(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    if value in {"", "internal_film", "film", "default"}:
        return "internal_film"
    if value in {"none", "off", "disabled"}:
        return "none"
    return "internal_film"


def load_conversion_params_config() -> dict[str, Any]:
    defaults = {
        "defaults": {
            "f0_method": "rmvpe",
            "fallback_f0_method": "system_default",
            "auto_predict_f0": False,
            "transpose": 0,
            "slice_db": -40.0,
            "clip_seconds": 0.0,
            "pad_seconds": 0.5,
        },
        "limits": {
            "transpose": {"min": -24, "max": 24},
            "slice_db": {"min": -80.0, "max": 0.0},
            "clip_seconds": {"min": 0.0, "max": 30.0},
            "pad_seconds": {"min": 0.0, "max": 5.0},
        },
        "cli_passthrough": {
            "transpose": True,
            "f0_method": False,
            "auto_predict_f0": False,
            "slice_db": False,
            "clip_seconds": False,
            "pad_seconds": False,
        },
        "notes": {
            "unsupported_passthrough": "当前 So-VITS-SVC 4.1 集成只直接透传 transpose；其余参数仅记录，不强行传入 CLI。"
        },
    }
    if not CONVERSION_PARAMS_PATH.exists():
        return defaults
    payload = json.loads(CONVERSION_PARAMS_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("conversion_params.json root must be an object")
    merged = {**defaults, **payload}
    merged["defaults"] = {**defaults["defaults"], **dict(payload.get("defaults") or {})}
    merged["limits"] = {**defaults["limits"], **dict(payload.get("limits") or {})}
    merged["cli_passthrough"] = {**defaults["cli_passthrough"], **dict(payload.get("cli_passthrough") or {})}
    merged["notes"] = {**defaults["notes"], **dict(payload.get("notes") or {})}
    return merged


@dataclass
class SoVitsRuntimeConfig:
    repo_dir: str
    infer_script: str
    base_infer_script: str
    model_path: str
    config_path: str
    speaker: str
    device: str
    transpose: int
    timeout_seconds: int
    mock_enabled: bool
    python_bin: str
    f0_method: str = "system_default"
    f0_fallback_reason: str = ""
    auto_predict_f0: bool = False
    slice_db: float = -40.0
    clip_seconds: float = 0.0
    pad_seconds: float = 0.5
    conversion_params_requested: dict[str, Any] | None = None
    cli_passthrough: dict[str, bool] | None = None
    cli_passthrough_notes: str = ""
    model_preset_id: str = ""
    requested_model_preset_id: str = ""
    effective_model_preset_id: str = ""
    preset_fallback_used: bool = False
    preset_fallback_reason: str = ""
    model_display_name: str = ""
    source_repo: str = ""
    source_url: str = ""
    license: str = ""
    install_report_path: str = ""
    notes: str = ""
    model_path_basename: str = ""
    config_path_basename: str = ""
    model_preset_ready: bool = False
    model_preset_configured: bool = False
    is_demo_quality: bool = False
    smoke_test_passed: bool = False
    is_technical_validation_only: bool = False
    validation_mode: str = ""
    bypass_configured_gate: bool = False
    condition_mode: str = "internal_film"
    style_dim: int = 256
    film_strength: float = 0.1
    film_target: str = "pre_decoder"
    style_emb_format: str = "pt"
    called_conditioned_inference: bool = False

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "repo_dir": self.repo_dir,
            "infer_script": self.infer_script,
            "base_infer_script": self.base_infer_script,
            "model_path": self.model_path,
            "config_path": self.config_path,
            "speaker": self.speaker,
            "device": self.device,
            "transpose": self.transpose,
            "timeout_seconds": self.timeout_seconds,
            "mock_enabled": self.mock_enabled,
            "python_bin": self.python_bin,
            "f0_method": self.f0_method,
            "f0_fallback_reason": self.f0_fallback_reason,
            "auto_predict_f0": self.auto_predict_f0,
            "slice_db": self.slice_db,
            "clip_seconds": self.clip_seconds,
            "pad_seconds": self.pad_seconds,
            "conversion_params_requested": self.conversion_params_requested or {},
            "cli_passthrough": self.cli_passthrough or {},
            "cli_passthrough_notes": self.cli_passthrough_notes,
            "model_preset_id": self.model_preset_id,
            "requested_model_preset_id": self.requested_model_preset_id,
            "effective_model_preset_id": self.effective_model_preset_id,
            "preset_fallback_used": self.preset_fallback_used,
            "preset_fallback_reason": self.preset_fallback_reason,
            "model_display_name": self.model_display_name,
            "source_repo": self.source_repo,
            "source_url": self.source_url,
            "license": self.license,
            "install_report_path": self.install_report_path,
            "notes": self.notes,
            "model_path_basename": self.model_path_basename or Path(self.model_path).name,
            "config_path_basename": self.config_path_basename or Path(self.config_path).name,
            "model_preset_ready": self.model_preset_ready,
            "model_preset_configured": self.model_preset_configured,
            "is_demo_quality": self.is_demo_quality,
            "smoke_test_passed": self.smoke_test_passed,
            "is_technical_validation_only": self.is_technical_validation_only,
            "validation_mode": self.validation_mode,
            "bypass_configured_gate": self.bypass_configured_gate,
            "condition_mode": self.condition_mode,
            "style_dim": self.style_dim,
            "film_strength": self.film_strength,
            "film_target": self.film_target,
            "style_emb_format": self.style_emb_format,
            "called_conditioned_inference": self.called_conditioned_inference,
        }


class SoVitsSvcError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "details": self.details,
        }


class SoVitsSvcEngine(VoiceConversionEngine):
    def __init__(self) -> None:
        self.repo_dir = os.environ.get("SOVITS_REPO_DIR", "/home/featurize/work/BS/so-vits-svc")
        self.infer_script = os.environ.get("SOVITS_INFER_SCRIPT", os.path.join(self.repo_dir, "inference_main.py"))
        self.conditioned_infer_script = os.environ.get(
            "SOVITS_CONDITIONED_INFER_SCRIPT",
            str(APP_DIR / "models_svc" / "inference_conditioned.py"),
        )
        self.model_path = os.environ.get("SOVITS_MODEL_PATH", "")
        self.config_path = os.environ.get("SOVITS_CONFIG_PATH", "")
        self.speaker = os.environ.get("SOVITS_SPEAKER", "")
        self.device = os.environ.get("SOVITS_DEVICE", "cuda")
        self.transpose = int(os.environ.get("SOVITS_TRANSPOSE", "0"))
        self.timeout_seconds = int(os.environ.get("SOVITS_TIMEOUT_SECONDS", "600"))
        self.mock_enabled = _env_flag("SOVITS_MOCK", True)
        self.python_bin = os.environ.get("SOVITS_PYTHON") or sys.executable
        self.vendor_path = os.environ.get("SOVITS_VENDOR_PATH", "").strip()
        self.condition_mode = _normalize_condition_mode(os.environ.get("SOVITS_CONDITION_MODE", "internal_film"))
        self.style_dim = int(os.environ.get("SOVITS_STYLE_DIM", "256"))
        self.film_strength = float(os.environ.get("SOVITS_FILM_STRENGTH", "0.10"))
        self.film_target = str(os.environ.get("SOVITS_FILM_TARGET", "pre_decoder") or "pre_decoder")
        self.style_emb_format = str(os.environ.get("SOVITS_STYLE_EMB_FORMAT", "pt") or "pt")

    def convert(
        self,
        input_vocals_path: str,
        prompt_text: str,
        style_strength: float,
        output_path: str,
        **kwargs,
    ) -> str:
        debug_dir = kwargs.get("debug_dir")
        task_id = kwargs.get("task_id")
        runtime_context = kwargs.get("runtime_context")
        style_preset = dict(kwargs.get("style_preset") or {})
        conversion_params = dict(kwargs.get("conversion_params") or {})
        allow_preset_fallback = bool(kwargs.get("allow_preset_fallback", False))
        allow_unconfigured_preset_smoke = bool(kwargs.get("allow_unconfigured_preset_smoke", False))
        style_prompt = str(kwargs.get("style_prompt") or prompt_text or "")
        style_emb_path = str(kwargs.get("style_emb_path") or "")
        style_dim = int(kwargs.get("style_dim") or self.style_dim)
        runtime_config = self.resolve_runtime_config(
            style_preset,
            conversion_params=conversion_params,
            allow_preset_fallback=allow_preset_fallback,
            allow_unconfigured_preset_smoke=allow_unconfigured_preset_smoke,
        )
        if isinstance(runtime_context, dict):
            runtime_context.update(
                {
                    "inference_mode": "mock" if runtime_config.mock_enabled else "real",
                    "engine": "sovits",
                    "runtime_config": runtime_config.to_public_dict(),
                    "resolved_conversion_params": runtime_config.to_public_dict(),
                }
            )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        if runtime_config.mock_enabled:
            shutil.copyfile(input_vocals_path, output_path)
            mock_result = {
                "inference_mode": "mock",
                "mock_enabled": True,
                "model_path": runtime_config.model_path,
                "config_path": runtime_config.config_path,
                "speaker": runtime_config.speaker,
                "device": runtime_config.device,
                "transpose": runtime_config.transpose,
                "f0_method": runtime_config.f0_method,
                "f0_fallback_reason": runtime_config.f0_fallback_reason,
                "auto_predict_f0": runtime_config.auto_predict_f0,
                "slice_db": runtime_config.slice_db,
                "clip_seconds": runtime_config.clip_seconds,
                "pad_seconds": runtime_config.pad_seconds,
                "model_preset_id": runtime_config.model_preset_id,
                "requested_model_preset_id": runtime_config.requested_model_preset_id,
                "effective_model_preset_id": runtime_config.effective_model_preset_id,
                "preset_fallback_used": runtime_config.preset_fallback_used,
                "preset_fallback_reason": runtime_config.preset_fallback_reason,
                "model_display_name": runtime_config.model_display_name,
                "source_repo": runtime_config.source_repo,
                "source_url": runtime_config.source_url,
                "license": runtime_config.license,
                "install_report_path": runtime_config.install_report_path,
                "notes": runtime_config.notes,
                "model_path_basename": runtime_config.model_path_basename or Path(runtime_config.model_path).name,
                "config_path_basename": runtime_config.config_path_basename or Path(runtime_config.config_path).name,
                "is_demo_quality": runtime_config.is_demo_quality,
                "is_technical_validation_only": runtime_config.is_technical_validation_only,
                "selected_output": output_path,
                "final_output_path": output_path,
                "return_code": 0,
                "elapsed_seconds": 0.0,
                "sovits_command_debug_path": os.path.join(debug_dir, "sovits_command.txt") if debug_dir else None,
                "called_inference_main": False,
                "validation_mode": runtime_config.validation_mode or None,
                "bypass_configured_gate": runtime_config.bypass_configured_gate,
                "condition_mode": runtime_config.condition_mode,
                "style_dim": style_dim,
                "film_strength": runtime_config.film_strength,
                "film_target": runtime_config.film_target,
                "injection_target": runtime_config.film_target,
                "style_emb_format": runtime_config.style_emb_format,
                "style_prompt": style_prompt,
                "style_emb_path": style_emb_path or None,
                "executed_internal_film": False,
                "called_conditioned_inference": False,
            }
            if isinstance(runtime_context, dict):
                runtime_context["result_metadata"] = mock_result
                runtime_context["runtime_config"] = {**runtime_config.to_public_dict(), **mock_result}
            debug_payload = {
                "mode": "mock",
                "input_vocals_path": input_vocals_path,
                "output_path": output_path,
                "prompt_text": prompt_text,
                "style_prompt": style_prompt,
                "style_strength": style_strength,
                "style_emb_path": style_emb_path or None,
                "style_preset": style_preset,
                "runtime_config": runtime_config.to_public_dict(),
            }
            self._write_debug_json(debug_dir, "sovits_debug.json", debug_payload)
            self._write_debug_text(
                debug_dir,
                "sovits_command.txt",
                json.dumps(
                    {
                        "mode": "mock",
                        "python_bin": runtime_config.python_bin,
                        "sys.executable": sys.executable,
                        "command": ["cp", input_vocals_path, output_path],
                        "cwd": runtime_config.repo_dir,
                        "SOVITS_DEVICE": runtime_config.device,
                        "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
                        "conversion_params": runtime_config.to_public_dict(),
                        "conditioning": {
                            "condition_mode": runtime_config.condition_mode,
                            "style_prompt": style_prompt,
                            "style_emb_path": style_emb_path or None,
                            "style_dim": style_dim,
                            "film_strength": runtime_config.film_strength,
                            "film_target": runtime_config.film_target,
                            "injection_target": runtime_config.film_target,
                            "style_emb_format": runtime_config.style_emb_format,
                        },
                        "env": self._env_snapshot(runtime_config),
                        "stdout": "",
                        "stderr": "",
                        "return_code": 0,
                        "elapsed_seconds": 0.0,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            return output_path

        return self._run_real_inference(
            runtime_config=runtime_config,
            input_vocals_path=input_vocals_path,
            prompt_text=prompt_text,
            style_strength=style_strength,
            output_path=output_path,
            debug_dir=debug_dir,
            style_preset=style_preset,
            task_id=task_id,
            runtime_context=runtime_context,
            style_prompt=style_prompt,
            style_emb_path=style_emb_path,
            style_dim=style_dim,
        )

    def resolve_runtime_config(
        self,
        style_preset: dict[str, Any] | None = None,
        conversion_params: dict[str, Any] | None = None,
        allow_preset_fallback: bool = False,
        allow_unconfigured_preset_smoke: bool = False,
    ) -> SoVitsRuntimeConfig:
        preset = style_preset or {}
        presets_disabled = _env_flag("SVC_DISABLE_MODEL_PRESETS", False)
        preset_id = str(preset.get("model_preset_id") or os.environ.get("SVC_MODEL_PRESET_ID", "") or "").strip() or None
        requested_preset_id = preset_id or ""
        preset_fallback_used = False
        preset_fallback_reason = ""
        model_preset = None if presets_disabled else svc_model_presets.resolve_preset(preset_id)
        if model_preset is not None and not model_preset.readiness().get("ready") and allow_preset_fallback:
            fallback_preset = self._resolve_demo_fallback_preset(requested_preset_id)
            if fallback_preset is not None:
                preset_fallback_used = True
                preset_fallback_reason = (
                    f"当前提示词匹配专用风格 preset，但该 preset 尚未绑定可用 SVC 模型；"
                    f"本次已回退到 {fallback_preset.preset_id}/{fallback_preset.speaker}，结果不代表该专用风格真实效果。"
                )
                model_preset = fallback_preset
        model_metadata = model_preset.to_runtime_dict() if model_preset else {}
        model_status = model_preset.readiness() if model_preset else {}
        conversion_config = load_conversion_params_config()
        resolved_conversion = self._resolve_conversion_params(conversion_config, preset, conversion_params)
        repo_dir = os.environ.get("SOVITS_REPO_DIR", self.repo_dir)
        base_infer_script = os.environ.get("SOVITS_INFER_SCRIPT", self.infer_script)
        model_path = str(
            (None if preset_fallback_used else preset.get("model_path"))
            or model_metadata.get("model_path")
            or os.environ.get("SOVITS_MODEL_PATH", self.model_path)
        )
        config_path = str(
            (None if preset_fallback_used else preset.get("config_path"))
            or model_metadata.get("config_path")
            or os.environ.get("SOVITS_CONFIG_PATH", self.config_path)
        )
        speaker = str(
            (None if preset_fallback_used else preset.get("speaker"))
            or model_metadata.get("speaker")
            or os.environ.get("SOVITS_SPEAKER", self.speaker)
        )
        device = str(
            (None if preset_fallback_used else preset.get("device"))
            or model_metadata.get("device")
            or os.environ.get("SOVITS_DEVICE", self.device)
        )
        transpose = int(
            preset.get(
                "transpose",
                resolved_conversion.get("transpose", model_metadata.get("transpose", os.environ.get("SOVITS_TRANSPOSE", self.transpose))),
            )
        )
        timeout_seconds = int(os.environ.get("SOVITS_TIMEOUT_SECONDS", str(self.timeout_seconds)))
        mock_enabled = _env_flag("SOVITS_MOCK", self.mock_enabled)
        condition_mode = _normalize_condition_mode(os.environ.get("SOVITS_CONDITION_MODE", self.condition_mode))
        python_bin = os.environ.get("SOVITS_PYTHON") or self.python_bin
        style_dim = int(os.environ.get("SOVITS_STYLE_DIM", str(self.style_dim)))
        film_strength = float(os.environ.get("SOVITS_FILM_STRENGTH", str(self.film_strength)))
        film_target = str(os.environ.get("SOVITS_FILM_TARGET", self.film_target) or self.film_target)
        style_emb_format = str(os.environ.get("SOVITS_STYLE_EMB_FORMAT", self.style_emb_format) or self.style_emb_format)
        conditioned_infer_script = os.environ.get("SOVITS_CONDITIONED_INFER_SCRIPT", self.conditioned_infer_script)
        called_conditioned_inference = condition_mode == "internal_film" and not mock_enabled
        infer_script = conditioned_infer_script if called_conditioned_inference else base_infer_script
        model_path_basename = str(model_metadata.get("model_path_basename") or Path(model_path).name)
        config_path_basename = str(model_metadata.get("config_path_basename") or Path(config_path).name)
        bypass_configured_gate = bool(allow_unconfigured_preset_smoke and model_preset is not None and not model_status.get("ready"))
        validation_mode = "unconfigured_preset_smoke" if bypass_configured_gate else ""
        return SoVitsRuntimeConfig(
            repo_dir=repo_dir,
            infer_script=infer_script,
            base_infer_script=base_infer_script,
            model_path=model_path,
            config_path=config_path,
            speaker=speaker,
            device=device,
            transpose=transpose,
            timeout_seconds=timeout_seconds,
            mock_enabled=mock_enabled,
            python_bin=python_bin,
            f0_method=str(resolved_conversion.get("f0_method") or "system_default"),
            f0_fallback_reason=str(resolved_conversion.get("f0_fallback_reason") or ""),
            auto_predict_f0=bool(resolved_conversion.get("auto_predict_f0", False)),
            slice_db=float(resolved_conversion.get("slice_db", -40.0)),
            clip_seconds=float(resolved_conversion.get("clip_seconds", 0.0)),
            pad_seconds=float(resolved_conversion.get("pad_seconds", 0.5)),
            conversion_params_requested=dict(conversion_params or {}),
            cli_passthrough=dict(conversion_config.get("cli_passthrough") or {}),
            cli_passthrough_notes=str(conversion_config.get("notes", {}).get("unsupported_passthrough") or ""),
            model_preset_id=str(model_metadata.get("model_preset_id") or preset.get("model_preset_id") or ""),
            requested_model_preset_id=requested_preset_id or str(preset.get("model_preset_id") or model_metadata.get("model_preset_id") or ""),
            effective_model_preset_id=str(model_metadata.get("model_preset_id") or preset.get("model_preset_id") or ""),
            preset_fallback_used=preset_fallback_used,
            preset_fallback_reason=preset_fallback_reason,
            model_display_name=str(model_metadata.get("model_display_name") or preset.get("model_display_name") or ""),
            source_repo=str(model_metadata.get("source_repo") or preset.get("source_repo") or ""),
            source_url=str(model_metadata.get("source_url") or preset.get("source_url") or ""),
            license=str(model_metadata.get("license") or preset.get("license") or ""),
            install_report_path=str(model_metadata.get("install_report_path") or preset.get("install_report_path") or ""),
            notes=str(model_metadata.get("notes") or preset.get("notes") or ""),
            model_path_basename=model_path_basename,
            config_path_basename=config_path_basename,
            model_preset_ready=bool(model_status.get("ready", False) or bypass_configured_gate),
            model_preset_configured=bool(model_status.get("is_configured", False)),
            is_demo_quality=bool(model_metadata.get("is_demo_quality", preset.get("is_demo_quality", False))),
            smoke_test_passed=bool(model_metadata.get("smoke_test_passed", preset.get("smoke_test_passed", False))),
            is_technical_validation_only=bool(
                model_metadata.get("is_technical_validation_only", preset.get("is_technical_validation_only", False))
            ),
            validation_mode=validation_mode,
            bypass_configured_gate=bypass_configured_gate,
            condition_mode=condition_mode,
            style_dim=style_dim,
            film_strength=film_strength,
            film_target=film_target,
            style_emb_format=style_emb_format,
            called_conditioned_inference=called_conditioned_inference,
        )

    def _resolve_demo_fallback_preset(self, requested_preset_id: str | None = None) -> svc_model_presets.SvcModelPreset | None:
        presets = svc_model_presets.load_presets()
        requested = str(requested_preset_id or "")
        final_primary = presets.get("final_primary")
        if final_primary is not None and final_primary.readiness().get("ready") and requested != "final_primary":
            return final_primary
        fallback = presets.get(svc_model_presets.fallback_preset_id())
        if fallback is not None and fallback.readiness().get("ready") and fallback.preset_id != "tech_villager":
            return fallback
        if final_primary is not None and final_primary.readiness().get("ready"):
            return final_primary
        return None

    def _resolve_conversion_params(
        self,
        conversion_config: dict[str, Any],
        style_preset: dict[str, Any],
        requested_params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        defaults = dict(conversion_config.get("defaults") or {})
        requested = dict(requested_params or {})
        requested_f0_method = str(requested.get("f0_method") or defaults.get("f0_method") or "system_default").strip() or "system_default"
        resolved_f0_method = requested_f0_method
        fallback_reason = ""
        if requested_f0_method == "rmvpe" and not self._rmvpe_supported():
            resolved_f0_method = str(defaults.get("fallback_f0_method") or "system_default")
            fallback_reason = "RMVPE_UNAVAILABLE"

        return {
            "f0_method_requested": requested_f0_method,
            "f0_method": resolved_f0_method,
            "f0_fallback_reason": fallback_reason,
            "auto_predict_f0": bool(requested.get("auto_predict_f0", defaults.get("auto_predict_f0", False))),
            "transpose": int(style_preset.get("transpose", requested.get("transpose", defaults.get("transpose", 0))) or 0),
            "slice_db": float(requested.get("slice_db", defaults.get("slice_db", -40.0)) or -40.0),
            "clip_seconds": float(requested.get("clip_seconds", defaults.get("clip_seconds", 0.0)) or 0.0),
            "pad_seconds": float(requested.get("pad_seconds", defaults.get("pad_seconds", 0.5)) or 0.5),
        }

    def _rmvpe_supported(self) -> bool:
        if importlib.util.find_spec("rmvpe") is None:
            return False
        ensure_repo_runtime_assets(self.repo_dir)
        candidate_paths = [
            os.environ.get("SOVITS_RMVPE_MODEL_PATH", "").strip(),
            os.environ.get("RMVPE_MODEL_PATH", "").strip(),
            str(APP_DIR / "models" / "rmvpe" / "rmvpe.pt"),
            str(Path(self.repo_dir) / "pretrain" / "rmvpe.pt"),
            str(Path(self.repo_dir) / "rmvpe.pt"),
            str(APP_DIR.parents[1] / "rmvpe.pt"),
        ]
        return any(path and Path(path).exists() for path in candidate_paths)

    def _run_real_inference(
        self,
        runtime_config: SoVitsRuntimeConfig,
        input_vocals_path: str,
        prompt_text: str,
        style_strength: float,
        output_path: str,
        debug_dir: str | None,
        style_preset: dict[str, Any],
        task_id: str | None,
        runtime_context: dict[str, Any] | None,
        style_prompt: str,
        style_emb_path: str,
        style_dim: int,
    ) -> str:
        self._validate_runtime(runtime_config, input_vocals_path, output_path)
        if runtime_config.condition_mode == "internal_film" and not style_emb_path:
            raise SoVitsSvcError(
                "SOVITS_STYLE_EMB_NOT_FOUND",
                "Internal FiLM mode requires a saved style embedding path",
                {
                    "condition_mode": runtime_config.condition_mode,
                    "style_emb_path": style_emb_path,
                },
            )
        raw_dir, results_dir, copied_input_path, clean_name, prepared_audio_info, audio_prepare_method = self._prepare_repo_io(
            runtime_config=runtime_config,
            input_vocals_path=input_vocals_path,
            task_id=task_id,
        )
        if debug_dir:
            os.makedirs(debug_dir, exist_ok=True)
        start_timestamp = time.time()
        existing_outputs = self._result_files(results_dir)
        conditioning_report_path = os.path.join(debug_dir, "conditioning_report.json") if debug_dir else ""
        command = self._build_command(
            runtime_config,
            clean_name,
            style_emb_path=style_emb_path,
            conditioning_report_path=conditioning_report_path,
        )
        start_time = time.monotonic()
        gpu_telemetry_debug_path = os.path.join(debug_dir, "gpu_telemetry.txt") if debug_dir else None
        command_log = {
            "mode": "real",
            "python_bin": runtime_config.python_bin,
            "sys.executable": sys.executable,
            "model_path": runtime_config.model_path,
            "config_path": runtime_config.config_path,
            "speaker": runtime_config.speaker,
            "model_preset_id": runtime_config.model_preset_id,
            "requested_model_preset_id": runtime_config.requested_model_preset_id,
            "validation_mode": runtime_config.validation_mode or None,
            "bypass_configured_gate": runtime_config.bypass_configured_gate,
            "original_input_path": input_vocals_path,
            "original_input_size": prepared_audio_info["original_input_size"],
            "copied_input_path": copied_input_path,
            "prepared_input_path": copied_input_path,
            "prepared_audio_info": prepared_audio_info,
            "audio_prepare_method": audio_prepare_method,
            "clean_name": f"{clean_name}.wav",
            "raw_dir": raw_dir,
            "results_dir": results_dir,
            "command": command,
            "cwd": runtime_config.repo_dir,
            "SOVITS_DEVICE": runtime_config.device,
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
            "command_includes_d_cuda": self._command_includes_d_cuda(command),
            "conversion_params": {
                "f0_method": runtime_config.f0_method,
                "f0_fallback_reason": runtime_config.f0_fallback_reason,
                "auto_predict_f0": runtime_config.auto_predict_f0,
                "transpose": runtime_config.transpose,
                "slice_db": runtime_config.slice_db,
                "clip_seconds": runtime_config.clip_seconds,
                "pad_seconds": runtime_config.pad_seconds,
                "cli_passthrough": runtime_config.cli_passthrough or {},
                "cli_passthrough_notes": runtime_config.cli_passthrough_notes,
            },
            "env": self._env_snapshot(runtime_config),
            "prompt_text": prompt_text,
            "style_prompt": style_prompt,
            "style_strength": style_strength,
            "condition_mode": runtime_config.condition_mode,
            "style_emb_path": style_emb_path or None,
            "style_dim": style_dim,
            "film_strength": runtime_config.film_strength,
            "film_target": runtime_config.film_target,
            "injection_target": runtime_config.film_target,
            "style_emb_format": runtime_config.style_emb_format,
            "conditioning_report_path": conditioning_report_path or None,
            "style_preset": style_preset,
            "stdout": "",
            "stderr": "",
            "return_code": None,
            "elapsed_seconds": None,
            "discovered_outputs": [],
            "selected_output": None,
            "final_output_path": output_path,
            "gpu_telemetry_debug_path": gpu_telemetry_debug_path,
        }
        gpu_telemetry_entries = [self._capture_gpu_telemetry("before_inference", runtime_config)]

        try:
            try:
                result = subprocess.run(
                    command,
                    cwd=runtime_config.repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=runtime_config.timeout_seconds,
                    env=self._build_subprocess_env(runtime_config),
                )
            finally:
                gpu_telemetry_entries.append(self._capture_gpu_telemetry("after_inference", runtime_config))
                self._write_gpu_telemetry(
                    debug_dir=debug_dir,
                    runtime_config=runtime_config,
                    command=command,
                    task_id=task_id,
                    entries=gpu_telemetry_entries,
                )
            command_log["stdout"] = result.stdout or ""
            command_log["stderr"] = result.stderr or ""
            command_log["return_code"] = result.returncode
            command_log["elapsed_seconds"] = round(time.monotonic() - start_time, 3)
            if result.returncode != 0:
                self._write_debug_text(debug_dir, "sovits_command.txt", json.dumps(command_log, ensure_ascii=False, indent=2))
                self._write_debug_json(
                    debug_dir,
                    "sovits_debug.json",
                    {
                        "mode": "real",
                        "runtime_config": runtime_config.to_public_dict(),
                        "style_preset": style_preset,
                        "return_code": result.returncode,
                        "stdout": result.stdout or "",
                        "stderr": result.stderr or "",
                        "elapsed_seconds": command_log["elapsed_seconds"],
                        "validation_mode": runtime_config.validation_mode or None,
                        "bypass_configured_gate": runtime_config.bypass_configured_gate,
                    },
                )
                error = SoVitsSvcError(
                    "SOVITS_INFERENCE_FAILED",
                    "So-VITS-SVC inference process failed",
                    {
                        "return_code": result.returncode,
                        "stdout": result.stdout or "",
                        "stderr": result.stderr or "",
                        "command": command,
                    },
                )
                self._write_debug_json(debug_dir, "error.json", error.to_dict())
                raise error
        except subprocess.TimeoutExpired as exc:
            command_log["stdout"] = exc.stdout or ""
            command_log["stderr"] = exc.stderr or ""
            command_log["return_code"] = -1
            command_log["elapsed_seconds"] = round(time.monotonic() - start_time, 3)
            self._write_debug_text(debug_dir, "sovits_command.txt", json.dumps(command_log, ensure_ascii=False, indent=2))
            error = SoVitsSvcError(
                "SOVITS_INFERENCE_FAILED",
                f"So-VITS-SVC inference timed out after {runtime_config.timeout_seconds}s",
                {
                    "stdout": exc.stdout or "",
                    "stderr": exc.stderr or "",
                    "command": command,
                },
            )
            self._write_debug_json(debug_dir, "error.json", error.to_dict())
            raise error from exc

        discovered_outputs = self._discover_new_outputs(results_dir, existing_outputs, since_timestamp=start_timestamp)
        command_log["discovered_outputs"] = discovered_outputs
        selected_output = discovered_outputs[-1] if discovered_outputs else None
        command_log["selected_output"] = selected_output

        if not selected_output:
            self._write_debug_text(debug_dir, "sovits_command.txt", json.dumps(command_log, ensure_ascii=False, indent=2))
            error = SoVitsSvcError(
                "SOVITS_OUTPUT_NOT_FOUND",
                "So-VITS-SVC finished without creating a new output file in results/",
                {
                    "results_dir": results_dir,
                    "output_path": output_path,
                    "discovered_outputs": discovered_outputs,
                    "command": command,
                },
            )
            self._write_debug_json(debug_dir, "error.json", error.to_dict())
            raise error

        self._finalize_output_wav(selected_output, output_path)
        command_log["final_output_path"] = output_path
        conditioning_report = self._load_conditioning_report(conditioning_report_path)
        executed_internal_film = bool(
            conditioning_report.get("executed_internal_film")
            if isinstance(conditioning_report, dict)
            else runtime_config.condition_mode == "internal_film"
        )
        result_metadata = {
            "inference_mode": "real",
            "mock_enabled": False,
            "model_path": runtime_config.model_path,
            "config_path": runtime_config.config_path,
            "speaker": runtime_config.speaker,
            "device": runtime_config.device,
            "transpose": runtime_config.transpose,
            "model_preset_id": runtime_config.model_preset_id,
            "model_display_name": runtime_config.model_display_name,
            "source_repo": runtime_config.source_repo,
            "source_url": runtime_config.source_url,
            "license": runtime_config.license,
            "install_report_path": runtime_config.install_report_path,
            "notes": runtime_config.notes,
            "model_path_basename": runtime_config.model_path_basename or Path(runtime_config.model_path).name,
            "config_path_basename": runtime_config.config_path_basename or Path(runtime_config.config_path).name,
            "is_demo_quality": runtime_config.is_demo_quality,
            "is_technical_validation_only": runtime_config.is_technical_validation_only,
            "selected_output": selected_output,
            "final_output_path": output_path,
            "return_code": result.returncode,
            "elapsed_seconds": command_log["elapsed_seconds"],
            "sovits_command_debug_path": os.path.join(debug_dir, "sovits_command.txt") if debug_dir else None,
            "gpu_telemetry_debug_path": gpu_telemetry_debug_path,
            "called_inference_main": not runtime_config.called_conditioned_inference,
            "called_conditioned_inference": runtime_config.called_conditioned_inference,
            "validation_mode": runtime_config.validation_mode or None,
            "bypass_configured_gate": runtime_config.bypass_configured_gate,
            "requested_model_preset_id": runtime_config.requested_model_preset_id,
            "condition_mode": runtime_config.condition_mode,
            "style_prompt": style_prompt,
            "style_emb_path": style_emb_path or None,
            "style_dim": style_dim,
            "film_strength": runtime_config.film_strength,
            "film_target": runtime_config.film_target,
            "injection_target": runtime_config.film_target,
            "style_emb_format": runtime_config.style_emb_format,
            "executed_internal_film": executed_internal_film,
            "conditioning_report_path": conditioning_report_path or None,
        }
        if isinstance(runtime_context, dict):
            runtime_context["result_metadata"] = result_metadata
            runtime_context["runtime_config"] = {**runtime_config.to_public_dict(), **result_metadata}
        self._write_debug_text(debug_dir, "sovits_command.txt", json.dumps(command_log, ensure_ascii=False, indent=2))
        self._write_debug_json(
            debug_dir,
            "sovits_debug.json",
            {
                "mode": "real",
                "runtime_config": runtime_config.to_public_dict(),
                "style_preset": style_preset,
                "return_code": result.returncode,
                "stdout": result.stdout or "",
                "stderr": result.stderr or "",
                "elapsed_seconds": command_log["elapsed_seconds"],
                "original_input_path": input_vocals_path,
                "original_input_size": prepared_audio_info["original_input_size"],
                "copied_input_path": copied_input_path,
                "prepared_input_path": copied_input_path,
                "prepared_audio_info": prepared_audio_info,
                "audio_prepare_method": audio_prepare_method,
                "clean_name": f"{clean_name}.wav",
                "discovered_outputs": discovered_outputs,
                "selected_output": selected_output,
                "final_output_path": output_path,
                "result_metadata": result_metadata,
                "conditioning_report": conditioning_report,
                "validation_mode": runtime_config.validation_mode or None,
                "bypass_configured_gate": runtime_config.bypass_configured_gate,
            },
        )
        return output_path

    def _validate_runtime(self, runtime_config: SoVitsRuntimeConfig, input_vocals_path: str, output_path: str) -> None:
        output_dir = os.path.dirname(output_path)
        if runtime_config.model_preset_id and not runtime_config.model_preset_ready:
            raise SoVitsSvcError(
                "SVC_MODEL_PRESET_NOT_CONFIGURED",
                "Selected SVC model preset is not configured for inference",
                {
                    "model_preset_id": runtime_config.model_preset_id,
                    "model_display_name": runtime_config.model_display_name,
                    "model_preset_configured": runtime_config.model_preset_configured,
                    "model_path": runtime_config.model_path,
                    "config_path": runtime_config.config_path,
                    "speaker": runtime_config.speaker,
                },
            )
        if not os.path.isdir(runtime_config.repo_dir):
            raise SoVitsSvcError(
                "SOVITS_REPO_NOT_FOUND",
                f"So-VITS-SVC repo directory not found: {runtime_config.repo_dir}",
                {"repo_dir": runtime_config.repo_dir},
            )
        if not os.path.exists(runtime_config.infer_script):
            raise SoVitsSvcError(
                "SOVITS_SCRIPT_NOT_FOUND",
                f"So-VITS-SVC inference script not found: {runtime_config.infer_script}",
                {"infer_script": runtime_config.infer_script},
            )
        if not runtime_config.model_path or not os.path.exists(runtime_config.model_path):
            raise SoVitsSvcError(
                "SOVITS_MODEL_NOT_FOUND",
                f"So-VITS-SVC model not found: {runtime_config.model_path}",
                {"model_path": runtime_config.model_path},
            )
        if not runtime_config.config_path or not os.path.exists(runtime_config.config_path):
            raise SoVitsSvcError(
                "SOVITS_CONFIG_NOT_FOUND",
                f"So-VITS-SVC config not found: {runtime_config.config_path}",
                {"config_path": runtime_config.config_path},
            )
        if not input_vocals_path or not os.path.exists(input_vocals_path):
            raise SoVitsSvcError(
                "SOVITS_INPUT_NOT_FOUND",
                f"Input vocals file not found: {input_vocals_path}",
                {"input_vocals_path": input_vocals_path},
            )
        if not runtime_config.speaker.strip():
            raise SoVitsSvcError(
                "SOVITS_INFERENCE_FAILED",
                "So-VITS-SVC speaker is required",
                {"speaker": runtime_config.speaker},
            )
        ensure_repo_runtime_assets(runtime_config.repo_dir)
        asset_report = inspect_sovits_assets(
            repo_dir=runtime_config.repo_dir,
            infer_script=runtime_config.infer_script,
            model_path=runtime_config.model_path,
            config_path=runtime_config.config_path,
            speaker=runtime_config.speaker,
            f0_method=runtime_config.f0_method,
        )
        validation_errors = asset_report.get("validation_errors", [])
        if validation_errors:
            first_error = validation_errors[0]
            raise SoVitsSvcError(
                str(first_error.get("code", "SOVITS_INFERENCE_FAILED")),
                str(first_error.get("message", "So-VITS-SVC runtime validation failed")),
                dict(first_error.get("details") or {}),
            )
        if not output_dir:
            raise SoVitsSvcError(
                "SOVITS_INFERENCE_FAILED",
                "Output directory is empty",
                {"output_path": output_path},
            )
        os.makedirs(output_dir, exist_ok=True)
        if not os.access(output_dir, os.W_OK):
            raise SoVitsSvcError(
                "SOVITS_INFERENCE_FAILED",
                f"Output directory is not writable: {output_dir}",
                {"output_dir": output_dir},
            )

    def _build_command(
        self,
        runtime_config: SoVitsRuntimeConfig,
        clean_name: str,
        style_emb_path: str = "",
        conditioning_report_path: str = "",
    ) -> list[str]:
        command = [
            runtime_config.python_bin,
            runtime_config.infer_script,
            "-m",
            runtime_config.model_path,
            "-c",
            runtime_config.config_path,
            "-n",
            f"{clean_name}.wav",
            "-t",
            str(runtime_config.transpose),
            "-s",
            runtime_config.speaker,
            "-d",
            runtime_config.device,
        ]
        if runtime_config.condition_mode == "internal_film":
            command.extend(
                [
                    "--style-emb-path",
                    style_emb_path,
                    "--style-emb-format",
                    runtime_config.style_emb_format,
                    "--condition-mode",
                    runtime_config.condition_mode,
                    "--film-strength",
                    str(runtime_config.film_strength),
                    "--film-target",
                    runtime_config.film_target,
                ]
            )
            if conditioning_report_path:
                command.extend(["--conditioning-report-path", conditioning_report_path])
        return command

    def _safe_clean_name(self, input_vocals_path: str, task_id: str | None = None) -> str:
        base = task_id or Path(input_vocals_path).stem or "sovits_input"
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._-")
        return safe or "sovits_input"

    def _prepare_repo_io(
        self,
        runtime_config: SoVitsRuntimeConfig,
        input_vocals_path: str,
        task_id: str | None = None,
    ) -> tuple[str, str, str, str, dict[str, Any], str]:
        prepared_audio_info = self._inspect_input_audio(input_vocals_path)
        raw_dir = os.path.join(runtime_config.repo_dir, "raw")
        results_dir = os.path.join(runtime_config.repo_dir, "results")
        os.makedirs(raw_dir, exist_ok=True)
        os.makedirs(results_dir, exist_ok=True)
        clean_name = self._safe_clean_name(input_vocals_path, task_id=task_id)
        copied_input_path = os.path.join(raw_dir, f"{clean_name}.wav")
        try:
            audio_data, sample_rate = sf.read(input_vocals_path, always_2d=False)
            sf.write(copied_input_path, audio_data, sample_rate, format="WAV")
        except Exception as exc:
            raise SoVitsSvcError(
                "SOVITS_INPUT_AUDIO_INVALID",
                "Input audio file could not be prepared as raw/<clean_name>.wav",
                {
                    "input_vocals_path": input_vocals_path,
                    "prepared_input_path": copied_input_path,
                    "reason": str(exc),
                },
            ) from exc
        return raw_dir, results_dir, copied_input_path, clean_name, prepared_audio_info, "soundfile_reencode_wav"

    def _inspect_input_audio(self, input_vocals_path: str) -> dict[str, Any]:
        if not input_vocals_path or not os.path.exists(input_vocals_path):
            raise SoVitsSvcError(
                "SOVITS_INPUT_NOT_FOUND",
                f"Input vocals file not found: {input_vocals_path}",
                {"input_vocals_path": input_vocals_path},
            )

        original_input_size = int(os.path.getsize(input_vocals_path))
        if original_input_size <= 1024:
            raise SoVitsSvcError(
                "SOVITS_INPUT_AUDIO_INVALID",
                "Input audio file is too small to be a valid So-VITS inference input",
                {
                    "input_vocals_path": input_vocals_path,
                    "original_input_size": original_input_size,
                },
            )

        try:
            info = sf.info(input_vocals_path)
        except Exception as exc:
            raise SoVitsSvcError(
                "SOVITS_INPUT_AUDIO_INVALID",
                "Input audio file cannot be parsed by soundfile",
                {
                    "input_vocals_path": input_vocals_path,
                    "original_input_size": original_input_size,
                    "reason": str(exc),
                },
            ) from exc

        duration_seconds = float(info.frames) / float(info.samplerate) if info.samplerate else 0.0
        if duration_seconds < 0.5:
            raise SoVitsSvcError(
                "SOVITS_INPUT_AUDIO_INVALID",
                "Input audio duration is too short for So-VITS inference",
                {
                    "input_vocals_path": input_vocals_path,
                    "original_input_size": original_input_size,
                    "duration_seconds": round(duration_seconds, 3),
                    "samplerate": info.samplerate,
                    "frames": info.frames,
                },
            )

        return {
            "original_input_path": input_vocals_path,
            "original_input_size": original_input_size,
            "samplerate": info.samplerate,
            "frames": info.frames,
            "channels": info.channels,
            "duration_seconds": round(duration_seconds, 3),
            "format": info.format,
            "subtype": info.subtype,
        }

    def _result_files(self, results_dir: str) -> set[str]:
        result_files: set[str] = set()
        if not os.path.isdir(results_dir):
            return result_files
        for entry in os.scandir(results_dir):
            if entry.is_file() and Path(entry.name).suffix.lower() in RESULT_AUDIO_EXTENSIONS:
                result_files.add(os.path.abspath(entry.path))
        return result_files

    def _discover_new_outputs(
        self,
        results_dir: str,
        existing_outputs: set[str],
        since_timestamp: float | None = None,
    ) -> list[str]:
        current_outputs = self._result_files(results_dir)
        new_outputs = []
        for path in current_outputs:
            if path not in existing_outputs:
                new_outputs.append(path)
                continue
            if since_timestamp is not None:
                try:
                    if os.path.getmtime(path) >= since_timestamp - 0.5:
                        new_outputs.append(path)
                except OSError:
                    continue
        new_outputs.sort(key=lambda path: (os.path.getmtime(path), path))
        return new_outputs

    def _finalize_output_wav(self, selected_output: str, output_path: str) -> None:
        try:
            audio_data, sample_rate = sf.read(selected_output, always_2d=False)
            sf.write(output_path, audio_data, sample_rate, format="WAV", subtype="PCM_16")
            output_info = sf.info(output_path)
        except Exception as exc:
            raise SoVitsSvcError(
                "SOVITS_OUTPUT_NOT_FOUND",
                "So-VITS-SVC output was generated but could not be transcoded into PCM_16 WAV",
                {
                    "selected_output": selected_output,
                    "final_output_path": output_path,
                    "reason": str(exc),
                },
            ) from exc

        if str(output_info.format).upper() != "WAV":
            raise SoVitsSvcError(
                "SOVITS_OUTPUT_NOT_FOUND",
                "Final So-VITS-SVC output is not a valid WAV container",
                {
                    "selected_output": selected_output,
                    "final_output_path": output_path,
                    "detected_format": output_info.format,
                },
            )

    def _load_conditioning_report(self, report_path: str) -> dict[str, Any]:
        if not report_path or not os.path.exists(report_path):
            return {}
        try:
            payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _env_snapshot(self, runtime_config: SoVitsRuntimeConfig) -> dict[str, Any]:
        return {
            "SOVITS_REPO_DIR": runtime_config.repo_dir,
            "SOVITS_INFER_SCRIPT": runtime_config.infer_script,
            "SOVITS_BASE_INFER_SCRIPT": runtime_config.base_infer_script,
            "SOVITS_MODEL_PATH": runtime_config.model_path,
            "SOVITS_CONFIG_PATH": runtime_config.config_path,
            "SOVITS_SPEAKER": runtime_config.speaker,
            "SOVITS_DEVICE": runtime_config.device,
            "SOVITS_TRANSPOSE": runtime_config.transpose,
            "SOVITS_TIMEOUT_SECONDS": runtime_config.timeout_seconds,
            "SOVITS_MOCK": runtime_config.mock_enabled,
            "SOVITS_PYTHON": runtime_config.python_bin,
            "SOVITS_VENDOR_PATH": self.vendor_path,
            "SOVITS_CONDITION_MODE": runtime_config.condition_mode,
            "SOVITS_STYLE_DIM": runtime_config.style_dim,
            "SOVITS_FILM_STRENGTH": runtime_config.film_strength,
            "SOVITS_FILM_TARGET": runtime_config.film_target,
            "SOVITS_STYLE_EMB_FORMAT": runtime_config.style_emb_format,
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
        }

    def _command_includes_d_cuda(self, command: list[str]) -> bool:
        for index, token in enumerate(command[:-1]):
            if token == "-d" and command[index + 1] == "cuda":
                return True
        return False

    def _capture_gpu_telemetry(self, phase: str, runtime_config: SoVitsRuntimeConfig) -> dict[str, Any]:
        entries: list[dict[str, Any]] = []
        for label, command in (
            ("gpu_summary", GPU_QUERY_COMMAND),
            ("compute_apps", GPU_COMPUTE_APPS_COMMAND),
        ):
            try:
                result = subprocess.run(
                    command,
                    cwd=runtime_config.repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=min(runtime_config.timeout_seconds, 15),
                    env=self._build_subprocess_env(runtime_config),
                )
                entries.append(
                    {
                        "label": label,
                        "command": command,
                        "return_code": result.returncode,
                        "stdout": result.stdout or "",
                        "stderr": result.stderr or "",
                    }
                )
            except FileNotFoundError as exc:
                entries.append(
                    {
                        "label": label,
                        "command": command,
                        "return_code": None,
                        "stdout": "",
                        "stderr": str(exc),
                        "error": "nvidia-smi not found",
                    }
                )
            except subprocess.TimeoutExpired as exc:
                entries.append(
                    {
                        "label": label,
                        "command": command,
                        "return_code": -1,
                        "stdout": exc.stdout or "",
                        "stderr": exc.stderr or "",
                        "error": "nvidia-smi timed out",
                    }
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                entries.append(
                    {
                        "label": label,
                        "command": command,
                        "return_code": None,
                        "stdout": "",
                        "stderr": str(exc),
                        "error": exc.__class__.__name__,
                    }
                )
        return {
            "phase": phase,
            "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "entries": entries,
        }

    def _write_gpu_telemetry(
        self,
        debug_dir: str | None,
        runtime_config: SoVitsRuntimeConfig,
        command: list[str],
        task_id: str | None,
        entries: list[dict[str, Any]],
    ) -> None:
        if not debug_dir:
            return
        lines = [
            f"task_id={task_id or ''}",
            f"SOVITS_DEVICE={runtime_config.device}",
            f"CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES', '')}",
            f"command_includes_d_cuda={str(self._command_includes_d_cuda(command)).lower()}",
            "note=CPU-side audio preparation can occur before So-VITS-SVC CLI launch. Do not use the pre-run snapshot alone to conclude GPU inference was skipped.",
        ]
        for phase_entry in entries:
            lines.append("")
            lines.append(f"[{phase_entry.get('phase', 'unknown')}]")
            lines.append(f"captured_at={phase_entry.get('captured_at', '')}")
            for query_entry in phase_entry.get("entries", []):
                lines.append(f"label={query_entry.get('label', '')}")
                lines.append(f"command={' '.join(query_entry.get('command', []))}")
                lines.append(f"return_code={query_entry.get('return_code')}")
                error_value = query_entry.get("error")
                if error_value:
                    lines.append(f"error={error_value}")
                lines.append("stdout:")
                stdout = str(query_entry.get("stdout", "")).rstrip()
                lines.append(stdout if stdout else "<empty>")
                lines.append("stderr:")
                stderr = str(query_entry.get("stderr", "")).rstrip()
                lines.append(stderr if stderr else "<empty>")
                lines.append("")
        self._write_debug_text(debug_dir, "gpu_telemetry.txt", "\n".join(lines).rstrip())

    def _build_subprocess_env(self, runtime_config: SoVitsRuntimeConfig) -> dict[str, str]:
        env = os.environ.copy()
        paths: list[str] = []
        if self.vendor_path:
            paths.append(self.vendor_path)
        existing = env.get("PYTHONPATH", "")
        if existing:
            paths.append(existing)
        if paths:
            env["PYTHONPATH"] = os.pathsep.join(paths)
        return env

    def _write_debug_json(self, debug_dir: str | None, filename: str, payload: Any) -> None:
        if not debug_dir:
            return
        os.makedirs(debug_dir, exist_ok=True)
        with open(os.path.join(debug_dir, filename), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def _write_debug_text(self, debug_dir: str | None, filename: str, text: str) -> None:
        if not debug_dir:
            return
        os.makedirs(debug_dir, exist_ok=True)
        with open(os.path.join(debug_dir, filename), "w", encoding="utf-8") as handle:
            handle.write(text.rstrip() + "\n")
