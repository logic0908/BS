from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


def analyze_audio_pair(input_path: str, output_path: str) -> dict[str, Any]:
    input_metrics = _analyze_single_audio(input_path)
    output_metrics = _analyze_single_audio(output_path)
    duration_mismatch_ratio = abs(output_metrics["duration"] - input_metrics["duration"]) / max(input_metrics["duration"], 1e-6)
    possible_dropouts = bool(output_metrics["low_energy_ratio"] >= 0.4 or duration_mismatch_ratio >= 0.08)
    return {
        "input_audio": input_metrics,
        "output_audio": output_metrics,
        "duration_mismatch_ratio": round(float(duration_mismatch_ratio), 6),
        "possible_dropouts": possible_dropouts,
        "summary": {
            "duration_consistency": round(max(0.0, 1.0 - duration_mismatch_ratio), 6),
            "low_energy_ratio": output_metrics["low_energy_ratio"],
            "possible_dropouts": possible_dropouts,
        },
    }


def write_audio_quality_report(debug_dir: str | Path, report: dict[str, Any]) -> str:
    target_dir = Path(debug_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "audio_quality_report.json"
    target_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(target_path)


def _analyze_single_audio(path: str) -> dict[str, Any]:
    audio, sample_rate = sf.read(path, always_2d=True)
    channels = int(audio.shape[1])
    mono = audio.mean(axis=1).astype(np.float32)
    if mono.size == 0:
        raise ValueError(f"Audio file is empty: {path}")
    rms = float(np.sqrt(np.mean(np.square(mono)) + 1e-8))
    peak = float(np.max(np.abs(mono)))
    duration = float(mono.shape[0]) / float(sample_rate)
    frame_length = min(2048, max(256, mono.shape[0]))
    hop_length = max(frame_length // 2, 128)
    windowed = []
    for start in range(0, mono.shape[0], hop_length):
        frame = mono[start : start + frame_length]
        if frame.size == 0:
            continue
        windowed.append(float(np.sqrt(np.mean(np.square(frame)) + 1e-8)))
    if not windowed:
        windowed = [rms]
    low_energy_threshold = max(rms * 0.25, 1e-4)
    low_energy_ratio = float(sum(value < low_energy_threshold for value in windowed)) / float(len(windowed))
    return {
        "path": path,
        "duration": round(duration, 6),
        "sample_rate": int(sample_rate),
        "channels": channels,
        "rms": round(rms, 8),
        "peak": round(peak, 8),
        "low_energy_ratio": round(low_energy_ratio, 6),
    }
