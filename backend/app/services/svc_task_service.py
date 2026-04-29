from __future__ import annotations

import json
import logging
import os
import shutil
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.models_svc.sovits_wrapper import SoVitsSvcEngine
from app.services import style_library
from app.services.separation_service import separation_service

logger = logging.getLogger(__name__)

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.dirname(APP_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
DATA_DIR = os.path.join(APP_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
RUNTIME_DEBUG_DIR = os.environ.get("STYLE_DEBUG_DIR", os.path.join(PROJECT_ROOT, "runtime", "debug"))

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RUNTIME_DEBUG_DIR, exist_ok=True)


@dataclass
class UploadRecord:
    vocals_id: str
    input_path: str
    vocals_path: str
    is_vocal_only: bool = False


@dataclass
class TaskState:
    task_id: str
    status: str
    message: str
    engine: str
    vocals_id: str
    stage: str = "uploaded"
    progress: int = 0
    output_path: str | None = None
    error: Any = None
    selected_style: dict[str, Any] | None = None
    inference_mode: str | None = None
    engine_details: dict[str, Any] | None = None
    reasons: list[str] = field(default_factory=list)


class SvcTaskService:
    def __init__(self) -> None:
        self._uploads: dict[str, UploadRecord] = {}
        self._tasks: dict[str, TaskState] = {}
        self._engines = {
            "sovits": SoVitsSvcEngine(),
        }

    def create_upload(self, input_path: str, is_vocal_only: bool = False) -> UploadRecord:
        vocals_id = str(uuid.uuid4())
        upload_dir = os.path.join(UPLOAD_DIR, vocals_id)
        os.makedirs(upload_dir, exist_ok=True)

        ext = os.path.splitext(input_path)[1].lower() or ".wav"
        stored_input = os.path.join(upload_dir, f"input{ext}")
        if os.path.abspath(input_path) != os.path.abspath(stored_input):
            shutil.copyfile(input_path, stored_input)
        else:
            stored_input = input_path

        vocals_path = os.path.join(upload_dir, "vocals.wav")
        separation_service.prepare_vocals(stored_input, vocals_path, is_vocal_only=is_vocal_only)

        record = UploadRecord(
            vocals_id=vocals_id,
            input_path=stored_input,
            vocals_path=vocals_path,
            is_vocal_only=is_vocal_only,
        )
        self._uploads[vocals_id] = record
        return record

    def get_upload(self, vocals_id: str) -> UploadRecord | None:
        return self._uploads.get(vocals_id)

    def create_task(self, vocals_id: str, engine: str = "sovits") -> str:
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = TaskState(
            task_id=task_id,
            status="queued",
            message="任务已创建",
            engine=engine,
            vocals_id=vocals_id,
            stage="uploaded",
            progress=0,
        )
        return task_id

    def get_task(self, task_id: str) -> TaskState | None:
        return self._tasks.get(task_id)

    def process_task(
        self,
        task_id: str,
        prompt_text: str,
        style_strength: float,
        style_preset_id: str | None = None,
        output_path: str | None = None,
    ) -> str:
        task = self._tasks[task_id]
        upload = self.get_upload(task.vocals_id)
        if upload is None:
            raise RuntimeError(f"vocals_id not found: {task.vocals_id}")

        debug_dir = self._debug_dir(task_id)
        target_output = output_path or os.path.join(debug_dir, "converted.wav")

        try:
            task.status = "running"
            task.stage = "uploaded"
            task.progress = 10
            task.message = "正在准备转换输入"
            self._copy_file(debug_dir, upload.input_path, "input.wav")
            self._copy_file(debug_dir, upload.vocals_path, "vocals.wav")
            self._write_json(
                debug_dir,
                "prompt.json",
                {
                    "task_id": task_id,
                    "engine": task.engine,
                    "vocals_id": task.vocals_id,
                    "prompt_text": prompt_text,
                    "style_strength": style_strength,
                    "style_preset_id": style_preset_id,
                    "is_vocal_only": upload.is_vocal_only,
                },
            )

            task.stage = "separated"
            task.progress = 35
            task.message = "人声已就绪，准备检索风格"

            task.stage = "style_selected"
            task.progress = 60
            task.message = "正在检索风格预设"
            selected_style = style_library.retrieve_style(prompt_text, style_preset_id=style_preset_id)
            task.selected_style = selected_style
            selected_style_payload = {
                "style_id": selected_style.get("style_id"),
                "description": selected_style.get("description"),
                "model_path": selected_style.get("model_path"),
                "config_path": selected_style.get("config_path"),
                "speaker": selected_style.get("speaker"),
                "transpose": selected_style.get("transpose"),
                "match_score": selected_style.get("match_score", 0),
                "matched_keywords": selected_style.get("matched_keywords", []),
                "reason": selected_style.get("reason", ""),
            }
            self._write_json(debug_dir, "selected_style.json", selected_style_payload)

            task.stage = "inference_running"
            task.progress = 85
            task.message = "正在执行 SVC 转换"
            engine = self._resolve_engine(task.engine)
            runtime_context: dict[str, Any] = {}
            output = engine.convert(
                input_vocals_path=upload.vocals_path,
                prompt_text=prompt_text,
                style_strength=style_strength,
                output_path=target_output,
                debug_dir=debug_dir,
                style_preset=selected_style,
                task_id=task_id,
                runtime_context=runtime_context,
            )
            if not os.path.exists(output):
                raise RuntimeError(f"converted output missing: {output}")

            task.status = "succeeded"
            task.stage = "completed"
            task.progress = 100
            task.message = "转换完成"
            task.output_path = output
            task.inference_mode = runtime_context.get("inference_mode")
            task.engine_details = runtime_context.get("runtime_config")
            if os.path.abspath(output) != os.path.abspath(os.path.join(debug_dir, "converted.wav")):
                self._copy_file(debug_dir, output, "converted.wav")
            return output
        except Exception as exc:
            task.status = "failed"
            task.stage = "failed"
            task.message = "转换失败"
            error_payload = self._normalize_error(exc)
            task.error = error_payload
            if "runtime_context" in locals():
                task.inference_mode = runtime_context.get("inference_mode", task.inference_mode)
                task.engine_details = runtime_context.get("runtime_config", task.engine_details)
            self._write_json(
                debug_dir,
                "error.json",
                error_payload,
            )
            raise

    def _resolve_engine(self, engine_name: str):
        if engine_name not in self._engines:
            raise RuntimeError(f"Unsupported engine: {engine_name}")
        return self._engines[engine_name]

    def _debug_dir(self, task_id: str) -> str:
        path = os.path.join(RUNTIME_DEBUG_DIR, str(task_id))
        os.makedirs(path, exist_ok=True)
        return path

    def _copy_file(self, debug_dir: str, src: str, filename: str) -> None:
        if not os.path.exists(src):
            return
        shutil.copyfile(src, os.path.join(debug_dir, filename))

    def _write_json(self, debug_dir: str, filename: str, payload: Any) -> None:
        with open(os.path.join(debug_dir, filename), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def _normalize_error(self, exc: Exception) -> dict[str, Any]:
        if hasattr(exc, "to_dict") and callable(exc.to_dict):
            payload = exc.to_dict()
            payload.setdefault("traceback", traceback.format_exc())
            return payload
        return {
            "code": "SVC_TASK_FAILED",
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }


svc_task_service = SvcTaskService()
