from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import soundfile as sf


def resolve_task_debug_dir(project_root: Path, task_id: str | None = None) -> Path:
    token = str(task_id or "").strip()
    if token:
        return project_root / "runtime" / "debug" / token
    return project_root / "runtime" / "debug" / "check_sovits_env"


def build_smoke_report(
    *,
    project_root: Path,
    preset_id: str,
    expected_speaker: str,
    input_path: str,
    output_path: str,
    started_at: str,
    stdout_path: str,
    stderr_path: str,
    task_id: str,
    return_code: int,
) -> dict[str, Any]:
    debug_dir = resolve_task_debug_dir(project_root, task_id)
    command_log_path = debug_dir / "sovits_command.txt"
    debug_json_path = debug_dir / "sovits_debug.json"
    output = Path(output_path)

    soundfile_ok = False
    duration = 0.0
    soundfile_error = ""
    if output.exists():
        try:
            info = sf.info(str(output))
            duration = float(info.frames) / float(info.samplerate) if info.samplerate else 0.0
            soundfile_ok = True
        except Exception as exc:
            soundfile_error = str(exc)

    command_payload = _load_json(command_log_path)
    debug_payload = _load_json(debug_json_path)
    result_metadata = dict(debug_payload.get("result_metadata") or {})
    runtime_config = dict(debug_payload.get("runtime_config") or {})
    command_env = dict(command_payload.get("env") or {})

    resolved_model_path = str(command_payload.get("model_path") or command_env.get("SOVITS_MODEL_PATH") or "")
    resolved_config_path = str(command_payload.get("config_path") or command_env.get("SOVITS_CONFIG_PATH") or "")
    resolved_speaker = str(command_payload.get("speaker") or command_env.get("SOVITS_SPEAKER") or "")
    selected_output = str(command_payload.get("selected_output") or result_metadata.get("selected_output") or "")
    command_return_code = command_payload.get("return_code")
    called_inference_main = bool(result_metadata.get("called_inference_main"))
    validation_mode = str(result_metadata.get("validation_mode") or runtime_config.get("validation_mode") or "")
    bypass_configured_gate = bool(
        result_metadata.get("bypass_configured_gate", runtime_config.get("bypass_configured_gate", False))
    )
    requested_model_preset_id = str(
        result_metadata.get("requested_model_preset_id") or runtime_config.get("requested_model_preset_id") or ""
    )
    model_preset_id = str(result_metadata.get("model_preset_id") or runtime_config.get("model_preset_id") or "")

    normalized_model_path = resolved_model_path.replace("\\", "/")
    normalized_selected_output = selected_output.replace("\\", "/").lower()
    command_matches_preset = f"/local_models/sovits-final/{preset_id}/" in normalized_model_path
    speaker_matches_preset = bool(expected_speaker) and resolved_speaker == expected_speaker
    selected_output_is_stale_legacy = "lain" in normalized_selected_output or "final_primary" in normalized_selected_output

    success = (
        return_code == 0
        and output.exists()
        and output.stat().st_size > 1024
        and soundfile_ok
        and duration >= 0.5
        and called_inference_main
        and command_matches_preset
        and speaker_matches_preset
        and bool(selected_output)
        and not selected_output_is_stale_legacy
    )

    return {
        "task_id": task_id,
        "preset_id": preset_id,
        "input": input_path,
        "output": output_path,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "return_code": return_code,
        "output_exists": output.exists(),
        "output_size": output.stat().st_size if output.exists() else 0,
        "soundfile_readable": soundfile_ok,
        "soundfile_error": soundfile_error,
        "duration_seconds": round(duration, 3),
        "called_inference_main": called_inference_main,
        "resolved_model_path": resolved_model_path,
        "resolved_config_path": resolved_config_path,
        "resolved_speaker": resolved_speaker,
        "expected_speaker": expected_speaker,
        "speaker_matches_preset": speaker_matches_preset,
        "selected_output": selected_output,
        "selected_output_is_stale_legacy": selected_output_is_stale_legacy,
        "command_return_code": command_return_code,
        "command_matches_preset": command_matches_preset,
        "validation_mode": validation_mode or None,
        "bypass_configured_gate": bypass_configured_gate,
        "requested_model_preset_id": requested_model_preset_id or None,
        "model_preset_id": model_preset_id or None,
        "success": success,
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
        "debug_dir": str(debug_dir),
        "sovits_command_debug_path": str(command_log_path),
        "sovits_debug_json_path": str(debug_json_path),
        "model_path": resolved_model_path,
        "config_path": resolved_config_path,
        "speaker": resolved_speaker,
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
