from __future__ import annotations

import json
from pathlib import Path

from app.models_svc.model_readiness import collect_model_readiness
from app.services import style_library


def _write_runtime_files(tmp_path: Path, *, speaker: str = "lain", include_model: bool = True) -> dict[str, Path]:
    repo_dir = tmp_path / "so-vits-svc"
    pretrain_dir = repo_dir / "pretrain"
    pretrain_dir.mkdir(parents=True)
    (repo_dir / "inference_main.py").write_text("print('ok')\n", encoding="utf-8")
    conditioned_script = tmp_path / "inference_conditioned.py"
    conditioned_script.write_text("print('conditioned')\n", encoding="utf-8")
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    model_path = model_dir / "G_2400_infer.pth"
    if include_model:
        model_path.write_bytes(b"weights")
    config_path = model_dir / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "spk": {speaker: 0},
                "data": {"sampling_rate": 44100},
                "model": {"speech_encoder": "vec768l12"},
            }
        ),
        encoding="utf-8",
    )
    (pretrain_dir / "checkpoint_best_legacy_500.pt").write_bytes(b"contentvec")
    text_style_config = tmp_path / "text_style_config.json"
    text_style_config.write_text(
        json.dumps(
            {
                "encoder_model_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                "embedding_dim": 256,
                "cache_dir": str(tmp_path / "missing-cache"),
                "enabled": True,
            }
        ),
        encoding="utf-8",
    )
    style_adapter_config = tmp_path / "style_adapter_config.json"
    style_adapter_config.write_text(
        json.dumps(
            {
                "enabled": True,
                "use_trained": True,
                "adapter_checkpoint_path": str(tmp_path / "runtime" / "style_adapter" / "missing.pt"),
            }
        ),
        encoding="utf-8",
    )
    return {
        "repo_dir": repo_dir,
        "conditioned_script": conditioned_script,
        "model_path": model_path,
        "config_path": config_path,
        "text_style_config": text_style_config,
        "style_adapter_config": style_adapter_config,
    }


def _apply_runtime_env(monkeypatch, paths: dict[str, Path], *, speaker: str = "lain", mock_enabled: bool = False) -> None:
    monkeypatch.setenv("SVC_DISABLE_MODEL_PRESETS", "true")
    monkeypatch.setenv("SOVITS_REPO_DIR", str(paths["repo_dir"]))
    monkeypatch.setenv("SOVITS_INFER_SCRIPT", str(paths["repo_dir"] / "inference_main.py"))
    monkeypatch.setenv("SOVITS_CONDITIONED_INFER_SCRIPT", str(paths["conditioned_script"]))
    monkeypatch.setenv("SOVITS_MODEL_PATH", str(paths["model_path"]))
    monkeypatch.setenv("SOVITS_CONFIG_PATH", str(paths["config_path"]))
    monkeypatch.setenv("SOVITS_SPEAKER", speaker)
    monkeypatch.setenv("SOVITS_DEVICE", "cpu")
    monkeypatch.setenv("SOVITS_MOCK", "true" if mock_enabled else "false")
    monkeypatch.setenv("SOVITS_CONDITION_MODE", "internal_film")
    monkeypatch.setenv("TEXT_STYLE_CONFIG_PATH", str(paths["text_style_config"]))
    monkeypatch.setenv("STYLE_ADAPTER_CONFIG_PATH", str(paths["style_adapter_config"]))
    monkeypatch.delenv("SOVITS_CONTENTVEC_PATH", raising=False)
    monkeypatch.delenv("SOVITS_RMVPE_MODEL_PATH", raising=False)
    monkeypatch.delenv("RMVPE_MODEL_PATH", raising=False)


def test_model_readiness_reports_missing_model_checkpoint(tmp_path, monkeypatch):
    paths = _write_runtime_files(tmp_path, include_model=False)
    _apply_runtime_env(monkeypatch, paths)

    readiness = collect_model_readiness()

    error_codes = {check["code"] for check in readiness["checks"] if check["level"] == "error"}
    assert readiness["ok"] is False
    assert "SOVITS_MODEL_NOT_FOUND" in error_codes


def test_model_readiness_allows_mock_mode_without_real_assets(tmp_path, monkeypatch):
    paths = _write_runtime_files(tmp_path, include_model=False)
    _apply_runtime_env(monkeypatch, paths, mock_enabled=True)

    readiness = collect_model_readiness(require_real_assets=False, skip_real_checks_if_mock=True)

    assert readiness["ok"] is True
    warning_codes = {check["code"] for check in readiness["checks"] if check["level"] == "warn"}
    assert "SOVITS_MOCK_ENABLED" in warning_codes


def test_model_readiness_parses_config_and_validates_speaker(tmp_path, monkeypatch):
    paths = _write_runtime_files(tmp_path, speaker="lain", include_model=True)
    _apply_runtime_env(monkeypatch, paths, speaker="not_lain")

    readiness = collect_model_readiness()

    ok_codes = {check["code"] for check in readiness["checks"] if check["level"] == "ok"}
    error_codes = {check["code"] for check in readiness["checks"] if check["level"] == "error"}
    assert "SOVITS_CONFIG_PARSED" in ok_codes
    assert "SOVITS_SPEAKER_NOT_IN_CONFIG" in error_codes


def test_model_readiness_optional_adapter_missing_is_warning_only(tmp_path, monkeypatch):
    paths = _write_runtime_files(tmp_path, include_model=True)
    _apply_runtime_env(monkeypatch, paths)

    readiness = collect_model_readiness(require_real_assets=False)

    warning_checks = [check for check in readiness["checks"] if check["code"] == "OPTIONAL_TEXT_STYLE_ADAPTER_MISSING"]
    assert warning_checks
    assert warning_checks[0]["level"] == "warn"


def test_style_library_manual_model_preset_override_wins_over_dedicated_style_match():
    selected = style_library.retrieve_style(
        "温柔、明亮、流行感更强的女声风格",
        model_preset_id="final_primary",
    )

    assert selected["model_preset_id"] == "final_primary"
    assert selected["speaker"] == "lain"
