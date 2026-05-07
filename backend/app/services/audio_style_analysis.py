from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import librosa
import numpy as np
import soundfile as sf


MIN_AUDIO_SECONDS = 0.2
STYLE_DIMENSIONS = ("brightness", "energy", "softness", "thickness", "pitch_height")
STYLE_SCORE_KEYS = {
    "brightness": "brightness_score",
    "energy": "energy_score",
    "softness": "softness_score",
    "thickness": "thickness_score",
    "pitch_height": "pitch_height_score",
}
STYLE_LABELS = {
    "brightness": "亮度",
    "energy": "能量",
    "softness": "柔和度",
    "thickness": "厚度",
    "pitch_height": "音高中心",
}
PROMPT_RULES: dict[str, dict[str, float]] = {
    "低沉": {"pitch_height": -1.0, "brightness": -1.0, "thickness": 1.0},
    "厚重": {"thickness": 1.0, "brightness": -1.0},
    "成熟": {"pitch_height": -1.0, "thickness": 1.0, "softness": 0.0},
    "男声": {"pitch_height": -1.0, "thickness": 1.0},
    "少年感": {"pitch_height": 1.0, "brightness": 1.0, "thickness": -1.0},
    "女声": {"pitch_height": 1.0, "brightness": 1.0, "thickness": -1.0},
    "温柔": {"energy": -1.0, "softness": 1.0, "brightness": -0.5},
    "治愈": {"energy": -1.0, "softness": 1.0},
    "清亮": {"brightness": 1.0, "thickness": -1.0},
    "气声": {"softness": 1.0, "energy": -1.0},
    "流行": {"energy": 0.0, "brightness": 0.0},
    "摇滚": {"energy": 1.0, "brightness": 1.0},
    "悲伤": {"energy": -1.0, "brightness": -1.0, "softness": 1.0},
    "激昂": {"energy": 1.0},
}


class AudioStyleAnalysisError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": False,
            "code": self.code,
            "message": str(self),
            "details": sanitize_for_json(self.details),
        }


def analyze_audio_style(audio_path: str | Path) -> dict[str, Any]:
    path = Path(audio_path).expanduser().resolve()
    warnings: list[str] = []
    if not path.exists():
        return _error_payload("AUDIO_NOT_FOUND", f"音频文件不存在：{path}", path=path)
    try:
        samples, sample_rate = sf.read(str(path), always_2d=True, dtype="float32")
    except Exception as exc:
        return _error_payload(
            "AUDIO_READ_FAILED",
            "无法读取音频文件，请确认输入是可解析的 wav/flac 等音频格式。",
            path=path,
            details={"reason": str(exc)},
        )

    if samples.size == 0:
        return _error_payload("AUDIO_EMPTY", "音频为空，无法提取风格证据。", path=path)

    channels = int(samples.shape[1])
    mono = np.mean(samples, axis=1, dtype=np.float32)
    mono = np.nan_to_num(mono, nan=0.0, posinf=0.0, neginf=0.0)
    frames = int(mono.shape[0])
    duration_seconds = float(frames / sample_rate) if sample_rate > 0 else 0.0
    if sample_rate <= 0 or duration_seconds < MIN_AUDIO_SECONDS:
        return _error_payload(
            "AUDIO_TOO_SHORT",
            "音频过短，无法稳定提取风格证据。",
            path=path,
            details={"duration_seconds": duration_seconds, "sample_rate": sample_rate},
        )

    analysis = _compute_analysis(mono, int(sample_rate), warnings)
    analysis.update(
        {
            "ok": True,
            "path": str(path),
            "duration_seconds": _safe_float(duration_seconds, digits=6),
            "sample_rate": int(sample_rate),
            "frames": frames,
            "channels": channels,
            "warnings": warnings,
        }
    )
    return sanitize_for_json(analysis)


def parse_prompt_style_targets(prompt_text: str) -> dict[str, Any]:
    normalized = " ".join(str(prompt_text or "").strip().split())
    matched_keywords: list[str] = []
    votes = {dimension: 0.0 for dimension in STYLE_DIMENSIONS}
    for keyword, effects in PROMPT_RULES.items():
        if keyword and keyword in normalized:
            matched_keywords.append(keyword)
            for dimension, delta in effects.items():
                if dimension in votes:
                    votes[dimension] += float(delta)

    target_dimensions: dict[str, str] = {}
    for dimension, score in votes.items():
        direction = _direction_from_vote(score)
        if direction is not None:
            target_dimensions[dimension] = direction

    human_readable_targets = _build_human_readable_targets(target_dimensions)
    return {
        "prompt_text": normalized,
        "target_dimensions": target_dimensions,
        "matched_keywords": matched_keywords,
        "human_readable_targets": human_readable_targets,
    }


def compare_audio_style(
    input_audio_path: str | Path,
    output_audio_path: str | Path,
    prompt_text: str,
    model_preset_id: str | None = None,
) -> dict[str, Any]:
    input_report = analyze_audio_style(input_audio_path)
    output_report = analyze_audio_style(output_audio_path)
    prompt_targets = parse_prompt_style_targets(prompt_text)
    warnings = [
        "该分析为启发式客观指标，仅用于展示趋势，不能替代人工听评。",
    ]
    if not input_report.get("ok"):
        warnings.append("输入音频风格分析未成功完成。")
    if not output_report.get("ok"):
        warnings.append("输出音频风格分析未成功完成。")

    comparisons = build_style_comparisons(input_report, output_report, prompt_targets)
    summary = build_style_evidence_summary(comparisons, prompt_targets)
    radar = build_style_radar(input_report, output_report, prompt_targets)

    if not input_report.get("f0_available", False):
        warnings.append("输入音频 F0 提取不可用，音高中心相关判断可能不完整。")
    if not output_report.get("f0_available", False):
        warnings.append("输出音频 F0 提取不可用，音高中心相关判断可能不完整。")

    ok = bool(input_report.get("ok")) and bool(output_report.get("ok"))
    return sanitize_for_json(
        {
            "ok": ok,
            "prompt_text": prompt_text,
            "model_preset_id": model_preset_id,
            "input": input_report,
            "output": output_report,
            "prompt_targets": prompt_targets,
            "comparisons": comparisons,
            "radar": radar,
            "summary": summary,
            "warnings": warnings,
        }
    )


def build_style_evidence_summary(comparisons: list[dict], prompt_targets: dict) -> dict:
    expected_dimensions = prompt_targets.get("target_dimensions") or {}
    comparable = [
        item
        for item in comparisons
        if item.get("expected_direction") and item.get("input_value") is not None and item.get("output_value") is not None
    ]
    total_count = len(comparable)
    matched_count = sum(1 for item in comparable if item.get("matches_prompt"))
    if total_count == 0:
        return {
            "matched_count": 0,
            "total_count": len(expected_dimensions),
            "score": 0.0,
            "level": "unknown",
            "text": "当前可用于比较的有效指标不足，暂时无法判断输出是否朝提示词目标方向移动。",
        }

    score = matched_count / total_count
    if score >= 0.75:
        level = "strong"
        text = "输出音频在多个可测指标上向提示词目标方向移动，说明本次转换具有较明显的风格响应趋势。但该结论仍属于客观特征辅助分析，最终效果仍需结合人工听评判断。"
    elif score >= 0.4:
        level = "partial"
        text = "输出音频在部分指标上向提示词目标方向移动，但仍有若干维度变化不明显，说明当前模型具备一定提示词响应趋势，但转换幅度有限。"
    else:
        level = "weak"
        text = "输出音频与输入相比变化有限，未能在多数可测指标上明显朝提示词目标方向移动。该结果可作为后续优化目标模型、提示词映射和条件控制强度的依据。"

    return {
        "matched_count": matched_count,
        "total_count": total_count,
        "score": _safe_float(score, digits=4),
        "level": level,
        "text": text,
    }


def build_style_comparisons(
    input_report: dict[str, Any],
    output_report: dict[str, Any],
    prompt_targets: dict[str, Any],
) -> list[dict[str, Any]]:
    target_dimensions = dict(prompt_targets.get("target_dimensions") or {})
    comparisons: list[dict[str, Any]] = []
    for dimension in STYLE_DIMENSIONS:
        score_key = STYLE_SCORE_KEYS[dimension]
        input_value = _coerce_score(input_report.get(score_key))
        output_value = _coerce_score(output_report.get(score_key))
        expected_direction = target_dimensions.get(dimension)
        delta = None if input_value is None or output_value is None else _safe_float(output_value - input_value, digits=4)
        actual_direction = _delta_direction(delta)
        matches_prompt = _matches_expected_direction(delta, expected_direction)
        explanation = _build_dimension_explanation(
            STYLE_LABELS[dimension],
            expected_direction,
            actual_direction,
            matches_prompt,
            input_value,
            output_value,
        )
        comparisons.append(
            {
                "key": score_key,
                "label": STYLE_LABELS[dimension],
                "input_value": input_value,
                "output_value": output_value,
                "delta": delta,
                "direction": actual_direction,
                "expected_direction": expected_direction,
                "matches_prompt": matches_prompt,
                "evidence_level": _evidence_level(delta),
                "explanation": explanation,
            }
        )
    return comparisons


def build_style_radar(
    input_report: dict[str, Any],
    output_report: dict[str, Any],
    prompt_targets: dict[str, Any],
) -> dict[str, Any]:
    target_dimensions = dict(prompt_targets.get("target_dimensions") or {})
    input_values = []
    output_values = []
    target_values = []
    for dimension in STYLE_DIMENSIONS:
        input_score = _coerce_score(input_report.get(STYLE_SCORE_KEYS[dimension]))
        output_score = _coerce_score(output_report.get(STYLE_SCORE_KEYS[dimension]))
        input_values.append(input_score if input_score is not None else 0.5)
        output_values.append(output_score if output_score is not None else 0.5)
        target_values.append(_target_score_for_direction(target_dimensions.get(dimension)))
    return {
        "dimensions": list(STYLE_DIMENSIONS),
        "input": sanitize_for_json(input_values),
        "output": sanitize_for_json(output_values),
        "target": sanitize_for_json(target_values),
    }


def sanitize_for_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize_for_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_for_json(item) for item in value]
    if isinstance(value, np.ndarray):
        return [sanitize_for_json(item) for item in value.tolist()]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, Path):
        return str(value)
    return value


def _compute_analysis(audio: np.ndarray, sample_rate: int, warnings: list[str]) -> dict[str, Any]:
    frame_length = int(min(max(512, 2 ** int(math.log2(min(len(audio), 4096)))), len(audio)))
    hop_length = max(128, frame_length // 4)

    rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]
    stft = librosa.stft(audio, n_fft=frame_length, hop_length=hop_length, center=True)
    magnitude = np.abs(stft)
    power = magnitude**2
    frequencies = librosa.fft_frequencies(sr=sample_rate, n_fft=frame_length)

    low_mask = frequencies < 500
    mid_mask = (frequencies >= 500) & (frequencies < 4000)
    high_mask = frequencies >= 4000
    total_energy = float(np.sum(power))
    low_energy_ratio = _band_energy_ratio(power, low_mask, total_energy)
    mid_energy_ratio = _band_energy_ratio(power, mid_mask, total_energy)
    high_energy_ratio = _band_energy_ratio(power, high_mask, total_energy)

    centroid = librosa.feature.spectral_centroid(S=magnitude, sr=sample_rate)[0]
    bandwidth = librosa.feature.spectral_bandwidth(S=magnitude, sr=sample_rate)[0]
    rolloff = librosa.feature.spectral_rolloff(S=magnitude, sr=sample_rate, roll_percent=0.85)[0]
    zcr = librosa.feature.zero_crossing_rate(audio, frame_length=frame_length, hop_length=hop_length)[0]

    f0_payload = _extract_f0(audio, sample_rate, frame_length, hop_length, warnings)
    rms_mean = _mean_or_none(rms)
    rms_std = _std_or_none(rms)
    dynamic_range = None
    if rms.size > 0:
        dynamic_range = _safe_float(np.nanpercentile(rms, 95) - np.nanpercentile(rms, 10), digits=6)

    energy_score = _clamp01((rms_mean or 0.0) / 0.12)
    brightness_score = _clamp01(0.55 * ((centroid.mean() if centroid.size else 0.0) / 4000.0) + 0.45 * high_energy_ratio)
    softness_score = _clamp01(0.55 * (1.0 - energy_score) + 0.25 * (1.0 - min((_mean_or_none(zcr) or 0.0) / 0.18, 1.0)) + 0.20 * (1.0 - high_energy_ratio))
    thickness_score = _clamp01(0.55 * low_energy_ratio + 0.25 * (1.0 - min((_mean_or_none(centroid) or 0.0) / 4000.0, 1.0)) + 0.20 * (1.0 - high_energy_ratio))
    pitch_height_score = None
    if f0_payload["f0_available"]:
        pitch_height_score = _clamp01(((f0_payload["f0_median"] or 0.0) - 90.0) / 240.0)

    return {
        "rms_mean": _safe_float(rms_mean),
        "rms_std": _safe_float(rms_std),
        "dynamic_range": _safe_float(dynamic_range),
        "spectral_centroid_mean": _safe_float(_mean_or_none(centroid)),
        "spectral_bandwidth_mean": _safe_float(_mean_or_none(bandwidth)),
        "spectral_rolloff_mean": _safe_float(_mean_or_none(rolloff)),
        "zero_crossing_rate_mean": _safe_float(_mean_or_none(zcr)),
        **f0_payload,
        "low_energy_ratio": _safe_float(low_energy_ratio),
        "mid_energy_ratio": _safe_float(mid_energy_ratio),
        "high_energy_ratio": _safe_float(high_energy_ratio),
        "brightness_score": _safe_float(brightness_score),
        "energy_score": _safe_float(energy_score),
        "softness_score": _safe_float(softness_score),
        "thickness_score": _safe_float(thickness_score),
        "pitch_height_score": _safe_float(pitch_height_score),
    }


def _extract_f0(
    audio: np.ndarray,
    sample_rate: int,
    frame_length: int,
    hop_length: int,
    warnings: list[str],
) -> dict[str, Any]:
    try:
        f0, voiced_flag, _ = librosa.pyin(
            audio,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sample_rate,
            frame_length=frame_length,
            hop_length=hop_length,
        )
    except Exception as exc:
        warnings.append(f"F0 提取失败，已降级跳过音高相关指标：{exc}")
        return {
            "f0_available": False,
            "f0_mean": None,
            "f0_median": None,
            "f0_std": None,
            "f0_min": None,
            "f0_max": None,
            "voiced_ratio": None,
        }

    valid_f0 = np.asarray(f0[~np.isnan(f0)], dtype=np.float32)
    if valid_f0.size == 0:
        warnings.append("F0 提取未得到有效有声帧，已降级跳过音高相关指标。")
        return {
            "f0_available": False,
            "f0_mean": None,
            "f0_median": None,
            "f0_std": None,
            "f0_min": None,
            "f0_max": None,
            "voiced_ratio": _safe_float(float(np.mean(voiced_flag.astype(np.float32))) if voiced_flag is not None else 0.0),
        }

    voiced_ratio = float(valid_f0.size / max(len(f0), 1))
    return {
        "f0_available": True,
        "f0_mean": _safe_float(float(np.mean(valid_f0))),
        "f0_median": _safe_float(float(np.median(valid_f0))),
        "f0_std": _safe_float(float(np.std(valid_f0))),
        "f0_min": _safe_float(float(np.min(valid_f0))),
        "f0_max": _safe_float(float(np.max(valid_f0))),
        "voiced_ratio": _safe_float(voiced_ratio),
    }


def _band_energy_ratio(power: np.ndarray, mask: np.ndarray, total_energy: float) -> float:
    if total_energy <= 0.0 or not np.any(mask):
        return 0.0
    band_energy = float(np.sum(power[mask, :]))
    return _clamp01(band_energy / total_energy)


def _mean_or_none(values: np.ndarray) -> float | None:
    if values.size == 0:
        return None
    return float(np.nanmean(values))


def _std_or_none(values: np.ndarray) -> float | None:
    if values.size == 0:
        return None
    return float(np.nanstd(values))


def _safe_float(value: float | None, *, digits: int = 6) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return round(numeric, digits)


def _clamp01(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


def _direction_from_vote(vote: float) -> str | None:
    if vote >= 0.75:
        return "up"
    if vote >= 0.25:
        return "slightly_up"
    if vote <= -0.75:
        return "down"
    if vote <= -0.25:
        return "slightly_down"
    if vote == 0.0:
        return "medium"
    return "medium"


def _build_human_readable_targets(target_dimensions: dict[str, str]) -> list[str]:
    messages: list[str] = []
    if target_dimensions.get("pitch_height") in {"down", "slightly_down"}:
        messages.append("音高中心降低")
    elif target_dimensions.get("pitch_height") in {"up", "slightly_up"}:
        messages.append("音高中心升高")
    if target_dimensions.get("thickness") in {"up", "slightly_up"}:
        messages.append("低频/厚度增强")
    elif target_dimensions.get("thickness") in {"down", "slightly_down"}:
        messages.append("厚度减弱、声音更轻薄")
    if target_dimensions.get("brightness") in {"down", "slightly_down"}:
        messages.append("亮度适度降低")
    elif target_dimensions.get("brightness") in {"up", "slightly_up"}:
        messages.append("亮度提升")
    if target_dimensions.get("energy") in {"up", "slightly_up"}:
        messages.append("能量保持中高或进一步增强")
    elif target_dimensions.get("energy") in {"down", "slightly_down"}:
        messages.append("能量降低")
    elif target_dimensions.get("energy") == "medium":
        messages.append("能量保持中等或略增强")
    if target_dimensions.get("softness") in {"up", "slightly_up"}:
        messages.append("柔和度增强")
    elif target_dimensions.get("softness") in {"down", "slightly_down"}:
        messages.append("柔和度降低")
    return messages


def _coerce_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return round(numeric, 4)


def _delta_direction(delta: float | None) -> str:
    if delta is None:
        return "unknown"
    if delta >= 0.03:
        return "up"
    if delta <= -0.03:
        return "down"
    return "stable"


def _matches_expected_direction(delta: float | None, expected_direction: str | None) -> bool:
    if delta is None or expected_direction is None:
        return False
    if expected_direction == "up":
        return delta >= 0.03
    if expected_direction == "slightly_up":
        return delta >= 0.01
    if expected_direction == "down":
        return delta <= -0.03
    if expected_direction == "slightly_down":
        return delta <= -0.01
    if expected_direction == "medium":
        return abs(delta) <= 0.06
    return False


def _evidence_level(delta: float | None) -> str:
    if delta is None:
        return "low"
    magnitude = abs(delta)
    if magnitude >= 0.18:
        return "high"
    if magnitude >= 0.08:
        return "medium"
    return "low"


def _build_dimension_explanation(
    label: str,
    expected_direction: str | None,
    actual_direction: str,
    matches_prompt: bool,
    input_value: float | None,
    output_value: float | None,
) -> str:
    if input_value is None or output_value is None:
        return f"{label}缺少可用数值，当前无法判断该维度是否响应提示词。"
    if expected_direction is None:
        return f"提示词未对{label}给出明确目标方向，本项仅展示输入与输出的客观差异。"
    if matches_prompt:
        return f"输出{label}{'上升' if actual_direction == 'up' else '下降' if actual_direction == 'down' else '保持相近'}，符合提示词期望方向。"
    return f"输出{label}{'上升' if actual_direction == 'up' else '下降' if actual_direction == 'down' else '变化有限'}，与提示词期望方向并不完全一致。"


def _target_score_for_direction(direction: str | None) -> float:
    if direction == "up":
        return 0.75
    if direction == "slightly_up":
        return 0.6
    if direction == "down":
        return 0.25
    if direction == "slightly_down":
        return 0.4
    return 0.5


def _error_payload(code: str, message: str, *, path: Path, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "code": code,
        "message": message,
        "path": str(path),
        "warnings": [],
        "details": sanitize_for_json(details or {}),
    }
