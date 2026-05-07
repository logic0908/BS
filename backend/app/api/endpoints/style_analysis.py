from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.audio_style_analysis import AudioStyleAnalysisError, compare_audio_style
from app.services.svc_task_service import svc_task_service


router = APIRouter()

APP_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = APP_DIR.parents[1]
UPLOADS_DIR = APP_DIR / "data" / "uploads"
PROCESSED_DIR = APP_DIR / "data" / "processed"
RUNTIME_DEBUG_DIR = PROJECT_ROOT / "runtime" / "debug"
URL_PREFIXES = {
    "/files/uploads/": UPLOADS_DIR,
    "/files/vocals/": UPLOADS_DIR,
    "/files/outputs/": PROCESSED_DIR,
}
TASK_RESULT_PATTERN = re.compile(r"^/api/v1/tasks/(?P<task_id>[^/]+)/result$")


class StyleAnalysisCompareRequest(BaseModel):
    input_url: str | None = None
    output_url: str | None = None
    input_path: str | None = None
    output_path: str | None = None
    prompt_text: str
    model_preset_id: str | None = None


@router.post("/style-analysis/compare")
async def compare_style_analysis(request: StyleAnalysisCompareRequest):
    try:
        input_path = resolve_analysis_path(request.input_path, request.input_url, field_name="input")
        output_path = resolve_analysis_path(request.output_path, request.output_url, field_name="output")
        return compare_audio_style(
            input_audio_path=input_path,
            output_audio_path=output_path,
            prompt_text=request.prompt_text,
            model_preset_id=request.model_preset_id,
        )
    except AudioStyleAnalysisError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_dict()) from exc


def resolve_analysis_path(local_path: str | None, url_path: str | None, *, field_name: str) -> Path:
    if local_path:
        return validate_allowed_path(Path(local_path), field_name=field_name)
    if url_path:
        return resolve_analysis_url(url_path, field_name=field_name)
    raise AudioStyleAnalysisError(
        "STYLE_ANALYSIS_PATH_MISSING",
        f"{field_name}_path 或 {field_name}_url 至少需要提供一个。",
        status_code=422,
    )


def resolve_analysis_url(url_path: str, *, field_name: str) -> Path:
    normalized = str(url_path).strip()
    task_match = TASK_RESULT_PATTERN.match(normalized)
    if task_match:
        task_id = task_match.group("task_id")
        task = svc_task_service.get_task(task_id)
        if task is None or not task.output_path:
            raise AudioStyleAnalysisError(
                "STYLE_ANALYSIS_TASK_OUTPUT_NOT_FOUND",
                f"无法根据任务结果 URL 解析 {field_name} 音频路径。",
                status_code=404,
                details={"task_id": task_id},
            )
        return validate_allowed_path(Path(task.output_path), field_name=field_name)

    for prefix, base_dir in URL_PREFIXES.items():
        if normalized.startswith(prefix):
            suffix = normalized[len(prefix) :].lstrip("/")
            if prefix == "/files/outputs/":
                return resolve_output_url(suffix, field_name=field_name)
            return validate_allowed_path(base_dir / suffix, field_name=field_name)

    raise AudioStyleAnalysisError(
        "STYLE_ANALYSIS_URL_FORBIDDEN",
        f"{field_name}_url 不在允许的文件映射范围内。",
        status_code=403,
        details={"url": normalized},
    )


def validate_allowed_path(path: Path, *, field_name: str) -> Path:
    resolved = path.expanduser().resolve()
    if _is_within(resolved, UPLOADS_DIR) or _is_within(resolved, PROCESSED_DIR):
        return resolved
    if _is_allowed_task_debug_output(resolved):
        return resolved
    raise AudioStyleAnalysisError(
        "STYLE_ANALYSIS_PATH_FORBIDDEN",
        f"{field_name} 路径不在允许目录内。",
        status_code=403,
        details={"path": str(resolved)},
    )


def resolve_output_url(relative_path: str, *, field_name: str) -> Path:
    suffix = Path(relative_path)
    debug_candidate = RUNTIME_DEBUG_DIR / suffix
    resolved_debug = debug_candidate.expanduser().resolve()
    if _is_allowed_task_debug_output(resolved_debug):
        return resolved_debug

    processed_candidate = PROCESSED_DIR / suffix
    if _is_within(processed_candidate.expanduser().resolve(), PROCESSED_DIR):
        return processed_candidate.expanduser().resolve()

    raise AudioStyleAnalysisError(
        "STYLE_ANALYSIS_OUTPUT_URL_FORBIDDEN",
        f"{field_name}_url 不是允许的任务输出路径。",
        status_code=403,
        details={"path": str(resolved_debug)},
    )


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _is_allowed_task_debug_output(path: Path) -> bool:
    if not _is_within(path, RUNTIME_DEBUG_DIR):
        return False
    try:
        relative = path.relative_to(RUNTIME_DEBUG_DIR.resolve())
    except ValueError:
        return False
    if len(relative.parts) < 2:
        return False

    task_id = relative.parts[0]
    task = svc_task_service.get_task(task_id)
    if task is None:
        return False

    candidate_paths = {
        task.output_path,
        (task.engine_details or {}).get("final_output_path"),
        str(RUNTIME_DEBUG_DIR / task_id / "converted.wav"),
    }
    for candidate in candidate_paths:
        if not candidate:
            continue
        if Path(candidate).expanduser().resolve() == path:
            return True
    return False
