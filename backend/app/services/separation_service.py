from __future__ import annotations

import logging
import os
import shutil
import subprocess

import librosa
import soundfile as sf

logger = logging.getLogger(__name__)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class SeparationService:
    def __init__(self) -> None:
        self.target_sr = int(os.environ.get("SOVITS_SAMPLE_RATE", "44100"))
        self.demucs_model = os.environ.get("DEMUCS_MODEL", "htdemucs")
        self.demucs_mock = _env_flag("DEMUCS_MOCK", True)
        self.demucs_allow_fallback = _env_flag("DEMUCS_ALLOW_FALLBACK", True)

    def prepare_vocals(self, input_path: str, output_path: str, is_vocal_only: bool = False) -> str:
        if is_vocal_only:
            return self.normalize_audio(input_path, output_path)
        return self.run_demucs(input_path, output_path)

    def normalize_audio(self, input_path: str, output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        audio, _sr = librosa.load(input_path, sr=self.target_sr, mono=True)
        sf.write(output_path, audio, self.target_sr, subtype="PCM_16")
        return output_path

    def run_demucs(self, input_path: str, output_path: str) -> str:
        normalized_input = self.normalize_audio(
            input_path,
            os.path.join(os.path.dirname(output_path), "normalized_input.wav"),
        )
        if self.demucs_mock:
            shutil.copyfile(normalized_input, output_path)
            return output_path

        work_dir = os.path.join(os.path.dirname(output_path), "demucs")
        os.makedirs(work_dir, exist_ok=True)
        command = [
            "demucs",
            "--two-stems",
            "vocals",
            "-n",
            self.demucs_model,
            "-o",
            work_dir,
            normalized_input,
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            if not self.demucs_allow_fallback:
                raise RuntimeError(f"Demucs separation failed: {exc}") from exc
            logger.warning("Demucs unavailable, falling back to normalized input: %s", exc)
            shutil.copyfile(normalized_input, output_path)
            return output_path

        base_name = os.path.splitext(os.path.basename(normalized_input))[0]
        vocals_candidate = os.path.join(work_dir, self.demucs_model, base_name, "vocals.wav")
        if not os.path.exists(vocals_candidate):
            if not self.demucs_allow_fallback:
                raise FileNotFoundError(f"Vocals file not found at {vocals_candidate}")
            logger.warning("Demucs output missing, falling back to normalized input: %s", vocals_candidate)
            shutil.copyfile(normalized_input, output_path)
            return output_path

        return self.normalize_audio(vocals_candidate, output_path)


separation_service = SeparationService()
