import json

import numpy as np
import soundfile as sf

from app.services.audio_quality import analyze_audio_pair, write_audio_quality_report


def test_audio_quality_report_contains_expected_metrics(tmp_path):
    input_path = tmp_path / "input.wav"
    output_path = tmp_path / "output.wav"
    sf.write(input_path, np.ones(44100, dtype=np.float32) * 0.2, 44100)
    sf.write(output_path, np.ones(44100, dtype=np.float32) * 0.15, 44100)

    report = analyze_audio_pair(str(input_path), str(output_path))

    assert report["input_audio"]["duration"] > 0
    assert report["output_audio"]["sample_rate"] == 44100
    assert "low_energy_ratio" in report["summary"]
    assert "possible_dropouts" in report["summary"]

    report_path = write_audio_quality_report(tmp_path / "debug", report)
    payload = json.loads((tmp_path / "debug" / "audio_quality_report.json").read_text(encoding="utf-8"))
    assert report_path.endswith("audio_quality_report.json")
    assert payload["summary"]["duration_consistency"] >= 0.0
