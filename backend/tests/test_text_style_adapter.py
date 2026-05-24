from pathlib import Path

import pytest

from app.models_svc.text_style_adapter import AdapterMLP, text_style_adapter

torch = pytest.importorskip("torch")


def test_text_style_adapter_outputs_rule_based_control_params(monkeypatch):
    monkeypatch.setenv("STYLE_ADAPTER_USE_TRAINED", "false")

    result = text_style_adapter.build_controls(
        prompt_embedding={
            "keywords": ["清亮", "少年感", "女声"],
            "embedding_norm": 1.0,
        },
        style_strength=0.8,
        selected_style={
            "model_preset_id": "final_primary",
            "transpose": 0,
        },
        available_model_presets=[
            {"preset_id": "final_primary"},
            {"preset_id": "tech_villager"},
        ],
    )

    assert result.adapter_enabled is True
    assert result.adapter_mode == "rule_based"
    assert result.control_params["model_preset_id"] == "final_primary"
    assert result.control_params["brightness"] >= 0.0
    assert result.control_params["power"] >= 0.0
    assert result.control_params["breathiness"] >= 0.0
    assert result.control_params["youthfulness"] >= 0.0
    assert result.control_params["style_strength"] == 0.8


def test_text_style_adapter_respects_requested_no_adapter(monkeypatch):
    monkeypatch.setenv("STYLE_ADAPTER_USE_TRAINED", "true")

    result = text_style_adapter.build_controls(
        prompt_embedding={
            "embedding": [1.0 / (384 ** 0.5)] * 384,
            "keywords": ["清亮", "少年感", "男声"],
            "embedding_norm": 1.0,
        },
        style_strength=0.75,
        selected_style={
            "model_preset_id": "final_male_youth",
            "transpose": 1,
        },
        available_model_presets=[{"preset_id": "final_male_youth"}],
        requested_adapter_mode="no_adapter",
    )

    assert result.adapter_enabled is False
    assert result.adapter_mode == "no_adapter"
    assert result.adapter_type == "disabled"
    assert result.control_params["model_preset_id"] == "final_male_youth"
    assert result.control_params["transpose"] == 1
    assert result.control_params["style_strength"] == 0.75


def test_text_style_adapter_loads_trained_checkpoint(tmp_path, monkeypatch):
    checkpoint_path = tmp_path / "adapter.pt"
    model = AdapterMLP(input_dim=384, output_dim=6, hidden_dims=[8])
    for param in model.parameters():
        param.data.zero_()
    model.layers[-1].bias.data = torch.tensor([0.91, 0.42, 0.33, 0.84, -1.0, 0.75], dtype=torch.float32)
    torch.save(
        {
            "adapter_version": "v0.7_trained_mlp_with_rule_based_fallback",
            "input_dim": 384,
            "output_dim": 6,
            "hidden_dims": [8],
            "target_keys": ["brightness", "power", "breathiness", "youthfulness", "transpose", "style_strength"],
            "model_state_dict": model.state_dict(),
            "sample_embeddings": [[1.0 / (384 ** 0.5)] * 384],
            "sample_records": [
                {
                    "id": "sample_trained",
                    "model_preset_id": "final_primary",
                    "gender_hint": "male",
                }
            ],
        },
        checkpoint_path,
    )
    monkeypatch.setenv("STYLE_ADAPTER_USE_TRAINED", "true")
    monkeypatch.setenv("STYLE_ADAPTER_CHECKPOINT_PATH", str(checkpoint_path))

    result = text_style_adapter.build_controls(
        prompt_embedding={
            "embedding": [1.0 / (384 ** 0.5)] * 384,
            "keywords": ["清亮", "少年感", "男声"],
            "embedding_norm": 1.0,
        },
        style_strength=0.7,
        selected_style={
            "model_preset_id": "final_primary",
            "transpose": 0,
        },
        available_model_presets=[{"preset_id": "final_primary"}],
    )

    assert result.adapter_enabled is True
    assert result.adapter_mode == "trained"
    assert result.adapter_type == "trained_mlp"
    assert result.control_params["model_preset_id"] == "final_primary"
    assert result.control_params["transpose"] == -1
    assert result.control_params["gender_hint"] == "male"
    assert result.control_params["brightness"] == pytest.approx(0.91, abs=1e-4)
    assert result.control_params["style_strength"] == pytest.approx(0.725, abs=1e-4)


def test_trained_text_style_adapter_keeps_dedicated_style_library_preset(tmp_path, monkeypatch):
    checkpoint_path = tmp_path / "adapter.pt"
    model = AdapterMLP(input_dim=384, output_dim=6, hidden_dims=[8])
    for param in model.parameters():
        param.data.zero_()
    torch.save(
        {
            "adapter_version": "v0.7_trained_mlp_with_rule_based_fallback",
            "input_dim": 384,
            "output_dim": 6,
            "hidden_dims": [8],
            "target_keys": ["brightness", "power", "breathiness", "youthfulness", "transpose", "style_strength"],
            "model_state_dict": model.state_dict(),
            "sample_embeddings": [[1.0 / (384 ** 0.5)] * 384],
            "sample_records": [
                {
                    "id": "sample_trained",
                    "model_preset_id": "final_primary",
                    "gender_hint": "neutral",
                }
            ],
        },
        checkpoint_path,
    )
    monkeypatch.setenv("STYLE_ADAPTER_USE_TRAINED", "true")
    monkeypatch.setenv("STYLE_ADAPTER_CHECKPOINT_PATH", str(checkpoint_path))

    result = text_style_adapter.build_controls(
        prompt_embedding={
            "embedding": [1.0 / (384 ** 0.5)] * 384,
            "keywords": ["低沉", "磁性", "叙事感"],
            "embedding_norm": 1.0,
        },
        style_strength=0.65,
        selected_style={
            "model_preset_id": "final_male_powerful",
            "transpose": 0,
            "current_style_has_dedicated_model": True,
            "model_preset_ready": True,
        },
        available_model_presets=[{"preset_id": "final_primary"}, {"preset_id": "final_male_powerful"}],
    )

    assert result.adapter_mode == "trained"
    assert result.control_params["model_preset_id"] == "final_male_powerful"


def test_text_style_adapter_falls_back_when_checkpoint_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("STYLE_ADAPTER_USE_TRAINED", "true")
    monkeypatch.setenv("STYLE_ADAPTER_CHECKPOINT_PATH", str(tmp_path / "missing.pt"))

    result = text_style_adapter.build_controls(
        prompt_embedding={
            "embedding": [1.0 / (384 ** 0.5)] * 384,
            "keywords": ["厚重", "摇滚", "男声"],
            "embedding_norm": 1.0,
        },
        style_strength=0.85,
        selected_style={
            "model_preset_id": "final_primary",
            "transpose": 0,
        },
        available_model_presets=[{"preset_id": "final_primary"}],
    )

    assert result.adapter_mode == "fallback"
    assert result.adapter_type == "rule_based"
    assert result.adapter_fallback_reason == "ADAPTER_CHECKPOINT_NOT_FOUND"
    assert result.control_params["model_preset_id"] == "final_primary"


def test_text_style_adapter_requested_rule_based_bypasses_trained_checkpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("STYLE_ADAPTER_USE_TRAINED", "true")
    monkeypatch.setenv("STYLE_ADAPTER_CHECKPOINT_PATH", str(tmp_path / "missing.pt"))

    result = text_style_adapter.build_controls(
        prompt_embedding={
            "embedding": [1.0 / (384 ** 0.5)] * 384,
            "keywords": ["厚重", "摇滚", "男声"],
            "embedding_norm": 1.0,
        },
        style_strength=0.85,
        selected_style={
            "model_preset_id": "final_primary",
            "transpose": 0,
        },
        available_model_presets=[{"preset_id": "final_primary"}],
        requested_adapter_mode="rule_based_adapter",
    )

    assert result.adapter_mode == "rule_based"
    assert result.adapter_type == "rule_based"
    assert result.adapter_fallback_reason is None
