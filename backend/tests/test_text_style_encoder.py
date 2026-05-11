import json
from pathlib import Path

import numpy as np
import pytest

from app.services import text_style_encoder as encoder_module


class DummySentenceTransformer:
    def __init__(self, model_name: str, cache_folder: str | None = None, local_files_only: bool = False) -> None:
        self.model_name = model_name
        self.cache_folder = cache_folder
        self.local_files_only = local_files_only

    def encode(self, texts, normalize_embeddings: bool = True):
        assert normalize_embeddings is True
        return [np.ones(384, dtype=np.float32) / np.sqrt(384.0) for _ in texts]


def test_text_style_encoder_encodes_prompt_and_writes_debug(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    config_path = tmp_path / "text_style_config.json"
    config_path.write_text(
        json.dumps(
            {
                "encoder_model_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                "embedding_dim": 256,
                "cache_dir": str(cache_dir),
                "enabled": True,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(encoder_module, "TEXT_STYLE_CONFIG_PATH", config_path)
    monkeypatch.setattr(encoder_module, "SentenceTransformer", DummySentenceTransformer)

    encoder = encoder_module.TextStyleEncoder()
    embedding = encoder.encode_prompt("清亮、少年感、男声")

    assert embedding.embedding_dim == 256
    assert embedding.model_name == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    assert "清亮" in embedding.keywords
    assert embedding.embedding_norm == pytest.approx(1.0, rel=1e-4)
    assert embedding.encoder_type == "sentence_transformer_projected"

    debug_paths = encoder.write_debug_artifacts(tmp_path / "debug", embedding)
    assert Path(debug_paths["style_embedding_json"]).exists()
    assert Path(debug_paths["style_embedding_npy"]).exists()
    assert Path(debug_paths["style_embedding_pt"]).exists()


def test_text_style_encoder_is_deterministic_and_falls_back_without_local_model(tmp_path, monkeypatch):
    config_path = tmp_path / "text_style_config.json"
    config_path.write_text(
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
    monkeypatch.setattr(encoder_module, "TEXT_STYLE_CONFIG_PATH", config_path)
    monkeypatch.setattr(encoder_module, "SentenceTransformer", DummySentenceTransformer)

    encoder = encoder_module.TextStyleEncoder()
    embedding_a = encoder.encode_prompt("温柔、明亮、流行感更强的女声风格")
    embedding_b = encoder.encode_prompt("温柔、明亮、流行感更强的女声风格")
    embedding_c = encoder.encode_prompt("低沉、厚重、力量感更强的男声风格")

    vector_a = np.asarray(embedding_a.embedding, dtype=np.float32)
    vector_b = np.asarray(embedding_b.embedding, dtype=np.float32)
    vector_c = np.asarray(embedding_c.embedding, dtype=np.float32)

    assert embedding_a.encoder_type == encoder_module.FALLBACK_ENCODER_TYPE
    assert embedding_a.embedding_dim == 256
    assert vector_a.dtype == np.float32
    assert np.allclose(vector_a, vector_b)
    assert not np.allclose(vector_a, vector_c)
    assert np.isfinite(vector_a).all()
    assert float(np.linalg.norm(vector_a)) == pytest.approx(1.0, rel=1e-5)


def test_text_style_encoder_save_embedding_writes_expected_artifacts(tmp_path, monkeypatch):
    config_path = tmp_path / "text_style_config.json"
    config_path.write_text(
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
    monkeypatch.setattr(encoder_module, "TEXT_STYLE_CONFIG_PATH", config_path)
    monkeypatch.setattr(encoder_module, "SentenceTransformer", DummySentenceTransformer)

    encoder = encoder_module.TextStyleEncoder()
    metadata = encoder.save_embedding("清亮、少年感、男声", tmp_path / "style_embedding")

    assert metadata["style_dim"] == 256
    assert Path(metadata["style_embedding_json"]).exists()
    assert Path(metadata["style_embedding_npy"]).exists()
    assert Path(metadata["style_embedding_pt"]).exists()
