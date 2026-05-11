from __future__ import annotations

import os

from celery import Celery


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


celery_app = Celery(
    "bs_svc",
    broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
)
celery_app.conf.update(
    task_default_queue="svc",
    task_routes={"svc.process_task": {"queue": "svc"}},
    task_always_eager=_env_flag("CELERY_TASK_ALWAYS_EAGER", False),
    task_store_eager_result=True,
    task_ignore_result=False,
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    broker_connection_retry_on_startup=True,
)

try:  # pragma: no cover - import path differs between app runtime and celery CLI
    from app.workers import svc_tasks as _svc_tasks  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    from backend.app.workers import svc_tasks as _svc_tasks  # noqa: F401
