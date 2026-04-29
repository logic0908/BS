from __future__ import annotations

import json
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

from app.models_svc.sovits_assets import inspect_sovits_assets
from app.models_svc.svc_base import VoiceConversionEngine

logger = logging.getLogger(__name__)
RESULT_AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".ogg", ".m4a"}


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class SoVitsRuntimeConfig:
    repo_dir: str
    infer_script: str
    model_path: str
    config_path: str
    speaker: str
    device: str
    transpose: int
    timeout_seconds: int
    mock_enabled: bool
    python_bin: str

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "repo_dir": self.repo_dir,
            "infer_script": self.infer_script,
            "model_path": self.model_path,
            "config_path": self.config_path,
            "speaker": self.speaker,
            "device": self.device,
            "transpose": self.transpose,
            "timeout_seconds": self.timeout_seconds,
            "mock_enabled": self.mock_enabled,
            "python_bin": self.python_bin,
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
        self.model_path = os.environ.get("SOVITS_MODEL_PATH", "")
        self.config_path = os.environ.get("SOVITS_CONFIG_PATH", "")
        self.speaker = os.environ.get("SOVITS_SPEAKER", "")
        self.device = os.environ.get("SOVITS_DEVICE", "cuda")
        self.transpose = int(os.environ.get("SOVITS_TRANSPOSE", "0"))
        self.timeout_seconds = int(os.environ.get("SOVITS_TIMEOUT_SECONDS", "600"))
        self.mock_enabled = _env_flag("SOVITS_MOCK", True)
        self.python_bin = os.environ.get("SOVITS_PYTHON") or sys.executable
        self.vendor_path = os.environ.get("SOVITS_VENDOR_PATH", "").strip()

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
        runtime_config = self.resolve_runtime_config(style_preset)
        if isinstance(runtime_context, dict):
            runtime_context.update(
                {
                    "inference_mode": "mock" if runtime_config.mock_enabled else "real",
                    "engine": "sovits",
                    "runtime_config": runtime_config.to_public_dict(),
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
                "selected_output": output_path,
                "final_output_path": output_path,
                "return_code": 0,
                "elapsed_seconds": 0.0,
                "sovits_command_debug_path": os.path.join(debug_dir, "sovits_command.txt") if debug_dir else None,
                "called_inference_main": False,
            }
            if isinstance(runtime_context, dict):
                runtime_context["result_metadata"] = mock_result
                runtime_context["runtime_config"] = {**runtime_config.to_public_dict(), **mock_result}
            debug_payload = {
                "mode": "mock",
                "input_vocals_path": input_vocals_path,
                "output_path": output_path,
                "prompt_text": prompt_text,
                "style_strength": style_strength,
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
        )

    def resolve_runtime_config(self, style_preset: dict[str, Any] | None = None) -> SoVitsRuntimeConfig:
        preset = style_preset or {}
        repo_dir = os.environ.get("SOVITS_REPO_DIR", self.repo_dir)
        infer_script = os.environ.get("SOVITS_INFER_SCRIPT", self.infer_script)
        model_path = str(preset.get("model_path") or os.environ.get("SOVITS_MODEL_PATH", self.model_path))
        config_path = str(preset.get("config_path") or os.environ.get("SOVITS_CONFIG_PATH", self.config_path))
        speaker = str(preset.get("speaker") or os.environ.get("SOVITS_SPEAKER", self.speaker))
        device = os.environ.get("SOVITS_DEVICE", self.device)
        transpose = int(preset.get("transpose", os.environ.get("SOVITS_TRANSPOSE", self.transpose)))
        timeout_seconds = int(os.environ.get("SOVITS_TIMEOUT_SECONDS", str(self.timeout_seconds)))
        mock_enabled = _env_flag("SOVITS_MOCK", self.mock_enabled)
        python_bin = os.environ.get("SOVITS_PYTHON") or self.python_bin
        return SoVitsRuntimeConfig(
            repo_dir=repo_dir,
            infer_script=infer_script,
            model_path=model_path,
            config_path=config_path,
            speaker=speaker,
            device=device,
            transpose=transpose,
            timeout_seconds=timeout_seconds,
            mock_enabled=mock_enabled,
            python_bin=python_bin,
        )

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
    ) -> str:
        self._validate_runtime(runtime_config, input_vocals_path, output_path)
        raw_dir, results_dir, copied_input_path, clean_name, prepared_audio_info, audio_prepare_method = self._prepare_repo_io(
            runtime_config=runtime_config,
            input_vocals_path=input_vocals_path,
            task_id=task_id,
        )
        existing_outputs = self._result_files(results_dir)
        command = self._build_command(runtime_config, clean_name)
        start_time = time.monotonic()
        command_log = {
            "mode": "real",
            "python_bin": runtime_config.python_bin,
            "sys.executable": sys.executable,
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
            "env": self._env_snapshot(runtime_config),
            "prompt_text": prompt_text,
            "style_strength": style_strength,
            "style_preset": style_preset,
            "stdout": "",
            "stderr": "",
            "return_code": None,
            "elapsed_seconds": None,
            "discovered_outputs": [],
            "selected_output": None,
            "final_output_path": output_path,
        }

        try:
            result = subprocess.run(
                command,
                cwd=runtime_config.repo_dir,
                capture_output=True,
                text=True,
                timeout=runtime_config.timeout_seconds,
                env=self._build_subprocess_env(runtime_config),
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

        discovered_outputs = self._discover_new_outputs(results_dir, existing_outputs)
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
        result_metadata = {
            "inference_mode": "real",
            "mock_enabled": False,
            "model_path": runtime_config.model_path,
            "config_path": runtime_config.config_path,
            "speaker": runtime_config.speaker,
            "device": runtime_config.device,
            "selected_output": selected_output,
            "final_output_path": output_path,
            "return_code": result.returncode,
            "elapsed_seconds": command_log["elapsed_seconds"],
            "sovits_command_debug_path": os.path.join(debug_dir, "sovits_command.txt") if debug_dir else None,
            "called_inference_main": True,
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
            },
        )
        return output_path

    def _validate_runtime(self, runtime_config: SoVitsRuntimeConfig, input_vocals_path: str, output_path: str) -> None:
        output_dir = os.path.dirname(output_path)
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
        asset_report = inspect_sovits_assets(
            repo_dir=runtime_config.repo_dir,
            infer_script=runtime_config.infer_script,
            model_path=runtime_config.model_path,
            config_path=runtime_config.config_path,
            speaker=runtime_config.speaker,
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
    ) -> list[str]:
        return [
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

    def _discover_new_outputs(self, results_dir: str, existing_outputs: set[str]) -> list[str]:
        current_outputs = self._result_files(results_dir)
        new_outputs = [path for path in current_outputs if path not in existing_outputs]
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

    def _env_snapshot(self, runtime_config: SoVitsRuntimeConfig) -> dict[str, Any]:
        return {
            "SOVITS_REPO_DIR": runtime_config.repo_dir,
            "SOVITS_INFER_SCRIPT": runtime_config.infer_script,
            "SOVITS_MODEL_PATH": runtime_config.model_path,
            "SOVITS_CONFIG_PATH": runtime_config.config_path,
            "SOVITS_SPEAKER": runtime_config.speaker,
            "SOVITS_DEVICE": runtime_config.device,
            "SOVITS_TRANSPOSE": runtime_config.transpose,
            "SOVITS_TIMEOUT_SECONDS": runtime_config.timeout_seconds,
            "SOVITS_MOCK": runtime_config.mock_enabled,
            "SOVITS_PYTHON": runtime_config.python_bin,
            "SOVITS_VENDOR_PATH": self.vendor_path,
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
        }

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
