from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, NamedTuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = PROJECT_ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

os.environ.setdefault("SOVITS_MOCK", "false")
os.environ.setdefault("NUMBA_CACHE_DIR", str(PROJECT_ROOT / "runtime" / "numba_cache"))
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

from app.services.svc_task_service import svc_task_service  # noqa: E402

try:  # pragma: no cover - import path differs when celery CLI imports the app package
    from app.workers.svc_tasks import process_svc_task  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover
    from backend.app.workers.svc_tasks import process_svc_task  # type: ignore[no-redef]  # noqa: E402


ADAPTER_MODE_ALIASES = {
    "trained": "trained_adapter",
    "trained_adapter": "trained_adapter",
    "no_adapter": "no_adapter",
    "rule_based": "rule_based_adapter",
    "rule_based_adapter": "rule_based_adapter",
}
DEFAULT_OUTPUT = PROJECT_ROOT / "runtime" / "eval_reports" / "effect_ablation_latest.json"
PRESET_CONFIG_PATH = BACKEND_PATH / "app" / "config" / "svc_model_presets.json"


class ExperimentCase(NamedTuple):
    label: str
    model_preset_id: str
    adapter_mode: str
    allow_preset_fallback: bool
    f0_method: str


def load_preset_index() -> dict[tuple[str, str], str]:
    if not PRESET_CONFIG_PATH.exists():
        return {}
    payload = json.loads(PRESET_CONFIG_PATH.read_text(encoding="utf-8"))
    index: dict[tuple[str, str], str] = {}
    for preset in payload.get("presets", []):
        model_path = str(preset.get("model_path") or "").strip()
        speaker = str(preset.get("speaker") or "").strip()
        preset_id = str(preset.get("preset_id") or "").strip()
        if model_path and speaker and preset_id:
            index[(model_path, speaker)] = preset_id
    return index


PRESET_INDEX = load_preset_index()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a So-VITS-SVC ablation matrix and record task/debug metadata."
    )
    parser.add_argument("--input", required=True, help="Input dry vocal path.")
    parser.add_argument("--prompt", required=True, help="Prompt text used for all runs.")
    parser.add_argument("--style-strength", type=float, default=0.65)
    parser.add_argument("--model-preset-id", default="final_primary")
    parser.add_argument(
        "--adapter-mode",
        action="append",
        dest="adapter_modes",
        choices=sorted(ADAPTER_MODE_ALIASES.keys()),
        help="Legacy matrix mode. Use --case for explicit experiments.",
    )
    parser.add_argument(
        "--f0-method",
        action="append",
        dest="f0_methods",
        help="Legacy matrix mode. If omitted, defaults to rmvpe.",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="cases",
        help=(
            "Explicit experiment case in the form "
            "'label|model_preset_id|adapter_mode|allow_preset_fallback'. "
            "Adapter mode accepts trained_adapter, no_adapter, or rule_based_adapter."
        ),
    )
    parser.add_argument(
        "--task-backend-mode",
        choices=["auto", "local", "celery"],
        default="auto",
        help="How the script should dispatch tasks. auto follows SVC_USE_CELERY.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=1.0,
        help="Polling interval used while waiting for Celery-backed tasks.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=900.0,
        help="Per-task timeout while waiting for Celery-backed tasks.",
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def normalize_adapter_mode(value: str) -> str:
    normalized = ADAPTER_MODE_ALIASES.get(value.strip().lower())
    if normalized is None:
        raise ValueError(f"unsupported adapter mode: {value}")
    return normalized


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"unsupported boolean value: {value}")


def parse_case(raw_case: str, default_f0_method: str) -> ExperimentCase:
    parts = [part.strip() for part in raw_case.split("|")]
    if len(parts) != 4:
        raise ValueError(
            "case must use the form 'label|model_preset_id|adapter_mode|allow_preset_fallback'"
        )
    label, model_preset_id, adapter_mode, allow_preset_fallback = parts
    if not label:
        raise ValueError("case label must not be empty")
    if not model_preset_id:
        raise ValueError("case model_preset_id must not be empty")
    return ExperimentCase(
        label=label,
        model_preset_id=model_preset_id,
        adapter_mode=normalize_adapter_mode(adapter_mode),
        allow_preset_fallback=parse_bool(allow_preset_fallback),
        f0_method=default_f0_method,
    )


def build_cases(args: argparse.Namespace) -> list[ExperimentCase]:
    default_f0_method = (args.f0_methods or ["rmvpe"])[0]
    if args.cases:
        return [parse_case(raw_case, default_f0_method) for raw_case in args.cases]

    adapter_modes = args.adapter_modes or ["no_adapter", "rule_based_adapter", "trained_adapter"]
    f0_methods = args.f0_methods or ["rmvpe"]
    cases: list[ExperimentCase] = []
    for adapter_mode in adapter_modes:
        for f0_method in f0_methods:
            normalized_adapter_mode = normalize_adapter_mode(adapter_mode)
            label = f"{args.model_preset_id}+{normalized_adapter_mode}+{f0_method}"
            cases.append(
                ExperimentCase(
                    label=label,
                    model_preset_id=args.model_preset_id,
                    adapter_mode=normalized_adapter_mode,
                    allow_preset_fallback=False,
                    f0_method=f0_method,
                )
            )
    return cases


def resolve_task_backend_mode(raw_mode: str) -> str:
    if raw_mode == "auto":
        env_value = os.environ.get("SVC_USE_CELERY", "true").strip().lower()
        return "celery" if env_value in {"1", "true", "yes", "on"} else "local"
    return raw_mode


def configure_runtime_mode(task_backend_mode: str) -> None:
    os.environ["SVC_USE_CELERY"] = "true" if task_backend_mode == "celery" else "false"


def run_command(command: list[str], timeout: int = 10) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception as exc:
        return {
            "command": command,
            "available": False,
            "return_code": None,
            "stdout": "",
            "stderr": str(exc),
        }
    return {
        "command": command,
        "available": result.returncode == 0,
        "return_code": result.returncode,
        "stdout": result.stdout or "",
        "stderr": result.stderr or "",
    }


def torch_cuda_summary() -> dict[str, Any]:
    try:
        import torch
    except Exception as exc:
        return {
            "torch_importable": False,
            "torch_version": None,
            "torch_cuda_version": None,
            "torch_cuda_is_available": False,
            "torch_cuda_device_count": 0,
            "error": str(exc),
        }

    cuda_available = bool(torch.cuda.is_available())
    return {
        "torch_importable": True,
        "torch_version": torch.__version__,
        "torch_cuda_version": torch.version.cuda,
        "torch_cuda_is_available": cuda_available,
        "torch_cuda_device_count": int(torch.cuda.device_count()),
    }


def build_environment_check() -> dict[str, Any]:
    nvidia_smi = run_command(["nvidia-smi"])
    payload = {
        "cwd": str(PROJECT_ROOT),
        "python": sys.executable,
        "SVC_USE_CELERY": os.environ.get("SVC_USE_CELERY", ""),
        "SOVITS_DEVICE": os.environ.get("SOVITS_DEVICE", ""),
        "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
        "NVIDIA_VISIBLE_DEVICES": os.environ.get("NVIDIA_VISIBLE_DEVICES", ""),
        "PYTORCH_NVML_BASED_CUDA_CHECK": os.environ.get("PYTORCH_NVML_BASED_CUDA_CHECK", ""),
        "nvidia_smi": nvidia_smi,
        "torch": torch_cuda_summary(),
    }
    print(json.dumps({"environment_check": payload}, ensure_ascii=False, indent=2))
    return payload


def tail_text(value: str, max_lines: int = 25, max_chars: int = 4000) -> str:
    trimmed = value[-max_chars:]
    lines = trimmed.splitlines()
    return "\n".join(lines[-max_lines:]).strip()


def read_command_payload(command_path: Path) -> dict[str, Any]:
    if not command_path.exists():
        return {}
    try:
        return json.loads(command_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def wait_for_task(task_id: str, timeout_seconds: float, poll_seconds: float) -> Any:
    deadline = time.monotonic() + timeout_seconds
    last_task = svc_task_service.get_task(task_id)
    while time.monotonic() < deadline:
        task = svc_task_service.get_task(task_id)
        if task is not None:
            last_task = task
            if task.status in {"succeeded", "failed"}:
                return task
        time.sleep(poll_seconds)
    return last_task


def dispatch_task(
    *,
    task_id: str,
    prompt: str,
    style_strength: float,
    case: ExperimentCase,
    task_backend_mode: str,
) -> None:
    kwargs = {
        "task_id": task_id,
        "prompt_text": prompt,
        "style_strength": style_strength,
        "model_preset_id": case.model_preset_id,
        "f0_method": case.f0_method,
        "allow_preset_fallback": case.allow_preset_fallback,
        "requested_adapter_mode": case.adapter_mode,
    }
    if task_backend_mode == "celery":
        process_svc_task.apply_async(kwargs=kwargs, queue="svc")
        return
    svc_task_service.process_task(**kwargs)


def collect_result(
    *,
    task_id: str,
    label: str,
    prompt: str,
    input_path: str,
    case: ExperimentCase,
    task_backend_mode: str,
    dispatch_error: str | None,
) -> dict[str, Any]:
    task = svc_task_service.get_task(task_id)
    audio_quality = dict((task.audio_quality or {})) if task else {}
    engine_details = dict((task.engine_details or {})) if task else {}
    debug_dir = PROJECT_ROOT / "runtime" / "debug" / task_id
    command_path = debug_dir / "sovits_command.txt"
    task_config_path = debug_dir / "task_config.json"
    command_payload = read_command_payload(command_path)
    task_config_payload = read_command_payload(task_config_path)
    command_model_path = str(command_payload.get("model_path") or engine_details.get("model_path") or "")
    command_speaker = str(command_payload.get("speaker") or engine_details.get("speaker") or "")
    effective_model_preset_id = PRESET_INDEX.get(
        (command_model_path, command_speaker),
        engine_details.get("effective_model_preset_id"),
    )
    output_path = (
        str(task.output_path)
        if task and task.output_path
        else command_payload.get("final_output_path")
    )
    output_exists = bool(output_path) and Path(str(output_path)).exists()
    error_payload = dict((task.error or {})) if task and isinstance(task.error, dict) else {}
    error_details = dict(error_payload.get("details") or {}) if isinstance(error_payload.get("details"), dict) else {}
    stderr_value = str(command_payload.get("stderr") or error_details.get("stderr") or "")
    stderr_tail = tail_text(stderr_value) if stderr_value else ""
    effective_adapter_mode = (
        task_config_payload.get("effective_adapter_mode")
        or engine_details.get("effective_adapter_mode")
        or ((task.adapter_result or {}).get("adapter_mode") if task else None)
    )
    return {
        "label": label,
        "input_path": input_path,
        "prompt": prompt,
        "task_id": task_id,
        "task_status": task.status if task else "missing",
        "task_backend_mode": task_backend_mode,
        "requested_model_preset_id": case.model_preset_id,
        "effective_model_preset_id": effective_model_preset_id,
        "speaker": command_speaker or ((task.selected_style or {}) if task else {}).get("speaker"),
        "requested_adapter_mode": task_config_payload.get("requested_adapter_mode")
        or engine_details.get("requested_adapter_mode")
        or case.adapter_mode,
        "effective_adapter_mode": effective_adapter_mode,
        "allow_preset_fallback": case.allow_preset_fallback,
        "f0_method_requested": case.f0_method,
        "f0_method": engine_details.get("f0_method") or case.f0_method,
        "f0_fallback_reason": engine_details.get("f0_fallback_reason"),
        "duration_consistency": audio_quality.get("duration_consistency"),
        "low_energy_ratio": audio_quality.get("low_energy_ratio"),
        "possible_dropouts": audio_quality.get("possible_dropouts"),
        "output_path": output_path,
        "output_exists": output_exists,
        "task_config_path": str(task_config_path),
        "sovits_command_path": str(command_path),
        "sovits_command_debug_path": engine_details.get("sovits_command_debug_path") or str(command_path),
        "return_code": command_payload.get("return_code"),
        "error_code": error_payload.get("code"),
        "error_message": dispatch_error or error_payload.get("message"),
        "stderr_tail": stderr_tail or None,
    }


def run_single_experiment(
    *,
    input_path: str,
    prompt: str,
    style_strength: float,
    case: ExperimentCase,
    task_backend_mode: str,
    timeout_seconds: float,
    poll_seconds: float,
) -> dict[str, Any]:
    upload = svc_task_service.create_upload(input_path, is_vocal_only=True)
    task_id = svc_task_service.create_task(
        upload.vocals_id,
        engine="sovits",
        task_backend_mode=task_backend_mode,
    )
    dispatch_error: str | None = None
    try:
        dispatch_task(
            task_id=task_id,
            prompt=prompt,
            style_strength=style_strength,
            case=case,
            task_backend_mode=task_backend_mode,
        )
        if task_backend_mode == "celery":
            waited = wait_for_task(task_id, timeout_seconds=timeout_seconds, poll_seconds=poll_seconds)
            if waited is None or getattr(waited, "status", None) not in {"succeeded", "failed"}:
                dispatch_error = f"Timed out waiting for task completion after {timeout_seconds:.1f}s"
    except Exception as exc:
        dispatch_error = str(exc)
    return collect_result(
        task_id=task_id,
        label=case.label,
        prompt=prompt,
        input_path=input_path,
        case=case,
        task_backend_mode=task_backend_mode,
        dispatch_error=dispatch_error,
    )


def main() -> int:
    args = parse_args()
    task_backend_mode = resolve_task_backend_mode(args.task_backend_mode)
    configure_runtime_mode(task_backend_mode)
    cases = build_cases(args)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    environment_check = build_environment_check()

    results = [
        run_single_experiment(
            input_path=args.input,
            prompt=args.prompt,
            style_strength=args.style_strength,
            case=case,
            task_backend_mode=task_backend_mode,
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
        )
        for case in cases
    ]

    payload = {
        "input_path": str(Path(args.input).expanduser().resolve()),
        "prompt": args.prompt,
        "style_strength": args.style_strength,
        "task_backend_mode": task_backend_mode,
        "environment_check": environment_check,
        "cases": [result["label"] for result in results],
        "results": results,
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"saved {len(results)} ablation rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
