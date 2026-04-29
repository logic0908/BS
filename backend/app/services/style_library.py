from __future__ import annotations

import json
import os
import re
from typing import Any

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


def retrieve_style(prompt_text: str = "", style_preset_id: str | None = None) -> dict[str, Any]:
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
                return apply_runtime_defaults(selected)
        raise RuntimeError(f"style_preset_id not found: {style_preset_id}")

    encoded = encode_prompt(prompt_text)
    normalized = encoded["normalized"]
    best_preset = presets[0]
    best_score = -1
    best_matched_keywords: list[str] = []

    for preset in presets:
        score, matched_keywords = _score_preset(preset, normalized, encoded["tokens"])
        if score > best_score:
            best_preset = preset
            best_score = score
            best_matched_keywords = matched_keywords

    selected = dict(best_preset)
    selected["matched_prompt"] = prompt_text
    selected["match_score"] = best_score
    selected["matched_via"] = "prompt_text"
    selected["matched_keywords"] = best_matched_keywords
    selected["reason"] = _build_reason(best_preset, best_matched_keywords, best_score)
    return apply_runtime_defaults(selected)


def apply_runtime_defaults(preset: dict[str, Any]) -> dict[str, Any]:
    resolved = dict(preset)
    resolved["model_path"] = resolved.get("model_path") or os.environ.get("SOVITS_MODEL_PATH", "")
    resolved["config_path"] = resolved.get("config_path") or os.environ.get("SOVITS_CONFIG_PATH", "")
    resolved["speaker"] = resolved.get("speaker") or os.environ.get("SOVITS_SPEAKER", "")
    resolved["transpose"] = int(resolved.get("transpose", 0))
    resolved["match_score"] = resolved.get("match_score", 0)
    resolved["matched_keywords"] = list(resolved.get("matched_keywords") or [])
    resolved["reason"] = str(resolved.get("reason") or "")
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
