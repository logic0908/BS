
import os
import logging
import json
# Must import multiprocess and set start method before torch or any cuda stuff is initialized
import multiprocessing as mp
try:
    mp.set_start_method('spawn', force=True)
except RuntimeError:
    pass

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, BackgroundTasks, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
import shutil
from app.models_svc.stylesinger_wrapper import STYLE_FEATURE_HARD_GATE, stylesinger_service
from app.services.system_status import collect_app_health, collect_sovits_check
from app.services.svc_task_service import svc_task_service

router = APIRouter()
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMP_DIR = os.path.join(BASE_DIR, "data/temp")
OUTPUT_DIR = os.path.join(BASE_DIR, "data/processed")

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


class ConvertRequest(BaseModel):
    vocals_id: str
    prompt_text: str
    style_strength: float = 0.6
    style_preset_id: str | None = None
    model_preset_id: str | None = None
    engine: str = "sovits"


def _save_upload_file(upload: UploadFile, task_id: str, prefix: str = "input") -> str:
    ext = (upload.filename or "wav").split(".")[-1].lower()
    input_path = os.path.join(TEMP_DIR, f"{task_id}_{prefix}.{ext}")
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    return input_path


def _task_output_path(task_id: str) -> str:
    return os.path.join(OUTPUT_DIR, f"{task_id}_out.wav")


def _ascii_header_value(value: object) -> str:
    if value is None:
        return ""
    return str(value).encode("ascii", errors="ignore").decode("ascii")


def _safe_result_filename(task_id: str) -> str:
    return f"converted_{task_id}.wav"


def _parse_float_list(raw: str | None) -> list[float] | None:
    if raw is None or raw.strip() == "":
        return None
    return [float(x.strip()) for x in raw.split(",") if x.strip() != ""]


def _parse_int_list(raw: str | None) -> list[int] | None:
    if raw is None or raw.strip() == "":
        return None
    return [int(float(x.strip())) for x in raw.split(",") if x.strip() != ""]


def _parse_str_list(raw: str | None) -> list[str] | None:
    if raw is None or raw.strip() == "":
        return None
    return [x.strip() for x in raw.split(",") if x.strip() != ""]


def _build_score_payload(
    ph_seq: str | None,
    note_seq: str | None,
    note_dur_seq: str | None,
    note_type_seq: str | None,
) -> dict | None:
    parsed = {
        "ph": _parse_str_list(ph_seq),
        "note": _parse_int_list(note_seq),
        "note_dur": _parse_float_list(note_dur_seq),
        "note_type": _parse_int_list(note_type_seq),
    }
    if not any(v is not None for v in parsed.values()):
        return None
    return parsed


def _log_soft_quality_gate(score_payload: dict | None) -> None:
    if not score_payload:
        return

    seq_ph, seq_note, seq_dur, seq_type = stylesinger_service._sanitize_feature_sequences(
        score_payload.get("ph", []),
        score_payload.get("note", []),
        score_payload.get("note_dur", []),
        score_payload.get("note_type", []),
    )
    gate_metrics = stylesinger_service._compute_feature_quality_metrics(seq_ph, seq_note, seq_dur, seq_type)
    allow_generation, quality_reason, _reasons = stylesinger_service._evaluate_feature_quality_gate_detailed(
        gate_metrics,
        ph_seq=seq_ph,
        note_seq=seq_note,
        dur_seq=seq_dur,
        type_seq=seq_type,
    )
    if not allow_generation:
        logger.warning("Soft quality gate warning for synthesis request: %s | metrics=%s", quality_reason, gate_metrics)


def _feature_gate_detail(validation: dict) -> dict:
    return {
        "ok": False,
        "code": "FEATURE_QUALITY_GATE_FAILED",
        "message": "当前提取的四维特征可信度较低，已停止转换。",
        "reasons": validation.get("reasons", []),
        "quality": validation.get("quality", {}),
        "features_preview": validation.get("features_preview", {}),
    }


def _enhanced_error_detail(
    message: str,
    missing: list[str] | None = None,
    error_code: str = "ENHANCED_STACK_MISSING_DEPENDENCY",
) -> dict:
    return {
        "error_code": error_code,
        "message": message,
        "missing": missing or [],
        "enhanced_ready": False,
    }


def _normalize_svc_task_payload(task_id: str, task) -> dict:
    result_url = f"/api/v1/tasks/{task_id}/result" if task.status == "succeeded" else None
    result_metadata = dict(task.engine_details or {})
    return {
        "task_id": task.task_id,
        "engine": task.engine,
        "status": task.status,
        "progress": getattr(task, "progress", 0),
        "stage": getattr(task, "stage", "uploaded"),
        "message": task.message,
        "selected_style": task.selected_style,
        "result_url": result_url,
        "error": task.error,
        "inference_mode": task.inference_mode,
        "engine_details": task.engine_details,
        "result_metadata": result_metadata,
        "mock_enabled": result_metadata.get("mock_enabled"),
        "model_path": result_metadata.get("model_path"),
        "config_path": result_metadata.get("config_path"),
        "speaker": result_metadata.get("speaker"),
        "model_preset_id": result_metadata.get("model_preset_id"),
        "model_display_name": result_metadata.get("model_display_name"),
        "source_repo": result_metadata.get("source_repo"),
        "license": result_metadata.get("license"),
        "model_path_basename": result_metadata.get("model_path_basename"),
        "config_path_basename": result_metadata.get("config_path_basename"),
        "is_demo_quality": result_metadata.get("is_demo_quality"),
        "is_technical_validation_only": result_metadata.get("is_technical_validation_only"),
        "device": result_metadata.get("device"),
        "selected_output": result_metadata.get("selected_output"),
        "final_output_path": result_metadata.get("final_output_path"),
        "return_code": result_metadata.get("return_code"),
        "elapsed_seconds": result_metadata.get("elapsed_seconds"),
        "sovits_command_debug_path": result_metadata.get("sovits_command_debug_path"),
        "reasons": getattr(task, "reasons", []),
        "legacy_status": "completed" if task.status == "succeeded" else task.status,
    }


def _normalize_stylesinger_task_payload(task_id: str, task) -> dict:
    status_map = {
        "queued": ("queued", 0, "uploaded"),
        "separating_vocals": ("running", 35, "separated"),
        "running": ("running", 85, "inference_running"),
        "completed": ("succeeded", 100, "completed"),
        "failed": ("failed", 100, "failed"),
    }
    status, progress, stage = status_map.get(task.status, ("running", 50, "inference_running"))
    result_url = f"/api/v1/tasks/{task_id}/result" if task.status == "completed" else None
    return {
        "task_id": task.task_id,
        "engine": "stylesinger",
        "status": status,
        "progress": progress,
        "stage": stage,
        "message": task.message,
        "selected_style": None,
        "result_url": result_url,
        "error": task.error,
        "reasons": getattr(task, "reasons", []),
        "legacy_status": task.status,
    }


@router.get("/health")
async def health(request: Request):
    stack = getattr(request.app.state, "enhanced_stack_status", stylesinger_service.get_enhanced_stack_status())
    return {
        "status": "ok",
        "service": "stylesinger-backend",
        "enhanced_ready": stack.get("ready", False),
        "ok": True,
    }


@router.get("/system/health")
async def system_health():
    return collect_app_health()


@router.get("/system/sovits-check")
async def system_sovits_check():
    return collect_sovits_check()


@router.get("/capabilities")
async def capabilities(request: Request):
    stack = getattr(request.app.state, "enhanced_stack_status", stylesinger_service.get_enhanced_stack_status())
    details = stack.get("details", {})
    return {
        "feature_extraction": {
            "legacy_ready": True,
            "enhanced_ready": stack.get("ready", False),
            "default_mode": stack.get("mode_default", "legacy"),
            "style_feature_hard_gate": STYLE_FEATURE_HARD_GATE,
            "missing_dependencies": stack.get("missing", []),
            "numpy_version": details.get("numpy_version", ""),
            "tensorflow_installed": details.get("tensorflow_installed", False),
            "ml_dtypes_installed": details.get("ml_dtypes_installed", False),
            "whisperx_runtime_ok": details.get("whisperx_runtime_ok", False),
            "whisperx_runtime_reason": details.get("whisperx_runtime_reason", ""),
            "rmvpe_ready": details.get("rmvpe_ready", False),
            "rmvpe_python_path": details.get("rmvpe_python_path", ""),
            "rmvpe_module_source": details.get("rmvpe_module_source", "missing"),
            "rmvpe_module_path": details.get("rmvpe_module_path", ""),
            "rmvpe_vendored_path": details.get("rmvpe_vendored_path", ""),
            "ffmpeg_available": details.get("ffmpeg_available", False),
            "rmvpe_model_path": details.get("rmvpe_model_path", ""),
            "rmvpe_model_exists": details.get("rmvpe_model_exists", False),
        }
    }


@router.post("/upload")
async def upload_audio(
    audio: UploadFile = File(...),
    is_vocal_only: bool = Form(False),
):
    try:
        vocals_id = str(os.urandom(8).hex())
        input_path = _save_upload_file(audio, vocals_id, "upload")
        upload_record = svc_task_service.create_upload(input_path, is_vocal_only=is_vocal_only)
        return {
            "vocals_id": upload_record.vocals_id,
            "status": "ready",
            "is_vocal_only": upload_record.is_vocal_only,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"上传音频失败: {exc}") from exc


@router.post("/convert")
async def convert_audio(
    request: ConvertRequest,
    background_tasks: BackgroundTasks,
):
    upload = svc_task_service.get_upload(request.vocals_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="vocals_id not found")

    task_id = svc_task_service.create_task(request.vocals_id, engine=request.engine or "sovits")
    background_tasks.add_task(
        svc_task_service.process_task,
        task_id=task_id,
        prompt_text=request.prompt_text,
        style_strength=request.style_strength,
        style_preset_id=request.style_preset_id,
        model_preset_id=request.model_preset_id,
    )
    return {
        "task_id": task_id,
        "status": "queued",
        "engine": request.engine or "sovits",
    }


@router.post("/synthesize")
async def synthesize_voice(
    text: str = Form(...),
    prompt_text: str = Form(""),
    style_prompt: str = Form(""),
    style_strength: float = Form(0.6),
    ph_seq: str | None = Form(None),
    note_seq: str | None = Form(None),
    note_dur_seq: str | None = Form(None),
    note_type_seq: str | None = Form(None),
    is_vocal_only: bool = Form(False),
    ref_audio: UploadFile = File(...),
):
    text_prompt = prompt_text or style_prompt or text
    logger.info("synthesize received prompt_text='%s'", text_prompt)
    score_payload = _build_score_payload(ph_seq, note_seq, note_dur_seq, note_type_seq)

    try:
        task_id = stylesinger_service.create_task()
        ref_path = _save_upload_file(ref_audio, task_id, "ref")
        validation = stylesinger_service.validate_score_payload(
            score_payload,
            audio_path=ref_path,
            prompt_text=text_prompt,
            debug_id=task_id,
        )
        if score_payload and not validation["ok"] and STYLE_FEATURE_HARD_GATE:
            raise HTTPException(status_code=422, detail=_feature_gate_detail(validation))
        output_path = _task_output_path(task_id)
        stylesinger_service.process_task(
            task_id=task_id,
            style_strength=style_strength,
            text_prompt=text_prompt,
            ref_audio_path=ref_path,
            output_path=output_path,
            score_payload=score_payload,
            is_vocal_only=is_vocal_only,
        )
        task = stylesinger_service.get_task(task_id)
        if not task or task.status != "completed":
            raise RuntimeError(task.error if task and task.error else "synthesis failed")
        return FileResponse(output_path, media_type="audio/wav", filename=os.path.basename(output_path))
    except HTTPException:
        raise
    except RuntimeError as e:
        message = str(e)
        missing = []
        error_code = "ENHANCED_STACK_MISSING_DEPENDENCY"
        if "whisperx" in message:
            missing = ["whisperx"]
        elif "NumPy / TensorFlow ABI conflict" in message or "numpy.core.umath failed to import" in message:
            missing = ["whisperx_runtime"]
            error_code = "ENHANCED_STACK_ENV_CONFLICT"
        elif "rmvpe" in message:
            missing = ["rmvpe"]
        elif "RMVPE_MODEL_PATH" in message:
            missing = ["RMVPE_MODEL_PATH"]
        elif "ffmpeg" in message:
            missing = ["ffmpeg"]
        raise HTTPException(status_code=422, detail=_enhanced_error_detail(message, missing, error_code=error_code))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract_features")
async def extract_features(
    audio: UploadFile = File(...),
    prompt_text: str = Form(""),
    style_prompt: str = Form(""),
    is_vocal_only: bool = Form(False),
    lyrics: str = Form(""),
    feature_mode: str | None = Form(None),
):
    """
    提取音频特征（音素、音高、时值、类型）
    前端上传源音频后，调用此接口一键回填。
    """
    try:
        prompt = prompt_text or style_prompt
        logger.info("extract_features received prompt_text='%s'", prompt)
        task_id = stylesinger_service.create_task()
        audio_path = _save_upload_file(audio, task_id, "extract")
        
        features = stylesinger_service.extract_features(
            audio_path,
            prompt,
            is_vocal_only,
            lyrics,
            task_id,
            audio.filename,
            feature_mode,
        )
        
        # 格式化为前端期望的逗号分隔字符串格式
        feature_values = features.get("features") if isinstance(features.get("features"), dict) else features
        quality = features.get("quality") or features.get("metrics") or {}
        formatted_features = {
            "ok": features.get("ok", features.get("quality_ok", True)),
            "hard_gate_enabled": STYLE_FEATURE_HARD_GATE,
            "code": features.get("code"),
            "message": features.get("message"),
            "reasons": features.get("reasons", quality.get("hard_gate_reasons", [])),
            "source": features.get("source", "legacy"),
            "ph": ",".join(str(x) for x in feature_values["ph"]),
            "note": ",".join(str(x) for x in feature_values["note"]),
            "note_dur": ",".join(str(x) for x in feature_values["note_dur"]),
            "note_type": ",".join(str(x) for x in feature_values["note_type"]),
            "quality_ok": features.get("quality_ok", True),
            "quality_reason": features.get("quality_reason", ""),
            "quality": quality,
            "metrics": quality,
            "features": features,
            "debug_artifacts": {
                "extracted_features": f"/runtime/debug/{task_id}/extracted_features.sanitized.json",
                "quality_report": f"/runtime/debug/{task_id}/quality_report.json",
            },
        }
        
        # 立即清理临时文件
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
        return formatted_features
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"特征提取失败: {e}\n{traceback.format_exc()}")
        # 如果文件存在，也要清理
        if 'audio_path' in locals() and os.path.exists(audio_path):
            os.remove(audio_path)
        raise HTTPException(status_code=500, detail=f"音频特征提取失败: {str(e)}")

@router.post("/analyze_audio")
async def analyze_audio(
    audio: UploadFile = File(...),
    is_vocal_only: bool = Form(False),
    lyrics: str = Form(""),
):
    try:
        # 生成临时文件
        task_id = stylesinger_service.create_task()
        audio_path = _save_upload_file(audio, task_id, "analyze")
        
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("Analyze audio request received. vocal_only=%s", is_vocal_only)
            
        import subprocess
        import sys
        import json
        
        script_path = os.path.join(TEMP_DIR, f"{task_id}_extract.py")
        with open(script_path, "w") as f:
            f.write(f"""
import sys
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""
# 获取 backend 的根目录
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, backend_dir)
from app.models_svc.stylesinger_wrapper import StyleSingerService
svc = StyleSingerService()
features = svc.extract_features('{audio_path}', is_vocal_only={str(is_vocal_only)}, transcript_hint={lyrics!r})
import json
print("###JSON_START###")
print(json.dumps(features))
print("###JSON_END###")
""")
        
        # 使用独立的进程执行，避免干扰当前 uvicorn 进程的 CUDA 状态
        import shlex
        import os
        cmd = f"CUDA_VISIBLE_DEVICES='' {sys.executable} {shlex.quote(script_path)}"
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        stdout, stderr = proc.communicate()
        
        if os.path.exists(script_path):
            os.remove(script_path)
            
        if proc.returncode != 0:
            raise RuntimeError(f"提取特征失败: {stderr.decode('utf-8')}")
            
        try:
            json_str = stdout.decode('utf-8').split("###JSON_START###")[1].split("###JSON_END###")[0].strip()
            features = json.loads(json_str)
        except Exception:
            raise RuntimeError(f"无法解析特征数据: {stdout.decode('utf-8')}")
        
        # 格式化为逗号分隔的字符串
        formatted_features = {
            "ph_seq": ",".join(str(x) for x in features["ph"]),
            "note_seq": ",".join(str(x) for x in features["note"]),
            "note_dur_seq": ",".join(str(x) for x in features["note_dur"]),
            "note_type_seq": ",".join(str(x) for x in features["note_type"]),
        }
        
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
        return formatted_features
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析音频失败: {str(e)}")

@router.post("/tasks")
async def create_synthesis_task(
    background_tasks: BackgroundTasks,
    text: str = Form(...),
    prompt_text: str = Form(""),
    style_prompt: str = Form(""),
    style_strength: float = Form(0.6),
    ph_seq: str | None = Form(None),
    note_seq: str | None = Form(None),
    note_dur_seq: str | None = Form(None),
    note_type_seq: str | None = Form(None),
    is_vocal_only: bool = Form(False),
    ref_audio: UploadFile = File(...),
):
    text_prompt = prompt_text or style_prompt or text
    logger.info("create task received prompt_text='%s'", text_prompt)
    score_payload = _build_score_payload(ph_seq, note_seq, note_dur_seq, note_type_seq)

    task_id = stylesinger_service.create_task()
    ref_path = _save_upload_file(ref_audio, task_id, "ref")
    validation = stylesinger_service.validate_score_payload(
        score_payload,
        audio_path=ref_path,
        prompt_text=text_prompt,
        debug_id=task_id,
    )
    if score_payload and not validation["ok"] and STYLE_FEATURE_HARD_GATE:
        task = stylesinger_service.get_task(task_id)
        if task is not None:
            task.status = "failed"
            task.message = "当前提取的四维特征可信度较低，已停止转换。"
            task.reasons = validation.get("reasons", [])
            task.error = json.dumps(_feature_gate_detail(validation), ensure_ascii=False)
        stylesinger_service._write_debug_json(task_id, "error.json", _feature_gate_detail(validation))
        raise HTTPException(status_code=422, detail=_feature_gate_detail(validation))
    output_path = _task_output_path(task_id)
    background_tasks.add_task(
        stylesinger_service.process_task,
        task_id=task_id,
        style_strength=style_strength,
        text_prompt=text_prompt,
        ref_audio_path=ref_path,
        output_path=output_path,
        score_payload=score_payload,
        is_vocal_only=is_vocal_only,
    )
    return {"task_id": task_id, "status": "queued"}


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    task = svc_task_service.get_task(task_id)
    if task is not None:
        return _normalize_svc_task_payload(task_id, task)

    task = stylesinger_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return _normalize_stylesinger_task_payload(task_id, task)


@router.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str):
    task = svc_task_service.get_task(task_id)
    if task is not None:
        if task.status == "failed":
            detail = {"message": task.message, "error": task.error, "reasons": getattr(task, "reasons", [])}
            raise HTTPException(status_code=409, detail=detail)
        if task.status != "succeeded" or not task.output_path or not os.path.exists(task.output_path):
            raise HTTPException(status_code=409, detail="task not completed")
        metadata = dict(task.engine_details or {})
        headers = {
            "X-Task-Id": _ascii_header_value(task_id),
            "X-Inference-Mode": _ascii_header_value(metadata.get("inference_mode") or task.inference_mode or ""),
            "X-Model-Preset-Id": _ascii_header_value(metadata.get("model_preset_id") or ""),
            "X-Speaker": _ascii_header_value(metadata.get("speaker") or ""),
        }
        return FileResponse(
            task.output_path,
            media_type="audio/wav",
            filename=_safe_result_filename(task_id),
            headers=headers,
        )

    task = stylesinger_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if task.status == "failed":
        detail = {"message": task.message, "error": task.error, "reasons": getattr(task, "reasons", [])}
        raise HTTPException(status_code=409, detail=detail)
    if task.status != "completed" or not task.output_path or not os.path.exists(task.output_path):
        raise HTTPException(status_code=409, detail="task not completed")
    return FileResponse(task.output_path, media_type="audio/wav", filename=_safe_result_filename(task_id))
