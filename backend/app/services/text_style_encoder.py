from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

from app.services import style_library

try:
    from sentence_transformers import SentenceTransformer
except ModuleNotFoundError:  # pragma: no cover - handled at runtime
    SentenceTransformer = None


APP_DIR = Path(__file__).resolve().parents[1]
TEXT_STYLE_CONFIG_PATH = Path(
    os.environ.get("TEXT_STYLE_CONFIG_PATH", str(APP_DIR / "config" / "text_style_config.json"))
)

FALLBACK_ENCODER_TYPE = "deterministic_style_hash_v1"


class TextStyleEncoderError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "details": self.details,
        }


@dataclass
class TextStyleEmbedding:
    embedding: list[float]
    embedding_dim: int
    model_name: str
    prompt_text: str
    normalized_prompt: str
    keywords: list[str]
    encoder_type: str = FALLBACK_ENCODER_TYPE
    source_model_dim: int | None = None

    @property
    def embedding_norm(self) -> float:
        return float(np.linalg.norm(np.asarray(self.embedding, dtype=np.float32)))

    def to_numpy(self) -> np.ndarray:
        return np.asarray(self.embedding, dtype=np.float32)

    def to_tensor(self, device: str | torch.device | None = None) -> torch.Tensor:
        tensor = torch.from_numpy(self.to_numpy())
        if device is not None:
            tensor = tensor.to(device)
        return tensor

    def to_debug_dict(self) -> dict[str, Any]:
        return {
            "embedding": self.embedding,
            "embedding_dim": self.embedding_dim,
            "model_name": self.model_name,
            "prompt_text": self.prompt_text,
            "normalized_prompt": self.normalized_prompt,
            "keywords": self.keywords,
            "embedding_norm": round(self.embedding_norm, 6),
            "encoder_type": self.encoder_type,
            "source_model_dim": self.source_model_dim,
        }

    def to_summary(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "status": "ready" if self.encoder_type != FALLBACK_ENCODER_TYPE else "fallback",
            "embedding_dim": self.embedding_dim,
            "embedding_norm": round(self.embedding_norm, 6),
            "top_keywords": self.keywords[:5],
            "encoder_model_name": self.model_name,
            "encoder_type": self.encoder_type,
            "source_model_dim": self.source_model_dim,
        }


def load_text_style_config() -> dict[str, Any]:
    defaults = {
        "encoder_model_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "embedding_dim": 256,
        "cache_dir": "/home/featurize/work/BS/local_models/text-encoders",
        "enabled": True,
    }
    if not TEXT_STYLE_CONFIG_PATH.exists():
        return defaults
    payload = json.loads(TEXT_STYLE_CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("text_style_config.json root must be an object")
    return {**defaults, **payload}


class TextStyleEncoder:
    def __init__(self, style_dim: int | None = None) -> None:
        self._config = load_text_style_config()
        if style_dim is not None:
            self._config["embedding_dim"] = int(style_dim)
        self._model = None
        self._model_load_attempted = False
        self._model_load_error: TextStyleEncoderError | None = None

    @property
    def config(self) -> dict[str, Any]:
        return dict(self._config)

    @property
    def style_dim(self) -> int:
        return int(self._config.get("embedding_dim", 256))

    def encode(self, prompt: str) -> np.ndarray:
        return self.encode_prompt(prompt).to_numpy()

    def encode_to_tensor(self, prompt: str, device: str | torch.device | None = None) -> torch.Tensor:
        embedding = self.encode_prompt(prompt)
        return embedding.to_tensor(device=device)

    def encode_prompt(self, prompt_text: str) -> TextStyleEmbedding:
        if not bool(self._config.get("enabled", True)):
            raise TextStyleEncoderError(
                "TEXT_ENCODER_DISABLED",
                "Text style encoder is disabled by configuration",
                {"config_path": str(TEXT_STYLE_CONFIG_PATH)},
            )

        normalized_prompt = _normalize_prompt(prompt_text)
        keywords = _extract_keywords(normalized_prompt)
        target_dim = self.style_dim
        source_vector = self._encode_with_sentence_transformer(normalized_prompt, target_dim)

        if source_vector is not None:
            embedding, source_model_dim = source_vector
            encoder_type = "sentence_transformer_projected" if source_model_dim != target_dim else "sentence_transformer"
            model_name = str(self._config.get("encoder_model_name") or "")
        else:
            embedding = self._fallback_encode(prompt_text, normalized_prompt, target_dim)
            source_model_dim = None
            encoder_type = FALLBACK_ENCODER_TYPE
            model_name = FALLBACK_ENCODER_TYPE

        return TextStyleEmbedding(
            embedding=embedding.astype(float).tolist(),
            embedding_dim=int(embedding.shape[0]),
            model_name=model_name,
            prompt_text=prompt_text,
            normalized_prompt=normalized_prompt,
            keywords=keywords,
            encoder_type=encoder_type,
            source_model_dim=source_model_dim,
        )

    def save_embedding(self, prompt: str | TextStyleEmbedding, path: Path) -> dict[str, Any]:
        embedding = prompt if isinstance(prompt, TextStyleEmbedding) else self.encode_prompt(prompt)
        base = Path(path)
        if base.suffix:
            base = base.with_suffix("")
        base.parent.mkdir(parents=True, exist_ok=True)

        json_path = base.with_suffix(".json")
        npy_path = base.with_suffix(".npy")
        pt_path = base.with_suffix(".pt")
        array = embedding.to_numpy()
        tensor = torch.from_numpy(array.copy())

        payload = embedding.to_debug_dict()
        payload.update(
            {
                "embedding_path": str(pt_path),
                "embedding_format": "pt",
            }
        )
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        np.save(npy_path, array)
        torch.save(
            {
                "style_emb": tensor,
                "style_prompt": embedding.prompt_text,
                "normalized_prompt": embedding.normalized_prompt,
                "style_dim": embedding.embedding_dim,
                "encoder_type": embedding.encoder_type,
                "model_name": embedding.model_name,
                "keywords": embedding.keywords,
            },
            pt_path,
        )
        return {
            "style_prompt": embedding.prompt_text,
            "style_dim": embedding.embedding_dim,
            "encoder_model_name": embedding.model_name,
            "encoder_type": embedding.encoder_type,
            "norm": round(embedding.embedding_norm, 6),
            "embedding_path": str(pt_path),
            "style_embedding_json": str(json_path),
            "style_embedding_npy": str(npy_path),
            "style_embedding_pt": str(pt_path),
        }

    def write_debug_artifacts(self, debug_dir: str | os.PathLike[str], embedding: TextStyleEmbedding) -> dict[str, str]:
        saved = self.save_embedding(embedding, Path(debug_dir) / "style_embedding")
        return {
            "style_embedding_json": saved["style_embedding_json"],
            "style_embedding_npy": saved["style_embedding_npy"],
            "style_embedding_pt": saved["style_embedding_pt"],
        }

    def _encode_with_sentence_transformer(self, normalized_prompt: str, target_dim: int) -> tuple[np.ndarray, int] | None:
        model = self._get_model()
        if model is None:
            return None
        try:
            vector = model.encode([normalized_prompt or ""], normalize_embeddings=True)[0]
        except Exception:
            return None
        raw = np.asarray(vector, dtype=np.float32)
        projected = _project_embedding(raw, target_dim)
        return projected, int(raw.shape[0])

    def _fallback_encode(self, prompt_text: str, normalized_prompt: str, target_dim: int) -> np.ndarray:
        prompt_key = normalized_prompt or (prompt_text or "").strip() or "<empty_prompt>"
        vector = 0.55 * _stable_hash_vector(prompt_key, target_dim)

        for token in _extract_keywords(prompt_key):
            vector += 0.15 * _stable_hash_vector(f"token::{token}", target_dim)

        for matched in _matched_style_features(prompt_key):
            vector += matched["weight"] * _stable_hash_vector(matched["key"], target_dim)

        if not np.any(vector):
            vector = _stable_hash_vector("fallback::empty", target_dim)
        return _normalize_vector(vector)

    def _get_model(self):
        if self._model is not None:
            return self._model
        if self._model_load_attempted:
            return None
        self._model_load_attempted = True
        if SentenceTransformer is None:
            self._model_load_error = TextStyleEncoderError(
                "TEXT_ENCODER_DEPENDENCY_MISSING",
                "sentence-transformers is not installed; using deterministic fallback encoder",
                {"package": "sentence-transformers"},
            )
            return None
        model_name = str(self._config.get("encoder_model_name") or "").strip()
        cache_dir = str(self._config.get("cache_dir") or "").strip()
        if not model_name or not cache_dir:
            self._model_load_error = TextStyleEncoderError(
                "TEXT_ENCODER_MODEL_NOT_FOUND",
                "Text encoder model path is incomplete; using deterministic fallback encoder",
                {"config_path": str(TEXT_STYLE_CONFIG_PATH)},
            )
            return None
        cache_dir_path = Path(cache_dir)
        if not cache_dir_path.exists():
            self._model_load_error = TextStyleEncoderError(
                "TEXT_ENCODER_MODEL_NOT_FOUND",
                "Text encoder cache directory does not exist; using deterministic fallback encoder",
                {"cache_dir": cache_dir},
            )
            return None
        try:
            model_load_path = _resolve_local_model_path(cache_dir_path, model_name)
            with _offline_model_load_env():
                self._model = SentenceTransformer(
                    model_load_path,
                    cache_folder=cache_dir,
                    local_files_only=True,
                )
        except Exception as exc:
            self._model_load_error = TextStyleEncoderError(
                "TEXT_ENCODER_MODEL_NOT_FOUND",
                "Text encoder model was not found in local cache; using deterministic fallback encoder",
                {"model_name": model_name, "cache_dir": cache_dir, "reason": str(exc)},
            )
            self._model = None
        return self._model


def _normalize_prompt(prompt_text: str) -> str:
    return re.sub(r"\s+", " ", (prompt_text or "").strip().lower())


def _extract_keywords(normalized_prompt: str) -> list[str]:
    parts = [
        token.strip()
        for token in re.split(r"[\s,;，。!！?？、/|]+", normalized_prompt)
        if token.strip()
    ]
    deduped: list[str] = []
    seen: set[str] = set()
    for token in parts:
        if token not in seen:
            seen.add(token)
            deduped.append(token)
    return deduped


def _resolve_local_model_path(cache_dir: Path, model_name: str) -> str:
    snapshot_root = cache_dir / f"models--{model_name.replace('/', '--')}" / "snapshots"
    if snapshot_root.exists():
        snapshots = sorted(path for path in snapshot_root.iterdir() if path.is_dir())
        if snapshots:
            return str(snapshots[-1])
    return model_name


@contextlib.contextmanager
def _offline_model_load_env():
    overrides = {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
    }
    original = {key: os.environ.get(key) for key in overrides}
    try:
        os.environ.update(overrides)
        yield
    finally:
        for key, previous in original.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous


def _matched_style_features(normalized_prompt: str) -> list[dict[str, Any]]:
    try:
        presets = style_library.load_style_library()
    except Exception:
        presets = []

    matched: list[dict[str, Any]] = []
    seen: set[str] = set()
    tokens = _extract_keywords(normalized_prompt)
    token_set = set(tokens)

    for preset in presets:
        style_id = str(preset.get("style_id") or "").strip()
        keywords = [str(item).strip().lower() for item in (preset.get("keywords") or []) if str(item).strip()]
        style_tags = [str(item).strip().lower() for item in (preset.get("style_tags") or []) if str(item).strip()]
        description = str(preset.get("description") or "").strip().lower()
        matched_score = 0.0
        matched_keywords: list[str] = []
        for keyword in keywords:
            if keyword and keyword in normalized_prompt:
                matched_score += 0.18
                matched_keywords.append(keyword)
            elif keyword and keyword in token_set:
                matched_score += 0.12
                matched_keywords.append(keyword)
        if matched_score <= 0:
            continue
        feature_keys = [f"style_id::{style_id}", f"description::{description}"]
        feature_keys.extend(f"style_tag::{tag}" for tag in style_tags)
        feature_keys.extend(f"keyword::{keyword}" for keyword in matched_keywords)
        for feature_key in feature_keys:
            if not feature_key or feature_key in seen:
                continue
            seen.add(feature_key)
            matched.append({"key": feature_key, "weight": min(0.35, matched_score)})
    return matched


def _stable_hash_vector(key: str, dim: int) -> np.ndarray:
    values = np.zeros(dim, dtype=np.float32)
    counter = 0
    cursor = 0
    while cursor < dim:
        digest = hashlib.sha256(f"{key}|{counter}".encode("utf-8")).digest()
        counter += 1
        for index in range(0, len(digest), 4):
            if cursor >= dim:
                break
            chunk = digest[index : index + 4]
            if len(chunk) < 4:
                chunk = chunk.ljust(4, b"\x00")
            integer = int.from_bytes(chunk, "little", signed=False)
            values[cursor] = (integer / 2**31) - 1.0
            cursor += 1
    return _normalize_vector(values)


def _project_embedding(vector: np.ndarray, target_dim: int) -> np.ndarray:
    if int(vector.shape[0]) == target_dim:
        return _normalize_vector(vector.astype(np.float32, copy=False))
    projected = np.zeros(target_dim, dtype=np.float32)
    for index, value in enumerate(vector.astype(np.float32, copy=False)):
        projected[index % target_dim] += value
        projected[(index * 17 + 11) % target_dim] += 0.5 * value
        projected[(index * 31 + 7) % target_dim] -= 0.25 * value
    return _normalize_vector(projected)


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    if not math.isfinite(norm) or norm <= 1e-8:
        if vector.shape[0] == 0:
            return vector
        fallback = np.zeros_like(vector)
        fallback[0] = 1.0
        return fallback
    return vector / norm


text_style_encoder = TextStyleEncoder()
