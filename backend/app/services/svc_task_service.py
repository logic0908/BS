from __future__ import annotations

import json
import logging
import os
import shutil
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from app.models_svc.sovits_wrapper import SoVitsSvcEngine
from app.models_svc.text_style_adapter import normalize_requested_adapter_mode, text_style_adapter
from app.services import style_library
from app.services.audio_quality import analyze_audio_pair, write_audio_quality_report
from app.services.input_quality import (
    analyze_input_audio,
    build_input_quality_fallback,
    summarize_input_quality,
    write_input_quality_report,
)
from app.services.separation_service import separation_service
from app.services.task_store import task_store
from app.services.text_style_encoder import TextStyleEncoderError, text_style_encoder

logger = logging.getLogger(__name__)

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.dirname(APP_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
DATA_DIR = os.path.join(APP_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
RUNTIME_DEBUG_DIR = os.environ.get("STYLE_DEBUG_DIR", os.path.join(PROJECT_ROOT, "runtime", "debug"))

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RUNTIME_DEBUG_DIR, exist_ok=True)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class UploadRecord:
    vocals_id: str
    input_path: str
    vocals_path: str
    is_vocal_only: bool = False
    input_quality_summary: dict[str, Any] | None = None
    input_quality_report_path: str | None = None


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
    task_backend_mode: str = "local"
    text_encoding: dict[str, Any] | None = None
    adapter_result: dict[str, Any] | None = None
    audio_quality: dict[str, Any] | None = None


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
        try:
            input_quality_report = analyze_input_audio(stored_input)
        except Exception as exc:
            input_quality_report = build_input_quality_fallback(stored_input, exc)
        input_quality_summary = summarize_input_quality(input_quality_report)
        input_quality_report_path = write_input_quality_report(upload_dir, input_quality_report)

        record = UploadRecord(
            vocals_id=vocals_id,
            input_path=stored_input,
            vocals_path=vocals_path,
            is_vocal_only=is_vocal_only,
            input_quality_summary=input_quality_summary,
            input_quality_report_path=input_quality_report_path,
        )
        self._uploads[vocals_id] = record
        task_store.save_upload(vocals_id, asdict(record))
        return record

    def get_upload(self, vocals_id: str) -> UploadRecord | None:
        record = self._uploads.get(vocals_id)
        if record is not None:
            return record
        payload = task_store.load_upload(vocals_id)
        if payload is None:
            return None
        record = UploadRecord(**payload)
        self._uploads[vocals_id] = record
        return record

    def create_task(self, vocals_id: str, engine: str = "sovits", task_backend_mode: str | None = None) -> str:
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = TaskState(
            task_id=task_id,
            status="queued",
            message="任务已创建",
            engine=engine,
            vocals_id=vocals_id,
            stage="uploaded",
            progress=0,
            task_backend_mode=task_backend_mode or ("celery" if self.use_celery() else "local"),
        )
        self._persist_task(self._tasks[task_id])
        return task_id

    def get_task(self, task_id: str) -> TaskState | None:
        if self.use_celery():
            payload = task_store.load_task(task_id)
            if payload is not None:
                task = self._task_from_payload(payload)
                self._tasks[task_id] = task
                return task
        task = self._tasks.get(task_id)
        if task is not None:
            return task
        payload = task_store.load_task(task_id)
        if payload is None:
            return None
        task = self._task_from_payload(payload)
        self._tasks[task_id] = task
        return task

    def use_celery(self) -> bool:
        return _env_flag("SVC_USE_CELERY", True)

    def process_task(
        self,
        task_id: str,
        prompt_text: str,
        style_strength: float,
        style_prompt: str | None = None,
        style_preset_id: str | None = None,
        model_preset_id: str | None = None,
        film_strength: float = 0.10,
        transpose: int | None = None,
        f0_method: str | None = None,
        auto_predict_f0: bool | None = None,
        slice_db: float | None = None,
        clip_seconds: float | None = None,
        pad_seconds: float | None = None,
        allow_preset_fallback: bool = False,
        output_path: str | None = None,
        requested_adapter_mode: str | None = None,
    ) -> str:
        task = self.get_task(task_id)
        if task is None:
            raise RuntimeError(f"task_id not found: {task_id}")
        upload = self.get_upload(task.vocals_id)
        if upload is None:
            raise RuntimeError(f"vocals_id not found: {task.vocals_id}")

        debug_dir = self._debug_dir(task_id)
        target_output = output_path or os.path.join(debug_dir, "converted.wav")
        runtime_context: dict[str, Any] = {}
        selected_style: dict[str, Any] | None = None
        text_encoding_summary: dict[str, Any] | None = None
        style_embedding_paths: dict[str, str] | None = None
        adapter_summary: dict[str, Any] | None = None
        audio_quality_summary: dict[str, Any] | None = None
        effective_style_strength = float(style_strength)
        resolved_style_prompt = (style_prompt or prompt_text or "").strip()
        normalized_requested_adapter_mode = normalize_requested_adapter_mode(requested_adapter_mode)
        requested_adapter_mode_label = normalized_requested_adapter_mode or "auto"
        effective_adapter_mode = "pending"
        conversion_params_request = {
            "film_strength": film_strength,
            "f0_method": f0_method,
            "auto_predict_f0": auto_predict_f0,
            "transpose": transpose,
            "slice_db": slice_db,
            "clip_seconds": clip_seconds,
            "pad_seconds": pad_seconds,
        }
        conversion_params_summary: dict[str, Any] | None = None

        try:
            task.status = "running"
            task.stage = "uploaded"
            task.progress = 10
            task.message = "正在准备转换输入"
            self._persist_task(task)
            self._copy_file(debug_dir, upload.input_path, "input.wav")
            self._copy_file(debug_dir, upload.vocals_path, "vocals.wav")
            self._write_task_config(
                debug_dir=debug_dir,
                task_id=task_id,
                task_backend_mode=task.task_backend_mode,
                requested_adapter_mode=requested_adapter_mode_label,
                effective_adapter_mode=effective_adapter_mode,
                output_path=target_output,
            )
            self._write_json(
                debug_dir,
                "prompt.json",
                {
                    "task_id": task_id,
                    "engine": task.engine,
                    "vocals_id": task.vocals_id,
                    "prompt_text": prompt_text,
                    "style_prompt": style_prompt,
                    "effective_style_prompt": resolved_style_prompt,
                    "style_strength": style_strength,
                    "style_preset_id": style_preset_id,
                    "model_preset_id": model_preset_id,
                    "film_strength": film_strength,
                    "transpose": transpose,
                    "f0_method": f0_method,
                    "auto_predict_f0": auto_predict_f0,
                    "slice_db": slice_db,
                    "clip_seconds": clip_seconds,
                    "pad_seconds": pad_seconds,
                    "allow_preset_fallback": allow_preset_fallback,
                    "requested_adapter_mode": requested_adapter_mode_label,
                    "is_vocal_only": upload.is_vocal_only,
                    "task_backend_mode": task.task_backend_mode,
                    "input_quality_summary": upload.input_quality_summary,
                },
            )

            task.stage = "separated"
            task.progress = 35
            task.message = "人声已就绪，准备检索风格"
            self._persist_task(task)

            task.stage = "style_selected"
            task.progress = 55
            task.message = "正在检索风格预设"
            selected_style = style_library.retrieve_style(
                resolved_style_prompt,
                style_preset_id=style_preset_id,
                model_preset_id=model_preset_id,
            )
            task.selected_style = selected_style
            self._write_json(debug_dir, "selected_style.json", self._selected_style_payload(selected_style))
            self._persist_task(task)

            task.stage = "text_encoded"
            task.progress = 65
            task.message = "正在编码文本风格提示词"
            self._persist_task(task)
            embedding = None
            try:
                embedding = text_style_encoder.encode_prompt(resolved_style_prompt)
                style_embedding_paths = text_style_encoder.write_debug_artifacts(debug_dir, embedding)
                text_encoding_summary = embedding.to_summary()
                text_encoding_summary.update(style_embedding_paths)
            except TextStyleEncoderError as exc:
                text_encoding_summary = {
                    "enabled": False,
                    "status": "fallback",
                    "embedding_dim": None,
                    "embedding_norm": None,
                    "top_keywords": [],
                    "encoder_model_name": str(text_style_encoder.config.get("encoder_model_name") or ""),
                    "error": exc.to_dict(),
                }
                self._write_json(debug_dir, "style_embedding.json", text_encoding_summary)
            task.text_encoding = text_encoding_summary
            self._persist_task(task)

            task.stage = "adapter_applied"
            task.progress = 75
            task.message = "正在应用 TextStyleAdapter 控制参数"
            self._persist_task(task)
            adapter_result = text_style_adapter.build_controls(
                prompt_embedding=embedding.to_debug_dict() if embedding else None,
                style_strength=style_strength,
                selected_style=selected_style,
                available_model_presets=style_library.available_model_presets(),
                requested_adapter_mode=normalized_requested_adapter_mode,
            )
            adapter_payload = adapter_result.to_dict()
            if not adapter_result.adapter_enabled and text_encoding_summary and text_encoding_summary.get("error"):
                adapter_payload["adapter_fallback_reason"] = text_encoding_summary["error"]["code"]
            self._write_json(debug_dir, "style_adapter_output.json", adapter_payload)
            adapter_summary = adapter_result.to_summary()
            task.adapter_result = adapter_summary
            effective_adapter_mode = str(adapter_result.adapter_mode or "unknown")
            self._write_task_config(
                debug_dir=debug_dir,
                task_id=task_id,
                task_backend_mode=task.task_backend_mode,
                requested_adapter_mode=requested_adapter_mode_label,
                effective_adapter_mode=effective_adapter_mode,
                output_path=target_output,
            )

            effective_style = dict(selected_style)
            if effective_adapter_mode != "no_adapter":
                effective_style = style_library.apply_adapter_controls(
                    selected_style,
                    adapter_result.control_params,
                    model_preset_id=model_preset_id,
                    override_reason=adapter_result.override_reason,
                )
            manual_controls: dict[str, Any] = {}
            if model_preset_id:
                manual_controls["model_preset_id"] = model_preset_id
            if transpose is not None:
                manual_controls["transpose"] = int(transpose)
            if manual_controls:
                effective_style = style_library.apply_adapter_controls(
                    effective_style,
                    manual_controls,
                    model_preset_id=manual_controls.get("model_preset_id"),
                    override_reason="Advanced conversion parameter override",
                )
            selected_style = effective_style
            task.selected_style = effective_style
            if adapter_result.control_params.get("style_strength") is not None:
                effective_style_strength = float(adapter_result.control_params["style_strength"])
            self._write_json(debug_dir, "selected_style.json", self._selected_style_payload(selected_style))
            self._persist_task(task)

            task.stage = "inference_running"
            task.progress = 85
            task.message = "正在执行 SVC 转换"
            self._persist_task(task)
            engine = self._resolve_engine(task.engine)
            runtime_preview = engine.resolve_runtime_config(
                selected_style,
                conversion_params=conversion_params_request,
                allow_preset_fallback=allow_preset_fallback,
            )
            conversion_params_summary = self._build_conversion_params_payload(
                runtime_preview=runtime_preview.to_public_dict(),
                debug_dir=debug_dir,
            )
            self._write_json(debug_dir, "conversion_params.json", conversion_params_summary)
            previous_film_strength = os.environ.get("SOVITS_FILM_STRENGTH")
            os.environ["SOVITS_FILM_STRENGTH"] = str(film_strength)
            try:
                output = engine.convert(
                    input_vocals_path=upload.vocals_path,
                    prompt_text=resolved_style_prompt,
                    style_strength=effective_style_strength,
                    output_path=target_output,
                    debug_dir=debug_dir,
                    style_preset=selected_style,
                    task_id=task_id,
                    runtime_context=runtime_context,
                    conversion_params=conversion_params_request,
                    allow_preset_fallback=allow_preset_fallback,
                    style_prompt=resolved_style_prompt,
                    style_emb_path=(style_embedding_paths or {}).get("style_embedding_pt"),
                    style_dim=(text_encoding_summary or {}).get("embedding_dim"),
                )
            finally:
                if previous_film_strength is None:
                    os.environ.pop("SOVITS_FILM_STRENGTH", None)
                else:
                    os.environ["SOVITS_FILM_STRENGTH"] = previous_film_strength
            if not os.path.exists(output):
                raise RuntimeError(f"converted output missing: {output}")

            task.stage = "quality_evaluated"
            task.progress = 92
            task.message = "正在生成音频质量报告"
            self._persist_task(task)
            audio_quality_report = analyze_audio_pair(upload.vocals_path, output)
            audio_quality_report["report_path"] = write_audio_quality_report(debug_dir, audio_quality_report)
            audio_quality_summary = audio_quality_report.get("summary")
            task.audio_quality = audio_quality_summary

            engine_details = dict(runtime_context.get("runtime_config") or {})
            engine_details.update(
                {
                    "task_backend_mode": task.task_backend_mode,
                    "requested_adapter_mode": requested_adapter_mode_label,
                    "effective_adapter_mode": effective_adapter_mode,
                    "encoder_model_name": (text_encoding_summary or {}).get("encoder_model_name"),
                    "embedding_dim": (text_encoding_summary or {}).get("embedding_dim"),
                    "embedding_norm": (text_encoding_summary or {}).get("embedding_norm"),
                    "top_keywords": (text_encoding_summary or {}).get("top_keywords", []),
                    "style_prompt": resolved_style_prompt,
                    "style_emb_path": (style_embedding_paths or {}).get("style_embedding_pt"),
                    "style_embedding_json": (style_embedding_paths or {}).get("style_embedding_json"),
                    "style_embedding_npy": (style_embedding_paths or {}).get("style_embedding_npy"),
                    "text_encoding_status": (text_encoding_summary or {}).get("status"),
                    "text_encoding_enabled": bool((text_encoding_summary or {}).get("enabled")),
                    "encoder_type": (text_encoding_summary or {}).get("encoder_type"),
                    "adapter_enabled": bool((adapter_summary or {}).get("adapter_enabled")),
                    "adapter_mode": (adapter_summary or {}).get("adapter_mode"),
                    "adapter_version": (adapter_summary or {}).get("adapter_version"),
                    "adapter_type": (adapter_summary or {}).get("adapter_type"),
                    "adapter_checkpoint_path": (adapter_summary or {}).get("adapter_checkpoint_path"),
                    "control_params_summary": (adapter_summary or {}).get("control_params"),
                    "adapter_override_reason": (adapter_summary or {}).get("override_reason"),
                    "adapter_fallback_reason": (adapter_summary or {}).get("adapter_fallback_reason"),
                    "audio_quality_summary": audio_quality_summary,
                    "audio_quality_report_path": audio_quality_report.get("report_path"),
                    "text_style_adapter_notice": "当前主链路默认启用 internal FiLM；TextStyleAdapter 仍负责提示词到 preset/参数的辅助映射，但真正的网络内 Bias/Scale 调制发生在 So-VITS-SVC 推理内部。",
                    "input_quality_summary": upload.input_quality_summary,
                    "input_quality_report_path": upload.input_quality_report_path,
                    "input_audio_path": upload.input_path,
                    "input_vocals_path": upload.vocals_path,
                    "effective_style_strength": round(effective_style_strength, 4),
                    "f0_method": (conversion_params_summary or {}).get("f0_method"),
                    "f0_fallback_reason": (conversion_params_summary or {}).get("f0_fallback_reason"),
                    "auto_predict_f0": (conversion_params_summary or {}).get("auto_predict_f0"),
                    "slice_db": (conversion_params_summary or {}).get("slice_db"),
                    "clip_seconds": (conversion_params_summary or {}).get("clip_seconds"),
                    "pad_seconds": (conversion_params_summary or {}).get("pad_seconds"),
                    "conversion_params_path": (conversion_params_summary or {}).get("conversion_params_path"),
                    "conversion_params_summary": conversion_params_summary,
                    "requested_model_preset_id": (conversion_params_summary or {}).get("requested_model_preset_id"),
                    "effective_model_preset_id": (conversion_params_summary or {}).get("effective_model_preset_id"),
                    "preset_fallback_used": (conversion_params_summary or {}).get("preset_fallback_used"),
                    "preset_fallback_reason": (conversion_params_summary or {}).get("preset_fallback_reason"),
                }
            )
            engine_details.setdefault("selected_output", output)
            engine_details.setdefault("final_output_path", output)

            task.status = "succeeded"
            task.stage = "completed"
            task.progress = 100
            task.message = "转换完成"
            task.output_path = output
            task.inference_mode = runtime_context.get("inference_mode")
            task.engine_details = engine_details
            self._write_task_config(
                debug_dir=debug_dir,
                task_id=task_id,
                task_backend_mode=task.task_backend_mode,
                requested_adapter_mode=requested_adapter_mode_label,
                effective_adapter_mode=effective_adapter_mode,
                output_path=output,
            )
            if os.path.abspath(output) != os.path.abspath(os.path.join(debug_dir, "converted.wav")):
                self._copy_file(debug_dir, output, "converted.wav")
            self._persist_task(task)
            return output
        except Exception as exc:
            task.status = "failed"
            task.stage = "failed"
            task.message = "转换失败"
            error_payload = self._normalize_error(exc)
            task.error = error_payload
            task.text_encoding = text_encoding_summary
            task.adapter_result = adapter_summary
            task.audio_quality = audio_quality_summary
            task.selected_style = selected_style
            if runtime_context:
                task.inference_mode = runtime_context.get("inference_mode", task.inference_mode)
                base_details = dict(runtime_context.get("runtime_config") or task.engine_details or {})
            else:
                base_details = dict(task.engine_details or {})
            base_details.update(
                {
                    "requested_adapter_mode": requested_adapter_mode_label,
                    "effective_adapter_mode": effective_adapter_mode,
                }
            )
            if text_encoding_summary:
                base_details.update(
                    {
                        "encoder_model_name": text_encoding_summary.get("encoder_model_name"),
                        "embedding_dim": text_encoding_summary.get("embedding_dim"),
                        "embedding_norm": text_encoding_summary.get("embedding_norm"),
                        "top_keywords": text_encoding_summary.get("top_keywords", []),
                        "style_prompt": resolved_style_prompt,
                        "style_emb_path": (style_embedding_paths or {}).get("style_embedding_pt"),
                        "style_embedding_json": (style_embedding_paths or {}).get("style_embedding_json"),
                        "style_embedding_npy": (style_embedding_paths or {}).get("style_embedding_npy"),
                        "text_encoding_status": text_encoding_summary.get("status"),
                        "text_encoding_enabled": bool(text_encoding_summary.get("enabled")),
                        "encoder_type": text_encoding_summary.get("encoder_type"),
                    }
                )
            if adapter_summary:
                base_details.update(
                    {
                        "adapter_enabled": bool(adapter_summary.get("adapter_enabled")),
                        "adapter_mode": adapter_summary.get("adapter_mode"),
                        "adapter_version": adapter_summary.get("adapter_version"),
                        "adapter_type": adapter_summary.get("adapter_type"),
                        "adapter_checkpoint_path": adapter_summary.get("adapter_checkpoint_path"),
                        "control_params_summary": adapter_summary.get("control_params"),
                        "adapter_override_reason": adapter_summary.get("override_reason"),
                        "adapter_fallback_reason": adapter_summary.get("adapter_fallback_reason"),
                    }
                )
            if conversion_params_summary:
                base_details.update(
                    {
                        "f0_method": conversion_params_summary.get("f0_method"),
                        "f0_fallback_reason": conversion_params_summary.get("f0_fallback_reason"),
                        "auto_predict_f0": conversion_params_summary.get("auto_predict_f0"),
                        "slice_db": conversion_params_summary.get("slice_db"),
                        "clip_seconds": conversion_params_summary.get("clip_seconds"),
                        "pad_seconds": conversion_params_summary.get("pad_seconds"),
                        "conversion_params_path": conversion_params_summary.get("conversion_params_path"),
                        "conversion_params_summary": conversion_params_summary,
                        "requested_model_preset_id": conversion_params_summary.get("requested_model_preset_id"),
                        "effective_model_preset_id": conversion_params_summary.get("effective_model_preset_id"),
                        "preset_fallback_used": conversion_params_summary.get("preset_fallback_used"),
                        "preset_fallback_reason": conversion_params_summary.get("preset_fallback_reason"),
                    }
                )
            base_details.setdefault("input_audio_path", upload.input_path)
            base_details.setdefault("input_vocals_path", upload.vocals_path)
            task.engine_details = base_details
            self._write_task_config(
                debug_dir=debug_dir,
                task_id=task_id,
                task_backend_mode=task.task_backend_mode,
                requested_adapter_mode=requested_adapter_mode_label,
                effective_adapter_mode=effective_adapter_mode,
                output_path=target_output,
            )
            self._write_json(debug_dir, "error.json", error_payload)
            self._persist_task(task)
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

    def _build_conversion_params_payload(self, runtime_preview: dict[str, Any], debug_dir: str) -> dict[str, Any]:
        return {
            "f0_method": runtime_preview.get("f0_method"),
            "f0_fallback_reason": runtime_preview.get("f0_fallback_reason"),
            "auto_predict_f0": runtime_preview.get("auto_predict_f0"),
            "transpose": runtime_preview.get("transpose"),
            "slice_db": runtime_preview.get("slice_db"),
            "clip_seconds": runtime_preview.get("clip_seconds"),
            "pad_seconds": runtime_preview.get("pad_seconds"),
            "model_preset_id": runtime_preview.get("model_preset_id"),
            "requested_model_preset_id": runtime_preview.get("requested_model_preset_id"),
            "effective_model_preset_id": runtime_preview.get("effective_model_preset_id"),
            "preset_fallback_used": runtime_preview.get("preset_fallback_used"),
            "preset_fallback_reason": runtime_preview.get("preset_fallback_reason"),
            "model_preset_ready": runtime_preview.get("model_preset_ready"),
            "model_preset_configured": runtime_preview.get("model_preset_configured"),
            "cli_passthrough": runtime_preview.get("cli_passthrough"),
            "cli_passthrough_notes": runtime_preview.get("cli_passthrough_notes"),
            "conversion_params_path": os.path.join(debug_dir, "conversion_params.json"),
        }

    def _write_json(self, debug_dir: str, filename: str, payload: Any) -> None:
        with open(os.path.join(debug_dir, filename), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def _write_task_config(
        self,
        *,
        debug_dir: str,
        task_id: str,
        task_backend_mode: str,
        requested_adapter_mode: str,
        effective_adapter_mode: str,
        output_path: str,
    ) -> None:
        self._write_json(
            debug_dir,
            "task_config.json",
            {
                "task_id": task_id,
                "task_backend_mode": task_backend_mode,
                "requested_adapter_mode": requested_adapter_mode,
                "effective_adapter_mode": effective_adapter_mode,
                "worker_pid": os.getpid(),
                "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
                "torch_cuda_available": self._torch_cuda_is_available(),
                "output_path": output_path,
            },
        )

    def _torch_cuda_is_available(self) -> bool:
        try:
            import torch
        except Exception:
            return False
        try:
            return bool(torch.cuda.is_available())
        except Exception:
            return False

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

    def _persist_task(self, task: TaskState) -> None:
        self._tasks[task.task_id] = task
        task_store.save_task(task.task_id, asdict(task))

    def _task_from_payload(self, payload: dict[str, Any]) -> TaskState:
        return TaskState(
            task_id=str(payload.get("task_id") or ""),
            status=str(payload.get("status") or "queued"),
            message=str(payload.get("message") or ""),
            engine=str(payload.get("engine") or "sovits"),
            vocals_id=str(payload.get("vocals_id") or ""),
            stage=str(payload.get("stage") or "uploaded"),
            progress=int(payload.get("progress", 0) or 0),
            output_path=payload.get("output_path"),
            error=payload.get("error"),
            selected_style=payload.get("selected_style"),
            inference_mode=payload.get("inference_mode"),
            engine_details=payload.get("engine_details"),
            reasons=list(payload.get("reasons") or []),
            task_backend_mode=str(payload.get("task_backend_mode") or "local"),
            text_encoding=payload.get("text_encoding"),
            adapter_result=payload.get("adapter_result"),
            audio_quality=payload.get("audio_quality"),
        )

    def _selected_style_payload(self, selected_style: dict[str, Any]) -> dict[str, Any]:
        return {
            "style_id": selected_style.get("style_id"),
            "description": selected_style.get("description"),
            "model_preset_id": selected_style.get("model_preset_id"),
            "model_display_name": selected_style.get("model_display_name"),
            "style_label": selected_style.get("style_label"),
            "model_path": selected_style.get("model_path"),
            "config_path": selected_style.get("config_path"),
            "speaker": selected_style.get("speaker"),
            "model_preset_ready": selected_style.get("model_preset_ready"),
            "model_preset_configured": selected_style.get("model_preset_configured"),
            "current_style_has_dedicated_model": selected_style.get("current_style_has_dedicated_model"),
            "model_preset_notice": selected_style.get("model_preset_notice"),
            "transpose": selected_style.get("transpose"),
            "match_score": selected_style.get("match_score", 0),
            "matched_keywords": selected_style.get("matched_keywords", []),
            "reason": selected_style.get("reason", ""),
            "adapter_override_reason": selected_style.get("adapter_override_reason"),
            "transpose_override_reason": selected_style.get("transpose_override_reason"),
            "adapter_control_params": selected_style.get("adapter_control_params"),
        }


svc_task_service = SvcTaskService()
