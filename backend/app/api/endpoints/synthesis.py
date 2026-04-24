
import os
import logging
# Must import multiprocess and set start method before torch or any cuda stuff is initialized
import multiprocessing as mp
try:
    mp.set_start_method('spawn', force=True)
except RuntimeError:
    pass

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, BackgroundTasks, Request
from fastapi.responses import FileResponse
import shutil
from app.models_svc.stylesinger_wrapper import stylesinger_service

router = APIRouter()
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMP_DIR = os.path.join(BASE_DIR, "data/temp")
OUTPUT_DIR = os.path.join(BASE_DIR, "data/processed")

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _save_upload_file(upload: UploadFile, task_id: str, prefix: str = "input") -> str:
    ext = (upload.filename or "wav").split(".")[-1].lower()
    input_path = os.path.join(TEMP_DIR, f"{task_id}_{prefix}.{ext}")
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    return input_path


def _task_output_path(task_id: str) -> str:
    return os.path.join(OUTPUT_DIR, f"{task_id}_out.wav")


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
    allow_generation, quality_reason = stylesinger_service._evaluate_feature_quality_gate(gate_metrics)
    if not allow_generation:
        logger.warning("Soft quality gate warning for synthesis request: %s | metrics=%s", quality_reason, gate_metrics)


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


@router.get("/health")
async def health(request: Request):
    stack = getattr(request.app.state, "enhanced_stack_status", stylesinger_service.get_enhanced_stack_status())
    return {
        "status": "ok",
        "service": "stylesinger-backend",
        "enhanced_ready": stack.get("ready", False),
    }


@router.get("/capabilities")
async def capabilities(request: Request):
    stack = getattr(request.app.state, "enhanced_stack_status", stylesinger_service.get_enhanced_stack_status())
    details = stack.get("details", {})
    return {
        "feature_extraction": {
            "legacy_ready": True,
            "enhanced_ready": stack.get("ready", False),
            "default_mode": stack.get("mode_default", "legacy"),
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


@router.post("/synthesize")
async def synthesize_voice(
    text: str = Form(...),
    style_strength: float = Form(0.6),
    ph_seq: str | None = Form(None),
    note_seq: str | None = Form(None),
    note_dur_seq: str | None = Form(None),
    note_type_seq: str | None = Form(None),
    is_vocal_only: bool = Form(False),
    ref_audio: UploadFile = File(...),
):
    score_payload = _build_score_payload(ph_seq, note_seq, note_dur_seq, note_type_seq)
    _log_soft_quality_gate(score_payload)

    try:
        task_id = stylesinger_service.create_task()
        ref_path = _save_upload_file(ref_audio, task_id, "ref")
        output_path = _task_output_path(task_id)
        stylesinger_service.process_task(
            task_id=task_id,
            style_strength=style_strength,
            text_prompt=text,
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
    is_vocal_only: bool = Form(False),
    lyrics: str = Form(""),
):
    """
    提取音频特征（音素、音高、时值、类型）
    前端上传源音频后，调用此接口一键回填。
    """
    from fastapi.concurrency import run_in_threadpool
    try:
        task_id = stylesinger_service.create_task()
        audio_path = _save_upload_file(audio, task_id, "extract")
        
        features = await run_in_threadpool(
            stylesinger_service.extract_features,
            audio_path,
            prompt_text,
            is_vocal_only,
            lyrics,
        )
        
        # 格式化为前端期望的逗号分隔字符串格式
        formatted_features = {
            "ph": ",".join(str(x) for x in features["ph"]),
            "note": ",".join(str(x) for x in features["note"]),
            "note_dur": ",".join(str(x) for x in features["note_dur"]),
            "note_type": ",".join(str(x) for x in features["note_type"]),
            "quality_ok": features.get("quality_ok", True),
            "quality_reason": features.get("quality_reason", ""),
            "metrics": features.get("metrics", {}),
        }
        
        # 立即清理临时文件
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
        return formatted_features
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
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
    style_strength: float = Form(0.6),
    ph_seq: str | None = Form(None),
    note_seq: str | None = Form(None),
    note_dur_seq: str | None = Form(None),
    note_type_seq: str | None = Form(None),
    is_vocal_only: bool = Form(False),
    ref_audio: UploadFile = File(...),
):
    score_payload = _build_score_payload(ph_seq, note_seq, note_dur_seq, note_type_seq)
    _log_soft_quality_gate(score_payload)

    task_id = stylesinger_service.create_task()
    ref_path = _save_upload_file(ref_audio, task_id, "ref")
    output_path = _task_output_path(task_id)
    background_tasks.add_task(
        stylesinger_service.process_task,
        task_id=task_id,
        style_strength=style_strength,
        text_prompt=text,
        ref_audio_path=ref_path,
        output_path=output_path,
        score_payload=score_payload,
        is_vocal_only=is_vocal_only,
    )
    return {"task_id": task_id, "status": "queued"}


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    task = stylesinger_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    result_url = f"/api/v1/tasks/{task_id}/result" if task.status == "completed" else None
    return {
        "task_id": task.task_id,
        "status": task.status,
        "message": task.message,
        "result_url": result_url,
        "error": task.error,
    }


@router.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str):
    task = stylesinger_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if task.status != "completed" or not task.output_path or not os.path.exists(task.output_path):
        raise HTTPException(status_code=409, detail="task not completed")
    return FileResponse(task.output_path, media_type="audio/wav", filename=os.path.basename(task.output_path))
