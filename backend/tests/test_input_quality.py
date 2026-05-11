import json

import numpy as np
import soundfile as sf

from app.services.input_quality import analyze_input_audio, summarize_input_quality, write_input_quality_report


def test_input_quality_report_contains_required_fields(tmp_path):
    input_path = tmp_path / "input.wav"
    samples = np.concatenate(
        [
            np.zeros(22050, dtype=np.float32),
            np.ones(44100, dtype=np.float32) * 0.08,
            np.zeros(22050, dtype=np.float32),
        ]
    )
    sf.write(input_path, samples, 44100)

    report = analyze_input_audio(str(input_path))
    summary = summarize_input_quality(report)
    report_path = write_input_quality_report(tmp_path / "debug", report)
    saved = json.loads((tmp_path / "debug" / "input_quality_report.json").read_text(encoding="utf-8"))

    assert report["duration"] > 0
    assert report["sample_rate"] == 44100
    assert report["channels"] == 1
    assert "low_energy_ratio" in report
    assert "clipping_ratio" in report
    assert "silence_ratio" in report
    assert report["quality_level"] in {"good", "warn", "bad"}
    assert isinstance(report["warnings"], list)
    assert summary["quality_level"] == report["quality_level"]
    assert report_path.endswith("input_quality_report.json")
    assert saved["duration"] == report["duration"]


def test_input_quality_marks_short_or_silent_audio_as_bad(tmp_path):
    input_path = tmp_path / "short.wav"
    sf.write(input_path, np.zeros(8000, dtype=np.float32), 16000)

    report = analyze_input_audio(str(input_path))

    assert report["is_too_short"] is True
    assert report["is_probably_silent"] is True
    assert report["quality_level"] == "bad"
    assert report["warnings"]
