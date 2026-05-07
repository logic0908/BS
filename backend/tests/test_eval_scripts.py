from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_script_module(name: str, relative_path: str):
    script_path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_conversion_ablation_accepts_all_adapter_modes(monkeypatch, tmp_path):
    module = _load_script_module("run_conversion_ablation", "scripts/run_conversion_ablation.py")
    captured: list[tuple[str, str]] = []

    monkeypatch.setattr(module, "build_environment_check", lambda: {"torch": {"torch_cuda_is_available": False}})

    def fake_run_single_experiment(
        *,
        input_path: str,
        prompt: str,
        style_strength: float,
        case,
        task_backend_mode: str,
        timeout_seconds: float,
        poll_seconds: float,
    ):
        captured.append((case.adapter_mode, case.f0_method))
        return {
            "label": case.label,
            "task_id": f"{case.adapter_mode}-{case.f0_method}",
            "prompt": prompt,
            "requested_model_preset_id": case.model_preset_id,
            "effective_model_preset_id": case.model_preset_id,
            "speaker": "lain",
            "adapter_mode": case.adapter_mode,
            "f0_method": case.f0_method,
            "duration_consistency": None,
            "low_energy_ratio": None,
            "possible_dropouts": None,
            "output_path": None,
        }

    monkeypatch.setattr(module, "run_single_experiment", fake_run_single_experiment)
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: module.argparse.Namespace(
            input="demo.wav",
            prompt="清亮、少年感、男声",
            style_strength=0.65,
            model_preset_id="final_primary",
            adapter_modes=["no_adapter", "rule_based", "trained"],
            f0_methods=["rmvpe"],
            cases=None,
            task_backend_mode="local",
            poll_seconds=0.1,
            timeout_seconds=1.0,
            output=str(tmp_path / "ablation.json"),
        ),
    )

    result = module.main()

    assert result == 0
    assert captured == [
        ("no_adapter", "rmvpe"),
        ("rule_based_adapter", "rmvpe"),
        ("trained_adapter", "rmvpe"),
    ]
