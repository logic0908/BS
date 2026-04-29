from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_DIR.parents[1]
PRESETS_PATH = Path(
    os.environ.get(
        "SVC_MODEL_PRESETS_PATH",
        str(APP_DIR / "config" / "svc_model_presets.json"),
    )
)


@dataclass(frozen=True)
class SvcModelPreset:
    preset_id: str
    display_name: str
    description: str
    model_path: str
    config_path: str
    speaker: str
    device: str = "cuda"
    is_demo_quality: bool = False
    is_technical_validation_only: bool = False
    source_repo: str = ""
    license: str = ""
    transpose: int = 0

    @property
    def model_path_basename(self) -> str:
        return Path(self.model_path).name if self.model_path else ""

    @property
    def config_path_basename(self) -> str:
        return Path(self.config_path).name if self.config_path else ""

    def to_runtime_dict(self) -> dict[str, Any]:
        return {
            "model_preset_id": self.preset_id,
            "model_display_name": self.display_name,
            "model_description": self.description,
            "model_path": self.model_path,
            "config_path": self.config_path,
            "speaker": self.speaker,
            "device": self.device,
            "transpose": self.transpose,
            "source_repo": self.source_repo,
            "license": self.license,
            "model_path_basename": self.model_path_basename,
            "config_path_basename": self.config_path_basename,
            "is_demo_quality": self.is_demo_quality,
            "is_technical_validation_only": self.is_technical_validation_only,
        }

    def readiness(self) -> dict[str, Any]:
        model_exists = bool(self.model_path and Path(self.model_path).exists())
        config_exists = bool(self.config_path and Path(self.config_path).exists())
        return {
            "preset_id": self.preset_id,
            "display_name": self.display_name,
            "ready": model_exists and config_exists and bool(self.speaker),
            "model_exists": model_exists,
            "config_exists": config_exists,
            "speaker": self.speaker,
            "source_repo": self.source_repo,
            "license": self.license,
            "is_demo_quality": self.is_demo_quality,
            "is_technical_validation_only": self.is_technical_validation_only,
        }


def load_presets_payload() -> dict[str, Any]:
    if not PRESETS_PATH.exists():
        return _default_payload()
    with PRESETS_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("svc_model_presets.json root must be an object")
    payload.setdefault("active_preset_id", "tech_villager")
    payload.setdefault("fallback_preset_id", "tech_villager")
    payload.setdefault("presets", [])
    return payload


def load_presets() -> dict[str, SvcModelPreset]:
    payload = load_presets_payload()
    presets: dict[str, SvcModelPreset] = {}
    for raw in payload.get("presets", []):
        if not isinstance(raw, dict):
            continue
        preset_id = str(raw.get("preset_id") or "").strip()
        if not preset_id:
            continue
        presets[preset_id] = SvcModelPreset(
            preset_id=preset_id,
            display_name=str(raw.get("display_name") or preset_id),
            description=str(raw.get("description") or ""),
            model_path=str(raw.get("model_path") or ""),
            config_path=str(raw.get("config_path") or ""),
            speaker=str(raw.get("speaker") or ""),
            device=str(raw.get("device") or "cuda"),
            is_demo_quality=bool(raw.get("is_demo_quality")),
            is_technical_validation_only=bool(raw.get("is_technical_validation_only")),
            source_repo=str(raw.get("source_repo") or ""),
            license=str(raw.get("license") or ""),
            transpose=int(raw.get("transpose", 0) or 0),
        )
    return presets


def active_preset_id() -> str:
    return str(load_presets_payload().get("active_preset_id") or "tech_villager")


def fallback_preset_id() -> str:
    return str(load_presets_payload().get("fallback_preset_id") or "tech_villager")


def resolve_preset(preset_id: str | None = None) -> SvcModelPreset | None:
    presets = load_presets()
    selected_id = (preset_id or active_preset_id()).strip()
    if selected_id and selected_id in presets:
        return presets[selected_id]
    fallback_id = fallback_preset_id()
    if fallback_id in presets:
        return presets[fallback_id]
    return next(iter(presets.values()), None)


def get_preset_metadata(preset_id: str | None = None) -> dict[str, Any]:
    preset = resolve_preset(preset_id)
    return preset.to_runtime_dict() if preset else {}


def collect_presets_status() -> dict[str, Any]:
    payload = load_presets_payload()
    presets = load_presets()
    active_id = str(payload.get("active_preset_id") or "")
    fallback_id = str(payload.get("fallback_preset_id") or "")
    active = presets.get(active_id)
    return {
        "config_path": str(PRESETS_PATH),
        "active_preset_id": active_id,
        "fallback_preset_id": fallback_id,
        "active_preset_ready": active.readiness()["ready"] if active else False,
        "active_preset": active.readiness() if active else None,
        "presets": [preset.readiness() for preset in presets.values()],
    }


def _default_payload() -> dict[str, Any]:
    return {
        "active_preset_id": "tech_villager",
        "fallback_preset_id": "tech_villager",
        "presets": [
            {
                "preset_id": "tech_villager",
                "display_name": "技术验收模型：Minecraft Villager",
                "description": "仅用于验证真实 So-VITS-SVC CUDA 推理链路。",
                "model_path": str(PROJECT_ROOT / "local_models" / "sovits-test" / "minecraft_villager" / "G_4000.pth"),
                "config_path": str(PROJECT_ROOT / "local_models" / "sovits-test" / "minecraft_villager" / "config.json"),
                "speaker": "villager",
                "device": "cuda",
                "is_demo_quality": False,
                "is_technical_validation_only": True,
            }
        ],
    }
