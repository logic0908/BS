from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

try:
    import librosa
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    librosa = None

try:
    from resemblyzer import VoiceEncoder, preprocess_wav
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    VoiceEncoder = None
    preprocess_wav = None


def analyze_audio_pair(input_path: str, output_path: str) -> dict[str, Any]:
    warnings: list[str] = []
    input_metrics = analyze_audio_file(input_path, warnings=warnings)
    output_metrics = analyze_audio_file(output_path, warnings=warnings)
    duration_mismatch_ratio = abs(output_metrics["duration_seconds"] - input_metrics["duration_seconds"]) / max(
        input_metrics["duration_seconds"], 1e-6
    )
    possible_dropouts = bool(output_metrics["silence_ratio"] >= 0.4 or duration_mismatch_ratio >= 0.08)
    mfcc_distance = _mfcc_distance(input_path, output_path, warnings)
    speaker_similarity = _speaker_embedding_similarity(input_path, output_path, warnings)
    style_direction_metrics = _style_direction_metrics(input_metrics, output_metrics)

    comparisons = {
        "duration_delta_seconds": round(output_metrics["duration_seconds"] - input_metrics["duration_seconds"], 6),
        "sample_rate_match": input_metrics["sample_rate"] == output_metrics["sample_rate"],
        "rms_energy_delta": round(output_metrics["rms_energy"] - input_metrics["rms_energy"], 8),
        "peak_amplitude_delta": round(output_metrics["peak_amplitude"] - input_metrics["peak_amplitude"], 8),
        "clipping_ratio_delta": round(output_metrics["clipping_ratio"] - input_metrics["clipping_ratio"], 8),
        "silence_ratio_delta": round(output_metrics["silence_ratio"] - input_metrics["silence_ratio"], 8),
        "spectral_centroid_mean_delta": round(
            output_metrics["spectral_centroid_mean"] - input_metrics["spectral_centroid_mean"], 6
        ),
        "spectral_centroid_std_delta": round(
            output_metrics["spectral_centroid_std"] - input_metrics["spectral_centroid_std"], 6
        ),
        "f0_mean_delta": _rounded_delta(output_metrics.get("f0_mean"), input_metrics.get("f0_mean"), digits=6),
        "f0_std_delta": _rounded_delta(output_metrics.get("f0_std"), input_metrics.get("f0_std"), digits=6),
        "f0_voiced_ratio_delta": _rounded_delta(
            output_metrics.get("f0_voiced_ratio"),
            input_metrics.get("f0_voiced_ratio"),
            digits=6,
        ),
        "mfcc_distance": mfcc_distance,
        "mel_spectral_distance": mfcc_distance,
        "speaker_embedding_similarity": speaker_similarity,
        "style_direction_metrics": style_direction_metrics,
    }

    return {
        "input_audio": input_metrics,
        "output_audio": output_metrics,
        "duration_mismatch_ratio": round(float(duration_mismatch_ratio), 6),
        "possible_dropouts": possible_dropouts,
        "comparisons": comparisons,
        "warnings": warnings,
        "summary": {
            "duration_consistency": round(max(0.0, 1.0 - duration_mismatch_ratio), 6),
            "low_energy_ratio": output_metrics["silence_ratio"],
            "possible_dropouts": possible_dropouts,
            "rms_energy_delta": comparisons["rms_energy_delta"],
            "spectral_centroid_mean_delta": comparisons["spectral_centroid_mean_delta"],
            "f0_mean_delta": comparisons["f0_mean_delta"],
        },
    }


def analyze_audio_file(path: str, warnings: list[str] | None = None) -> dict[str, Any]:
    audio, sample_rate = sf.read(path, always_2d=True)
    channels = int(audio.shape[1])
    mono = audio.mean(axis=1).astype(np.float32)
    if mono.size == 0:
        raise ValueError(f"Audio file is empty: {path}")

    rms = float(np.sqrt(np.mean(np.square(mono)) + 1e-8))
    peak = float(np.max(np.abs(mono)))
    duration = float(mono.shape[0]) / float(sample_rate)
    clipping_ratio = float(np.mean(np.abs(mono) >= 0.99))
    frames = _frame_rms(mono)
    low_energy_threshold = max(rms * 0.25, 1e-4)
    silence_ratio = float(np.mean(frames < low_energy_threshold)) if frames.size else 0.0
    centroid_mean, centroid_std = _spectral_centroid_stats(mono, sample_rate)
    f0_mean, f0_std, voiced_ratio = _estimate_f0_stats(mono, sample_rate, warnings)

    payload = {
        "path": path,
        "duration": round(duration, 6),
        "duration_seconds": round(duration, 6),
        "sample_rate": int(sample_rate),
        "channels": channels,
        "rms": round(rms, 8),
        "rms_energy": round(rms, 8),
        "peak": round(peak, 8),
        "peak_amplitude": round(peak, 8),
        "clipping_ratio": round(clipping_ratio, 8),
        "low_energy_ratio": round(silence_ratio, 6),
        "silence_ratio": round(silence_ratio, 6),
        "spectral_centroid_mean": round(centroid_mean, 6),
        "spectral_centroid_std": round(centroid_std, 6),
        "f0_mean": f0_mean,
        "f0_std": f0_std,
        "f0_voiced_ratio": voiced_ratio,
        "has_nan_or_inf": bool(np.isnan(mono).any() or np.isinf(mono).any()),
    }
    return payload


def write_audio_quality_report(debug_dir: str | Path, report: dict[str, Any]) -> str:
    target_dir = Path(debug_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "audio_quality_report.json"
    target_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(target_path)


def _frame_rms(mono: np.ndarray, frame_length: int = 2048, hop_length: int = 512) -> np.ndarray:
    if mono.size <= frame_length:
        return np.asarray([float(np.sqrt(np.mean(np.square(mono)) + 1e-8))], dtype=np.float32)
    values: list[float] = []
    for start in range(0, mono.shape[0] - frame_length + 1, hop_length):
        frame = mono[start : start + frame_length]
        values.append(float(np.sqrt(np.mean(np.square(frame)) + 1e-8)))
    return np.asarray(values, dtype=np.float32)


def _spectral_centroid_stats(mono: np.ndarray, sample_rate: int) -> tuple[float, float]:
    frame_length = min(2048, max(512, mono.shape[0]))
    hop_length = max(frame_length // 4, 128)
    window = np.hanning(frame_length).astype(np.float32)
    freqs = np.fft.rfftfreq(frame_length, d=1.0 / float(sample_rate))
    centroids: list[float] = []
    if mono.size <= frame_length:
        padded = np.pad(mono, (0, max(0, frame_length - mono.size)))
        magnitude = np.abs(np.fft.rfft(padded[:frame_length] * window))
        denominator = float(np.sum(magnitude) + 1e-8)
        centroids.append(float(np.sum(freqs * magnitude) / denominator))
    else:
        for start in range(0, mono.shape[0] - frame_length + 1, hop_length):
            frame = mono[start : start + frame_length]
            magnitude = np.abs(np.fft.rfft(frame * window))
            denominator = float(np.sum(magnitude) + 1e-8)
            centroids.append(float(np.sum(freqs * magnitude) / denominator))
    values = np.asarray(centroids or [0.0], dtype=np.float32)
    return float(values.mean()), float(values.std())


def _estimate_f0_stats(
    mono: np.ndarray,
    sample_rate: int,
    warnings: list[str] | None,
) -> tuple[float | None, float | None, float | None]:
    if librosa is None:
        if warnings is not None:
            warnings.append("librosa_missing:f0_metrics_skipped")
        return None, None, None

    try:
        f0, _, _ = librosa.pyin(
            mono.astype(np.float32),
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sample_rate,
            frame_length=2048,
            hop_length=256,
        )
    except Exception as exc:  # pragma: no cover - depends on local librosa backend
        if warnings is not None:
            warnings.append(f"f0_metrics_failed:{type(exc).__name__}")
        return None, None, None

    voiced = f0[~np.isnan(f0)]
    if voiced.size == 0:
        return None, None, 0.0
    return round(float(np.mean(voiced)), 6), round(float(np.std(voiced)), 6), round(float(voiced.size / f0.size), 6)


def _mfcc_distance(input_path: str, output_path: str, warnings: list[str]) -> float | None:
    if librosa is None:
        warnings.append("librosa_missing:mfcc_distance_skipped")
        return None
    try:
        in_audio, in_sr = librosa.load(input_path, sr=None, mono=True)
        out_audio, out_sr = librosa.load(output_path, sr=None, mono=True)
        target_sr = in_sr if in_sr == out_sr else min(in_sr, out_sr)
        if in_sr != target_sr:
            in_audio = librosa.resample(in_audio, orig_sr=in_sr, target_sr=target_sr)
        if out_sr != target_sr:
            out_audio = librosa.resample(out_audio, orig_sr=out_sr, target_sr=target_sr)
        mfcc_in = librosa.feature.mfcc(y=in_audio, sr=target_sr, n_mfcc=13)
        mfcc_out = librosa.feature.mfcc(y=out_audio, sr=target_sr, n_mfcc=13)
        min_frames = min(mfcc_in.shape[1], mfcc_out.shape[1])
        if min_frames == 0:
            return None
        delta = mfcc_in[:, :min_frames] - mfcc_out[:, :min_frames]
        return round(float(np.sqrt(np.mean(np.square(delta)))), 6)
    except Exception as exc:  # pragma: no cover - depends on local librosa backend
        warnings.append(f"mfcc_distance_failed:{type(exc).__name__}")
        return None


_VOICE_ENCODER: VoiceEncoder | None | bool = None


def _speaker_embedding_similarity(input_path: str, output_path: str, warnings: list[str]) -> float | None:
    global _VOICE_ENCODER
    if VoiceEncoder is None or preprocess_wav is None:
        warnings.append("resemblyzer_missing:speaker_similarity_skipped")
        return None
    try:
        if _VOICE_ENCODER is None:
            _VOICE_ENCODER = VoiceEncoder()
        encoder = _VOICE_ENCODER
        assert encoder is not False
        input_embed = encoder.embed_utterance(preprocess_wav(input_path))
        output_embed = encoder.embed_utterance(preprocess_wav(output_path))
        similarity = float(
            np.dot(input_embed, output_embed)
            / max(np.linalg.norm(input_embed) * np.linalg.norm(output_embed), 1e-8)
        )
        return round(similarity, 6)
    except Exception as exc:  # pragma: no cover - depends on optional package
        warnings.append(f"speaker_similarity_failed:{type(exc).__name__}")
        return None


def _style_direction_metrics(input_metrics: dict[str, Any], output_metrics: dict[str, Any]) -> dict[str, float | None]:
    brightness_delta = _rounded_delta(
        output_metrics.get("spectral_centroid_mean"),
        input_metrics.get("spectral_centroid_mean"),
        digits=6,
    )
    energy_delta = _rounded_delta(output_metrics.get("rms_energy"), input_metrics.get("rms_energy"), digits=8)
    pitch_delta = _rounded_delta(output_metrics.get("f0_mean"), input_metrics.get("f0_mean"), digits=6)

    input_softness = _softness_proxy(input_metrics)
    output_softness = _softness_proxy(output_metrics)
    softness_delta = _rounded_delta(output_softness, input_softness, digits=6)

    input_thickness = _thickness_proxy(input_metrics)
    output_thickness = _thickness_proxy(output_metrics)
    thickness_delta = _rounded_delta(output_thickness, input_thickness, digits=6)
    return {
        "brightness_delta": brightness_delta,
        "energy_delta": energy_delta,
        "pitch_height_delta": pitch_delta,
        "softness_delta": softness_delta,
        "thickness_delta": thickness_delta,
    }


def _softness_proxy(metrics: dict[str, Any]) -> float | None:
    centroid = metrics.get("spectral_centroid_mean")
    peak = metrics.get("peak_amplitude")
    if centroid is None or peak is None:
        return None
    return float((1.0 / max(float(centroid), 1.0)) * max(0.05, 1.0 - min(float(peak), 1.0)))


def _thickness_proxy(metrics: dict[str, Any]) -> float | None:
    rms = metrics.get("rms_energy")
    centroid = metrics.get("spectral_centroid_mean")
    if rms is None or centroid is None:
        return None
    return float(float(rms) / max(float(centroid), 1.0))


def _rounded_delta(after: Any, before: Any, *, digits: int) -> float | None:
    if after is None or before is None:
        return None
    return round(float(after) - float(before), digits)
