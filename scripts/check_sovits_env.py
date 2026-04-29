#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models_svc.sovits_assets import inspect_sovits_assets  # noqa: E402
from app.models_svc.sovits_wrapper import SoVitsSvcEngine, SoVitsSvcError  # noqa: E402

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check local So-VITS-SVC runtime configuration.")
    parser.add_argument("--input", required=True, help="Input wav path used for validation.")
    parser.add_argument("--output", required=True, help="Output wav path used for validation.")
    parser.add_argument("--prompt-text", default="测试 So-VITS-SVC 真实推理", help="Prompt text for debug context.")
    parser.add_argument("--style-strength", type=float, default=0.65, help="Style strength for debug context.")
    parser.add_argument("--style-preset-id", default="", help="Optional style preset id to document in output.")
    parser.add_argument("--run", action="store_true", help="Actually run model inference after checks pass.")
    return parser


def run_command(command: list[str], timeout: int = 10) -> dict[str, object]:
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


def check_torch() -> dict[str, object]:
    try:
        import torch
    except Exception as exc:
        return {
            "torch_importable": False,
            "python_version": sys.version,
            "torch_version": None,
            "cuda_available": False,
            "torch_cuda_version": None,
            "device_count": 0,
            "current_device": None,
            "reason": str(exc),
        }

    cuda_available = bool(torch.cuda.is_available())
    return {
        "torch_importable": True,
        "python_version": sys.version,
        "torch_version": torch.__version__,
        "cuda_available": cuda_available,
        "torch_cuda_version": torch.version.cuda,
        "device_count": int(torch.cuda.device_count()),
        "current_device": int(torch.cuda.current_device()) if cuda_available else None,
    }


def check_imports() -> dict[str, dict[str, object]]:
    statuses: dict[str, dict[str, object]] = {}
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


def summarize_gpu_visibility(
    *,
    nvidia_smi: dict[str, object],
    torch_info: dict[str, object],
    dev_nvidia_devices: list[str],
) -> dict[str, object]:
    required_nodes = ["/dev/nvidia0", "/dev/nvidiactl", "/dev/nvidia-uvm"]
    missing_nodes = [node for node in required_nodes if node not in dev_nvidia_devices]
    gpu_visible = bool(
        nvidia_smi.get("return_code") == 0
        and torch_info.get("cuda_available")
        and int(torch_info.get("device_count") or 0) > 0
    )

    if gpu_visible:
        summary = "当前运行环境中 GPU 可见。"
    else:
        summary = "当前容器/会话未检测到完整 GPU 设备映射，当前运行环境中 GPU 不可见。"

    explanation = [
        "服务器有 GPU 不代表当前容器已挂载 GPU。",
        "如果 /dev/nvidia0、/dev/nvidiactl、/dev/nvidia-uvm 缺失，通常说明当前容器没有完整 GPU 设备映射。",
    ]
    suggestions = [
        "检查当前实例是否是 GPU 实例。",
        "检查当前终端是否来自 GPU 容器。",
        "Docker 环境需要使用 --gpus all。",
        "检查 NVIDIA_VISIBLE_DEVICES。",
        "检查 CUDA_VISIBLE_DEVICES。",
        "重新启动 GPU 容器或 Notebook 后再运行 nvidia-smi。",
    ]

    return {
        "gpu_visible": gpu_visible,
        "summary": summary,
        "missing_required_devices": missing_nodes,
        "explanation": explanation,
        "suggestions": suggestions,
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    debug_dir = PROJECT_ROOT / "runtime" / "debug" / "check_sovits_env"
    debug_dir.mkdir(parents=True, exist_ok=True)

    python_bin = os.getenv("SOVITS_PYTHON") or sys.executable
    engine = SoVitsSvcEngine()
    runtime_config = engine.resolve_runtime_config({})
    asset_report = inspect_sovits_assets(
        repo_dir=runtime_config.repo_dir,
        infer_script=runtime_config.infer_script,
        model_path=runtime_config.model_path,
        config_path=runtime_config.config_path,
        speaker=runtime_config.speaker,
    )
    clean_name = engine._safe_clean_name(str(input_path))
    raw_dir = os.path.join(runtime_config.repo_dir, "raw")
    results_dir = os.path.join(runtime_config.repo_dir, "results")
    copied_input_path = os.path.join(raw_dir, f"{clean_name}.wav")
    prepared_audio_info: dict[str, object] | None = None
    audio_prepare_method = None
    input_audio_validation_error: dict[str, object] | None = None
    if Path(runtime_config.repo_dir).exists() and input_path.exists():
        try:
            _raw_dir, _results_dir, copied_input_path, clean_name, prepared_audio_info, audio_prepare_method = engine._prepare_repo_io(
                runtime_config=runtime_config,
                input_vocals_path=str(input_path),
            )
            raw_dir = _raw_dir
            results_dir = _results_dir
        except SoVitsSvcError as exc:
            if exc.code == "SOVITS_INPUT_AUDIO_INVALID":
                input_audio_validation_error = exc.to_dict()
            else:
                raise
    command = engine._build_command(runtime_config, clean_name)  # intentional inspection helper
    torch_info = check_torch()
    nvidia_smi_path = shutil.which("nvidia-smi")
    nvidia_smi = run_command(["nvidia-smi"]) if nvidia_smi_path else {
        "available": False,
        "return_code": None,
        "stdout": "",
        "stderr": "nvidia-smi not found in PATH",
    }
    import_status = check_imports()
    dev_nvidia_devices = glob.glob("/dev/nvidia*")
    gpu_visibility = summarize_gpu_visibility(
        nvidia_smi=nvidia_smi,
        torch_info=torch_info,
        dev_nvidia_devices=dev_nvidia_devices,
    )

    report = {
        "message": "SOVITS_PYTHON not set; using current conda/base python."
        if not os.getenv("SOVITS_PYTHON")
        else "SOVITS_PYTHON is set; using explicit python override.",
        "sys.executable": sys.executable,
        "python_bin": python_bin,
        "python_version": sys.version,
        "conda_env_name": os.getenv("CONDA_DEFAULT_ENV", ""),
        "NVIDIA_VISIBLE_DEVICES": os.getenv("NVIDIA_VISIBLE_DEVICES", ""),
        "CUDA_VISIBLE_DEVICES": os.getenv("CUDA_VISIBLE_DEVICES", ""),
        "which_nvidia_smi": nvidia_smi_path,
        "/dev/nvidia*": dev_nvidia_devices,
        "torch_version": torch_info.get("torch_version"),
        "torch.cuda.is_available()": torch_info.get("cuda_available"),
        "torch.version.cuda": torch_info.get("torch_cuda_version"),
        "torch.cuda.device_count()": torch_info.get("device_count"),
        "gpu_visibility": gpu_visibility,
        "nvidia_smi": nvidia_smi,
        "imports": import_status,
        "input_exists": input_path.exists(),
        "output_parent_exists": output_path.parent.exists(),
        "output_parent_writable": os.access(output_path.parent, os.W_OK) if output_path.parent.exists() else False,
        "repo_dir": runtime_config.repo_dir,
        "repo_exists": Path(runtime_config.repo_dir).exists(),
        "raw_dir": raw_dir,
        "results_dir": results_dir,
        "clean_name": f"{clean_name}.wav",
        "copied_input_path": copied_input_path,
        "original_input_path": str(input_path),
        "original_input_size": input_path.stat().st_size if input_path.exists() else None,
        "prepared_input_path": copied_input_path if prepared_audio_info else None,
        "prepared_audio_info": prepared_audio_info,
        "audio_prepare_method": audio_prepare_method,
        "input_audio_validation_error": input_audio_validation_error,
        "infer_script": runtime_config.infer_script,
        "infer_script_exists": Path(runtime_config.infer_script).exists(),
        "model_path": runtime_config.model_path,
        "model_exists": Path(runtime_config.model_path).exists() if runtime_config.model_path else False,
        "config_path": runtime_config.config_path,
        "config_exists": Path(runtime_config.config_path).exists() if runtime_config.config_path else False,
        "speaker": runtime_config.speaker,
        "config_speakers": asset_report["config_summary"]["speakers"],
        "config_sampling_rate": asset_report["config_summary"]["sampling_rate"],
        "config_speech_encoder": asset_report["config_summary"]["speech_encoder"],
        "speaker_exists_in_config": asset_report["speaker_exists_in_config"],
        "contentvec_required": asset_report["contentvec_required"],
        "contentvec_candidate_paths": asset_report["contentvec_candidate_paths"],
        "contentvec_found_paths": asset_report["contentvec_found_paths"],
        "validation_errors": asset_report["validation_errors"],
        "device": runtime_config.device,
        "transpose": runtime_config.transpose,
        "timeout_seconds": runtime_config.timeout_seconds,
        "mock_enabled": runtime_config.mock_enabled,
        "cuda": torch_info,
        "final_command": command,
        "style_preset_id": args.style_preset_id or None,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if input_audio_validation_error:
        print(json.dumps(input_audio_validation_error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    if not args.run:
        return 0

    try:
        engine.convert(
            input_vocals_path=str(input_path),
            prompt_text=args.prompt_text,
            style_strength=args.style_strength,
            output_path=str(output_path),
            debug_dir=str(debug_dir),
            style_preset={},
        )
    except SoVitsSvcError as exc:
        print(json.dumps(exc.to_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    except Exception as exc:
        print(json.dumps({"code": "CHECK_SOVITS_ENV_FAILED", "message": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3

    print(json.dumps({"status": "ok", "output_path": str(output_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
