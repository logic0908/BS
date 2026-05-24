from __future__ import annotations

import glob
import importlib
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models_svc.model_readiness import collect_model_readiness
from app.models_svc.sovits_assets import inspect_sovits_assets
from app.models_svc.sovits_wrapper import SoVitsSvcEngine
from app.services.svc_model_presets import collect_presets_status
from app.services.svc_task_service import svc_task_service

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
IMPORT_TARGETS = [
    "numpy",
    "scipy",
    "librosa",
    "numba",
    "resampy",
    "faiss",
    "fairseq",
    "pyworld",
    "parselmouth",
    "torchcrepe",
]


def _iso_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_command(command: list[str], timeout: int = 10) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception as exc:
        return {
            "available": False,
            "return_code": None,
            "stdout": "",
            "stderr": str(exc),
        }

    return {
        "available": result.returncode == 0,
        "return_code": result.returncode,
        "stdout": result.stdout or "",
        "stderr": result.stderr or "",
    }


def _check_torch() -> dict[str, Any]:
    try:
        import torch
    except Exception as exc:
        return {
            "torch_importable": False,
            "torch_version": None,
            "torch_cuda_available": False,
            "torch_cuda_version": None,
            "torch_device_count": 0,
            "reason": str(exc),
        }

    return {
        "torch_importable": True,
        "torch_version": torch.__version__,
        "torch_cuda_available": bool(torch.cuda.is_available()),
        "torch_cuda_version": torch.version.cuda,
        "torch_device_count": int(torch.cuda.device_count()),
    }


def _check_imports() -> dict[str, dict[str, Any]]:
    statuses: dict[str, dict[str, Any]] = {}
    for module_name in IMPORT_TARGETS:
        try:
            module = importlib.import_module(module_name)
            statuses[module_name] = {
                "ok": True,
                "version": getattr(module, "__version__", None),
                "path": getattr(module, "__file__", None),
            }
        except Exception as exc:
            statuses[module_name] = {
                "ok": False,
                "error": repr(exc),
            }
    return statuses


def _frontend_build_info() -> dict[str, Any] | None:
    if not FRONTEND_DIST_DIR.exists():
        return None
    index_path = FRONTEND_DIST_DIR / "index.html"
    return {
        "dist_exists": True,
        "index_exists": index_path.exists(),
        "dist_path": str(FRONTEND_DIST_DIR),
        "last_modified": datetime.fromtimestamp(
            FRONTEND_DIST_DIR.stat().st_mtime,
            tz=timezone.utc,
        ).isoformat(),
    }


def collect_app_health() -> dict[str, Any]:
    readiness = collect_model_readiness(require_real_assets=False, skip_real_checks_if_mock=True)
    runtime_config = readiness["runtime_config"]
    return {
        "ok": True,
        "app_status": "ok",
        "python_executable": sys.executable,
        "python_version": sys.version,
        "conda_env": os.environ.get("CONDA_DEFAULT_ENV", ""),
        "mock_mode": runtime_config["mock_enabled"],
        "task_backend_mode": "celery" if svc_task_service.use_celery() else "local",
        "svc_model_presets": collect_presets_status(),
        "sovits": readiness["sovits"],
        "text_conditioning": readiness["text_conditioning"],
        "frontend_build_info": _frontend_build_info(),
        "timestamp": _iso_timestamp(),
    }


def collect_sovits_check() -> dict[str, Any]:
    engine = SoVitsSvcEngine()
    runtime_config = engine.resolve_runtime_config({})
    asset_report = inspect_sovits_assets(
        repo_dir=runtime_config.repo_dir,
        infer_script=runtime_config.infer_script,
        model_path=runtime_config.model_path,
        config_path=runtime_config.config_path,
        speaker=runtime_config.speaker,
    )
    torch_info = _check_torch()
    nvidia_smi_path = shutil.which("nvidia-smi")
    nvidia_smi = _run_command(["nvidia-smi"]) if nvidia_smi_path else {
        "available": False,
        "return_code": None,
        "stdout": "",
        "stderr": "nvidia-smi not found in PATH",
    }

    readiness = collect_model_readiness(require_real_assets=False, skip_real_checks_if_mock=True)
    return {
        "SOVITS_MOCK": runtime_config.mock_enabled,
        "SOVITS_REPO_DIR": runtime_config.repo_dir,
        "SOVITS_REPO_DIR_exists": Path(runtime_config.repo_dir).exists(),
        "SOVITS_INFER_SCRIPT": runtime_config.infer_script,
        "SOVITS_INFER_SCRIPT_exists": Path(runtime_config.infer_script).exists(),
        "SOVITS_MODEL_PATH": runtime_config.model_path,
        "SOVITS_MODEL_PATH_exists": Path(runtime_config.model_path).exists() if runtime_config.model_path else False,
        "SOVITS_CONFIG_PATH": runtime_config.config_path,
        "SOVITS_CONFIG_PATH_exists": Path(runtime_config.config_path).exists() if runtime_config.config_path else False,
        "SOVITS_SPEAKER": runtime_config.speaker,
        "model_preset_id": runtime_config.model_preset_id,
        "model_display_name": runtime_config.model_display_name,
        "source_repo": runtime_config.source_repo,
        "source_url": runtime_config.source_url,
        "license": runtime_config.license,
        "internal_test_only": getattr(runtime_config, "internal_test_only", False),
        "temporary_demo_reason": getattr(runtime_config, "temporary_demo_reason", ""),
        "install_report_path": runtime_config.install_report_path,
        "notes": runtime_config.notes,
        "model_path_basename": runtime_config.model_path_basename,
        "config_path_basename": runtime_config.config_path_basename,
        "is_demo_quality": runtime_config.is_demo_quality,
        "is_technical_validation_only": runtime_config.is_technical_validation_only,
        "svc_model_presets": collect_presets_status(),
        "config_speakers": asset_report["config_summary"]["speakers"],
        "config_sampling_rate": asset_report["config_summary"]["sampling_rate"],
        "config_speech_encoder": asset_report["config_summary"]["speech_encoder"],
        "SOVITS_SPEAKER_exists_in_config": asset_report["speaker_exists_in_config"],
        "SOVITS_DEVICE": runtime_config.device,
        "f0_method": runtime_config.f0_method,
        "f0_fallback_reason": runtime_config.f0_fallback_reason,
        "auto_predict_f0": runtime_config.auto_predict_f0,
        "slice_db": runtime_config.slice_db,
        "clip_seconds": runtime_config.clip_seconds,
        "pad_seconds": runtime_config.pad_seconds,
        "SOVITS_PYTHON": runtime_config.python_bin,
        "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
        "contentvec_required": asset_report["contentvec_required"],
        "contentvec_candidate_paths": asset_report["contentvec_candidate_paths"],
        "contentvec_found_paths": asset_report["contentvec_found_paths"],
        "rmvpe_required": asset_report.get("rmvpe_required"),
        "rmvpe_candidate_paths": asset_report.get("rmvpe_candidate_paths"),
        "rmvpe_found_paths": asset_report.get("rmvpe_found_paths"),
        "validation_errors": asset_report["validation_errors"],
        "nvidia_smi": nvidia_smi,
        "dev_nvidia_devices": glob.glob("/dev/nvidia*"),
        "torch_version": torch_info.get("torch_version"),
        "torch_cuda_available": torch_info.get("torch_cuda_available"),
        "torch_cuda_version": torch_info.get("torch_cuda_version"),
        "torch_device_count": torch_info.get("torch_device_count"),
        "import_status": _check_imports(),
        "checks": readiness["checks"],
        "sovits": readiness["sovits"],
        "text_conditioning": readiness["text_conditioning"],
        "timestamp": _iso_timestamp(),
    }
