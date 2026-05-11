from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


def analyze_input_audio(path: str) -> dict[str, Any]:
    audio, sample_rate = sf.read(path, always_2d=True)
    channels = int(audio.shape[1])
    mono = audio.mean(axis=1).astype(np.float32)
    if mono.size == 0:
        raise ValueError(f"Audio file is empty: {path}")

    duration = float(mono.shape[0]) / float(sample_rate)
    rms = float(np.sqrt(np.mean(np.square(mono)) + 1e-8))
    peak = float(np.max(np.abs(mono)))
    frame_rms = _compute_frame_rms(mono)
    silence_threshold = max(rms * 0.1, 2e-4)
    low_energy_threshold = max(rms * 0.25, 5e-4)
    silence_ratio = float(sum(value < silence_threshold for value in frame_rms)) / float(len(frame_rms))
    low_energy_ratio = float(sum(value < low_energy_threshold for value in frame_rms)) / float(len(frame_rms))
    clipping_ratio = float(np.mean(np.abs(mono) >= 0.98))

    is_too_short = duration < 3.0
    is_probably_silent = rms < 0.01 or silence_ratio >= 0.82

    warnings: list[str] = []
    if is_too_short:
        warnings.append("音频时长过短，可能不足以稳定提取音高与风格特征。")
    elif duration < 8.0:
        warnings.append("音频较短，转换结果可能不够稳定。")

    if sample_rate < 16000:
        warnings.append("采样率过低，可能影响人声细节与 F0 提取。")
    elif sample_rate < 32000:
        warnings.append("采样率偏低，风格细节可能有所损失。")

    if channels > 2:
        warnings.append("声道数较多，建议先转为单声道或双声道人声。")

    if is_probably_silent:
        warnings.append("音频整体能量偏低或静音比例过高，可能导致转换失败或输出空洞。")
    elif low_energy_ratio >= 0.65:
        warnings.append("低能量片段较多，气声或弱唱段可能放大瑕疵。")

    if clipping_ratio >= 0.05:
        warnings.append("削波比例较高，原始录音可能已失真。")
    elif clipping_ratio >= 0.01:
        warnings.append("检测到少量削波，建议降低输入增益后重试。")

    quality_level = "good"
    if (
        is_too_short
        or is_probably_silent
        or sample_rate < 16000
        or clipping_ratio >= 0.05
    ):
        quality_level = "bad"
    elif (
        duration < 8.0
        or sample_rate < 32000
        or low_energy_ratio >= 0.65
        or silence_ratio >= 0.45
        or clipping_ratio >= 0.01
    ):
        quality_level = "warn"

    return {
        "path": path,
        "duration": round(duration, 6),
        "sample_rate": int(sample_rate),
        "channels": channels,
        "rms": round(rms, 8),
        "peak": round(peak, 8),
        "low_energy_ratio": round(low_energy_ratio, 6),
        "clipping_ratio": round(clipping_ratio, 6),
        "silence_ratio": round(silence_ratio, 6),
        "is_too_short": is_too_short,
        "is_probably_silent": is_probably_silent,
        "quality_level": quality_level,
        "warnings": warnings,
    }


def summarize_input_quality(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "duration": report.get("duration"),
        "sample_rate": report.get("sample_rate"),
        "channels": report.get("channels"),
        "rms": report.get("rms"),
        "peak": report.get("peak"),
        "low_energy_ratio": report.get("low_energy_ratio"),
        "clipping_ratio": report.get("clipping_ratio"),
        "silence_ratio": report.get("silence_ratio"),
        "is_too_short": bool(report.get("is_too_short")),
        "is_probably_silent": bool(report.get("is_probably_silent")),
        "quality_level": str(report.get("quality_level") or "warn"),
        "warnings": list(report.get("warnings") or []),
    }


def write_input_quality_report(target_dir: str | Path, report: dict[str, Any]) -> str:
    output_dir = Path(target_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "input_quality_report.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output_path)


def build_input_quality_fallback(path: str, exc: Exception) -> dict[str, Any]:
    return {
        "path": path,
        "duration": None,
        "sample_rate": None,
        "channels": None,
        "rms": None,
        "peak": None,
        "low_energy_ratio": None,
        "clipping_ratio": None,
        "silence_ratio": None,
        "is_too_short": False,
        "is_probably_silent": False,
        "quality_level": "warn",
        "warnings": [f"输入质量分析失败，已跳过自动判断：{exc}"],
    }


def _compute_frame_rms(mono: np.ndarray) -> list[float]:
    frame_length = min(2048, max(256, mono.shape[0]))
    hop_length = max(frame_length // 2, 128)
    values: list[float] = []
    for start in range(0, mono.shape[0], hop_length):
        frame = mono[start : start + frame_length]
        if frame.size == 0:
            continue
        values.append(float(np.sqrt(np.mean(np.square(frame)) + 1e-8)))
    return values or [0.0]
