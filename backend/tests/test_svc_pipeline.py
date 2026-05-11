import asyncio
import json
import shutil
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
import torch
from fastapi import BackgroundTasks, UploadFile

from app.api.endpoints import synthesis as synthesis_endpoint
from app.api.endpoints.synthesis import ConvertRequest
from app.models_svc.sovits_wrapper import SoVitsSvcEngine, SoVitsSvcError
from app.models_svc.text_style_adapter import TextStyleAdapterResult
from app.services import style_library
from app.services import svc_model_presets
from app.services.svc_smoke_validation import build_smoke_report, resolve_task_debug_dir
import app.services.svc_task_service as svc_task_service_module
from app.services.svc_task_service import TaskState, UploadRecord, svc_task_service
from app.services.text_style_encoder import TextStyleEmbedding
from app.workers.svc_tasks import process_svc_task
from app.models_svc.stylesinger_wrapper import stylesinger_service


@pytest.fixture(autouse=True)
def _default_condition_mode(monkeypatch):
    monkeypatch.setenv("SOVITS_CONDITION_MODE", "none")


def _write_wav(path: Path) -> None:
    sf.write(path, np.zeros(44100, dtype=np.float32), 44100)


def _write_flac(path: Path) -> None:
    sf.write(path, np.zeros(44100, dtype=np.float32), 44100, format="FLAC")


def _prepare_runtime_files(tmp_path: Path) -> dict[str, Path]:
    repo_dir = tmp_path / "so-vits-svc"
    repo_dir.mkdir()
    script_path = repo_dir / "inference_main.py"
    script_path.write_text("print('ok')\n", encoding="utf-8")
    model_path = tmp_path / "model.pth"
    model_path.write_text("model", encoding="utf-8")
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    input_path = tmp_path / "input.wav"
    _write_wav(input_path)
    output_path = tmp_path / "output.wav"
    return {
        "repo_dir": repo_dir,
        "script_path": script_path,
        "model_path": model_path,
        "config_path": config_path,
        "input_path": input_path,
        "output_path": output_path,
    }


def _prepare_valid_sovits_assets(files: dict[str, Path], speaker: str = "villager") -> None:
    (files["repo_dir"] / "pretrain").mkdir(exist_ok=True)
    (files["repo_dir"] / "pretrain" / "checkpoint_best_legacy_500.pt").write_text("pt", encoding="utf-8")
    files["config_path"].write_text(
        json.dumps(
            {
                "data": {"sampling_rate": 44100},
                "model": {"speech_encoder": "vec768l12"},
                "spk": {speaker: 0},
            }
        ),
        encoding="utf-8",
    )


def _write_preset_config(path: Path, final_model: Path, final_config: Path, tech_model: Path, tech_config: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "active_preset_id": "final_primary",
                "fallback_preset_id": "tech_villager",
                "presets": [
                    {
                        "preset_id": "final_primary",
                        "display_name": "最终演示 So-VITS-SVC 模型",
                        "description": "用于毕业设计默认演示的目标歌声转换模型。",
                        "style_tags": ["baseline", "demo", "general"],
                        "model_path": str(final_model),
                        "config_path": str(final_config),
                        "speaker": "final_spk",
                        "device": "cuda",
                        "is_configured": True,
                        "is_demo_quality": True,
                        "smoke_test_passed": True,
                        "is_technical_validation_only": False,
                        "source_repo": "owner/final",
                        "license": "mit",
                    },
                    {
                        "preset_id": "final_male_youth",
                        "display_name": "少年感男声目标模型",
                        "description": "预留给更贴近少年感男声的目标模型。",
                        "style_tags": ["male", "youth", "bright"],
                        "model_path": "",
                        "config_path": "",
                        "speaker": "",
                        "device": "cuda",
                        "is_configured": False,
                        "is_demo_quality": False,
                        "smoke_test_passed": False,
                        "is_technical_validation_only": False,
                        "source_repo": "",
                        "license": "",
                    },
                    {
                        "preset_id": "final_male_powerful",
                        "display_name": "力量感男声目标模型",
                        "description": "预留给更贴近厚重/力量感男声的目标模型。",
                        "style_tags": ["male", "powerful", "thick"],
                        "model_path": str(tech_model),
                        "config_path": str(tech_config),
                        "speaker": "AY",
                        "device": "cuda",
                        "is_configured": False,
                        "is_demo_quality": False,
                        "smoke_test_passed": False,
                        "is_technical_validation_only": False,
                        "source_repo": "owner/powerful",
                        "license": "license_unknown",
                    },
                    {
                        "preset_id": "tech_villager",
                        "display_name": "技术验收模型：Minecraft Villager",
                        "description": "仅用于验证真实 So-VITS-SVC CUDA 推理链路。",
                        "style_tags": ["technical", "validation", "fallback"],
                        "model_path": str(tech_model),
                        "config_path": str(tech_config),
                        "speaker": "villager",
                        "device": "cuda",
                        "is_configured": True,
                        "is_demo_quality": False,
                        "smoke_test_passed": True,
                        "is_technical_validation_only": True,
                        "source_repo": "owner/tech",
                        "license": "cc-by-nc-sa-4.0",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_sovits_mock_convert_copies_file_and_returns_output_path(tmp_path, monkeypatch):
    monkeypatch.setenv("SOVITS_MOCK", "true")
    input_path = tmp_path / "input.wav"
    output_path = tmp_path / "output.wav"
    _write_wav(input_path)

    engine = SoVitsSvcEngine()
    out = engine.convert(
        input_vocals_path=str(input_path),
        prompt_text="明亮流行",
        style_strength=0.8,
        output_path=str(output_path),
        debug_dir=str(tmp_path / "debug"),
        style_preset={"style_id": "pop_bright"},
    )

    assert out == str(output_path)
    assert output_path.exists()
    assert output_path.read_bytes() == input_path.read_bytes()
    debug_payload = json.loads((tmp_path / "debug" / "sovits_debug.json").read_text(encoding="utf-8"))
    assert debug_payload["mode"] == "mock"


def test_sovits_real_mode_repo_not_found_returns_structured_error(tmp_path, monkeypatch):
    files = _prepare_runtime_files(tmp_path)
    monkeypatch.setenv("SOVITS_MOCK", "false")
    monkeypatch.setenv("SOVITS_REPO_DIR", str(tmp_path / "missing_repo"))
    monkeypatch.setenv("SOVITS_INFER_SCRIPT", str(files["script_path"]))
    monkeypatch.setenv("SOVITS_MODEL_PATH", str(files["model_path"]))
    monkeypatch.setenv("SOVITS_CONFIG_PATH", str(files["config_path"]))
    monkeypatch.setenv("SOVITS_SPEAKER", "speaker_a")

    engine = SoVitsSvcEngine()
    with pytest.raises(SoVitsSvcError) as exc_info:
        engine.convert(
            input_vocals_path=str(files["input_path"]),
            prompt_text="明亮流行",
            style_strength=0.8,
            output_path=str(files["output_path"]),
            debug_dir=str(tmp_path / "debug"),
        )

    assert exc_info.value.code == "SOVITS_REPO_NOT_FOUND"


def test_sovits_real_mode_model_not_found_returns_structured_error(tmp_path, monkeypatch):
    files = _prepare_runtime_files(tmp_path)
    monkeypatch.setenv("SVC_DISABLE_MODEL_PRESETS", "true")
    monkeypatch.setenv("SOVITS_MOCK", "false")
    monkeypatch.setenv("SOVITS_REPO_DIR", str(files["repo_dir"]))
    monkeypatch.setenv("SOVITS_INFER_SCRIPT", str(files["script_path"]))
    monkeypatch.setenv("SOVITS_MODEL_PATH", str(tmp_path / "missing_model.pth"))
    monkeypatch.setenv("SOVITS_CONFIG_PATH", str(files["config_path"]))
    monkeypatch.setenv("SOVITS_SPEAKER", "speaker_a")

    engine = SoVitsSvcEngine()
    with pytest.raises(SoVitsSvcError) as exc_info:
        engine.convert(
            input_vocals_path=str(files["input_path"]),
            prompt_text="明亮流行",
            style_strength=0.8,
            output_path=str(files["output_path"]),
            debug_dir=str(tmp_path / "debug"),
        )

    assert exc_info.value.code == "SOVITS_MODEL_NOT_FOUND"


def test_sovits_real_mode_speaker_not_in_config_returns_structured_error(tmp_path, monkeypatch):
    files = _prepare_runtime_files(tmp_path)
    _prepare_valid_sovits_assets(files, speaker="villager")
    monkeypatch.setenv("SVC_DISABLE_MODEL_PRESETS", "true")
    monkeypatch.setenv("SOVITS_MOCK", "false")
    monkeypatch.setenv("SOVITS_REPO_DIR", str(files["repo_dir"]))
    monkeypatch.setenv("SOVITS_INFER_SCRIPT", str(files["script_path"]))
    monkeypatch.setenv("SOVITS_MODEL_PATH", str(files["model_path"]))
    monkeypatch.setenv("SOVITS_CONFIG_PATH", str(files["config_path"]))
    monkeypatch.setenv("SOVITS_SPEAKER", "speaker_a")

    engine = SoVitsSvcEngine()
    with pytest.raises(SoVitsSvcError) as exc_info:
        engine.convert(
            input_vocals_path=str(files["input_path"]),
            prompt_text="明亮流行",
            style_strength=0.8,
            output_path=str(files["output_path"]),
            debug_dir=str(tmp_path / "debug"),
        )

    assert exc_info.value.code == "SOVITS_SPEAKER_NOT_IN_CONFIG"


def test_sovits_real_mode_missing_contentvec_returns_structured_error(tmp_path, monkeypatch):
    files = _prepare_runtime_files(tmp_path)
    (files["repo_dir"] / "pretrain").mkdir()
    files["config_path"].write_text(
        json.dumps(
            {
                "data": {"sampling_rate": 44100},
                "model": {"speech_encoder": "vec768l12"},
                "spk": {"villager": 0},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SOVITS_MOCK", "false")
    monkeypatch.setenv("SOVITS_REPO_DIR", str(files["repo_dir"]))
    monkeypatch.setenv("SOVITS_INFER_SCRIPT", str(files["script_path"]))
    monkeypatch.setenv("SOVITS_MODEL_PATH", str(files["model_path"]))
    monkeypatch.setenv("SOVITS_CONFIG_PATH", str(files["config_path"]))
    monkeypatch.setenv("SOVITS_SPEAKER", "villager")

    engine = SoVitsSvcEngine()
    with pytest.raises(SoVitsSvcError) as exc_info:
        engine.convert(
            input_vocals_path=str(files["input_path"]),
            prompt_text="明亮流行",
            style_strength=0.8,
            output_path=str(files["output_path"]),
            debug_dir=str(tmp_path / "debug"),
        )

    assert exc_info.value.code == "CONTENTVEC_PRETRAIN_NOT_FOUND"


def test_sovits_real_mode_uses_41_cli_and_copies_input_to_raw(mocker, tmp_path, monkeypatch):
    files = _prepare_runtime_files(tmp_path)
    _prepare_valid_sovits_assets(files, speaker="villager")
    monkeypatch.setenv("SVC_DISABLE_MODEL_PRESETS", "true")
    monkeypatch.setenv("SOVITS_MOCK", "false")
    monkeypatch.setenv("SOVITS_CONDITION_MODE", "internal_film")
    monkeypatch.setenv("SOVITS_REPO_DIR", str(files["repo_dir"]))
    monkeypatch.setenv("SOVITS_INFER_SCRIPT", str(files["script_path"]))
    monkeypatch.setenv("SOVITS_MODEL_PATH", str(files["model_path"]))
    monkeypatch.setenv("SOVITS_CONFIG_PATH", str(files["config_path"]))
    monkeypatch.setenv("SOVITS_SPEAKER", "villager")
    monkeypatch.setenv("SOVITS_DEVICE", "cuda")

    runtime_context: dict[str, object] = {}
    style_emb_path = tmp_path / "style_embedding.pt"
    torch.save({"style_emb": torch.ones(256, dtype=torch.float32)}, style_emb_path)

    def _fake_run(command, cwd, capture_output, text, timeout, env):
        if command[:1] == ["nvidia-smi"]:
            if "--query-gpu=timestamp,name,utilization.gpu,memory.used,memory.total" in command:
                return SimpleNamespace(
                    returncode=0,
                    stdout="timestamp, name, utilization.gpu [%], memory.used [MiB], memory.total [MiB]\n2026/05/02 14:00:00.000, RTX, 88 %, 4096 MiB, 24564 MiB\n",
                    stderr="",
                )
            if "--query-compute-apps=pid,process_name,used_memory" in command:
                return SimpleNamespace(
                    returncode=0,
                    stdout="pid, process_name, used_memory [MiB]\n12345, python, 4096 MiB\n",
                    stderr="",
                )
        if "--conditioning-report-path" in command:
            report_path = Path(command[command.index("--conditioning-report-path") + 1])
            report_path.write_text(
                json.dumps(
                    {
                        "condition_mode": "internal_film",
                        "executed_internal_film": True,
                        "film_target": "pre_decoder",
                        "film_strength": 0.1,
                    }
                ),
                encoding="utf-8",
            )
        result_path = files["repo_dir"] / "results" / "task_123_0key_villager_sovits_pm.flac"
        _write_flac(result_path)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    run_mock = mocker.patch(
        "app.models_svc.sovits_wrapper.subprocess.run",
        side_effect=_fake_run,
    )

    engine = SoVitsSvcEngine()
    output = engine.convert(
        input_vocals_path=str(files["input_path"]),
        prompt_text="明亮流行",
        style_strength=0.8,
        output_path=str(files["output_path"]),
        debug_dir=str(tmp_path / "debug"),
        task_id="task-123",
        runtime_context=runtime_context,
        style_prompt="明亮流行",
        style_emb_path=str(style_emb_path),
        style_dim=256,
    )

    assert output == str(files["output_path"])
    assert files["output_path"].exists()
    output_info = sf.info(files["output_path"])
    assert output_info.format == "WAV"
    assert output_info.subtype == "PCM_16"
    raw_copy = files["repo_dir"] / "raw" / "task-123.wav"
    assert raw_copy.exists()
    assert raw_copy.read_bytes() == files["input_path"].read_bytes()
    inference_call = next(
        call
        for call in run_mock.call_args_list
        if (call.kwargs["args"] if "args" in call.kwargs else call.args[0])[0] != "nvidia-smi"
    )
    command = inference_call.kwargs["args"] if "args" in inference_call.kwargs else inference_call.args[0]
    assert "-i" not in command
    assert "-o" not in command
    assert "-n" in command
    assert "task-123.wav" in command
    assert "-s" in command
    assert "villager" in command
    assert "-t" in command
    assert "0" in command
    assert "-d" in command
    assert "cuda" in command
    assert "--style-emb-path" in command
    assert str(style_emb_path) in command
    assert "--condition-mode" in command
    assert "internal_film" in command
    assert "--film-strength" in command
    assert "--film-target" in command
    assert "pre_decoder" in command
    command_log = json.loads((tmp_path / "debug" / "sovits_command.txt").read_text(encoding="utf-8"))
    assert command_log["original_input_path"] == str(files["input_path"])
    assert command_log["original_input_size"] > 1024
    assert command_log["copied_input_path"].endswith("task-123.wav")
    assert command_log["prepared_input_path"].endswith("task-123.wav")
    assert command_log["prepared_audio_info"]["duration_seconds"] >= 0.5
    assert command_log["audio_prepare_method"] == "soundfile_reencode_wav"
    assert command_log["selected_output"].endswith(".flac")
    assert command_log["final_output_path"] == str(files["output_path"])
    assert command_log["SOVITS_DEVICE"] == "cuda"
    assert command_log["command_includes_d_cuda"] is True
    assert command_log["gpu_telemetry_debug_path"].endswith("gpu_telemetry.txt")
    assert command_log["condition_mode"] == "internal_film"
    assert command_log["style_emb_path"] == str(style_emb_path)
    assert runtime_context["result_metadata"]["gpu_telemetry_debug_path"].endswith("gpu_telemetry.txt")
    assert runtime_context["result_metadata"]["executed_internal_film"] is True
    assert runtime_context["result_metadata"]["called_conditioned_inference"] is True
    telemetry_text = (tmp_path / "debug" / "gpu_telemetry.txt").read_text(encoding="utf-8")
    assert "SOVITS_DEVICE=cuda" in telemetry_text
    assert "command_includes_d_cuda=true" in telemetry_text
    assert "[before_inference]" in telemetry_text
    assert "[after_inference]" in telemetry_text
    assert "Do not use the pre-run snapshot alone" in telemetry_text


def test_active_preset_is_used_before_legacy_sovits_env(tmp_path, monkeypatch):
    files = _prepare_runtime_files(tmp_path)
    final_model = tmp_path / "final.pth"
    final_model.write_text("final", encoding="utf-8")
    final_config = tmp_path / "final_config.json"
    final_config.write_text(
        json.dumps({"data": {"sampling_rate": 44100}, "model": {"speech_encoder": "hubertsoft"}, "spk": {"final_spk": 0}}),
        encoding="utf-8",
    )
    preset_path = tmp_path / "svc_model_presets.json"
    _write_preset_config(preset_path, final_model, final_config, files["model_path"], files["config_path"])
    monkeypatch.setattr(svc_model_presets, "PRESETS_PATH", preset_path)
    monkeypatch.setenv("SOVITS_MODEL_PATH", str(files["model_path"]))
    monkeypatch.setenv("SOVITS_CONFIG_PATH", str(files["config_path"]))
    monkeypatch.setenv("SOVITS_SPEAKER", "villager")

    runtime_config = SoVitsSvcEngine().resolve_runtime_config({})

    assert runtime_config.model_path == str(final_model)
    assert runtime_config.config_path == str(final_config)
    assert runtime_config.speaker == "final_spk"
    assert runtime_config.model_preset_id == "final_primary"
    assert runtime_config.source_repo == "owner/final"


def test_sovits_build_command_omits_internal_film_args_when_condition_mode_none(tmp_path, monkeypatch):
    files = _prepare_runtime_files(tmp_path)
    _prepare_valid_sovits_assets(files, speaker="villager")
    monkeypatch.setenv("SVC_DISABLE_MODEL_PRESETS", "true")
    monkeypatch.setenv("SOVITS_REPO_DIR", str(files["repo_dir"]))
    monkeypatch.setenv("SOVITS_INFER_SCRIPT", str(files["script_path"]))
    monkeypatch.setenv("SOVITS_MODEL_PATH", str(files["model_path"]))
    monkeypatch.setenv("SOVITS_CONFIG_PATH", str(files["config_path"]))
    monkeypatch.setenv("SOVITS_SPEAKER", "villager")
    monkeypatch.setenv("SOVITS_CONDITION_MODE", "none")

    engine = SoVitsSvcEngine()
    runtime_config = engine.resolve_runtime_config({})
    command = engine._build_command(runtime_config, "task-none", style_emb_path="/tmp/style.pt")

    assert "--style-emb-path" not in command
    assert "--condition-mode" not in command
    assert "--film-strength" not in command


def test_explicit_model_preset_id_can_select_tech_fallback(tmp_path, monkeypatch):
    files = _prepare_runtime_files(tmp_path)
    final_model = tmp_path / "final.pth"
    final_model.write_text("final", encoding="utf-8")
    final_config = tmp_path / "final_config.json"
    final_config.write_text(
        json.dumps({"data": {"sampling_rate": 44100}, "model": {"speech_encoder": "hubertsoft"}, "spk": {"final_spk": 0}}),
        encoding="utf-8",
    )
    preset_path = tmp_path / "svc_model_presets.json"
    _write_preset_config(preset_path, final_model, final_config, files["model_path"], files["config_path"])
    monkeypatch.setattr(svc_model_presets, "PRESETS_PATH", preset_path)

    runtime_config = SoVitsSvcEngine().resolve_runtime_config({"model_preset_id": "tech_villager"})

    assert runtime_config.model_path == str(files["model_path"])
    assert runtime_config.config_path == str(files["config_path"])
    assert runtime_config.speaker == "villager"
    assert runtime_config.model_preset_id == "tech_villager"
    assert runtime_config.is_technical_validation_only is True


def test_unconfigured_preset_is_blocked_before_inference(tmp_path, monkeypatch):
    files = _prepare_runtime_files(tmp_path)
    final_model = tmp_path / "final.pth"
    final_model.write_text("final", encoding="utf-8")
    final_config = tmp_path / "final_config.json"
    final_config.write_text(
        json.dumps({"data": {"sampling_rate": 44100}, "model": {"speech_encoder": "hubertsoft"}, "spk": {"final_spk": 0}}),
        encoding="utf-8",
    )
    preset_path = tmp_path / "svc_model_presets.json"
    _write_preset_config(preset_path, final_model, final_config, files["model_path"], files["config_path"])
    monkeypatch.setattr(svc_model_presets, "PRESETS_PATH", preset_path)
    monkeypatch.setenv("SOVITS_MOCK", "false")
    monkeypatch.setenv("SOVITS_REPO_DIR", str(files["repo_dir"]))
    monkeypatch.setenv("SOVITS_INFER_SCRIPT", str(files["script_path"]))

    engine = SoVitsSvcEngine()
    with pytest.raises(SoVitsSvcError) as exc_info:
        engine.convert(
            input_vocals_path=str(files["input_path"]),
            prompt_text="少年感男声",
            style_strength=0.7,
            output_path=str(files["output_path"]),
            debug_dir=str(tmp_path / "debug"),
            style_preset={"model_preset_id": "final_male_youth"},
            conversion_params={"f0_method": "rmvpe"},
        )

    assert exc_info.value.code == "SVC_MODEL_PRESET_NOT_CONFIGURED"


def test_convert_route_regular_task_still_blocks_unconfigured_final_male_powerful(mocker, tmp_path, monkeypatch):
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setattr(svc_task_service_module, "RUNTIME_DEBUG_DIR", str(runtime_dir))
    svc_task_service._uploads.clear()
    svc_task_service._tasks.clear()

    files = _prepare_runtime_files(tmp_path)
    _prepare_valid_sovits_assets(files, speaker="AY")
    final_model = tmp_path / "final.pth"
    final_model.write_text("final", encoding="utf-8")
    final_config = tmp_path / "final_config.json"
    final_config.write_text(
        json.dumps({"data": {"sampling_rate": 44100}, "model": {"speech_encoder": "hubertsoft"}, "spk": {"final_spk": 0}}),
        encoding="utf-8",
    )
    preset_path = tmp_path / "svc_model_presets.json"
    _write_preset_config(preset_path, final_model, final_config, files["model_path"], files["config_path"])
    monkeypatch.setattr(svc_model_presets, "PRESETS_PATH", preset_path)
    monkeypatch.setenv("SOVITS_MOCK", "false")
    monkeypatch.setenv("SOVITS_REPO_DIR", str(files["repo_dir"]))
    monkeypatch.setenv("SOVITS_INFER_SCRIPT", str(files["script_path"]))

    input_path = tmp_path / "input.wav"
    vocals_path = tmp_path / "vocals.wav"
    _write_wav(input_path)
    _write_wav(vocals_path)
    svc_task_service._uploads["vocals-locked"] = UploadRecord(
        vocals_id="vocals-locked",
        input_path=str(input_path),
        vocals_path=str(vocals_path),
        is_vocal_only=True,
    )
    svc_task_service._tasks["task-locked"] = TaskState(
        task_id="task-locked",
        status="queued",
        message="任务已创建",
        engine="sovits",
        vocals_id="vocals-locked",
        task_backend_mode="local",
    )
    mocker.patch(
        "app.services.svc_task_service.style_library.retrieve_style",
        return_value={
            "style_id": "baseline_general",
            "style_label": "基础通用风格",
            "description": "通用流行 / 基础内容保持型 SVC",
            "model_preset_id": "final_primary",
            "model_display_name": "最终演示 So-VITS-SVC 模型",
            "model_path": str(final_model),
            "config_path": str(final_config),
            "speaker": "final_spk",
            "transpose": 0,
            "match_score": 10,
            "matched_keywords": ["默认"],
            "reason": "未命中明显关键词；使用默认候选 baseline_general",
            "model_preset_ready": True,
            "model_preset_configured": True,
            "current_style_has_dedicated_model": False,
        },
    )
    mocker.patch(
        "app.services.svc_task_service.text_style_encoder.encode_prompt",
        return_value=TextStyleEmbedding(
            embedding=(np.ones(8, dtype=np.float32) / np.sqrt(8.0)).astype(float).tolist(),
            embedding_dim=8,
            model_name="test-encoder",
            prompt_text="厚重、力量感、男声",
            normalized_prompt="厚重、力量感、男声",
            keywords=["厚重", "力量感", "男声"],
        ),
    )
    mocker.patch(
        "app.services.svc_task_service.text_style_adapter.build_controls",
        return_value=TextStyleAdapterResult(
            adapter_enabled=True,
            adapter_mode="rule_based",
            adapter_version="v1",
            adapter_type="rule_based",
            adapter_checkpoint_path="",
            trainable=False,
            control_params={"model_preset_id": "final_male_powerful", "transpose": 0, "style_strength": 0.7},
            override_reason="test adapter",
        ),
    )
    mocker.patch(
        "app.services.svc_task_service.style_library.apply_adapter_controls",
        return_value={
            "style_id": "baseline_general",
            "style_label": "基础通用风格",
            "description": "通用流行 / 基础内容保持型 SVC",
            "model_preset_id": "final_male_powerful",
            "model_display_name": "力量感男声目标模型",
            "model_path": str(files["model_path"]),
            "config_path": str(files["config_path"]),
            "speaker": "AY",
            "transpose": 0,
            "match_score": 10,
            "matched_keywords": ["默认"],
            "reason": "测试覆盖未 configured preset gate",
            "model_preset_ready": False,
            "model_preset_configured": False,
            "current_style_has_dedicated_model": True,
        },
    )

    with pytest.raises(SoVitsSvcError) as exc_info:
        svc_task_service.process_task(
            "task-locked",
            prompt_text="厚重、力量感、男声",
            style_strength=0.7,
            model_preset_id="final_male_powerful",
        )

    assert exc_info.value.code == "SVC_MODEL_PRESET_NOT_CONFIGURED"
    task = svc_task_service.get_task("task-locked")
    assert task is not None
    assert task.status == "failed"
    assert isinstance(task.error, dict)
    assert task.error["code"] == "SVC_MODEL_PRESET_NOT_CONFIGURED"


def test_check_sovits_env_smoke_mode_allows_unconfigured_preset_runtime_preview(tmp_path, monkeypatch):
    files = _prepare_runtime_files(tmp_path)
    _prepare_valid_sovits_assets(files, speaker="AY")
    final_model = tmp_path / "final.pth"
    final_model.write_text("final", encoding="utf-8")
    final_config = tmp_path / "final_config.json"
    final_config.write_text(
        json.dumps({"data": {"sampling_rate": 44100}, "model": {"speech_encoder": "hubertsoft"}, "spk": {"final_spk": 0}}),
        encoding="utf-8",
    )
    preset_path = tmp_path / "svc_model_presets.json"
    _write_preset_config(preset_path, final_model, final_config, files["model_path"], files["config_path"])
    monkeypatch.setattr(svc_model_presets, "PRESETS_PATH", preset_path)
    monkeypatch.setenv("SOVITS_REPO_DIR", str(files["repo_dir"]))
    monkeypatch.setenv("SOVITS_INFER_SCRIPT", str(files["script_path"]))
    monkeypatch.setenv("SOVITS_MODEL_PATH", str(files["model_path"]))
    monkeypatch.setenv("SOVITS_CONFIG_PATH", str(files["config_path"]))
    monkeypatch.setenv("SOVITS_SPEAKER", "AY")

    runtime_config = SoVitsSvcEngine().resolve_runtime_config(
        {"model_preset_id": "final_male_powerful"},
        allow_unconfigured_preset_smoke=True,
    )

    assert runtime_config.validation_mode == "unconfigured_preset_smoke"
    assert runtime_config.bypass_configured_gate is True
    assert runtime_config.model_preset_id == "final_male_powerful"
    assert runtime_config.requested_model_preset_id == "final_male_powerful"
    assert runtime_config.model_preset_ready is True
    assert runtime_config.model_preset_configured is False
    assert runtime_config.model_path == str(files["model_path"])
    assert runtime_config.config_path == str(files["config_path"])
    assert runtime_config.speaker == "AY"


def test_smoke_report_ignores_legacy_final_primary_debug(tmp_path):
    project_root = tmp_path
    legacy_debug_dir = project_root / "runtime" / "debug" / "check_sovits_env"
    legacy_debug_dir.mkdir(parents=True, exist_ok=True)
    (legacy_debug_dir / "sovits_command.txt").write_text(
        json.dumps(
            {
                "model_path": "/home/featurize/work/BS/local_models/sovits-final/final_primary/G_2400_infer.pth",
                "config_path": "/home/featurize/work/BS/local_models/sovits-final/final_primary/config.json",
                "speaker": "lain",
                "selected_output": "test.wav_0key_lain_sovits_pm.flac",
                "return_code": 0,
            }
        ),
        encoding="utf-8",
    )
    (legacy_debug_dir / "sovits_debug.json").write_text(
        json.dumps({"result_metadata": {"called_inference_main": True, "model_preset_id": "final_primary"}}),
        encoding="utf-8",
    )

    task_id = "smoke-final_male_powerful-123"
    task_debug_dir = resolve_task_debug_dir(project_root, task_id)
    task_debug_dir.mkdir(parents=True, exist_ok=True)
    (task_debug_dir / "sovits_command.txt").write_text(
        json.dumps(
            {
                "model_path": "/home/featurize/work/BS/local_models/sovits-final/final_male_powerful/G_15000.pth",
                "config_path": "/home/featurize/work/BS/local_models/sovits-final/final_male_powerful/config.json",
                "speaker": "AY",
                "selected_output": "smoke-final_male_powerful-123_0key_AY_sovits_pm.flac",
                "return_code": 0,
                "env": {
                    "SOVITS_MODEL_PATH": "/home/featurize/work/BS/local_models/sovits-final/final_male_powerful/G_15000.pth",
                    "SOVITS_CONFIG_PATH": "/home/featurize/work/BS/local_models/sovits-final/final_male_powerful/config.json",
                    "SOVITS_SPEAKER": "AY",
                },
            }
        ),
        encoding="utf-8",
    )
    (task_debug_dir / "sovits_debug.json").write_text(
        json.dumps(
            {
                "runtime_config": {
                    "model_preset_id": "final_male_powerful",
                    "requested_model_preset_id": "final_male_powerful",
                    "validation_mode": "unconfigured_preset_smoke",
                    "bypass_configured_gate": True,
                },
                "result_metadata": {
                    "called_inference_main": True,
                    "model_preset_id": "final_male_powerful",
                    "requested_model_preset_id": "final_male_powerful",
                    "validation_mode": "unconfigured_preset_smoke",
                    "bypass_configured_gate": True,
                    "selected_output": "smoke-final_male_powerful-123_0key_AY_sovits_pm.flac",
                },
            }
        ),
        encoding="utf-8",
    )

    output_path = project_root / "smoke.wav"
    _write_wav(output_path)
    report = build_smoke_report(
        project_root=project_root,
        preset_id="final_male_powerful",
        expected_speaker="AY",
        input_path=str(project_root / "input.wav"),
        output_path=str(output_path),
        started_at="2026-05-04T00:00:00Z",
        stdout_path=str(project_root / "stdout.log"),
        stderr_path=str(project_root / "stderr.log"),
        task_id=task_id,
        return_code=0,
    )

    assert report["success"] is True
    assert report["resolved_model_path"].endswith("/local_models/sovits-final/final_male_powerful/G_15000.pth")
    assert report["resolved_speaker"] == "AY"
    assert report["command_matches_preset"] is True
    assert report["speaker_matches_preset"] is True
    assert report["selected_output_is_stale_legacy"] is False
    assert report["selected_output"].endswith("AY_sovits_pm.flac")
    assert "final_primary" not in report["resolved_model_path"]


def test_allow_preset_fallback_uses_final_primary_without_claiming_requested_style(tmp_path, monkeypatch):
    files = _prepare_runtime_files(tmp_path)
    final_model = tmp_path / "final.pth"
    final_model.write_text("final", encoding="utf-8")
    final_config = tmp_path / "final_config.json"
    final_config.write_text(
        json.dumps({"data": {"sampling_rate": 44100}, "model": {"speech_encoder": "hubertsoft"}, "spk": {"final_spk": 0}}),
        encoding="utf-8",
    )
    preset_path = tmp_path / "svc_model_presets.json"
    _write_preset_config(preset_path, final_model, final_config, files["model_path"], files["config_path"])
    monkeypatch.setattr(svc_model_presets, "PRESETS_PATH", preset_path)
    monkeypatch.setenv("SOVITS_MOCK", "true")

    runtime_context: dict[str, object] = {}
    output = SoVitsSvcEngine().convert(
        input_vocals_path=str(files["input_path"]),
        prompt_text="少年感、男声、清亮",
        style_strength=0.7,
        output_path=str(files["output_path"]),
        debug_dir=str(tmp_path / "debug"),
        style_preset={"model_preset_id": "final_male_youth"},
        allow_preset_fallback=True,
        runtime_context=runtime_context,
    )

    metadata = runtime_context["result_metadata"]
    assert output == str(files["output_path"])
    assert metadata["requested_model_preset_id"] == "final_male_youth"
    assert metadata["effective_model_preset_id"] == "final_primary"
    assert metadata["model_preset_id"] == "final_primary"
    assert metadata["preset_fallback_used"] is True
    assert "结果不代表该专用风格真实效果" in metadata["preset_fallback_reason"]
    assert metadata["speaker"] == "final_spk"


def test_sovits_real_mode_raises_output_not_found_when_results_have_no_new_file(mocker, tmp_path, monkeypatch):
    files = _prepare_runtime_files(tmp_path)
    _prepare_valid_sovits_assets(files, speaker="villager")
    monkeypatch.setenv("SOVITS_MOCK", "false")
    monkeypatch.setenv("SOVITS_REPO_DIR", str(files["repo_dir"]))
    monkeypatch.setenv("SOVITS_INFER_SCRIPT", str(files["script_path"]))
    monkeypatch.setenv("SOVITS_MODEL_PATH", str(files["model_path"]))
    monkeypatch.setenv("SOVITS_CONFIG_PATH", str(files["config_path"]))
    monkeypatch.setenv("SOVITS_SPEAKER", "villager")

    mocker.patch(
        "app.models_svc.sovits_wrapper.subprocess.run",
        return_value=SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    )

    engine = SoVitsSvcEngine()
    with pytest.raises(SoVitsSvcError) as exc_info:
        engine.convert(
            input_vocals_path=str(files["input_path"]),
            prompt_text="明亮流行",
            style_strength=0.8,
            output_path=str(files["output_path"]),
            debug_dir=str(tmp_path / "debug"),
            task_id="task-456",
        )

    assert exc_info.value.code == "SOVITS_OUTPUT_NOT_FOUND"


def test_sovits_real_mode_invalid_audio_returns_structured_error_without_subprocess(mocker, tmp_path, monkeypatch):
    files = _prepare_runtime_files(tmp_path)
    _prepare_valid_sovits_assets(files, speaker="villager")
    invalid_input = tmp_path / "invalid.wav"
    invalid_input.write_bytes(b"RIFF")
    monkeypatch.setenv("SOVITS_MOCK", "false")
    monkeypatch.setenv("SOVITS_REPO_DIR", str(files["repo_dir"]))
    monkeypatch.setenv("SOVITS_INFER_SCRIPT", str(files["script_path"]))
    monkeypatch.setenv("SOVITS_MODEL_PATH", str(files["model_path"]))
    monkeypatch.setenv("SOVITS_CONFIG_PATH", str(files["config_path"]))
    monkeypatch.setenv("SOVITS_SPEAKER", "villager")
    run_mock = mocker.patch("app.models_svc.sovits_wrapper.subprocess.run")

    engine = SoVitsSvcEngine()
    with pytest.raises(SoVitsSvcError) as exc_info:
        engine.convert(
            input_vocals_path=str(invalid_input),
            prompt_text="明亮流行",
            style_strength=0.8,
            output_path=str(files["output_path"]),
            debug_dir=str(tmp_path / "debug"),
            task_id="task-invalid",
        )

    assert exc_info.value.code == "SOVITS_INPUT_AUDIO_INVALID"
    run_mock.assert_not_called()


def test_sovits_real_mode_subprocess_failure_marks_task_failed_and_writes_error_json(mocker, tmp_path, monkeypatch):
    files = _prepare_runtime_files(tmp_path)
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setenv("SOVITS_MOCK", "false")
    monkeypatch.setenv("SOVITS_REPO_DIR", str(files["repo_dir"]))
    monkeypatch.setenv("SOVITS_INFER_SCRIPT", str(files["script_path"]))
    monkeypatch.setenv("SOVITS_MODEL_PATH", str(files["model_path"]))
    monkeypatch.setenv("SOVITS_CONFIG_PATH", str(files["config_path"]))
    monkeypatch.setenv("SOVITS_SPEAKER", "speaker_a")
    monkeypatch.setattr(svc_task_service_module, "RUNTIME_DEBUG_DIR", str(runtime_dir))
    svc_task_service._uploads.clear()
    svc_task_service._tasks.clear()
    svc_task_service._engines["sovits"] = SoVitsSvcEngine()

    svc_task_service._uploads["vocals-fail"] = UploadRecord(
        vocals_id="vocals-fail",
        input_path=str(files["input_path"]),
        vocals_path=str(files["input_path"]),
        is_vocal_only=True,
    )
    svc_task_service._tasks["task-fail"] = TaskState(
        task_id="task-fail",
        status="queued",
        message="任务已创建",
        engine="sovits",
        vocals_id="vocals-fail",
    )

    mocker.patch(
        "app.models_svc.sovits_wrapper.subprocess.run",
        return_value=SimpleNamespace(returncode=1, stdout="mock stdout", stderr="mock stderr"),
    )
    mocker.patch(
        "app.services.svc_task_service.style_library.retrieve_style",
        return_value={
            "style_id": "pop_bright",
            "description": "流行、明亮、清澈、少年感",
            "model_path": str(files["model_path"]),
            "config_path": str(files["config_path"]),
            "speaker": "speaker_a",
            "transpose": 0,
            "match_score": 99,
            "matched_keywords": ["流行"],
            "reason": "命中关键词：流行；选择 pop_bright",
        },
    )

    with pytest.raises(SoVitsSvcError) as exc_info:
        svc_task_service.process_task("task-fail", prompt_text="流行", style_strength=0.5)

    assert exc_info.value.code == "SOVITS_INFERENCE_FAILED"
    task = svc_task_service.get_task("task-fail")
    assert task is not None
    assert task.status == "failed"
    assert isinstance(task.error, dict)
    assert task.error["code"] == "SOVITS_INFERENCE_FAILED"
    error_path = runtime_dir / "task-fail" / "error.json"
    assert error_path.exists()
    error_payload = json.loads(error_path.read_text(encoding="utf-8"))
    assert error_payload["code"] == "SOVITS_INFERENCE_FAILED"
    assert "mock stderr" in error_payload["details"]["stderr"]


def test_style_library_preset_overrides_default_env_config(tmp_path, monkeypatch):
    style_file = tmp_path / "style_library.json"
    style_file.write_text(
        json.dumps(
            [
                {
                    "style_id": "preset_a",
                    "description": "定制风格",
                    "keywords": ["定制"],
                    "model_path": "preset-model.pth",
                    "config_path": "preset-config.json",
                    "speaker": "preset-speaker",
                    "transpose": 2,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(style_library, "STYLE_LIBRARY_PATH", str(style_file))
    monkeypatch.setenv("SOVITS_MODEL_PATH", "env-model.pth")
    monkeypatch.setenv("SOVITS_CONFIG_PATH", "env-config.json")
    monkeypatch.setenv("SOVITS_SPEAKER", "env-speaker")

    preset = style_library.retrieve_style("任意文本", style_preset_id="preset_a")

    assert preset["style_id"] == "preset_a"
    assert preset["model_path"] == "preset-model.pth"
    assert preset["config_path"] == "preset-config.json"
    assert preset["speaker"] == "preset-speaker"
    assert preset["transpose"] == 2


def test_convert_route_defaults_to_sovits_and_passes_style_preset_id(mocker):
    mocker.patch.object(synthesis_endpoint.svc_task_service, "use_celery", return_value=False)
    mocker.patch.object(synthesis_endpoint.svc_task_service, "get_upload", return_value=object())
    mocker.patch.object(synthesis_endpoint.svc_task_service, "create_task", return_value="task-1")
    background_tasks = BackgroundTasks()

    result = asyncio.run(
        synthesis_endpoint.convert_audio(
            request=ConvertRequest(
                vocals_id="vocals-1",
                prompt_text="清澈少年感",
                style_prompt="清澈少年感",
                style_preset_id="pop_bright",
                model_preset_id="final_primary",
                transpose=-2,
                f0_method="rmvpe",
                auto_predict_f0=False,
                slice_db=-38.0,
                clip_seconds=5.0,
                pad_seconds=0.5,
                allow_preset_fallback=True,
                adapter_mode="no_adapter",
            ),
            background_tasks=background_tasks,
        )
    )

    assert result["engine"] == "sovits"
    assert result["task_id"] == "task-1"
    assert result["task_backend_mode"] == "local"
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].kwargs["style_preset_id"] == "pop_bright"
    assert background_tasks.tasks[0].kwargs["model_preset_id"] == "final_primary"
    assert background_tasks.tasks[0].kwargs["transpose"] == -2
    assert background_tasks.tasks[0].kwargs["f0_method"] == "rmvpe"
    assert background_tasks.tasks[0].kwargs["slice_db"] == -38.0
    assert background_tasks.tasks[0].kwargs["allow_preset_fallback"] is True
    assert background_tasks.tasks[0].kwargs["style_prompt"] == "清澈少年感"
    assert background_tasks.tasks[0].kwargs["requested_adapter_mode"] == "no_adapter"


def test_convert_route_uses_celery_dispatch_when_enabled(mocker):
    mocker.patch.object(synthesis_endpoint.svc_task_service, "use_celery", return_value=True)
    mocker.patch.object(synthesis_endpoint.svc_task_service, "get_upload", return_value=object())
    mocker.patch.object(synthesis_endpoint.svc_task_service, "create_task", return_value="task-celery")
    apply_async_mock = mocker.patch("app.workers.svc_tasks.process_svc_task.apply_async")
    background_tasks = BackgroundTasks()

    result = asyncio.run(
        synthesis_endpoint.convert_audio(
            request=ConvertRequest(
                vocals_id="vocals-1",
                prompt_text="清澈少年感",
                style_prompt="清澈少年感",
                style_preset_id="pop_bright",
                adapter_mode="rule_based_adapter",
            ),
            background_tasks=background_tasks,
        )
    )

    assert result["task_backend_mode"] == "celery"
    assert len(background_tasks.tasks) == 0
    apply_async_mock.assert_called_once()
    assert apply_async_mock.call_args.kwargs["kwargs"]["style_prompt"] == "清澈少年感"
    assert apply_async_mock.call_args.kwargs["kwargs"]["requested_adapter_mode"] == "rule_based_adapter"


def test_celery_eager_mode_task_can_complete(mocker):
    process_mock = mocker.patch.object(
        svc_task_service,
        "process_task",
        return_value="/tmp/converted.wav",
    )
    mocker.patch.object(process_svc_task.backend, "mark_as_done", return_value=None)
    result = process_svc_task.apply(
        kwargs={
            "task_id": "task-eager",
            "prompt_text": "清亮、少年感",
            "style_prompt": "清亮、少年感",
            "style_strength": 0.8,
            "style_preset_id": "pop_bright",
            "model_preset_id": "final_primary",
            "transpose": -1,
            "allow_preset_fallback": True,
            "requested_adapter_mode": "no_adapter",
        },
    )
    assert result.get() == "/tmp/converted.wav"
    process_mock.assert_called_once()
    assert process_mock.call_args.kwargs["allow_preset_fallback"] is True
    assert process_mock.call_args.kwargs["style_prompt"] == "清亮、少年感"
    assert process_mock.call_args.kwargs["requested_adapter_mode"] == "no_adapter"


def test_prompt_text_is_passed_to_style_library_and_selected_style_written_to_debug(mocker, tmp_path, monkeypatch):
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setattr(svc_task_service_module, "RUNTIME_DEBUG_DIR", str(runtime_dir))
    svc_task_service._uploads.clear()
    svc_task_service._tasks.clear()

    input_path = tmp_path / "input.wav"
    vocals_path = tmp_path / "vocals.wav"
    _write_wav(input_path)
    _write_wav(vocals_path)

    svc_task_service._uploads["vocals-1"] = UploadRecord(
        vocals_id="vocals-1",
        input_path=str(input_path),
        vocals_path=str(vocals_path),
        is_vocal_only=True,
    )
    svc_task_service._tasks["task-1"] = TaskState(
        task_id="task-1",
        status="queued",
        message="任务已创建",
        engine="sovits",
        vocals_id="vocals-1",
    )

    retrieve_mock = mocker.patch(
        "app.services.svc_task_service.style_library.retrieve_style",
        return_value={
            "style_id": "pop_bright",
            "description": "流行、明亮、清澈、少年感",
            "model_path": "model.pth",
            "config_path": "config.json",
            "speaker": "speaker_a",
            "transpose": 1,
            "match_score": 88,
            "matched_keywords": ["明亮", "流行"],
            "reason": "命中关键词：明亮、流行；选择 pop_bright",
        },
    )
    convert_mock = mocker.patch.object(
        svc_task_service._engines["sovits"],
        "convert",
        side_effect=lambda **kwargs: shutil.copyfile(str(vocals_path), kwargs["output_path"]) or kwargs["output_path"],
    )

    svc_task_service.process_task(
        "task-1",
        prompt_text="明亮流行",
        style_strength=0.7,
        style_preset_id="pop_bright",
    )

    retrieve_mock.assert_called_once_with("明亮流行", style_preset_id="pop_bright", model_preset_id=None)
    assert convert_mock.call_args.kwargs["style_preset"]["style_id"] == "pop_bright"
    debug_payload = json.loads((runtime_dir / "task-1" / "selected_style.json").read_text(encoding="utf-8"))
    assert debug_payload["style_id"] == "pop_bright"
    assert debug_payload["description"] == "流行、明亮、清澈、少年感"
    assert debug_payload["match_score"] == 88
    assert debug_payload["matched_keywords"] == ["明亮", "流行"]
    assert debug_payload["reason"] == "命中关键词：明亮、流行；选择 pop_bright"


def test_process_task_writes_style_embedding_adapter_and_audio_quality(mocker, tmp_path, monkeypatch):
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setattr(svc_task_service_module, "RUNTIME_DEBUG_DIR", str(runtime_dir))
    svc_task_service._uploads.clear()
    svc_task_service._tasks.clear()

    input_path = tmp_path / "input.wav"
    vocals_path = tmp_path / "vocals.wav"
    _write_wav(input_path)
    _write_wav(vocals_path)

    svc_task_service._uploads["vocals-embed"] = UploadRecord(
        vocals_id="vocals-embed",
        input_path=str(input_path),
        vocals_path=str(vocals_path),
        is_vocal_only=True,
    )
    svc_task_service._tasks["task-embed"] = TaskState(
        task_id="task-embed",
        status="queued",
        message="任务已创建",
        engine="sovits",
        vocals_id="vocals-embed",
        task_backend_mode="local",
    )

    mocker.patch(
        "app.services.svc_task_service.style_library.retrieve_style",
        return_value={
            "style_id": "pop_bright",
            "description": "流行、明亮、清澈、少年感",
            "model_preset_id": "final_primary",
            "model_display_name": "最终演示 So-VITS-SVC 模型",
            "model_path": "model.pth",
            "config_path": "config.json",
            "speaker": "lain",
            "transpose": 0,
            "match_score": 88,
            "matched_keywords": ["明亮", "流行"],
            "reason": "命中关键词：明亮、流行；选择 pop_bright",
            "source_repo": "SuCicada/Lain-so-vits-svc-4.1",
            "license": "gpl",
        },
    )
    mocker.patch(
        "app.services.svc_task_service.text_style_encoder.encode_prompt",
        return_value=TextStyleEmbedding(
            embedding=(np.ones(256, dtype=np.float32) / np.sqrt(256.0)).astype(float).tolist(),
            embedding_dim=256,
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            prompt_text="清亮、少年感、男声",
            normalized_prompt="清亮、少年感、男声",
            keywords=["清亮", "少年感", "男声"],
        ),
    )
    mocker.patch(
        "app.services.svc_task_service.text_style_adapter.build_controls",
        return_value=TextStyleAdapterResult(
            adapter_enabled=True,
            adapter_mode="rule_based",
            adapter_version="v1_rule_mlp_or_rule_based",
            adapter_type="rule_based",
            adapter_checkpoint_path="",
            trainable=False,
            control_params={
                "model_preset_id": "final_primary",
                "transpose": 0,
                "brightness": 0.88,
                "power": 0.55,
                "breathiness": 0.41,
                "youthfulness": 0.91,
                "gender_hint": "male",
                "style_strength": 0.7,
            },
            override_reason="rule-based adapter mapping",
        ),
    )
    convert_mock = mocker.patch.object(
        svc_task_service._engines["sovits"],
        "convert",
        side_effect=lambda **kwargs: shutil.copyfile(str(vocals_path), kwargs["output_path"]) or kwargs["output_path"],
    )

    svc_task_service.process_task(
        "task-embed",
        prompt_text="清亮、少年感、男声",
        style_strength=0.7,
        style_preset_id="pop_bright",
    )

    debug_dir = runtime_dir / "task-embed"
    assert (debug_dir / "style_embedding.json").exists()
    assert (debug_dir / "style_embedding.npy").exists()
    assert (debug_dir / "style_embedding.pt").exists()
    assert (debug_dir / "style_adapter_output.json").exists()
    assert (debug_dir / "audio_quality_report.json").exists()
    task = svc_task_service.get_task("task-embed")
    assert task is not None
    assert task.engine_details["embedding_dim"] == 256
    assert task.engine_details["adapter_mode"] == "rule_based"
    assert task.engine_details["adapter_version"] == "v1_rule_mlp_or_rule_based"
    assert task.engine_details["audio_quality_summary"]["duration_consistency"] >= 0.0
    assert convert_mock.call_args.kwargs["style_prompt"] == "清亮、少年感、男声"
    assert convert_mock.call_args.kwargs["style_emb_path"].endswith("style_embedding.pt")


def test_process_task_writes_conversion_params_json(mocker, tmp_path, monkeypatch):
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setattr(svc_task_service_module, "RUNTIME_DEBUG_DIR", str(runtime_dir))
    svc_task_service._uploads.clear()
    svc_task_service._tasks.clear()

    input_path = tmp_path / "input.wav"
    vocals_path = tmp_path / "vocals.wav"
    _write_wav(input_path)
    _write_wav(vocals_path)

    svc_task_service._uploads["vocals-conv"] = UploadRecord(
        vocals_id="vocals-conv",
        input_path=str(input_path),
        vocals_path=str(vocals_path),
        is_vocal_only=True,
    )
    svc_task_service._tasks["task-conv"] = TaskState(
        task_id="task-conv",
        status="queued",
        message="任务已创建",
        engine="sovits",
        vocals_id="vocals-conv",
        task_backend_mode="local",
    )

    mocker.patch(
        "app.services.svc_task_service.style_library.retrieve_style",
        return_value={
            "style_id": "baseline_general",
            "style_label": "基础通用风格",
            "description": "通用流行 / 基础内容保持型 SVC",
            "model_preset_id": "final_primary",
            "model_display_name": "最终演示 So-VITS-SVC 模型",
            "model_path": "model.pth",
            "config_path": "config.json",
            "speaker": "lain",
            "transpose": 0,
            "match_score": 10,
            "matched_keywords": ["默认"],
            "reason": "未命中明显关键词；使用默认候选 baseline_general",
            "model_preset_ready": True,
            "model_preset_configured": True,
            "current_style_has_dedicated_model": False,
        },
    )
    mocker.patch(
        "app.services.svc_task_service.text_style_adapter.build_controls",
        return_value=TextStyleAdapterResult(
            adapter_enabled=True,
            adapter_mode="trained",
            adapter_version="v1",
            adapter_type="trained_mlp",
            adapter_checkpoint_path="checkpoint.pt",
            trainable=True,
            control_params={"model_preset_id": "final_primary", "transpose": -1, "style_strength": 0.7},
            override_reason="trained adapter",
        ),
    )
    mocker.patch.object(
        svc_task_service._engines["sovits"],
        "convert",
        side_effect=lambda **kwargs: shutil.copyfile(str(vocals_path), kwargs["output_path"]) or kwargs["output_path"],
    )

    svc_task_service.process_task(
        "task-conv",
        prompt_text="默认",
        style_strength=0.7,
        f0_method="rmvpe",
        auto_predict_f0=False,
        slice_db=-36.0,
        clip_seconds=4.0,
        pad_seconds=0.75,
    )

    payload = json.loads((runtime_dir / "task-conv" / "conversion_params.json").read_text(encoding="utf-8"))
    assert payload["f0_method"] in {"rmvpe", "system_default"}
    assert payload["auto_predict_f0"] is False
    assert payload["slice_db"] == -36.0
    assert payload["clip_seconds"] == 4.0
    assert payload["pad_seconds"] == 0.75
    assert payload["conversion_params_path"].endswith("conversion_params.json")


def test_process_task_requested_no_adapter_skips_adapter_controls_and_writes_task_config(mocker, tmp_path, monkeypatch):
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setattr(svc_task_service_module, "RUNTIME_DEBUG_DIR", str(runtime_dir))
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    svc_task_service._uploads.clear()
    svc_task_service._tasks.clear()

    input_path = tmp_path / "input.wav"
    vocals_path = tmp_path / "vocals.wav"
    _write_wav(input_path)
    _write_wav(vocals_path)

    svc_task_service._uploads["vocals-no-adapter"] = UploadRecord(
        vocals_id="vocals-no-adapter",
        input_path=str(input_path),
        vocals_path=str(vocals_path),
        is_vocal_only=True,
    )
    svc_task_service._tasks["task-no-adapter"] = TaskState(
        task_id="task-no-adapter",
        status="queued",
        message="任务已创建",
        engine="sovits",
        vocals_id="vocals-no-adapter",
        task_backend_mode="celery",
    )

    mocker.patch(
        "app.services.svc_task_service.style_library.retrieve_style",
        return_value={
            "style_id": "pop_bright",
            "description": "流行、明亮、清澈、少年感",
            "model_preset_id": "final_male_youth",
            "model_display_name": "少年感男声目标模型",
            "model_path": "model.pth",
            "config_path": "config.json",
            "speaker": "Nova_Adult",
            "transpose": 1,
            "match_score": 88,
            "matched_keywords": ["清亮", "少年感"],
            "reason": "命中关键词：清亮、少年感；选择 pop_bright",
            "model_preset_ready": True,
            "model_preset_configured": True,
            "current_style_has_dedicated_model": True,
        },
    )
    mocker.patch(
        "app.services.svc_task_service.text_style_encoder.encode_prompt",
        return_value=TextStyleEmbedding(
            embedding=(np.ones(384, dtype=np.float32) / np.sqrt(384.0)).astype(float).tolist(),
            embedding_dim=384,
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            prompt_text="清亮、少年感、男声",
            normalized_prompt="清亮、少年感、男声",
            keywords=["清亮", "少年感", "男声"],
        ),
    )
    build_controls_mock = mocker.patch(
        "app.services.svc_task_service.text_style_adapter.build_controls",
        return_value=TextStyleAdapterResult(
            adapter_enabled=False,
            adapter_mode="no_adapter",
            adapter_version="v1",
            adapter_type="disabled",
            adapter_checkpoint_path="checkpoint.pt",
            trainable=False,
            control_params={"model_preset_id": "final_male_youth", "transpose": 1, "style_strength": 0.65},
            override_reason="requested_adapter_mode=no_adapter; skipped TextStyleAdapter control injection",
        ),
    )
    apply_controls_mock = mocker.patch(
        "app.services.svc_task_service.style_library.apply_adapter_controls",
        side_effect=lambda preset, control_params, model_preset_id=None, override_reason=None: {
            **dict(preset),
            "model_preset_id": model_preset_id or dict(preset).get("model_preset_id"),
            "adapter_control_params": dict(control_params or {}),
            "adapter_override_reason": override_reason,
        },
    )
    mocker.patch.object(
        svc_task_service._engines["sovits"],
        "convert",
        side_effect=lambda **kwargs: shutil.copyfile(str(vocals_path), kwargs["output_path"]) or kwargs["output_path"],
    )

    svc_task_service.process_task(
        "task-no-adapter",
        prompt_text="清亮、少年感、男声",
        style_strength=0.65,
        model_preset_id="final_male_youth",
        requested_adapter_mode="no_adapter",
    )

    build_controls_mock.assert_called_once()
    assert build_controls_mock.call_args.kwargs["requested_adapter_mode"] == "no_adapter"
    apply_controls_mock.assert_called_once()
    assert apply_controls_mock.call_args.args[1] == {"model_preset_id": "final_male_youth"}
    task = svc_task_service.get_task("task-no-adapter")
    assert task is not None
    assert task.engine_details["requested_adapter_mode"] == "no_adapter"
    assert task.engine_details["effective_adapter_mode"] == "no_adapter"
    assert task.engine_details["adapter_mode"] == "no_adapter"
    debug_dir = runtime_dir / "task-no-adapter"
    task_config = json.loads((debug_dir / "task_config.json").read_text(encoding="utf-8"))
    assert task_config["requested_adapter_mode"] == "no_adapter"
    assert task_config["effective_adapter_mode"] == "no_adapter"
    assert task_config["worker_pid"] > 0
    assert task_config["cuda_visible_devices"] == "0"
    assert isinstance(task_config["torch_cuda_available"], bool)
    assert task_config["output_path"].endswith("converted.wav")


def test_upload_route_returns_vocals_id(mocker):
    mocker.patch.object(
        synthesis_endpoint.svc_task_service,
        "create_upload",
        return_value=SimpleNamespace(
            vocals_id="vocals-123",
            is_vocal_only=True,
            input_quality_summary={"quality_level": "warn", "warnings": ["音频较短"]},
        ),
    )

    result = asyncio.run(
        synthesis_endpoint.upload_audio(
            audio=UploadFile(filename="demo.wav", file=BytesIO(b"fake")),
            is_vocal_only=True,
        )
    )

    assert result["vocals_id"] == "vocals-123"
    assert result["input_quality_summary"]["quality_level"] == "warn"


def test_system_health_returns_ok(mocker):
    mocker.patch.object(
        synthesis_endpoint,
        "collect_app_health",
        return_value={
            "ok": True,
            "app_status": "ok",
            "python_executable": "/usr/bin/python",
            "python_version": "3.11",
            "conda_env": "base",
            "mock_mode": True,
            "frontend_build_info": None,
            "timestamp": "2026-04-27T00:00:00+00:00",
        },
    )

    data = asyncio.run(synthesis_endpoint.system_health())

    assert data["ok"] is True
    assert data["app_status"] == "ok"


def test_task_result_response_uses_ascii_safe_headers_and_filename(tmp_path):
    output_path = tmp_path / "converted.wav"
    _write_wav(output_path)
    svc_task_service._tasks.clear()
    svc_task_service._tasks["task-result"] = TaskState(
        task_id="task-result",
        status="succeeded",
        message="转换完成",
        engine="sovits",
        vocals_id="vocals-1",
        output_path=str(output_path),
        inference_mode="real",
        engine_details={
            "inference_mode": "real",
            "mock_enabled": False,
            "model_preset_id": "final_primary",
            "model_display_name": "最终演示 So-VITS-SVC 模型",
            "model_path": "/models/villager/G_4000.pth",
            "config_path": "/models/villager/config.json",
            "speaker": "villager",
            "device": "cuda",
            "selected_output": "/repo/results/test.flac",
            "final_output_path": str(output_path),
            "return_code": 0,
            "elapsed_seconds": 34.297,
            "sovits_command_debug_path": "/runtime/debug/task-result/sovits_command.txt",
            "gpu_telemetry_debug_path": "/runtime/debug/task-result/gpu_telemetry.txt",
        },
    )

    response = asyncio.run(synthesis_endpoint.get_task_result("task-result"))
    task_payload = asyncio.run(synthesis_endpoint.get_task_status("task-result"))

    assert response.headers["x-task-id"] == "task-result"
    assert response.headers["x-inference-mode"] == "real"
    assert response.headers["x-model-preset-id"] == "final_primary"
    assert response.headers["x-speaker"] == "villager"
    assert response.headers["content-disposition"] == 'attachment; filename="converted_task-result.wav"'
    assert "x-svc-model-display-name" not in response.headers
    assert "x-svc-selected-output" not in response.headers
    assert task_payload["gpu_telemetry_debug_path"] == "/runtime/debug/task-result/gpu_telemetry.txt"
    for header_value in response.headers.values():
        header_value.encode("latin-1")


def test_task_result_keeps_chinese_metadata_in_json_but_not_headers(tmp_path):
    output_path = tmp_path / "converted.wav"
    _write_wav(output_path)
    svc_task_service._tasks.clear()
    svc_task_service._tasks["task-cn"] = TaskState(
        task_id="task-cn",
        status="succeeded",
        message="转换完成",
        engine="sovits",
        vocals_id="vocals-1",
        output_path=str(output_path),
        inference_mode="real",
        selected_style={
            "style_id": "female_pop_bright",
            "description": "清亮、女声、流行",
            "reason": "命中关键词：清亮、女声；选择 final_primary",
        },
        engine_details={
            "inference_mode": "real",
            "model_preset_id": "final_primary",
            "model_display_name": "最终演示 So-VITS-SVC 模型",
            "speaker": "lain",
        },
    )

    response = asyncio.run(synthesis_endpoint.get_task_result("task-cn"))
    task_payload = asyncio.run(synthesis_endpoint.get_task_status("task-cn"))

    assert response.headers["content-disposition"] == 'attachment; filename="converted_task-cn.wav"'
    for header_value in response.headers.values():
        header_value.encode("latin-1")
    assert task_payload["model_display_name"] == "最终演示 So-VITS-SVC 模型"
    assert task_payload["selected_style"]["description"] == "清亮、女声、流行"
    assert task_payload["selected_style"]["reason"] == "命中关键词：清亮、女声；选择 final_primary"


def test_system_sovits_check_handles_missing_paths_without_500(monkeypatch):
    monkeypatch.setenv("SVC_DISABLE_MODEL_PRESETS", "true")
    monkeypatch.setenv("SOVITS_MOCK", "false")
    monkeypatch.setenv("SOVITS_REPO_DIR", "/tmp/missing-sovits-repo")
    monkeypatch.setenv("SOVITS_INFER_SCRIPT", "/tmp/missing-sovits-repo/inference_main.py")
    monkeypatch.setenv("SOVITS_MODEL_PATH", "/tmp/missing-model.pth")
    monkeypatch.setenv("SOVITS_CONFIG_PATH", "/tmp/missing-config.json")
    monkeypatch.setenv("SOVITS_SPEAKER", "speaker_missing")

    data = asyncio.run(synthesis_endpoint.system_sovits_check())

    assert data["SOVITS_REPO_DIR_exists"] is False
    assert data["SOVITS_MODEL_PATH_exists"] is False
    assert data["SOVITS_CONFIG_PATH_exists"] is False
    assert data["SOVITS_SPEAKER"] == "speaker_missing"


def test_system_sovits_check_reports_torch_cuda_keys():
    data = asyncio.run(synthesis_endpoint.system_sovits_check())

    assert "torch_version" in data
    assert "torch_cuda_available" in data
    assert "torch_cuda_version" in data
    assert "torch_device_count" in data
    assert "numpy" in data["import_status"]


def test_system_sovits_check_reports_asset_validation_errors(monkeypatch, tmp_path):
    repo_dir = tmp_path / "so-vits-svc"
    repo_dir.mkdir()
    infer_script = repo_dir / "inference_main.py"
    infer_script.write_text("print('ok')\n", encoding="utf-8")
    model_path = tmp_path / "model.pth"
    model_path.write_text("model", encoding="utf-8")
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "data": {"sampling_rate": 44100},
                "model": {"speech_encoder": "vec768l12"},
                "spk": {"villager": 0},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SVC_DISABLE_MODEL_PRESETS", "true")
    monkeypatch.setenv("SOVITS_MOCK", "false")
    monkeypatch.setenv("SOVITS_REPO_DIR", str(repo_dir))
    monkeypatch.setenv("SOVITS_INFER_SCRIPT", str(infer_script))
    monkeypatch.setenv("SOVITS_MODEL_PATH", str(model_path))
    monkeypatch.setenv("SOVITS_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("SOVITS_SPEAKER", "speaker_missing")

    data = asyncio.run(synthesis_endpoint.system_sovits_check())

    codes = {item["code"] for item in data["validation_errors"]}
    assert data["config_speech_encoder"] == "vec768l12"
    assert "SOVITS_SPEAKER_NOT_IN_CONFIG" in codes
    assert "CONTENTVEC_PRETRAIN_NOT_FOUND" in codes


def test_style_library_returns_match_score_keywords_and_reason(tmp_path, monkeypatch):
    style_file = tmp_path / "style_library.json"
    style_file.write_text(
        json.dumps(
            [
                {
                    "style_id": "pop_bright",
                    "description": "流行、明亮、清澈、少年感",
                    "keywords": ["流行", "明亮", "清亮"],
                    "model_path": "",
                    "config_path": "",
                    "speaker": "",
                    "transpose": 0,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(style_library, "STYLE_LIBRARY_PATH", str(style_file))

    preset = style_library.retrieve_style("我想要流行又清亮的感觉")

    assert preset["match_score"] > 0
    assert "流行" in preset["matched_keywords"]
    assert "清亮" in preset["matched_keywords"]
    assert "选择 pop_bright" in preset["reason"]


def test_svc_task_status_response_contains_engine_status_stage_progress_message():
    svc_task_service._tasks.clear()
    svc_task_service._tasks["task-status"] = TaskState(
        task_id="task-status",
        status="running",
        message="正在执行 SVC 转换",
        engine="sovits",
        vocals_id="vocals-1",
        stage="inference_running",
        progress=85,
    )

    data = asyncio.run(synthesis_endpoint.get_task_status("task-status"))

    assert data["engine"] == "sovits"
    assert data["status"] == "running"
    assert data["stage"] == "inference_running"
    assert data["progress"] == 85
    assert data["message"] == "正在执行 SVC 转换"


def test_stylesinger_task_status_keeps_compatibility(mocker):
    mocker.patch.object(
        synthesis_endpoint.svc_task_service,
        "get_task",
        return_value=None,
    )
    mocker.patch.object(
        stylesinger_service,
        "get_task",
        return_value=SimpleNamespace(
            task_id="style-task",
            status="completed",
            message="转换完成",
            output_path="/tmp/out.wav",
            error=None,
            reasons=[],
        ),
    )

    data = asyncio.run(synthesis_endpoint.get_task_status("style-task"))

    assert data["engine"] == "stylesinger"
    assert data["status"] == "succeeded"
    assert data["legacy_status"] == "completed"
    assert data["stage"] == "completed"
