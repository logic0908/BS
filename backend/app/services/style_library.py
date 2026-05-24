from __future__ import annotations

import json
import os
import re
from typing import Any

from app.services import svc_model_presets

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STYLE_LIBRARY_PATH = os.environ.get(
    "STYLE_LIBRARY_PATH",
    os.path.join(APP_DIR, "config", "style_library.json"),
)


def load_style_library() -> list[dict[str, Any]]:
    with open(STYLE_LIBRARY_PATH, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("style library must be a list")
    return [dict(item) for item in data]


def encode_prompt(prompt_text: str) -> dict[str, Any]:
    normalized = (prompt_text or "").strip().lower()
    tokens = [token for token in re.split(r"[\s,;，。!！?？、/]+", normalized) if token]
    return {"normalized": normalized, "tokens": tokens}


def retrieve_style(
    prompt_text: str = "",
    style_preset_id: str | None = None,
    model_preset_id: str | None = None,
) -> dict[str, Any]:
    presets = load_style_library()
    if not presets:
        raise RuntimeError("style library is empty")

    if style_preset_id:
        for preset in presets:
            if str(preset.get("style_id", "")).strip() == style_preset_id:
                selected = dict(preset)
                selected["match_score"] = 10_000
                selected["matched_prompt"] = prompt_text
                selected["matched_via"] = "style_preset_id"
                selected["matched_keywords"] = [style_preset_id]
                selected["reason"] = f"显式指定 style_preset_id：{style_preset_id}"
                return apply_runtime_defaults(selected, model_preset_id=model_preset_id)
        raise RuntimeError(f"style_preset_id not found: {style_preset_id}")

    encoded = encode_prompt(prompt_text)
    normalized = encoded["normalized"]
    best_preset = presets[0]
    best_score = -1
    best_ready = False
    best_matched_keywords: list[str] = []

    for preset in presets:
        score, matched_keywords = _score_preset(preset, normalized, encoded["tokens"])
        preset_with_runtime = apply_runtime_defaults(preset)
        preset_ready = bool(preset_with_runtime.get("model_preset_ready"))
        if score > best_score or (score == best_score and preset_ready and not best_ready):
            best_preset = preset
            best_score = score
            best_ready = preset_ready
            best_matched_keywords = matched_keywords

    selected = dict(best_preset)
    selected["matched_prompt"] = prompt_text
    selected["match_score"] = best_score
    selected["matched_via"] = "prompt_text"
    selected["matched_keywords"] = best_matched_keywords
    selected["reason"] = _build_reason(best_preset, best_matched_keywords, best_score)
    return apply_runtime_defaults(selected, model_preset_id=model_preset_id)


def apply_runtime_defaults(preset: dict[str, Any], model_preset_id: str | None = None) -> dict[str, Any]:
    resolved = dict(preset)
    explicit_model_preset_id = str(model_preset_id or "").strip()
    preset_id = explicit_model_preset_id or str(resolved.get("model_preset_id") or "").strip() or None
    model_preset = svc_model_presets.resolve_preset(preset_id)
    model_metadata = model_preset.to_runtime_dict() if model_preset else {}
    model_status = model_preset.readiness() if model_preset else {}
    if explicit_model_preset_id:
        resolved["model_preset_id"] = str(model_metadata.get("model_preset_id") or explicit_model_preset_id)
        resolved["model_display_name"] = str(model_metadata.get("model_display_name") or resolved.get("model_display_name") or "")
        resolved["model_path"] = model_metadata.get("model_path") or resolved.get("model_path") or os.environ.get("SOVITS_MODEL_PATH", "")
        resolved["config_path"] = model_metadata.get("config_path") or resolved.get("config_path") or os.environ.get("SOVITS_CONFIG_PATH", "")
        resolved["speaker"] = model_metadata.get("speaker") or resolved.get("speaker") or os.environ.get("SOVITS_SPEAKER", "")
        resolved["device"] = model_metadata.get("device") or resolved.get("device")
        resolved["source_repo"] = model_metadata.get("source_repo") or resolved.get("source_repo") or ""
        resolved["license"] = model_metadata.get("license") or resolved.get("license") or ""
        resolved["internal_test_only"] = bool(
            model_metadata.get("internal_test_only", resolved.get("internal_test_only", False))
        )
        resolved["temporary_demo_reason"] = str(
            model_metadata.get("temporary_demo_reason") or resolved.get("temporary_demo_reason") or ""
        )
        resolved["model_path_basename"] = model_metadata.get("model_path_basename") or resolved.get("model_path_basename") or ""
        resolved["config_path_basename"] = model_metadata.get("config_path_basename") or resolved.get("config_path_basename") or ""
    else:
        for key, value in model_metadata.items():
            resolved.setdefault(key, value)
        resolved["model_preset_id"] = str(resolved.get("model_preset_id") or model_metadata.get("model_preset_id") or "")
        resolved["model_display_name"] = str(resolved.get("model_display_name") or model_metadata.get("model_display_name") or "")
        resolved["model_path"] = resolved.get("model_path") or model_metadata.get("model_path") or os.environ.get("SOVITS_MODEL_PATH", "")
        resolved["config_path"] = resolved.get("config_path") or model_metadata.get("config_path") or os.environ.get("SOVITS_CONFIG_PATH", "")
        resolved["speaker"] = resolved.get("speaker") or model_metadata.get("speaker") or os.environ.get("SOVITS_SPEAKER", "")
        resolved["device"] = resolved.get("device") or model_metadata.get("device")
        resolved["source_repo"] = resolved.get("source_repo") or model_metadata.get("source_repo", "")
        resolved["license"] = resolved.get("license") or model_metadata.get("license", "")
        resolved["internal_test_only"] = bool(
            resolved.get("internal_test_only", model_metadata.get("internal_test_only", False))
        )
        resolved["temporary_demo_reason"] = str(
            resolved.get("temporary_demo_reason") or model_metadata.get("temporary_demo_reason", "")
        )
        resolved["model_path_basename"] = resolved.get("model_path_basename") or model_metadata.get("model_path_basename", "")
        resolved["config_path_basename"] = resolved.get("config_path_basename") or model_metadata.get("config_path_basename", "")
    resolved["style_tags"] = list(resolved.get("style_tags") or model_metadata.get("style_tags") or [])
    resolved["is_demo_quality"] = bool(resolved.get("is_demo_quality", model_metadata.get("is_demo_quality", False)))
    resolved["is_configured"] = bool(resolved.get("is_configured", model_metadata.get("is_configured", False)))
    resolved["smoke_test_passed"] = bool(resolved.get("smoke_test_passed", model_metadata.get("smoke_test_passed", False)))
    resolved["is_technical_validation_only"] = bool(
        resolved.get("is_technical_validation_only", model_metadata.get("is_technical_validation_only", False))
    )
    resolved["model_preset_ready"] = bool(model_status.get("ready", False))
    resolved["model_preset_configured"] = bool(model_status.get("is_configured", resolved.get("is_configured", False)))
    resolved["current_style_has_dedicated_model"] = bool(
        resolved.get("model_preset_id") and resolved.get("model_preset_id") not in {"", "final_primary"}
    )
    if resolved["current_style_has_dedicated_model"] and not resolved["model_preset_ready"]:
        resolved["model_preset_notice"] = "该风格尚未绑定目标模型"
    elif resolved["current_style_has_dedicated_model"]:
        resolved["model_preset_notice"] = "该风格已绑定专用目标模型"
    else:
        resolved["model_preset_notice"] = "当前使用基础通用目标模型"
    resolved["transpose"] = int(resolved.get("transpose", 0))
    resolved["match_score"] = resolved.get("match_score", 0)
    resolved["matched_keywords"] = list(resolved.get("matched_keywords") or [])
    resolved["reason"] = str(resolved.get("reason") or "")
    return resolved


def available_model_presets() -> list[dict[str, Any]]:
    presets = svc_model_presets.load_presets()
    return [{**preset.to_runtime_dict(), **preset.readiness()} for preset in presets.values()]


def apply_adapter_controls(
    preset: dict[str, Any],
    control_params: dict[str, Any] | None,
    model_preset_id: str | None = None,
    override_reason: str | None = None,
) -> dict[str, Any]:
    resolved = dict(preset)
    controls = dict(control_params or {})
    target_model_preset_id = str(controls.get("model_preset_id") or model_preset_id or resolved.get("model_preset_id") or "")
    resolved = apply_runtime_defaults(resolved, model_preset_id=target_model_preset_id or None)
    if "transpose" in controls and controls.get("transpose") is not None:
        original_transpose = int(resolved.get("transpose", 0) or 0)
        new_transpose = int(controls.get("transpose", 0) or 0)
        resolved["transpose"] = new_transpose
        if new_transpose != original_transpose:
            resolved["transpose_override_reason"] = override_reason or "TextStyleAdapter override"
    if override_reason:
        resolved["adapter_override_reason"] = override_reason
    if controls:
        resolved["adapter_control_params"] = controls
    return resolved


def _score_preset(preset: dict[str, Any], normalized: str, tokens: list[str]) -> tuple[int, list[str]]:
    if not normalized:
        return 0, []

    keywords = list(preset.get("keywords") or [])
    keywords.extend([preset.get("style_id", ""), preset.get("description", "")])

    score = 0
    matched_keywords: list[str] = []
    for keyword in keywords:
        candidate = str(keyword).strip().lower()
        if not candidate:
            continue
        if candidate in normalized:
            score += max(2, len(candidate))
            matched_keywords.append(str(keyword).strip())
            continue
        token_hits = [token for token in tokens if token and token in candidate]
        if token_hits:
            score += len(token_hits)
            matched_keywords.extend(token_hits)
    return score, _dedupe_keep_order(matched_keywords)


def _build_reason(preset: dict[str, Any], matched_keywords: list[str], score: int) -> str:
    style_id = str(preset.get("style_id") or "unknown_style")
    if matched_keywords:
        return f"命中关键词：{'、'.join(matched_keywords)}；选择 {style_id}"
    if score <= 0:
        return f"未命中明显关键词；使用默认候选 {style_id}"
    return f"根据弱匹配信号选择 {style_id}"


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result
