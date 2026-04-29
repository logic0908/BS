from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTENTVEC_REQUIRED_ENCODERS = {
    "vec768l12",
    "vec256l9",
}
CONTENTVEC_CANDIDATE_FILENAMES = (
    "checkpoint_best_legacy_500.pt",
    "hubert_base.pt",
)


def load_sovits_config(config_path: str) -> dict[str, Any]:
    with open(config_path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("So-VITS config.json root must be an object")
    return payload


def extract_speaker_list(config_payload: dict[str, Any]) -> list[str]:
    spk_section = config_payload.get("spk")
    if isinstance(spk_section, dict):
        return [str(name) for name in spk_section.keys()]

    speakers = config_payload.get("speakers")
    if isinstance(speakers, list):
        return [str(name) for name in speakers]
    if isinstance(speakers, dict):
        return [str(name) for name in speakers.keys()]
    return []


def summarize_sovits_config(config_payload: dict[str, Any]) -> dict[str, Any]:
    data_section = config_payload.get("data") if isinstance(config_payload.get("data"), dict) else {}
    model_section = config_payload.get("model") if isinstance(config_payload.get("model"), dict) else {}
    return {
        "speakers": extract_speaker_list(config_payload),
        "sampling_rate": data_section.get("sampling_rate"),
        "speech_encoder": model_section.get("speech_encoder"),
    }


def contentvec_candidate_paths(repo_dir: str) -> list[Path]:
    pretrain_dir = Path(repo_dir) / "pretrain"
    return [pretrain_dir / filename for filename in CONTENTVEC_CANDIDATE_FILENAMES]


def inspect_sovits_assets(
    *,
    repo_dir: str,
    infer_script: str,
    model_path: str,
    config_path: str,
    speaker: str,
) -> dict[str, Any]:
    repo_path = Path(repo_dir)
    script_path = Path(infer_script)
    model_file = Path(model_path) if model_path else None
    config_file = Path(config_path) if config_path else None
    report: dict[str, Any] = {
        "repo_exists": repo_path.exists(),
        "infer_script_exists": script_path.exists(),
        "model_exists": bool(model_file and model_file.exists()),
        "config_exists": bool(config_file and config_file.exists()),
        "config_parse_ok": False,
        "config_error": None,
        "config_summary": {
            "speakers": [],
            "sampling_rate": None,
            "speech_encoder": None,
        },
        "speaker_exists_in_config": None,
        "contentvec_required": False,
        "contentvec_candidate_paths": [str(path) for path in contentvec_candidate_paths(repo_dir)],
        "contentvec_found_paths": [],
        "validation_errors": [],
    }

    if not report["config_exists"]:
        return report

    try:
        config_payload = load_sovits_config(config_path)
    except Exception as exc:
        report["config_error"] = str(exc)
        report["validation_errors"].append(
            {
                "code": "SOVITS_CONFIG_INVALID",
                "message": f"Failed to parse So-VITS config.json: {exc}",
            }
        )
        return report

    report["config_parse_ok"] = True
    report["config_summary"] = summarize_sovits_config(config_payload)
    speakers = report["config_summary"]["speakers"]
    speech_encoder = report["config_summary"]["speech_encoder"]

    if speaker.strip():
        report["speaker_exists_in_config"] = speaker in speakers if speakers else None
        if speakers and speaker not in speakers:
            report["validation_errors"].append(
                {
                    "code": "SOVITS_SPEAKER_NOT_IN_CONFIG",
                    "message": f"Speaker '{speaker}' is not present in config speaker list",
                    "details": {
                        "speaker": speaker,
                        "available_speakers": speakers,
                    },
                }
            )

    if speech_encoder in CONTENTVEC_REQUIRED_ENCODERS:
        report["contentvec_required"] = True
        found_paths = [str(path) for path in contentvec_candidate_paths(repo_dir) if path.exists()]
        report["contentvec_found_paths"] = found_paths
        if not found_paths:
            report["validation_errors"].append(
                {
                    "code": "CONTENTVEC_PRETRAIN_NOT_FOUND",
                    "message": (
                        f"speech_encoder={speech_encoder} requires ContentVec pretrain files under "
                        f"{repo_path / 'pretrain'}"
                    ),
                    "details": {
                        "speech_encoder": speech_encoder,
                        "expected_paths": report["contentvec_candidate_paths"],
                    },
                }
            )

    return report


def build_sovits_env_exports(
    *,
    repo_dir: str,
    infer_script: str,
    model_path: str,
    config_path: str,
    speaker: str,
    device: str,
) -> list[str]:
    return [
        "export SOVITS_MOCK=false",
        f"export SOVITS_REPO_DIR={repo_dir}",
        f"export SOVITS_INFER_SCRIPT={infer_script}",
        f"export SOVITS_MODEL_PATH={model_path}",
        f"export SOVITS_CONFIG_PATH={config_path}",
        f"export SOVITS_SPEAKER={speaker}",
        f"export SOVITS_DEVICE={device}",
        "export SOVITS_TRANSPOSE=0",
        "export SOVITS_TIMEOUT_SECONDS=300",
        "export SOVITS_PYTHON=",
        "export SOVITS_VENDOR_PATH=",
    ]
