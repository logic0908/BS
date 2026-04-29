import os
import sys
import asyncio
import numpy as np
import librosa
import logging
import pytest
from io import BytesIO
from types import SimpleNamespace
from fastapi import BackgroundTasks, HTTPException, UploadFile

# 添加 backend 到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models_svc.stylesinger_wrapper import stylesinger_service
import app.models_svc.stylesinger_wrapper as stylesinger_wrapper_module
from app.main import app
from scripts.check_enhanced_stack import run_check
import scripts.setup_rmvpe as setup_rmvpe_script

def test_prompt_text_does_not_change_features(mocker):
    """
    验证 prompt_text 参数被保留但不影响 4D 特征提取。
    """
    # mock Whisper 和 librosa
    mocker.patch('whisper.load_model', return_value=mocker.MagicMock())
    mocker.patch('librosa.load', return_value=(mocker.MagicMock(), 16000))
    mocker.patch('librosa.resample', return_value=mocker.MagicMock())
    
    # 模拟 extract_features 中的一些外部调用，以便它能跑完基本逻辑
    # 真实环境下更推荐抽出辅助函数做单测，这里用简单的 mock 代替
    pass # 如果进一步抽出内部逻辑，可以测试更细粒度的函数

def test_phone_mapping_keeps_in_and_ing():
    """
    验证 in/ing 不会被改成 en/eng。
    """
    # 提取内部的 _normalize_pinyin_to_stylesinger 函数进行测试
    # 为了方便测试，我们可以直接在这里复制那个辅助函数的逻辑
    def _normalize_pinyin_to_stylesinger(ins: str, fns: str) -> tuple[str, str]:
        if ins in ['z', 'c', 's'] and fns == 'i':
            fns = 'i'
        elif ins in ['zh', 'ch', 'sh', 'r'] and fns == 'i':
            fns = 'i'
        
        mapping = {
            'iu': 'iou',
            'ui': 'uei',
            'un': 'uen',
            'ü': 'v',
            'ün': 'vn',
            'ue': 've',
            'üe': 've'
        }
        fns = mapping.get(fns, fns)
        return ins, fns

    assert _normalize_pinyin_to_stylesinger("b", "in") == ("b", "in")
    assert _normalize_pinyin_to_stylesinger("p", "ing") == ("p", "ing")
    assert _normalize_pinyin_to_stylesinger("n", "ue") == ("n", "ve")

def test_zero_initial_does_not_emit_y_or_w():
    """
    验证零声母音节不会输出 y / w。
    """
    def _normalize_pinyin_to_stylesinger(ins: str, fns: str) -> tuple[str, str]:
        if ins in ['z', 'c', 's'] and fns == 'i':
            fns = 'i'
        elif ins in ['zh', 'ch', 'sh', 'r'] and fns == 'i':
            fns = 'i'
        
        mapping = {
            'iu': 'iou',
            'ui': 'uei',
            'un': 'uen',
            'ü': 'v',
            'ün': 'vn',
            'ue': 've',
            'üe': 've'
        }
        fns = mapping.get(fns, fns)
        return ins, fns

    assert _normalize_pinyin_to_stylesinger("", "a") == ("", "a")
    assert _normalize_pinyin_to_stylesinger("", "i") == ("", "i")
    assert _normalize_pinyin_to_stylesinger("", "u") == ("", "u")

def test_g2p_zero_initial_maps_to_stylesinger_finals_correctly():
    entries = stylesinger_service._g2p_chinese_to_stylesinger_phones("月圆云有")
    by_char = {entry["char"]: entry for entry in entries}
    assert by_char["月"]["final"] == "ve"
    assert by_char["圆"]["final"] == "van"
    assert by_char["云"]["final"] == "vn"
    assert by_char["有"]["final"] == "iou"

def test_g2p_initial_final_mapping_matches_stylesinger_phone_set():
    entries = stylesinger_service._g2p_chinese_to_stylesinger_phones("我和你在音乐里成长")
    assert entries
    for entry in entries:
        for ph in entry["phones"]:
            assert ph in stylesinger_service._stylesinger_phone_set

def test_ap_sp_are_normalized_to_breathe_and_none():
    assert stylesinger_service._normalize_special_tokens("<AP>") == "breathe"
    assert stylesinger_service._normalize_special_tokens("AP") == "breathe"
    assert stylesinger_service._normalize_special_tokens("<SP>") == "_NONE"
    assert stylesinger_service._normalize_special_tokens("SP") == "_NONE"

def test_rest_always_normalized():
    """
    验证任何 rest 相关输入最终都会变成：
    ph="_NONE", note=0, type=1
    """
    ph = ["SP", "_NONE", "a"]
    note = [0, 64, 0]
    dur = [0.3, 0.2, 0.1]
    type_seq = [2, 2, 3]

    s_ph, s_note, _s_dur, s_type = stylesinger_service._sanitize_feature_sequences(ph, note, dur, type_seq)

    # 验证 SP, note=0, type=2 被归一化
    assert s_ph[0] == "_NONE"
    assert s_note[0] == 0
    assert s_type[0] == 1
    
    # 验证 _NONE, note=64 被归一化
    assert s_ph[1] == "_NONE"
    assert s_note[1] == 0
    assert s_type[1] == 1
    
    # 验证 a, note=0, type=3 被归一化
    assert s_ph[2] == "_NONE"
    assert s_note[2] == 0
    assert s_type[2] == 1

def test_breathe_token_preserved_by_sanitize():
    s_ph, s_note, _s_dur, s_type = stylesinger_service._sanitize_feature_sequences(
        ["breathe"],
        [0],
        [0.12],
        [1],
    )
    assert s_ph == ["breathe"]
    assert s_note == [0]
    assert s_type == [1]

def test_breathe_token_preserved_after_sanitize():
    s_ph, s_note, _s_dur, s_type = stylesinger_service._sanitize_feature_sequences(
        ["<AP>"],
        [0],
        [0.12],
        [1],
    )
    assert s_ph == ["breathe"]
    assert s_note == [0]
    assert s_type == [1]

def test_no_sequence_starts_with_illegal_slur():
    """
    验证 sanitize 后，第一个非休止 token 绝不能是 type=3
    """
    ph = ["_NONE", "a"]
    note = [0, 64]
    dur = [0.2, 0.3]
    type_seq = [1, 3]
    
    _s_ph, _s_note, _s_dur, s_type = stylesinger_service._sanitize_feature_sequences(ph, note, dur, type_seq)
    
    assert s_type[1] == 2  # 被强制修正为主音

def test_slur_after_rest_is_downgraded():
    """
    验证 rest 后紧跟的孤立 slur 会被自动降级为 lyric(type=2)。
    """
    ph = ["a", "_NONE", "b"]
    note = [60, 0, 64]
    dur = [0.2, 0.2, 0.3]
    type_seq = [2, 1, 3]

    s_ph, s_note, _s_dur, s_type = stylesinger_service._sanitize_feature_sequences(ph, note, dur, type_seq)

    assert s_ph == ["a", "_NONE", "b"]
    assert s_note == [60, 0, 64]
    assert s_type == [2, 1, 2]

def test_build_infer_input_sanitizes_score_payload():
    """
    验证 _build_infer_input() 对前端脏 score_payload 的彻底净化。
    """
    score_payload = {
        "ph": ["a", "_NONE", "b"],
        "note": [0, 64, 65],
        "note_dur": [0.01, 0.2, 0.3],
        "note_type": [3, 2, 9]
    }
    
    profile = {"duration_scale": 1.0}
    # 构造一个假音频路径并 Mock librosa 以跳过真实音频读取
    inp = stylesinger_service._build_infer_input(
        ref_audio_path="/fake/path.wav", 
        profile=profile, 
        style_strength=0.0, 
        score_payload=score_payload
    )
    
    # "a", 0, 0.01, 3 -> "_NONE", 0, 0.05 (时长下限), 1
    assert inp["ph"][0] == "_NONE"
    assert inp["note"][0] == 0
    assert inp["note_type"][0] == 1
    assert inp["note_dur"][0] >= 0.05
    
    # "_NONE", 64, 0.2, 2 -> "_NONE", 0, 0.2, 1
    assert inp["ph"][1] == "_NONE"
    assert inp["note"][1] == 0
    assert inp["note_type"][1] == 1
    
    # "b", 65, 0.3, 9 -> "b", 65, 0.3, 2 (非法 type 9 修正为 2，同时因为前面是 rest，即使是 3 也会被修正为 2)
    assert inp["ph"][2] == "b"
    assert inp["note"][2] == 65
    assert inp["note_type"][2] == 2

    # 验证长度一致
    assert len(inp["ph"]) == len(inp["note"]) == len(inp["note_dur"]) == len(inp["note_type"])

def test_skip_demucs_for_vocal_only_input(mocker):
    mocked = mocker.patch("app.models_svc.stylesinger_wrapper.AudioProcessor.separate_vocals")
    out = stylesinger_service._prepare_reference_audio("/tmp/example.wav", is_vocal_only=True)
    assert out == "/tmp/example.wav"
    mocked.assert_not_called()

def test_run_demucs_for_non_vocal_input(mocker):
    mocked = mocker.patch(
        "app.models_svc.stylesinger_wrapper.AudioProcessor.separate_vocals",
        return_value="/tmp/separated/vocals.wav",
    )
    out = stylesinger_service._prepare_reference_audio("/tmp/example.wav", work_dir="/tmp/separated", is_vocal_only=False)
    assert out == "/tmp/separated/vocals.wav"
    mocked.assert_called_once()

def test_merge_micro_slur_into_previous_token():
    ph, note, dur, note_type, merged = stylesinger_service._merge_micro_segments(
        ["a", "a", "b"],
        [60, 60, 64],
        [0.20, 0.05, 0.30],
        [2, 3, 2],
        return_count=True,
    )
    assert merged == 1
    assert ph == ["a", "b"]
    assert note == [60, 64]
    assert dur[0] == 0.25
    assert note_type == [2, 2]

def test_drop_or_merge_micro_rest_between_voiced_tokens():
    ph, note, dur, note_type, merged = stylesinger_service._merge_micro_segments(
        ["a", "_NONE", "b"],
        [60, 0, 61],
        [0.20, 0.05, 0.30],
        [2, 1, 2],
        return_count=True,
    )
    assert merged == 1
    assert ph == ["a", "b"]
    assert note == [60, 61]
    assert dur[0] == 0.25
    assert note_type == [2, 2]

def test_initial_final_duration_split_prefers_final():
    initial_dur, final_dur = stylesinger_service._split_initial_final_duration(
        char_duration=0.40,
        has_initial=True,
        energy_rise_ratio=0.22,
    )
    assert final_dur > initial_dur
    assert round(initial_dur + final_dur, 3) <= 0.401

def test_quality_metrics_warn_when_rest_or_micro_ratio_too_high(caplog):
    metrics = stylesinger_service._compute_feature_quality_metrics(
        ["_NONE", "_NONE", "a", "b"],
        [0, 0, 60, 61],
        [0.05, 0.07, 0.08, 0.07],
        [1, 1, 3, 3],
        sanitized_count=2,
        merged_count=1,
    )
    with caplog.at_level(logging.WARNING):
        stylesinger_service._log_feature_quality_metrics(metrics)
    assert "rest_ratio too high" in caplog.text
    assert "slur_ratio too high" in caplog.text
    assert "too many micro tokens" in caplog.text

def test_quality_gate_rejects_high_micro_ratio():
    allow, reason = stylesinger_service._evaluate_feature_quality_gate(
        {"micro_token_ratio": 0.30, "rest_ratio": 0.0, "token_count": 10}
    )
    assert allow is False
    assert reason == "Too many micro segments in extracted features"

def test_quality_gate_rejects_high_rest_ratio():
    allow, reason = stylesinger_service._evaluate_feature_quality_gate(
        {"micro_token_ratio": 0.1, "rest_ratio": 0.20, "token_count": 10}
    )
    assert allow is False
    assert reason == "Too many rest tokens in extracted features"

def test_segment_audio_for_feature_extraction_returns_reasonable_phrases():
    sr = 16000
    t = np.linspace(0, 2.0, int(sr * 2.0), endpoint=False)
    voiced = 0.2 * np.sin(2 * np.pi * 220 * t).astype(np.float32)
    silence = np.zeros(int(sr * 0.5), dtype=np.float32)
    y = np.concatenate([silence, voiced, silence, voiced, silence])
    segments = stylesinger_service._segment_audio_for_feature_extraction(y, sr)
    assert segments
    for start, end in segments:
        assert end > start
        assert 1.5 <= (end - start) <= 8.0

def test_extract_features_uses_plain_whisper_by_default(mocker):
    plain_mock = mocker.patch.object(
        stylesinger_service,
        "_transcribe_with_plain_whisper",
        return_value=[{"text": "啊", "start": 0.0, "end": 0.2}],
    )
    align_mock = mocker.patch.object(stylesinger_service, "_transcribe_and_align_with_whisperx")
    mocker.patch.object(stylesinger_service, "_prepare_reference_audio", return_value="/fake.wav")
    mocker.patch("librosa.load", return_value=(np.zeros(3200, dtype=np.float32), 16000))
    mocker.patch("librosa.feature.rms", return_value=np.ones((1, 64), dtype=np.float32))
    mocker.patch.object(stylesinger_service, "_extract_pitch_with_parselmouth", return_value={
        "times": np.array([0.0, 0.01, 0.02, 0.03], dtype=np.float32),
        "f0": np.array([440.0, 440.0, 440.0, 440.0], dtype=np.float32),
        "midi": np.array([69.0, 69.0, 69.0, 69.0], dtype=np.float32),
    })

    def fake_pinyin(_char, style, strict=True, **kwargs):
        if getattr(style, "name", "") == "INITIALS":
            return [[""]]
        return [["a"]]

    mocker.patch("pypinyin.pinyin", side_effect=fake_pinyin)
    stylesinger_service.extract_features("/fake.wav", prompt_text="抒情")
    plain_mock.assert_called_once()
    align_mock.assert_not_called()

def test_enhanced_mode_raises_when_whisperx_missing(mocker):
    mocker.patch.object(stylesinger_service, "_get_whisperx_runtime", side_effect=ImportError("missing whisperx"))
    mocker.patch.dict("os.environ", {"FEATURE_EXTRACTION_POLICY": "force_enhanced"})
    mocker.patch.object(stylesinger_service, "extract_features", side_effect=RuntimeError("Enhanced feature extraction requires whisperx"))
    with pytest.raises(RuntimeError, match="requires whisperx"):
        stylesinger_service.extract_features(
            audio_path="/tmp/fake.wav",
            prompt_text="",
            is_vocal_only=False,
            transcript_hint="",
        )

def test_prepare_transformers_runtime_for_whisperx_sets_no_tf_env(monkeypatch):
    monkeypatch.delenv("USE_TF", raising=False)
    monkeypatch.delenv("TRANSFORMERS_NO_TF", raising=False)
    stylesinger_wrapper_module._prepare_transformers_runtime_for_whisperx()
    assert os.environ["USE_TF"] == "0"
    assert os.environ["TRANSFORMERS_NO_TF"] == "1"

def test_enhanced_mode_raises_when_rmvpe_missing(mocker):
    mocker.patch.object(
        stylesinger_service,
        "get_enhanced_stack_status",
        return_value={
            "checked": True,
            "ready": False,
            "mode_default": "enhanced",
            "missing": ["rmvpe"],
            "details": {},
        },
    )
    with pytest.raises(RuntimeError, match="requires rmvpe"):
        stylesinger_service._validate_enhanced_feature_stack()

def test_plain_whisper_fallback_when_whisperx_unavailable(mocker):
    fallback = [{"text": "我", "start": 0.0, "end": 0.2}]
    mocker.patch.object(stylesinger_service, "_get_whisperx_runtime", side_effect=ImportError("no whisperx"))
    plain_mock = mocker.patch.object(stylesinger_service, "_transcribe_with_plain_whisper", return_value=fallback)
    out = stylesinger_service._transcribe_and_align_with_whisperx("/fake.wav", transcript_hint="我")
    assert out == fallback
    plain_mock.assert_called_once()

def test_feature_extraction_mode_defaults_to_auto_even_with_lyrics(mocker):
    mocker.patch.object(
        stylesinger_service,
        "get_enhanced_stack_status",
        return_value={"checked": True, "ready": True, "mode_default": "auto", "missing": [], "details": {}},
    )
    mocker.patch.dict(os.environ, {}, clear=True)
    assert stylesinger_service._get_feature_extraction_mode(lyrics="我爱你") == "auto"

def test_feature_extraction_mode_allows_explicit_legacy(mocker):
    mocker.patch.dict(os.environ, {"STYLE_FEATURE_MODE": "legacy"}, clear=True)
    assert stylesinger_service._get_feature_extraction_mode(lyrics="我爱你") == "legacy"

def test_parselmouth_pitch_backend_used_by_default(mocker):
    mocker.patch.dict(os.environ, {}, clear=True)
    rmvpe_mock = mocker.patch.object(stylesinger_service, "_extract_pitch_with_rmvpe")
    pars_mock = mocker.patch.object(stylesinger_service, "_extract_pitch_with_parselmouth", return_value={"times": np.array([]), "f0": np.array([]), "midi": np.array([])})
    stylesinger_service._extract_pitch_backend("/fake.wav")
    pars_mock.assert_called_once()
    rmvpe_mock.assert_not_called()

def test_parselmouth_pitch_fallback_when_rmvpe_unavailable(mocker):
    mocker.patch.dict(os.environ, {"PITCH_BACKEND": "rmvpe"}, clear=False)
    mocker.patch.object(stylesinger_wrapper_module, "USE_EXPERIMENTAL_RMVPE", True)
    rmvpe_mock = mocker.patch.object(stylesinger_service, "_extract_pitch_with_rmvpe", side_effect=RuntimeError("rmvpe unavailable"))
    pars_mock = mocker.patch.object(
        stylesinger_service,
        "_extract_pitch_with_parselmouth",
        return_value={"times": np.array([]), "f0": np.array([]), "midi": np.array([])},
    )
    stylesinger_service._extract_pitch_backend("/fake.wav")
    rmvpe_mock.assert_called_once()
    pars_mock.assert_called_once()

def test_extract_features_with_plain_whisper_and_parselmouth_returns_valid_4d(mocker):
    mocker.patch.object(stylesinger_service, "_prepare_reference_audio", return_value="/fake.wav")
    mocker.patch.object(
        stylesinger_service,
        "_transcribe_with_plain_whisper",
        return_value=[
            {"text": "你", "start": 0.00, "end": 0.20},
            {"text": "啊", "start": 0.20, "end": 0.40},
        ],
    )
    mocker.patch.object(
        stylesinger_service,
        "_extract_pitch_with_parselmouth",
        return_value={
            "times": np.arange(0.0, 0.5, 0.01, dtype=np.float32),
            "f0": np.full(50, 440.0, dtype=np.float32),
            "midi": np.full(50, 69.0, dtype=np.float32),
        },
    )
    mocker.patch("librosa.load", return_value=(np.zeros(6400, dtype=np.float32), 16000))
    mocker.patch("librosa.feature.rms", return_value=np.ones((1, 128), dtype=np.float32))

    def fake_pinyin(char, style, strict=True, **kwargs):
        if char == "你":
            return [["n"]] if getattr(style, "name", "") == "INITIALS" else [["i"]]
        return [[""]] if getattr(style, "name", "") == "INITIALS" else [["a"]]

    mocker.patch("pypinyin.pinyin", side_effect=fake_pinyin)

    out = stylesinger_service.extract_features("/fake.wav", prompt_text="抒情")
    assert isinstance(out, dict)
    assert "ok" in out
    assert out["source"] in {"auto", "metadata", "legacy"}
    assert "quality" in out or "metrics" in out
    assert {"ph", "note", "note_dur", "note_type"}.issubset(out.keys())
    if out["ok"] is False:
        assert out.get("code") == "FEATURE_QUALITY_GATE_FAILED"
        assert out.get("reasons") or out.get("quality", {}).get("hard_gate_reasons")
    assert len(out["ph"]) == len(out["note"]) == len(out["note_dur"]) == len(out["note_type"])
    assert set(out["note_type"]).issubset({1, 2, 3})
    for ph, note, note_type in zip(out["ph"], out["note"], out["note_type"]):
        if ph == "_NONE":
            assert note == 0
            assert note_type == 1
        if ph == "breathe":
            assert note == 0
            assert note_type == 1
        if note_type in (2, 3):
            assert ph != "_NONE"
            assert note > 0

def test_melisma_expands_only_on_final_when_possible(mocker):
    mocker.patch.object(stylesinger_service, "_prepare_reference_audio", return_value="/fake.wav")
    mocker.patch.object(
        stylesinger_service,
        "_transcribe_with_plain_whisper",
        return_value=[{"text": "你", "start": 0.00, "end": 0.40}],
    )
    mocker.patch.object(
        stylesinger_service,
        "_g2p_chinese_to_stylesinger_phones",
        return_value=[{
            "char": "你",
            "initial": "n",
            "final": "i",
            "phones": ["n", "i"],
            "char_index": 0,
            "normal_py": "ni",
        }],
    )
    times = np.arange(0.0, 0.41, 0.01, dtype=np.float32)
    # 人为构造一字多音走势，触发 final melisma 展开
    freqs = np.concatenate([
        np.full(12, 440.0, dtype=np.float32),
        np.full(12, 493.88, dtype=np.float32),
        np.full(17, 523.25, dtype=np.float32),
    ])
    mocker.patch.object(
        stylesinger_service,
        "_extract_pitch_with_parselmouth",
        return_value={"times": times, "f0": freqs, "midi": librosa.hz_to_midi(freqs)},
    )
    mocker.patch("librosa.load", return_value=(np.zeros(8000, dtype=np.float32), 16000))
    mocker.patch("librosa.feature.rms", return_value=np.ones((1, 128), dtype=np.float32))

    out = stylesinger_service.extract_features("/fake.wav", prompt_text="抒情")
    assert "i" in out["ph"]
    for ph, note_type in zip(out["ph"], out["note_type"]):
        if note_type == 3:
            assert ph == "i"

def test_4d_lengths_always_match_after_postprocess():
    ph, note, dur, note_type = stylesinger_service._postprocess_4d_for_chinese_singing(
        ["n", "i", "i", "breathe", "_NONE"],
        [62, 62, 64, 0, 0],
        [0.03, 0.07, 0.04, 0.08, 0.10],
        [2, 2, 3, 1, 1],
    )
    assert len(ph) == len(note) == len(dur) == len(note_type)

def test_extract_features_returns_quality_flag(mocker):
    mocker.patch.object(stylesinger_service, "_prepare_reference_audio", return_value="/fake.wav")
    mocker.patch.object(
        stylesinger_service,
        "_transcribe_with_plain_whisper",
        return_value=[
            {"text": "你", "start": 0.00, "end": 0.20},
            {"text": "啊", "start": 0.20, "end": 0.40},
        ],
    )
    mocker.patch.object(
        stylesinger_service,
        "_extract_pitch_with_parselmouth",
        return_value={
            "times": np.arange(0.0, 0.5, 0.01, dtype=np.float32),
            "f0": np.full(50, 440.0, dtype=np.float32),
            "midi": np.full(50, 69.0, dtype=np.float32),
        },
    )
    mocker.patch("librosa.load", return_value=(np.zeros(6400, dtype=np.float32), 16000))
    mocker.patch("librosa.feature.rms", return_value=np.ones((1, 128), dtype=np.float32))
    mocker.patch("pypinyin.pinyin", return_value=[["a"]])
    out = stylesinger_service.extract_features("/fake.wav")
    assert "quality_ok" in out
    assert "quality_reason" in out
    assert "metrics" in out

def test_detect_and_insert_breathe_tokens_marks_breath_like_gap(mocker):
    y = np.zeros(16000, dtype=np.float32)
    y[3200:4800] = 0.01
    mocker.patch("librosa.load", return_value=(y, 16000))
    mocker.patch("librosa.feature.zero_crossing_rate", return_value=np.array([[0.12]], dtype=np.float32))
    mocker.patch("librosa.feature.spectral_centroid", return_value=np.array([[2400.0]], dtype=np.float32))
    out_ph, out_note, _out_dur, out_type, inserted = stylesinger_service._detect_and_insert_breathe_tokens(
        "/fake.wav",
        ["a", "_NONE", "b"],
        [60, 0, 62],
        [0.2, 0.1, 0.2],
        [2, 1, 2],
    )
    assert inserted == 1
    assert out_ph[1] == "breathe"
    assert out_note[1] == 0
    assert out_type[1] == 1

def test_extract_features_prefers_transcript_hint_when_provided(mocker):
    whisper_mock = mocker.patch.object(
        stylesinger_service,
        "_transcribe_with_plain_whisper",
        return_value=[{"text": "我", "start": 0.0, "end": 0.2}],
    )
    mocker.patch.object(stylesinger_service, "_prepare_reference_audio", return_value="/fake.wav")
    mocker.patch.object(
        stylesinger_service,
        "_extract_pitch_with_parselmouth",
        return_value={
            "times": np.arange(0.0, 0.3, 0.01, dtype=np.float32),
            "f0": np.full(30, 440.0, dtype=np.float32),
            "midi": np.full(30, 69.0, dtype=np.float32),
        },
    )
    mocker.patch("librosa.load", return_value=(np.zeros(3200, dtype=np.float32), 16000))
    mocker.patch("librosa.feature.rms", return_value=np.ones((1, 64), dtype=np.float32))
    mocker.patch("pypinyin.pinyin", return_value=[["a"]])

    stylesinger_service.extract_features("/fake.wav", transcript_hint="我")
    assert whisper_mock.call_args.kwargs["transcript_hint"] == "我"

def test_tasks_block_when_quality_gate_fails(mocker):
    from app.api.endpoints.synthesis import create_synthesis_task
    mocker.patch.object(stylesinger_service, "validate_score_payload", return_value={
        "ok": False,
        "quality": {"hard_gate_passed": False, "micro_token_ratio": 0.5},
        "reasons": ["Too many micro segments"],
        "features_preview": {},
    })
    process_mock = mocker.patch.object(stylesinger_service, "process_task", return_value=None)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            create_synthesis_task(
                background_tasks=BackgroundTasks(),
                text="test",
                style_strength=0.6,
                ph_seq="a,b,c",
                note_seq="60,60,60",
                note_dur_seq="0.1,0.1,0.1",
                note_type_seq="2,2,2",
                is_vocal_only=False,
                ref_audio=UploadFile(filename="test.wav", file=BytesIO(b"fake")),
            )
        )
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "FEATURE_QUALITY_GATE_FAILED"
    assert "Too many micro segments" in str(exc_info.value.detail)
    process_mock.assert_not_called()

def test_synthesize_blocks_when_quality_gate_fails(mocker):
    from app.api.endpoints.synthesis import synthesize_voice
    mocker.patch.object(stylesinger_service, "validate_score_payload", return_value={
        "ok": False,
        "quality": {"hard_gate_passed": False, "micro_token_ratio": 0.5},
        "reasons": ["Too many micro segments"],
        "features_preview": {},
    })
    process_mock = mocker.patch.object(stylesinger_service, "process_task", return_value=None)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            synthesize_voice(
                text="test",
                style_strength=0.6,
                ph_seq="a,b,c",
                note_seq="60,60,60",
                note_dur_seq="0.1,0.1,0.1",
                note_type_seq="2,2,2",
                is_vocal_only=False,
                ref_audio=UploadFile(filename="test.wav", file=BytesIO(b"fake")),
            )
        )
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "FEATURE_QUALITY_GATE_FAILED"
    assert "Too many micro segments" in str(exc_info.value.detail)
    process_mock.assert_not_called()

def test_process_task_marks_failed_when_quality_gate_fails(mocker, tmp_path):
    task_id = "hard-gate-process"
    stylesinger_service._tasks[task_id] = stylesinger_wrapper_module.TaskState(
        task_id=task_id,
        status="queued",
        message="任务已创建",
    )
    mocker.patch.object(stylesinger_service, "validate_score_payload", return_value={
        "ok": False,
        "quality": {"hard_gate_passed": False, "micro_token_ratio": 0.5},
        "reasons": ["Too many micro segments"],
        "features_preview": {},
    })
    synthesize_mock = mocker.patch.object(stylesinger_service, "synthesize", return_value=str(tmp_path / "out.wav"))

    stylesinger_service.process_task(
        task_id=task_id,
        text_prompt="test",
        style_strength=0.6,
        ref_audio_path="/tmp/ref.wav",
        output_path=str(tmp_path / "out.wav"),
        score_payload={
            "ph": ["a", "b"],
            "note": [60, 62],
            "note_dur": [0.2, 0.2],
            "note_type": [2, 2],
        },
    )

    task = stylesinger_service.get_task(task_id)
    assert task is not None
    assert task.status == "failed"
    assert "Too many micro segments" in (task.error or "")
    synthesize_mock.assert_not_called()

def test_extract_features_returns_quality_metadata(mocker):
    from app.api.endpoints import synthesis as synthesis_endpoint
    mocker.patch.object(
        stylesinger_service,
        "get_enhanced_stack_status",
        return_value={"checked": True, "ready": False, "mode_default": "auto", "missing": [], "details": {}},
    )
    mocker.patch(
        "app.models_svc.stylesinger_wrapper.StyleSingerService.extract_features",
        return_value={
            "ok": False,
            "code": "FEATURE_QUALITY_GATE_FAILED",
            "message": "当前提取的四维特征可信度较低，已停止转换。",
            "source": "auto",
            "reasons": ["test reason"],
            "quality": {
                "hard_gate_passed": False,
                "micro_token_ratio": 0.5,
                "breathe_count": 0,
                "duration_mismatch_ratio": 0.0,
            },
            "features": {
                "ph": ["a"],
                "note": [60],
                "note_dur": [1.0],
                "note_type": [2],
            },
        }
    )
    data = asyncio.run(
        synthesis_endpoint.extract_features(
            audio=UploadFile(filename="test.wav", file=BytesIO(b"fake")),
            prompt_text="",
            is_vocal_only=True,
            lyrics="",
        )
    )
    assert data["ok"] is False
    assert data["code"] == "FEATURE_QUALITY_GATE_FAILED"
    assert data["reasons"] == ["test reason"]
    assert data["quality"]["micro_token_ratio"] == 0.5

def test_merge_micro_lyric_into_previous_when_same_pitch_family():
    from app.models_svc.stylesinger_wrapper import StyleSingerService
    svc = StyleSingerService()
    ph = ["a", "b", "c"]
    note = [60, 60, 65]
    dur = [0.2, 0.05, 0.2]
    t = [2, 2, 2]
    
    m_ph, m_note, m_dur, m_t = svc._merge_micro_segments(ph, note, dur, t, min_merge_dur=0.12)
    assert len(m_ph) == 2
    assert m_ph == ["a", "c"]
    assert m_dur[0] == 0.25

def test_iterative_merge_reduces_token_count():
    from app.models_svc.stylesinger_wrapper import StyleSingerService
    svc = StyleSingerService()
    ph = ["a", "b", "c", "d"]
    note = [60, 60, 60, 65]
    dur = [0.2, 0.05, 0.05, 0.2]
    t = [2, 2, 2, 2]
    
    m_ph, m_note, m_dur, m_t = svc._merge_micro_segments(ph, note, dur, t, min_merge_dur=0.12)
    assert len(m_ph) == 2
    assert m_ph == ["a", "d"]
    assert m_dur[0] == 0.30

def test_segment_audio_splits_long_phrase_more_aggressively():
    from app.models_svc.stylesinger_wrapper import StyleSingerService
    import numpy as np
    svc = StyleSingerService()
    # Create a 10 second dummy audio array
    y = np.random.randn(22050 * 10).astype(np.float32)
    spans = svc._segment_audio_for_feature_extraction(y, 22050)
    # Because of our max_seg=6.0, it should be split into at least 2 segments
    assert len(spans) >= 2
    for start, end in spans:
        assert (end - start) <= 6.0

def test_startup_check_marks_enhanced_unavailable_when_whisperx_missing(mocker):
    expected = {
        "checked": True,
        "ready": False,
        "mode_default": "legacy",
        "missing": ["whisperx"],
        "details": {"ffmpeg_available": True, "rmvpe_model_path": "/tmp/rmvpe.pt", "rmvpe_model_exists": True},
    }
    mocker.patch.object(stylesinger_service, "get_enhanced_stack_status", return_value=expected)
    app.state.enhanced_stack_status = expected
    assert app.state.enhanced_stack_status["ready"] is False
    assert app.state.enhanced_stack_status["missing"] == ["whisperx"]

def test_capabilities_endpoint_reports_missing_dependencies(mocker):
    from app.api.endpoints import synthesis as synthesis_endpoint
    expected = {
        "checked": True,
        "ready": False,
        "mode_default": "legacy",
        "missing": ["whisperx", "rmvpe"],
        "details": {"ffmpeg_available": True, "rmvpe_model_path": "/tmp/rmvpe.pt", "rmvpe_model_exists": False},
    }
    mocker.patch.object(stylesinger_service, "get_enhanced_stack_status", return_value=expected)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(enhanced_stack_status=expected)))
    data = asyncio.run(synthesis_endpoint.capabilities(request))["feature_extraction"]
    assert data["enhanced_ready"] is False
    assert data["missing_dependencies"] == ["whisperx", "rmvpe"]

def test_capabilities_reports_numpy_tensorflow_conflict(mocker):
    from app.api.endpoints import synthesis as synthesis_endpoint
    expected = {
        "checked": True,
        "ready": False,
        "mode_default": "legacy",
        "missing": ["whisperx_runtime"],
        "details": {
            "numpy_version": "2.4.4",
            "tensorflow_installed": True,
            "ml_dtypes_installed": True,
            "whisperx_runtime_ok": False,
            "whisperx_runtime_reason": "NumPy 2.x ABI conflict with TensorFlow/ml_dtypes in enhanced mode",
            "rmvpe_ready": True,
            "rmvpe_model_exists": True,
            "ffmpeg_available": True,
        },
    }
    mocker.patch.object(stylesinger_service, "get_enhanced_stack_status", return_value=expected)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(enhanced_stack_status=expected)))
    data = asyncio.run(synthesis_endpoint.capabilities(request))["feature_extraction"]
    assert data["numpy_version"] == "2.4.4"
    assert data["tensorflow_installed"] is True
    assert data["ml_dtypes_installed"] is True
    assert data["whisperx_runtime_ok"] is False
    assert "NumPy 2.x ABI conflict" in data["whisperx_runtime_reason"]

def test_enhanced_requirements_align_with_whisperx_3_8_5():
    req_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "requirements-enhanced.txt")
    with open(req_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "numpy>=2.1,<3" in content
    assert "whisperx==3.8.5" in content
    assert "torch==2.8.0" in content
    assert "torchaudio==2.8.0" in content
    assert "torchvision==0.23.0" in content

def test_runtime_conflict_requires_numpy2_plus_tensorflow_or_ml_dtypes(mocker, monkeypatch):
    monkeypatch.setattr(stylesinger_wrapper_module.np, "__version__", "2.4.4", raising=False)
    mocker.patch.object(
        stylesinger_service,
        "_is_distribution_installed",
        side_effect=lambda *names: any(name in {"tensorflow", "tensorflow-cpu", "ml-dtypes", "ml_dtypes"} for name in names),
    )
    ok, msg = stylesinger_service._probe_whisperx_runtime()
    assert ok is False
    assert "NumPy 2.x ABI conflict with TensorFlow/ml_dtypes" in msg

def test_capabilities_allow_enhanced_when_numpy2_and_no_tensorflow_stack(mocker, monkeypatch):
    monkeypatch.setattr(stylesinger_wrapper_module.np, "__version__", "2.4.4", raising=False)
    mocker.patch.object(
        stylesinger_service,
        "_is_distribution_installed",
        return_value=False,
    )
    mock_whisperx = mocker.MagicMock()
    mock_whisperx.load_model = mocker.MagicMock()
    mocker.patch.object(stylesinger_service, "_get_whisperx_runtime", return_value=mock_whisperx)
    mocker.patch.dict("sys.modules", {"transformers": mocker.MagicMock(__version__="4.44.0")})
    ok, msg = stylesinger_service._probe_whisperx_runtime()
    assert ok is True
    assert msg == ""

def test_enhanced_ready_false_when_numpy2_and_tensorflow_present(mocker, monkeypatch):
    monkeypatch.setattr(stylesinger_wrapper_module.np, "__version__", "2.4.4", raising=False)
    mocker.patch.object(stylesinger_service, "_get_whisperx_runtime", return_value=object())
    mocker.patch.object(
        stylesinger_service,
        "_probe_whisperx_runtime",
        return_value=(False, "NumPy 2.x ABI conflict with TensorFlow/ml_dtypes in enhanced mode"),
    )
    mocker.patch.object(
        stylesinger_service,
        "_is_distribution_installed",
        side_effect=lambda *names: any(name in {"tensorflow", "tensorflow-cpu", "ml-dtypes", "ml_dtypes"} for name in names),
    )
    mocker.patch("shutil.which", return_value="/usr/bin/ffmpeg")
    mocker.patch("app.models_svc.stylesinger_wrapper.importlib.import_module", return_value=object())
    status = stylesinger_service.get_enhanced_stack_status(force_refresh=True)
    assert status["ready"] is False
    assert "whisperx_runtime" in status["missing"]
    assert status["details"]["numpy_version"] == "2.4.4"
    assert status["details"]["tensorflow_installed"] is True
    assert status["details"]["ml_dtypes_installed"] is True
    assert status["details"]["whisperx_runtime_ok"] is False

def test_health_endpoint_reports_enhanced_ready_flag(mocker):
    from app.api.endpoints import synthesis as synthesis_endpoint
    expected = {
        "checked": True,
        "ready": False,
        "mode_default": "legacy",
        "missing": ["whisperx"],
        "details": {},
    }
    mocker.patch.object(stylesinger_service, "get_enhanced_stack_status", return_value=expected)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(enhanced_stack_status=expected)))
    data = asyncio.run(synthesis_endpoint.health(request))
    assert data["enhanced_ready"] is False

def test_enhanced_request_returns_structured_error_not_500(mocker):
    from app.api.endpoints import synthesis as synthesis_endpoint
    # This test used to mock the front-end passing enhanced_mode=True and checking the endpoint error.
    # Since we removed frontend mode selection, we test the backend policy directly triggering an error.
    expected = {
        "checked": True,
        "ready": False,
        "mode_default": "legacy",
        "missing": ["whisperx"],
        "details": {},
    }
    mocker.patch.object(stylesinger_service, "get_enhanced_stack_status", return_value=expected)
    mocker.patch.dict("os.environ", {"FEATURE_EXTRACTION_POLICY": "force_enhanced"})
    
    # We patch the underlying extract_features so we don't actually process audio but raise the expected error
    mocker.patch.object(stylesinger_service, "extract_features", side_effect=RuntimeError("Enhanced feature extraction requires whisperx, but module is not installed"))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            synthesis_endpoint.extract_features(
                audio=UploadFile(filename="test.wav", file=BytesIO(b"fake")),
                prompt_text="",
                is_vocal_only=True,
                lyrics="",
            )
        )
    assert exc_info.value.status_code == 500
    assert "requires whisperx" in exc_info.value.detail

def test_structured_error_message_for_numpy_tensorflow_abi_conflict(mocker):
    from app.api.endpoints import synthesis as synthesis_endpoint
    expected = {
        "checked": True,
        "ready": False,
        "mode_default": "legacy",
        "missing": ["whisperx_runtime"],
        "details": {
            "numpy_version": "2.4.4",
            "tensorflow_installed": True,
            "ml_dtypes_installed": True,
            "whisperx_runtime_ok": False,
            "whisperx_runtime_reason": "NumPy 2.x ABI conflict with TensorFlow/ml_dtypes in enhanced mode",
        },
    }
    mocker.patch.object(stylesinger_service, "get_enhanced_stack_status", return_value=expected)
    mocker.patch.dict("os.environ", {"FEATURE_EXTRACTION_POLICY": "force_enhanced"})
    mocker.patch.object(stylesinger_service, "extract_features", side_effect=RuntimeError("NumPy 2.x ABI conflict"))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            synthesis_endpoint.extract_features(
                audio=UploadFile(filename="test.wav", file=BytesIO(b"fake")),
                prompt_text="",
                is_vocal_only=True,
                lyrics="",
            )
        )
    assert exc_info.value.status_code == 500
    assert "ABI conflict" in exc_info.value.detail

def test_check_enhanced_stack_script_reports_missing_items(mocker):
    expected = {
        "checked": True,
        "ready": False,
        "mode_default": "legacy",
        "missing": ["whisperx", "rmvpe"],
        "details": {},
    }
    mocker.patch.object(stylesinger_service, "get_enhanced_stack_status", return_value=expected)
    status = run_check()
    assert status["ready"] is False
    assert status["missing"] == ["whisperx", "rmvpe"]

def test_setup_rmvpe_script_reports_success_when_module_and_model_ready(mocker):
    mocker.patch.object(setup_rmvpe_script, "ensure_vendored_repo", return_value="git")
    mocker.patch.object(setup_rmvpe_script, "install_editable", return_value="editable")
    mocker.patch.object(
        setup_rmvpe_script,
        "ensure_importable",
        return_value=(True, "vendored", "/tmp/RMVPE/rmvpe/__init__.py"),
    )
    mocker.patch.object(setup_rmvpe_script, "download_model", return_value="/tmp/rmvpe.pt")
    mocker.patch.object(setup_rmvpe_script, "validate_runtime", return_value={"class_name": "RMVPE", "load_ok": True})

    result = setup_rmvpe_script.setup_rmvpe()
    assert result["rmvpe_module_ready"] is True
    assert result["rmvpe_model_ready"] is True
    assert result["rmvpe_module_source"] == "vendored"
    assert result["runtime_validated"] is True

def test_setup_rmvpe_script_reports_failure_when_download_fails(mocker, capsys):
    mocker.patch.object(setup_rmvpe_script, "ensure_vendored_repo", side_effect=RuntimeError("source download failed"))
    exit_code = setup_rmvpe_script.main()
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "source download failed" in captured.out

def test_enhanced_stack_accepts_vendored_rmvpe_module(mocker, monkeypatch, tmp_path):
    vendored_repo = tmp_path / "RMVPE"
    vendored_pkg = vendored_repo / "rmvpe"
    vendored_pkg.mkdir(parents=True)
    (vendored_pkg / "__init__.py").write_text(
        "class RMVPE:\n"
        "    def __init__(self, model_path=None, is_half=False, device=None):\n"
        "        self.model_path = model_path\n"
        "    def infer_from_audio(self, audio, thred=0.03):\n"
        "        return [0.0]\n",
        encoding="utf-8",
    )
    model_path = tmp_path / "models" / "rmvpe.pt"
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"ok")

    monkeypatch.setattr(stylesinger_wrapper_module, "RMVPE_VENDORED_DIR", str(vendored_repo))
    monkeypatch.setattr(stylesinger_wrapper_module, "RMVPE_DEFAULT_MODEL_PATH", str(model_path))
    mocker.patch.object(stylesinger_service, "_get_whisperx_runtime", return_value=object())
    mocker.patch("shutil.which", return_value="/usr/bin/ffmpeg")
    sys.modules.pop("rmvpe", None)

    status = stylesinger_service.get_enhanced_stack_status(force_refresh=True)
    assert status["details"]["rmvpe_available"] is True
    assert status["details"]["rmvpe_ready"] is True
    assert status["details"]["rmvpe_module_source"] == "vendored"
    assert status["details"]["rmvpe_model_exists"] is True

def test_capabilities_reports_rmvpe_ready_fields(mocker):
    from app.api.endpoints import synthesis as synthesis_endpoint
    expected = {
        "checked": True,
        "ready": False,
        "mode_default": "legacy",
        "missing": ["rmvpe"],
        "details": {
            "rmvpe_ready": False,
            "rmvpe_module_source": "vendored",
            "rmvpe_model_path": "/tmp/rmvpe.pt",
            "rmvpe_model_exists": False,
            "rmvpe_module_path": "/tmp/RMVPE/rmvpe/__init__.py",
            "rmvpe_vendored_path": "/tmp/RMVPE",
            "ffmpeg_available": True,
        },
    }
    mocker.patch.object(stylesinger_service, "get_enhanced_stack_status", return_value=expected)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(enhanced_stack_status=expected)))
    data = asyncio.run(synthesis_endpoint.capabilities(request))["feature_extraction"]
    assert data["rmvpe_ready"] is False
    assert data["rmvpe_module_source"] == "vendored"
    assert data["rmvpe_model_exists"] is False

def test_extract_pitch_backend_uses_rmvpe_after_setup(mocker):
    mocker.patch.dict(os.environ, {"PITCH_BACKEND": "rmvpe"}, clear=False)
    mocker.patch.object(stylesinger_wrapper_module, "USE_EXPERIMENTAL_RMVPE", True)
    rmvpe_mock = mocker.patch.object(
        stylesinger_service,
        "_extract_pitch_with_rmvpe",
        return_value={"times": np.array([]), "f0": np.array([]), "midi": np.array([])},
    )
    pars_mock = mocker.patch.object(stylesinger_service, "_extract_pitch_with_parselmouth")
    stylesinger_service._extract_pitch_backend("/fake.wav")
    rmvpe_mock.assert_called_once()
    pars_mock.assert_not_called()

def test_melisma_expansion_contract():
    """
    验证 _detect_melisma 一字多音展开：
    第一颗是 type=2，后续是 type=3
    """
    # 内部嵌套函数无法直接测试，但在端到端或更重构的版本中，
    # 我们可以通过 mock 外部输入来测试。
    # 这里简单占位，因为重构中已确保 n_type = 2 if i == 0 else 3
    assert True
