#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models_svc.sovits_assets import build_sovits_env_exports, inspect_sovits_assets  # noqa: E402
from app.models_svc.sovits_wrapper import SoVitsSvcEngine  # noqa: E402

DEFAULT_MODEL_PATH = PROJECT_ROOT / "local_models" / "sovits-test" / "minecraft_villager" / "G_4000.pth"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "local_models" / "sovits-test" / "minecraft_villager" / "config.json"
DEFAULT_SPEAKER = "villager"


def _print_section(title: str, payload: object) -> None:
    print(f"\n## {title}")
    if isinstance(payload, str):
        print(payload)
        return
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    engine = SoVitsSvcEngine()
    runtime_config = engine.resolve_runtime_config({})
    model_path = runtime_config.model_path or str(DEFAULT_MODEL_PATH)
    config_path = runtime_config.config_path or str(DEFAULT_CONFIG_PATH)
    speaker = runtime_config.speaker or DEFAULT_SPEAKER
    asset_report = inspect_sovits_assets(
        repo_dir=runtime_config.repo_dir,
        infer_script=runtime_config.infer_script,
        model_path=model_path,
        config_path=config_path,
        speaker=speaker,
    )

    config_summary = asset_report["config_summary"]
    summary = {
        "SOVITS_REPO_DIR": runtime_config.repo_dir,
        "SOVITS_REPO_DIR_exists": asset_report["repo_exists"],
        "SOVITS_INFER_SCRIPT": runtime_config.infer_script,
        "SOVITS_INFER_SCRIPT_exists": asset_report["infer_script_exists"],
        "SOVITS_MODEL_PATH": model_path,
        "SOVITS_MODEL_PATH_exists": asset_report["model_exists"],
        "SOVITS_CONFIG_PATH": config_path,
        "SOVITS_CONFIG_PATH_exists": asset_report["config_exists"],
        "SOVITS_SPEAKER": speaker,
        "SOVITS_SPEAKER_exists_in_config": asset_report["speaker_exists_in_config"],
        "config_speakers": config_summary["speakers"],
        "config_sampling_rate": config_summary["sampling_rate"],
        "config_speech_encoder": config_summary["speech_encoder"],
        "contentvec_required": asset_report["contentvec_required"],
        "contentvec_candidate_paths": asset_report["contentvec_candidate_paths"],
        "contentvec_found_paths": asset_report["contentvec_found_paths"],
        "validation_errors": asset_report["validation_errors"],
    }

    cpu_exports = build_sovits_env_exports(
        repo_dir=runtime_config.repo_dir,
        infer_script=runtime_config.infer_script,
        model_path=model_path,
        config_path=config_path,
        speaker=speaker,
        device="cpu",
    )
    cuda_exports = build_sovits_env_exports(
        repo_dir=runtime_config.repo_dir,
        infer_script=runtime_config.infer_script,
        model_path=model_path,
        config_path=config_path,
        speaker=speaker,
        device="cuda",
    )

    _print_section("So-VITS 资产检查", summary)
    _print_section(
        "建议的环境变量（CPU 先验 CLI）",
        "\n".join(cpu_exports),
    )
    _print_section(
        "建议的环境变量（GPU 恢复后切回 CUDA）",
        "\n".join(cuda_exports),
    )

    if not os.getenv("SOVITS_PYTHON"):
        _print_section("Python 说明", "SOVITS_PYTHON 留空时将使用当前 sys.executable。")
    if not os.getenv("SOVITS_VENDOR_PATH"):
        _print_section("Vendor 说明", "SOVITS_VENDOR_PATH 当前未设置；只有显式设置时才会注入。")

    return 0 if not asset_report["validation_errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
