from __future__ import annotations

from app.services import system_status


def test_collect_app_health_includes_sovits_and_text_conditioning(mocker):
    mocker.patch.object(
        system_status,
        "collect_model_readiness",
        return_value={
            "runtime_config": {"mock_enabled": False},
            "sovits": {
                "mock": False,
                "preset": "final_primary",
                "model_exists": True,
                "config_exists": True,
                "model_basename": "G_2400_infer.pth",
                "config_basename": "config.json",
                "speaker": "lain",
                "device": "cuda",
                "condition_mode": "internal_film",
                "conditioned_infer_exists": True,
            },
            "text_conditioning": {
                "enabled": True,
                "style_dim": 256,
                "film_strength": 0.1,
                "film_target": "pre_decoder",
            },
        },
    )
    mocker.patch.object(system_status, "collect_presets_status", return_value={"active_preset_id": "final_primary", "presets": []})
    mocker.patch.object(system_status, "_frontend_build_info", return_value=None)

    data = system_status.collect_app_health()

    assert data["ok"] is True
    assert data["sovits"]["preset"] == "final_primary"
    assert data["sovits"]["condition_mode"] == "internal_film"
    assert data["text_conditioning"]["style_dim"] == 256
    assert data["text_conditioning"]["film_target"] == "pre_decoder"


def test_collect_sovits_check_exposes_structured_runtime_summary_without_absolute_basename_leak(mocker):
    runtime_config = type(
        "RuntimeConfig",
        (),
        {
            "mock_enabled": False,
            "repo_dir": "/repo/so-vits-svc",
            "infer_script": "/repo/backend/app/models_svc/inference_conditioned.py",
            "model_path": "/repo/local_models/sovits-final/final_primary/G_2400_infer.pth",
            "config_path": "/repo/local_models/sovits-final/final_primary/config.json",
            "speaker": "lain",
            "model_preset_id": "final_primary",
            "model_display_name": "默认模型",
            "source_repo": "SuCicada/Lain-so-vits-svc-4.1",
            "source_url": "https://huggingface.co/SuCicada/Lain-so-vits-svc-4.1",
            "license": "gpl",
            "install_report_path": "/repo/local_models/sovits-final/final_primary/install_report.json",
            "notes": "notes",
            "model_path_basename": "G_2400_infer.pth",
            "config_path_basename": "config.json",
            "is_demo_quality": True,
            "is_technical_validation_only": False,
            "device": "cuda",
            "f0_method": "system_default",
            "f0_fallback_reason": "RMVPE_UNAVAILABLE",
            "auto_predict_f0": False,
            "slice_db": -40.0,
            "clip_seconds": 0.0,
            "pad_seconds": 0.5,
            "python_bin": "/usr/bin/python",
        },
    )()
    mocker.patch.object(system_status, "SoVitsSvcEngine")
    system_status.SoVitsSvcEngine.return_value.resolve_runtime_config.return_value = runtime_config
    mocker.patch.object(
        system_status,
        "inspect_sovits_assets",
        return_value={
            "config_summary": {
                "speakers": ["lain"],
                "sampling_rate": 44100,
                "speech_encoder": "vec768l12",
                "f0_predictor": None,
            },
            "speaker_exists_in_config": True,
            "contentvec_required": True,
            "contentvec_candidate_paths": ["/repo/so-vits-svc/pretrain/checkpoint_best_legacy_500.pt"],
            "contentvec_found_paths": ["/repo/so-vits-svc/pretrain/checkpoint_best_legacy_500.pt"],
            "rmvpe_required": False,
            "rmvpe_candidate_paths": [],
            "rmvpe_found_paths": [],
            "validation_errors": [],
        },
    )
    mocker.patch.object(system_status, "_check_torch", return_value={"torch_version": "2.0", "torch_cuda_available": True, "torch_cuda_version": "12.1", "torch_device_count": 1})
    mocker.patch.object(system_status, "_check_imports", return_value={})
    mocker.patch.object(system_status, "_run_command", return_value={"available": True, "return_code": 0, "stdout": "", "stderr": ""})
    mocker.patch.object(system_status.shutil, "which", return_value="/usr/bin/nvidia-smi")
    mocker.patch.object(system_status.glob, "glob", return_value=["/dev/nvidia0"])
    mocker.patch.object(system_status, "collect_presets_status", return_value={"active_preset_id": "final_primary", "presets": []})
    mocker.patch.object(
        system_status,
        "collect_model_readiness",
        return_value={
            "checks": [],
            "sovits": {
                "mock": False,
                "preset": "final_primary",
                "model_exists": True,
                "config_exists": True,
                "model_basename": "G_2400_infer.pth",
                "config_basename": "config.json",
                "speaker": "lain",
                "device": "cuda",
                "condition_mode": "internal_film",
                "conditioned_infer_exists": True,
            },
            "text_conditioning": {
                "enabled": True,
                "style_dim": 256,
                "film_strength": 0.1,
                "film_target": "pre_decoder",
            },
        },
    )

    data = system_status.collect_sovits_check()

    assert data["sovits"]["condition_mode"] == "internal_film"
    assert data["text_conditioning"]["enabled"] is True
    assert data["sovits"]["model_basename"] == "G_2400_infer.pth"
    assert "/repo/" not in data["sovits"]["model_basename"]
