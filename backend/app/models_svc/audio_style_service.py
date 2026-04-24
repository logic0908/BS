from __future__ import annotations

import os
import uuid
import traceback
from dataclasses import dataclass
from typing import Dict, Any

import librosa
import numpy as np
import soundfile as sf
from scipy import signal
from sentence_transformers import SentenceTransformer


TARGET_SR = 44100


@dataclass
class TaskState:
    task_id: str
    status: str
    message: str
    output_path: str | None = None
    error: str | None = None


class AudioStyleService:
    def __init__(self) -> None:
        self._embedder = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        self._tasks: Dict[str, TaskState] = {}
        self._prototypes = [
            ("温柔 抒情 柔和 细腻", {"pitch_semitone": -1.2, "speed": 0.98, "brightness": -0.25, "reverb": 0.35, "saturation": 0.05}),
            ("明亮 清澈 通透 甜美", {"pitch_semitone": 0.8, "speed": 1.01, "brightness": 0.3, "reverb": 0.15, "saturation": 0.04}),
            ("摇滚 爆发 力量 沙哑", {"pitch_semitone": 0.0, "speed": 1.02, "brightness": 0.18, "reverb": 0.08, "saturation": 0.28}),
            ("电音 梦幻 空灵 氛围", {"pitch_semitone": 0.3, "speed": 1.0, "brightness": 0.2, "reverb": 0.45, "saturation": 0.08}),
            ("低沉 厚重 磁性 成熟", {"pitch_semitone": -1.8, "speed": 0.99, "brightness": -0.35, "reverb": 0.12, "saturation": 0.1}),
            ("悲伤 忧郁 克制 冷淡", {"pitch_semitone": -0.6, "speed": 0.97, "brightness": -0.2, "reverb": 0.28, "saturation": 0.03}),
            ("开心 轻快 阳光 活力", {"pitch_semitone": 1.1, "speed": 1.04, "brightness": 0.22, "reverb": 0.1, "saturation": 0.06}),
        ]
        self._prototype_embeddings = self._embedder.encode([p[0] for p in self._prototypes], normalize_embeddings=True)

    def create_task(self) -> str:
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = TaskState(task_id=task_id, status="queued", message="任务已创建")
        return task_id

    def get_task(self, task_id: str) -> TaskState | None:
        return self._tasks.get(task_id)

    def process_task(
        self,
        task_id: str,
        input_path: str,
        text_prompt: str,
        style_strength: float,
        output_path: str,
    ) -> None:
        task = self._tasks[task_id]
        task.status = "running"
        task.message = "正在进行风格转换"
        try:
            y, sr = librosa.load(input_path, sr=TARGET_SR, mono=True)
            y = self._normalize_rms(y)
            params = self._map_prompt_to_params(text_prompt, style_strength)
            y = self._apply_style(y, sr, params)
            y = self._normalize_peak(y)
            sf.write(output_path, y, sr, subtype="PCM_16")
            task.status = "completed"
            task.message = "转换完成"
            task.output_path = output_path
        except Exception as exc:
            task.status = "failed"
            task.message = "转换失败"
            task.error = f"{exc}\n{traceback.format_exc()}"

    def _normalize_rms(self, y: np.ndarray, target_db: float = -20.0) -> np.ndarray:
        rms = np.sqrt(np.mean(np.square(y)) + 1e-8)
        current_db = 20 * np.log10(rms + 1e-8)
        gain_db = target_db - current_db
        return y * (10 ** (gain_db / 20))

    def _normalize_peak(self, y: np.ndarray, peak: float = 0.98) -> np.ndarray:
        m = np.max(np.abs(y)) + 1e-8
        return y / m * peak

    def _map_prompt_to_params(self, text_prompt: str, strength: float) -> Dict[str, float]:
        strength = float(np.clip(strength, 0.0, 1.0))
        query = self._embedder.encode([text_prompt], normalize_embeddings=True)[0]
        sims = np.dot(self._prototype_embeddings, query)
        top_idx = np.argsort(-sims)[:3]
        weights = np.maximum(sims[top_idx], 0.0)
        if np.sum(weights) < 1e-6:
            weights = np.array([1.0, 0.0, 0.0])
        weights = weights / np.sum(weights)

        mixed = {"pitch_semitone": 0.0, "speed": 1.0, "brightness": 0.0, "reverb": 0.0, "saturation": 0.0}
        for i, w in zip(top_idx, weights):
            proto = self._prototypes[i][1]
            for k in mixed:
                mixed[k] += w * proto[k]

        mixed["pitch_semitone"] *= strength
        mixed["brightness"] *= strength
        mixed["reverb"] *= strength
        mixed["saturation"] *= strength
        mixed["speed"] = 1.0 + (mixed["speed"] - 1.0) * strength
        return mixed

    def _apply_style(self, y: np.ndarray, sr: int, p: Dict[str, float]) -> np.ndarray:
        if abs(p["pitch_semitone"]) > 1e-3:
            y = librosa.effects.pitch_shift(y, sr=sr, n_steps=p["pitch_semitone"])
        if abs(p["speed"] - 1.0) > 1e-3:
            y = librosa.effects.time_stretch(y, rate=float(np.clip(p["speed"], 0.92, 1.08)))

        y = self._apply_tilt_eq(y, sr, p["brightness"])

        if p["saturation"] > 0:
            drive = 1.0 + 8.0 * float(p["saturation"])
            y = np.tanh(drive * y) / np.tanh(drive)

        if p["reverb"] > 0:
            y = self._apply_reverb(y, sr, p["reverb"])

        return y.astype(np.float32)

    def _apply_tilt_eq(self, y: np.ndarray, sr: int, brightness: float) -> np.ndarray:
        brightness = float(np.clip(brightness, -0.5, 0.5))
        if abs(brightness) < 1e-4:
            return y

        low_fc = 250.0
        high_fc = 3000.0
        b_l, a_l = signal.butter(2, low_fc / (sr / 2), btype="low")
        b_h, a_h = signal.butter(2, high_fc / (sr / 2), btype="high")

        low = signal.lfilter(b_l, a_l, y)
        high = signal.lfilter(b_h, a_h, y)
        mid = y - low - high

        high_gain = 1.0 + brightness * 1.2
        low_gain = 1.0 - brightness * 0.7
        return low * low_gain + mid + high * high_gain

    def _apply_reverb(self, y: np.ndarray, sr: int, amount: float) -> np.ndarray:
        amount = float(np.clip(amount, 0.0, 0.6))
        ir_len = int(sr * (0.18 + 0.45 * amount))
        t = np.linspace(0.0, 1.0, ir_len, endpoint=False)
        ir = (np.random.randn(ir_len) * np.exp(-4.0 * t)).astype(np.float32)
        ir = ir / (np.max(np.abs(ir)) + 1e-8)
        wet = signal.fftconvolve(y, ir, mode="full")[: len(y)]
        return y * (1.0 - amount * 0.5) + wet * (amount * 0.35)


audio_style_service = AudioStyleService()
