from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

try:
    import redis
except ModuleNotFoundError:  # pragma: no cover - dependency is optional at import time
    redis = None


logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_DIR.parents[1]
TASK_STORE_ROOT = Path(os.environ.get("TASK_STORE_DIR", str(PROJECT_ROOT / "runtime" / "task_store")))
TASK_STATE_DIR = TASK_STORE_ROOT / "tasks"
UPLOAD_STATE_DIR = TASK_STORE_ROOT / "uploads"


class TaskStore:
    def __init__(self) -> None:
        self.redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self._redis_client = None
        TASK_STATE_DIR.mkdir(parents=True, exist_ok=True)
        UPLOAD_STATE_DIR.mkdir(parents=True, exist_ok=True)

    def save_upload(self, vocals_id: str, payload: dict[str, Any]) -> None:
        normalized = dict(payload)
        self._write_json(UPLOAD_STATE_DIR / f"{vocals_id}.json", normalized)
        self._redis_set(self._upload_key(vocals_id), normalized)

    def load_upload(self, vocals_id: str) -> dict[str, Any] | None:
        payload = self._redis_get(self._upload_key(vocals_id))
        if payload is not None:
            return payload
        return self._read_json(UPLOAD_STATE_DIR / f"{vocals_id}.json")

    def save_task(self, task_id: str, payload: dict[str, Any]) -> None:
        normalized = dict(payload)
        self._write_json(TASK_STATE_DIR / f"{task_id}.json", normalized)
        self._redis_set(self._task_key(task_id), normalized)

    def load_task(self, task_id: str) -> dict[str, Any] | None:
        payload = self._redis_get(self._task_key(task_id))
        if payload is not None:
            return payload
        return self._read_json(TASK_STATE_DIR / f"{task_id}.json")

    def _redis(self):
        if redis is None:
            return None
        if self._redis_client is None:
            self._redis_client = redis.Redis.from_url(self.redis_url, decode_responses=True)
        return self._redis_client

    def _redis_set(self, key: str, payload: dict[str, Any]) -> None:
        client = self._redis()
        if client is None:
            return
        try:
            client.set(key, json.dumps(payload, ensure_ascii=False))
        except Exception as exc:  # pragma: no cover - depends on external Redis availability
            logger.warning("TaskStore redis set failed for %s: %s", key, exc)

    def _redis_get(self, key: str) -> dict[str, Any] | None:
        client = self._redis()
        if client is None:
            return None
        try:
            raw = client.get(key)
        except Exception as exc:  # pragma: no cover - depends on external Redis availability
            logger.warning("TaskStore redis get failed for %s: %s", key, exc)
            return None
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _task_key(self, task_id: str) -> str:
        return f"svc:task:{task_id}"

    def _upload_key(self, vocals_id: str) -> str:
        return f"svc:upload:{vocals_id}"


task_store = TaskStore()
