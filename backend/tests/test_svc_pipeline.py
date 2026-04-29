import asyncio
import json
import shutil
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
from fastapi import BackgroundTasks, UploadFile

from app.api.endpoints import synthesis as synthesis_endpoint
from app.api.endpoints.synthesis import ConvertRequest
from app.models_svc.sovits_wrapper import SoVitsSvcEngine, SoVitsSvcError
from app.services import style_library
import app.services.svc_task_service as svc_task_service_module
from app.services.svc_task_service import TaskState, UploadRecord, svc_task_service
from app.models_svc.stylesinger_wrapper import stylesinger_service


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
    monkeypatch.setenv("SOVITS_MOCK", "false")
    monkeypatch.setenv("SOVITS_REPO_DIR", str(files["repo_dir"]))
    monkeypatch.setenv("SOVITS_INFER_SCRIPT", str(files["script_path"]))
    monkeypatch.setenv("SOVITS_MODEL_PATH", str(files["model_path"]))
    monkeypatch.setenv("SOVITS_CONFIG_PATH", str(files["config_path"]))
    monkeypatch.setenv("SOVITS_SPEAKER", "villager")
    monkeypatch.setenv("SOVITS_DEVICE", "cuda")

    def _fake_run(command, cwd, capture_output, text, timeout, env):
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
    )

    assert output == str(files["output_path"])
    assert files["output_path"].exists()
    output_info = sf.info(files["output_path"])
    assert output_info.format == "WAV"
    assert output_info.subtype == "PCM_16"
    raw_copy = files["repo_dir"] / "raw" / "task-123.wav"
    assert raw_copy.exists()
    assert raw_copy.read_bytes() == files["input_path"].read_bytes()
    command = run_mock.call_args.kwargs["args"] if "args" in run_mock.call_args.kwargs else run_mock.call_args.args[0]
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
    command_log = json.loads((tmp_path / "debug" / "sovits_command.txt").read_text(encoding="utf-8"))
    assert command_log["original_input_path"] == str(files["input_path"])
    assert command_log["original_input_size"] > 1024
    assert command_log["copied_input_path"].endswith("task-123.wav")
    assert command_log["prepared_input_path"].endswith("task-123.wav")
    assert command_log["prepared_audio_info"]["duration_seconds"] >= 0.5
    assert command_log["audio_prepare_method"] == "soundfile_reencode_wav"
    assert command_log["selected_output"].endswith(".flac")
    assert command_log["final_output_path"] == str(files["output_path"])


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
    mocker.patch.object(synthesis_endpoint.svc_task_service, "get_upload", return_value=object())
    mocker.patch.object(synthesis_endpoint.svc_task_service, "create_task", return_value="task-1")
    background_tasks = BackgroundTasks()

    result = asyncio.run(
        synthesis_endpoint.convert_audio(
            request=ConvertRequest(
                vocals_id="vocals-1",
                prompt_text="清澈少年感",
                style_preset_id="pop_bright",
            ),
            background_tasks=background_tasks,
        )
    )

    assert result["engine"] == "sovits"
    assert result["task_id"] == "task-1"
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].kwargs["style_preset_id"] == "pop_bright"


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

    retrieve_mock.assert_called_once_with("明亮流行", style_preset_id="pop_bright")
    assert convert_mock.call_args.kwargs["style_preset"]["style_id"] == "pop_bright"
    debug_payload = json.loads((runtime_dir / "task-1" / "selected_style.json").read_text(encoding="utf-8"))
    assert debug_payload["style_id"] == "pop_bright"
    assert debug_payload["description"] == "流行、明亮、清澈、少年感"
    assert debug_payload["match_score"] == 88
    assert debug_payload["matched_keywords"] == ["明亮", "流行"]
    assert debug_payload["reason"] == "命中关键词：明亮、流行；选择 pop_bright"


def test_upload_route_returns_vocals_id(mocker):
    mocker.patch.object(
        synthesis_endpoint.svc_task_service,
        "create_upload",
        return_value=SimpleNamespace(vocals_id="vocals-123", is_vocal_only=True),
    )

    result = asyncio.run(
        synthesis_endpoint.upload_audio(
            audio=UploadFile(filename="demo.wav", file=BytesIO(b"fake")),
            is_vocal_only=True,
        )
    )

    assert result["vocals_id"] == "vocals-123"


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


def test_task_result_response_includes_sovits_metadata_headers(tmp_path):
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
            "model_path": "/models/villager/G_4000.pth",
            "config_path": "/models/villager/config.json",
            "speaker": "villager",
            "device": "cuda",
            "selected_output": "/repo/results/test.flac",
            "final_output_path": str(output_path),
            "return_code": 0,
            "elapsed_seconds": 34.297,
            "sovits_command_debug_path": "/runtime/debug/task-result/sovits_command.txt",
        },
    )

    response = asyncio.run(synthesis_endpoint.get_task_result("task-result"))

    assert response.headers["x-svc-inference-mode"] == "real"
    assert response.headers["x-svc-speaker"] == "villager"
    assert response.headers["x-svc-selected-output"] == "/repo/results/test.flac"


def test_system_sovits_check_handles_missing_paths_without_500(monkeypatch):
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
