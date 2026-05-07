from __future__ import annotations

import asyncio
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi import HTTPException

from app.api.endpoints import style_analysis as style_analysis_endpoint
from app.services.audio_style_analysis import (
    analyze_audio_style,
    compare_audio_style,
    parse_prompt_style_targets,
)
from app.services.svc_task_service import TaskState, svc_task_service


def _write_sine(path: Path, *, sample_rate: int = 22050, frequency: float = 220.0, duration: float = 0.8) -> None:
    timeline = np.linspace(0.0, duration, int(sample_rate * duration), endpoint=False, dtype=np.float32)
    audio = 0.2 * np.sin(2 * np.pi * frequency * timeline)
    sf.write(path, audio, sample_rate)


def _assert_no_nonfinite(value) -> None:
    if isinstance(value, dict):
        for nested in value.values():
            _assert_no_nonfinite(nested)
        return
    if isinstance(value, list):
        for nested in value:
            _assert_no_nonfinite(nested)
        return
    if isinstance(value, float):
        assert np.isfinite(value)


def _simple_compute_analysis(audio: np.ndarray, sample_rate: int, warnings: list[str]):
    del warnings
    spectrum = np.abs(np.fft.rfft(audio))
    frequencies = np.fft.rfftfreq(len(audio), d=1.0 / sample_rate)
    dominant_index = int(np.argmax(spectrum[1:]) + 1) if spectrum.size > 1 else 0
    dominant_frequency = float(frequencies[dominant_index]) if frequencies.size else 0.0
    rms_mean = float(np.sqrt(np.mean(np.square(audio), dtype=np.float64)))
    zero_crossing = float(np.mean(np.abs(np.diff(np.signbit(audio)).astype(np.float32))))
    low_energy_ratio = 0.65 if dominant_frequency < 260 else 0.28
    high_energy_ratio = 0.12 if dominant_frequency < 260 else 0.34
    brightness = min(1.0, dominant_frequency / 500.0)
    softness = max(0.0, 1.0 - dominant_frequency / 700.0)
    thickness = max(0.0, 1.0 - dominant_frequency / 650.0)
    return {
        "rms_mean": round(rms_mean, 6),
        "rms_std": 0.0,
        "dynamic_range": round(float(np.max(audio) - np.min(audio)), 6),
        "spectral_centroid_mean": round(dominant_frequency, 6),
        "spectral_bandwidth_mean": round(dominant_frequency / 2.0, 6),
        "spectral_rolloff_mean": round(dominant_frequency * 1.2, 6),
        "zero_crossing_rate_mean": round(zero_crossing, 6),
        "f0_available": True,
        "f0_mean": round(dominant_frequency, 6),
        "f0_median": round(dominant_frequency, 6),
        "f0_std": 0.0,
        "f0_min": round(dominant_frequency, 6),
        "f0_max": round(dominant_frequency, 6),
        "voiced_ratio": 1.0,
        "low_energy_ratio": low_energy_ratio,
        "mid_energy_ratio": round(1.0 - low_energy_ratio - high_energy_ratio, 6),
        "high_energy_ratio": high_energy_ratio,
        "brightness_score": round(brightness, 6),
        "energy_score": round(min(1.0, rms_mean / 0.25), 6),
        "softness_score": round(softness, 6),
        "thickness_score": round(thickness, 6),
        "pitch_height_score": round(brightness, 6),
    }


@pytest.fixture(autouse=True)
def clear_task_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("NUMBA_DISABLE_JIT", "1")
    monkeypatch.setenv("NUMBA_CACHE_DIR", str(tmp_path / "numba_cache"))
    monkeypatch.setattr(svc_task_service, "use_celery", lambda: False)
    svc_task_service._tasks.clear()
    yield
    svc_task_service._tasks.clear()


@pytest.fixture
def style_analysis_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    uploads_dir = tmp_path / "backend" / "app" / "data" / "uploads"
    processed_dir = tmp_path / "backend" / "app" / "data" / "processed"
    runtime_debug_dir = tmp_path / "runtime" / "debug"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    runtime_debug_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(style_analysis_endpoint, "UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr(style_analysis_endpoint, "PROCESSED_DIR", processed_dir)
    monkeypatch.setattr(style_analysis_endpoint, "RUNTIME_DEBUG_DIR", runtime_debug_dir)
    monkeypatch.setattr(
        style_analysis_endpoint,
        "URL_PREFIXES",
        {
            "/files/uploads/": uploads_dir,
            "/files/vocals/": uploads_dir,
            "/files/outputs/": processed_dir,
        },
    )
    return {
        "uploads": uploads_dir,
        "processed": processed_dir,
        "runtime_debug": runtime_debug_dir,
    }


def test_analyze_audio_style_sanitizes_nan_and_inf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    audio_path = tmp_path / "input.wav"
    _write_sine(audio_path)

    monkeypatch.setattr(
        "app.services.audio_style_analysis._compute_analysis",
        lambda *_args, **_kwargs: {
            "brightness_score": np.nan,
            "energy_score": np.inf,
            "softness_score": -np.inf,
            "thickness_score": 0.42,
            "pitch_height_score": 0.36,
            "warnings": [],
        },
    )

    report = analyze_audio_style(audio_path)

    assert report["ok"] is True
    assert report["brightness_score"] is None
    assert report["energy_score"] is None
    assert report["softness_score"] is None
    assert report["thickness_score"] == 0.42
    _assert_no_nonfinite(report)


def test_compare_audio_style_returns_expected_sections(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    input_path = tmp_path / "input.wav"
    output_path = tmp_path / "output.wav"
    _write_sine(input_path, frequency=220.0)
    _write_sine(output_path, frequency=330.0)
    monkeypatch.setattr("app.services.audio_style_analysis._compute_analysis", _simple_compute_analysis)

    report = compare_audio_style(input_path, output_path, "清亮、少年感", model_preset_id="final_primary")

    assert report["ok"] is True
    assert set(report) >= {"input", "output", "prompt_targets", "comparisons", "radar", "summary", "warnings"}
    assert report["prompt_targets"]["matched_keywords"] == ["少年感", "清亮"]
    assert isinstance(report["comparisons"], list)
    assert report["radar"]["dimensions"] == ["brightness", "energy", "softness", "thickness", "pitch_height"]
    _assert_no_nonfinite(report)


def test_parse_prompt_style_targets_extracts_expected_dimensions():
    targets = parse_prompt_style_targets("温柔、治愈、气声")

    assert targets["matched_keywords"] == ["温柔", "治愈", "气声"]
    assert targets["target_dimensions"]["softness"] in {"up", "slightly_up"}
    assert "柔和度增强" in targets["human_readable_targets"]


def test_style_analysis_endpoint_accepts_known_task_output_and_rejects_forbidden_paths(
    style_analysis_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
):
    uploads_dir = style_analysis_paths["uploads"]
    runtime_debug_dir = style_analysis_paths["runtime_debug"]
    upload_dir = uploads_dir / "vocals-1"
    upload_dir.mkdir(parents=True, exist_ok=True)

    input_path = upload_dir / "vocals.wav"
    output_path = runtime_debug_dir / "task-1" / "converted.wav"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_sine(input_path, frequency=220.0)
    _write_sine(output_path, frequency=330.0)
    monkeypatch.setattr("app.services.audio_style_analysis._compute_analysis", _simple_compute_analysis)

    svc_task_service._tasks["task-1"] = TaskState(
        task_id="task-1",
        status="succeeded",
        message="转换完成",
        engine="sovits",
        vocals_id="vocals-1",
        output_path=str(output_path),
        engine_details={"final_output_path": str(output_path)},
    )

    payload = asyncio.run(
        style_analysis_endpoint.compare_style_analysis(
            style_analysis_endpoint.StyleAnalysisCompareRequest(
                input_path=str(input_path),
                output_url="/files/outputs/task-1/converted.wav",
                prompt_text="清亮、少年感",
                model_preset_id="final_primary",
            )
        )
    )

    assert payload["ok"] is True
    assert payload["output"]["path"] == str(output_path.resolve())

    forbidden_path = style_analysis_paths["runtime_debug"] / "task-x" / "secret.wav"
    forbidden_path.parent.mkdir(parents=True, exist_ok=True)
    _write_sine(forbidden_path, frequency=440.0)

    with pytest.raises(HTTPException) as forbidden_error:
        asyncio.run(
            style_analysis_endpoint.compare_style_analysis(
                style_analysis_endpoint.StyleAnalysisCompareRequest(
                    input_path=str(input_path),
                    output_path=str(forbidden_path),
                    prompt_text="清亮",
                )
            )
        )
    assert forbidden_error.value.status_code == 403
    assert forbidden_error.value.detail["code"] == "STYLE_ANALYSIS_PATH_FORBIDDEN"

    local_models_path = runtime_debug_dir.parent.parent / "local_models" / "blocked.wav"
    local_models_path.parent.mkdir(parents=True, exist_ok=True)
    _write_sine(local_models_path, frequency=110.0)

    with pytest.raises(HTTPException) as blocked_error:
        asyncio.run(
            style_analysis_endpoint.compare_style_analysis(
                style_analysis_endpoint.StyleAnalysisCompareRequest(
                    input_path=str(local_models_path),
                    output_url="/files/outputs/task-1/converted.wav",
                    prompt_text="清亮",
                )
            )
        )
    assert blocked_error.value.status_code == 403
    assert blocked_error.value.detail["code"] == "STYLE_ANALYSIS_PATH_FORBIDDEN"
