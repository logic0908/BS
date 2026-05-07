from __future__ import annotations

try:  # pragma: no cover - import path differs between app runtime and celery CLI
    from app.core.celery_app import celery_app
    from app.services.svc_task_service import svc_task_service
except ModuleNotFoundError:  # pragma: no cover
    from backend.app.core.celery_app import celery_app
    from backend.app.services.svc_task_service import svc_task_service


@celery_app.task(name="svc.process_task", queue="svc")
def process_svc_task(
    task_id: str,
    prompt_text: str,
    style_strength: float,
    style_preset_id: str | None = None,
    model_preset_id: str | None = None,
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
    return svc_task_service.process_task(
        task_id=task_id,
        prompt_text=prompt_text,
        style_strength=style_strength,
        style_preset_id=style_preset_id,
        model_preset_id=model_preset_id,
        transpose=transpose,
        f0_method=f0_method,
        auto_predict_f0=auto_predict_f0,
        slice_db=slice_db,
        clip_seconds=clip_seconds,
        pad_seconds=pad_seconds,
        allow_preset_fallback=allow_preset_fallback,
        output_path=output_path,
        requested_adapter_mode=requested_adapter_mode,
    )
