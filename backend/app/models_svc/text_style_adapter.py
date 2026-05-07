from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

try:
    import torch
    from torch import nn
except ModuleNotFoundError:  # pragma: no cover - handled through fallback mode
    torch = None
    nn = None


APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_DIR.parents[1]
STYLE_ADAPTER_CONFIG_PATH = Path(
    os.environ.get("STYLE_ADAPTER_CONFIG_PATH", str(APP_DIR / "config" / "style_adapter_config.json"))
)
DEFAULT_CHECKPOINT_PATH = str(PROJECT_ROOT / "runtime" / "style_adapter" / "text_style_adapter_v1.pt")
TRAINED_TARGET_KEYS = (
    "brightness",
    "power",
    "breathiness",
    "youthfulness",
    "transpose",
    "style_strength",
)
REQUESTED_ADAPTER_MODE_ALIASES = {
    "trained": "trained_adapter",
    "trained_adapter": "trained_adapter",
    "rule_based": "rule_based_adapter",
    "rule_based_adapter": "rule_based_adapter",
    "no_adapter": "no_adapter",
}


if nn is not None:
    class AdapterMLP(nn.Module):
        def __init__(self, input_dim: int, output_dim: int, hidden_dims: list[int] | tuple[int, ...] | None = None) -> None:
            super().__init__()
            dims = list(hidden_dims or [128, 64])
            layers: list[nn.Module] = []
            current_dim = input_dim
            for hidden_dim in dims:
                layers.append(nn.Linear(current_dim, int(hidden_dim)))
                layers.append(nn.ReLU())
                current_dim = int(hidden_dim)
            layers.append(nn.Linear(current_dim, output_dim))
            self.layers = nn.Sequential(*layers)

        def forward(self, x):
            return self.layers(x)
else:  # pragma: no cover - only used when torch is unavailable
    class AdapterMLP:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("torch is not available")


class TextStyleAdapterError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass
class TextStyleAdapterResult:
    adapter_enabled: bool
    adapter_mode: str
    adapter_version: str
    adapter_type: str
    adapter_checkpoint_path: str
    trainable: bool
    control_params: dict[str, Any]
    override_reason: str
    adapter_fallback_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_enabled": self.adapter_enabled,
            "adapter_mode": self.adapter_mode,
            "adapter_version": self.adapter_version,
            "adapter_type": self.adapter_type,
            "adapter_checkpoint_path": self.adapter_checkpoint_path,
            "trainable": self.trainable,
            "control_params": self.control_params,
            "override_reason": self.override_reason,
            "adapter_fallback_reason": self.adapter_fallback_reason,
        }

    def to_summary(self) -> dict[str, Any]:
        summary = {
            "adapter_enabled": self.adapter_enabled,
            "adapter_mode": self.adapter_mode,
            "adapter_version": self.adapter_version,
            "adapter_type": self.adapter_type,
            "control_params": {
                "model_preset_id": self.control_params.get("model_preset_id"),
                "transpose": self.control_params.get("transpose"),
                "brightness": self.control_params.get("brightness"),
                "power": self.control_params.get("power"),
                "breathiness": self.control_params.get("breathiness"),
                "youthfulness": self.control_params.get("youthfulness"),
                "gender_hint": self.control_params.get("gender_hint"),
                "style_strength": self.control_params.get("style_strength"),
            },
            "override_reason": self.override_reason,
            "adapter_checkpoint_path": self.adapter_checkpoint_path,
        }
        if self.adapter_fallback_reason:
            summary["adapter_fallback_reason"] = self.adapter_fallback_reason
        return summary


def load_style_adapter_config() -> dict[str, Any]:
    defaults = {
        "enabled": True,
        "use_trained": True,
        "adapter_version": "v0.7_trained_mlp_with_rule_based_fallback",
        "adapter_type": "trained_mlp",
        "adapter_checkpoint_path": DEFAULT_CHECKPOINT_PATH,
        "trainable": True,
    }
    payload: dict[str, Any] = {}
    if STYLE_ADAPTER_CONFIG_PATH.exists():
        loaded = json.loads(STYLE_ADAPTER_CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("style_adapter_config.json root must be an object")
        payload.update(loaded)
    payload = {**defaults, **payload}
    payload["enabled"] = _env_flag("STYLE_ADAPTER_ENABLED", bool(payload.get("enabled", True)))
    payload["use_trained"] = _env_flag("STYLE_ADAPTER_USE_TRAINED", bool(payload.get("use_trained", True)))
    payload["adapter_checkpoint_path"] = str(
        os.environ.get("STYLE_ADAPTER_CHECKPOINT_PATH", str(payload.get("adapter_checkpoint_path") or DEFAULT_CHECKPOINT_PATH))
    )
    payload["adapter_type"] = (
        "trained_mlp" if bool(payload.get("use_trained", True)) else str(payload.get("adapter_type") or "rule_based")
    )
    payload["trainable"] = bool(payload.get("trainable", bool(payload.get("use_trained", True))))
    return payload


def build_training_target(row: dict[str, Any]) -> dict[str, Any]:
    tags = {str(tag).strip().lower() for tag in (row.get("style_tags") or []) if str(tag).strip()}
    prompt = str(row.get("prompt") or "").strip().lower()

    male = "male" in tags or "男声" in prompt
    female = "female" in tags or "女声" in prompt
    bright = bool({"bright", "clear", "shiny"} & tags) or any(token in prompt for token in ["清亮", "明亮", "通透"])
    power = bool({"power", "rock", "strong"} & tags) or any(token in prompt for token in ["厚重", "力量", "摇滚"])
    breathy = bool({"breathy", "airy", "soft"} & tags) or any(token in prompt for token in ["气声", "轻柔", "空灵"])
    youth = bool({"youth", "young"} & tags) or any(token in prompt for token in ["少年感", "青春", "年轻"])

    gender_hint = "female" if female and not male else "male" if male and not female else "neutral"
    transpose = int(row.get("transpose", 0) or 0)
    if gender_hint == "female":
        transpose = max(transpose, 1)
    elif gender_hint == "male":
        transpose = min(transpose, -1 if transpose == 0 else transpose)

    brightness = _clamp01(0.32 + 0.52 * float(bright) + 0.08 * float(youth) + 0.04 * float(female))
    power_value = _clamp01(0.28 + 0.54 * float(power) + 0.06 * float(male))
    breathiness = _clamp01(0.24 + 0.58 * float(breathy) + 0.05 * float(female))
    youthfulness = _clamp01(0.26 + 0.56 * float(youth) + 0.08 * float(bright))
    style_strength = _clamp01(float(row.get("style_strength", 0.65) or 0.65))

    return {
        "model_preset_id": str(row.get("model_preset_id") or "final_primary"),
        "transpose": transpose,
        "brightness": round(brightness, 4),
        "power": round(power_value, 4),
        "breathiness": round(breathiness, 4),
        "youthfulness": round(youthfulness, 4),
        "gender_hint": gender_hint,
        "style_strength": round(style_strength, 4),
    }


def numeric_target_vector(control_params: dict[str, Any]) -> list[float]:
    return [
        float(control_params.get("brightness", 0.5) or 0.5),
        float(control_params.get("power", 0.5) or 0.5),
        float(control_params.get("breathiness", 0.5) or 0.5),
        float(control_params.get("youthfulness", 0.5) or 0.5),
        float(control_params.get("transpose", 0.0) or 0.0),
        float(control_params.get("style_strength", 0.65) or 0.65),
    ]


class TextStyleAdapter:
    def __init__(self) -> None:
        self._trained_runtime_cache: dict[str, dict[str, Any]] = {}

    @property
    def config(self) -> dict[str, Any]:
        return load_style_adapter_config()

    def build_controls(
        self,
        prompt_embedding: dict[str, Any] | None,
        style_strength: float,
        selected_style: dict[str, Any] | None,
        available_model_presets: list[dict[str, Any]] | None,
        requested_adapter_mode: str | None = None,
    ) -> TextStyleAdapterResult:
        config = load_style_adapter_config()
        normalized_requested_mode = normalize_requested_adapter_mode(requested_adapter_mode)
        if normalized_requested_mode == "no_adapter":
            return self._build_disabled_controls(
                style_strength=style_strength,
                selected_style=selected_style,
                config=config,
            )

        enabled = bool(config.get("enabled", True)) and prompt_embedding is not None
        if not enabled:
            return self._build_rule_based_controls(
                prompt_embedding=prompt_embedding,
                style_strength=style_strength,
                selected_style=selected_style,
                available_model_presets=available_model_presets,
                config=config,
                adapter_mode="fallback",
                adapter_fallback_reason="PROMPT_EMBEDDING_UNAVAILABLE",
                enabled=False,
            )

        if normalized_requested_mode == "rule_based_adapter":
            return self._build_rule_based_controls(
                prompt_embedding=prompt_embedding,
                style_strength=style_strength,
                selected_style=selected_style,
                available_model_presets=available_model_presets,
                config=config,
                adapter_mode="rule_based",
                adapter_fallback_reason=None,
                enabled=True,
            )

        use_trained = bool(config.get("use_trained", True))
        if normalized_requested_mode == "trained_adapter":
            use_trained = True

        if use_trained:
            try:
                return self._build_trained_controls(
                    prompt_embedding=prompt_embedding,
                    style_strength=style_strength,
                    selected_style=selected_style,
                    available_model_presets=available_model_presets,
                    config=config,
                )
            except TextStyleAdapterError as exc:
                return self._build_rule_based_controls(
                    prompt_embedding=prompt_embedding,
                    style_strength=style_strength,
                    selected_style=selected_style,
                    available_model_presets=available_model_presets,
                    config=config,
                    adapter_mode="fallback",
                    adapter_fallback_reason=exc.code,
                    enabled=True,
                )

        return self._build_rule_based_controls(
            prompt_embedding=prompt_embedding,
            style_strength=style_strength,
            selected_style=selected_style,
            available_model_presets=available_model_presets,
            config=config,
            adapter_mode="rule_based",
            adapter_fallback_reason=None,
            enabled=True,
        )

    def _build_disabled_controls(
        self,
        style_strength: float,
        selected_style: dict[str, Any] | None,
        config: dict[str, Any],
    ) -> TextStyleAdapterResult:
        return TextStyleAdapterResult(
            adapter_enabled=False,
            adapter_mode="no_adapter",
            adapter_version=str(config.get("adapter_version") or "v0.7_trained_mlp_with_rule_based_fallback"),
            adapter_type="disabled",
            adapter_checkpoint_path=str(config.get("adapter_checkpoint_path") or DEFAULT_CHECKPOINT_PATH),
            trainable=bool(config.get("trainable", True)),
            control_params={
                "model_preset_id": str((selected_style or {}).get("model_preset_id") or ""),
                "transpose": int((selected_style or {}).get("transpose", 0) or 0),
                "style_strength": round(float(np.clip(style_strength, 0.0, 1.0)), 4),
            },
            override_reason="requested_adapter_mode=no_adapter; skipped TextStyleAdapter control injection",
            adapter_fallback_reason=None,
        )

    def _build_trained_controls(
        self,
        prompt_embedding: dict[str, Any],
        style_strength: float,
        selected_style: dict[str, Any] | None,
        available_model_presets: list[dict[str, Any]] | None,
        config: dict[str, Any],
    ) -> TextStyleAdapterResult:
        checkpoint_path = str(config.get("adapter_checkpoint_path") or DEFAULT_CHECKPOINT_PATH)
        bundle = self._load_trained_bundle(checkpoint_path)

        raw_embedding = prompt_embedding.get("embedding")
        if not isinstance(raw_embedding, list) or not raw_embedding:
            raise TextStyleAdapterError(
                "ADAPTER_EMBEDDING_MISSING",
                "Prompt embedding vector is missing; cannot run trained adapter",
            )
        embedding = np.asarray(raw_embedding, dtype=np.float32)
        input_dim = int(bundle["payload"].get("input_dim", 0))
        if embedding.shape[0] != input_dim:
            raise TextStyleAdapterError(
                "ADAPTER_INPUT_DIM_MISMATCH",
                "Prompt embedding dimension does not match the trained adapter checkpoint",
                {"expected_dim": input_dim, "actual_dim": int(embedding.shape[0])},
            )

        model = bundle["model"]
        with torch.no_grad():
            predicted = model(torch.tensor(embedding[None, :], dtype=torch.float32)).detach().cpu().numpy()[0]

        target_keys = list(bundle["payload"].get("target_keys") or TRAINED_TARGET_KEYS)
        numeric_controls = {key: float(value) for key, value in zip(target_keys, predicted)}
        nearest_sample, similarity = self._nearest_sample(bundle, embedding)

        ready_ids = {
            str(item.get("preset_id") or item.get("model_preset_id") or "")
            for item in (available_model_presets or [])
            if isinstance(item, dict)
        }
        base_model_preset_id = str((selected_style or {}).get("model_preset_id") or "")
        predicted_preset_id = str(nearest_sample.get("model_preset_id") or base_model_preset_id or "final_primary")
        if ready_ids and predicted_preset_id not in ready_ids:
            predicted_preset_id = base_model_preset_id if base_model_preset_id in ready_ids else "final_primary"

        gender_hint = str(nearest_sample.get("gender_hint") or "neutral")
        style_strength_out = _clamp01((float(style_strength) + numeric_controls.get("style_strength", 0.65)) / 2.0)
        transpose_value = int(round(numeric_controls.get("transpose", float((selected_style or {}).get("transpose", 0) or 0))))
        if gender_hint == "female":
            transpose_value = max(transpose_value, 1)
        elif gender_hint == "male":
            transpose_value = min(transpose_value, -1 if transpose_value == 0 else transpose_value)

        control_params = {
            "model_preset_id": predicted_preset_id,
            "transpose": transpose_value,
            "brightness": round(_clamp01(numeric_controls.get("brightness", 0.5)), 4),
            "power": round(_clamp01(numeric_controls.get("power", 0.5)), 4),
            "breathiness": round(_clamp01(numeric_controls.get("breathiness", 0.5)), 4),
            "youthfulness": round(_clamp01(numeric_controls.get("youthfulness", 0.5)), 4),
            "gender_hint": gender_hint,
            "style_strength": round(style_strength_out, 4),
        }
        override_reason = (
            f"Trained TextStyleAdapter matched {nearest_sample.get('id', 'nearest_sample')} "
            f"(cosine={similarity:.4f}) and mapped the prompt embedding to preset/controls"
        )
        return TextStyleAdapterResult(
            adapter_enabled=True,
            adapter_mode="trained",
            adapter_version=str(
                bundle["payload"].get("adapter_version") or config.get("adapter_version") or "v0.7_trained_mlp_with_rule_based_fallback"
            ),
            adapter_type="trained_mlp",
            adapter_checkpoint_path=checkpoint_path,
            trainable=bool(config.get("trainable", True)),
            control_params=control_params,
            override_reason=override_reason,
            adapter_fallback_reason=None,
        )

    def _build_rule_based_controls(
        self,
        prompt_embedding: dict[str, Any] | None,
        style_strength: float,
        selected_style: dict[str, Any] | None,
        available_model_presets: list[dict[str, Any]] | None,
        config: dict[str, Any],
        adapter_mode: str,
        adapter_fallback_reason: str | None,
        enabled: bool,
    ) -> TextStyleAdapterResult:
        base_model_preset_id = str((selected_style or {}).get("model_preset_id") or "")
        normalized_keywords = [
            str(item).strip().lower()
            for item in ((prompt_embedding or {}).get("keywords") or [])
            if str(item).strip()
        ]
        embedding_norm = float((prompt_embedding or {}).get("embedding_norm") or 1.0)
        strength = float(np.clip(style_strength, 0.0, 1.0))

        if prompt_embedding is None:
            return TextStyleAdapterResult(
                adapter_enabled=enabled,
                adapter_mode=adapter_mode,
                adapter_version=str(config.get("adapter_version") or "v0.7_trained_mlp_with_rule_based_fallback"),
                adapter_type="rule_based",
                adapter_checkpoint_path=str(config.get("adapter_checkpoint_path") or DEFAULT_CHECKPOINT_PATH),
                trainable=bool(config.get("trainable", True)),
                control_params={
                    "model_preset_id": base_model_preset_id or "final_primary",
                    "transpose": int((selected_style or {}).get("transpose", 0) or 0),
                    "brightness": 0.5,
                    "power": 0.5,
                    "breathiness": 0.5,
                    "youthfulness": 0.5,
                    "gender_hint": "neutral",
                    "style_strength": round(strength, 4),
                },
                override_reason="Adapter disabled or prompt embedding unavailable; keeping style_library output",
                adapter_fallback_reason=adapter_fallback_reason,
            )

        female_hits = _has_any(normalized_keywords, {"女声", "少女", "甜美", "轻柔"})
        male_hits = _has_any(normalized_keywords, {"男声", "低沉", "厚重", "磁性"})
        bright_hits = _has_any(normalized_keywords, {"清亮", "明亮", "通透", "少年感", "阳光"})
        power_hits = _has_any(normalized_keywords, {"力量", "爆发", "厚重", "摇滚", "强烈"})
        breath_hits = _has_any(normalized_keywords, {"气声", "轻柔", "空灵", "细腻"})
        youth_hits = _has_any(normalized_keywords, {"少年感", "青春", "年轻", "清澈"})

        gender_hint = "female" if female_hits and not male_hits else "male" if male_hits and not female_hits else "neutral"
        transpose = int((selected_style or {}).get("transpose", 0) or 0)
        override_reasons: list[str] = []
        if female_hits and not male_hits:
            transpose = max(transpose, 1)
            override_reasons.append("female-leaning prompt suggests a slightly higher transpose target")
        elif male_hits and not female_hits:
            transpose = min(transpose, -1)
            override_reasons.append("male or low-register prompt suggests a slightly lower transpose target")

        preset_id = base_model_preset_id or "final_primary"
        if available_model_presets:
            ready_ids = {str(item.get("preset_id") or item.get("model_preset_id") or "") for item in available_model_presets}
            if preset_id not in ready_ids and "final_primary" in ready_ids:
                preset_id = "final_primary"
            if _has_any(normalized_keywords, {"技术", "验收"}) and "tech_villager" in ready_ids:
                preset_id = "tech_villager"
                override_reasons.append("prompt explicitly indicates technical validation")

        brightness = _clamp01(0.35 + 0.4 * float(bright_hits) + 0.08 * strength + 0.02 * embedding_norm)
        power = _clamp01(0.3 + 0.45 * float(power_hits) + 0.1 * strength)
        breathiness = _clamp01(0.28 + 0.42 * float(breath_hits) + 0.08 * strength)
        youthfulness = _clamp01(0.32 + 0.4 * float(youth_hits or bright_hits) + 0.08 * strength)

        if adapter_mode == "fallback" and adapter_fallback_reason:
            override_reasons.insert(0, f"trained adapter unavailable ({adapter_fallback_reason}); falling back to rule-based controls")
        elif not override_reasons:
            override_reasons.append("Rule-based TextStyleAdapter maps prompt semantics to lightweight controls")

        return TextStyleAdapterResult(
            adapter_enabled=enabled,
            adapter_mode=adapter_mode,
            adapter_version=str(config.get("adapter_version") or "v0.7_trained_mlp_with_rule_based_fallback"),
            adapter_type="rule_based",
            adapter_checkpoint_path=str(config.get("adapter_checkpoint_path") or DEFAULT_CHECKPOINT_PATH),
            trainable=bool(config.get("trainable", True)),
            control_params={
                "model_preset_id": preset_id,
                "transpose": transpose,
                "brightness": round(brightness, 4),
                "power": round(power, 4),
                "breathiness": round(breathiness, 4),
                "youthfulness": round(youthfulness, 4),
                "gender_hint": gender_hint,
                "style_strength": round(strength, 4),
            },
            override_reason="; ".join(override_reasons),
            adapter_fallback_reason=adapter_fallback_reason,
        )

    def _load_trained_bundle(self, checkpoint_path: str) -> dict[str, Any]:
        if torch is None or nn is None:
            raise TextStyleAdapterError(
                "ADAPTER_TORCH_UNAVAILABLE",
                "torch is not available in the current environment; trained adapter cannot be loaded",
            )
        checkpoint_file = Path(checkpoint_path)
        if not checkpoint_file.exists():
            raise TextStyleAdapterError(
                "ADAPTER_CHECKPOINT_NOT_FOUND",
                "Trained adapter checkpoint does not exist",
                {"checkpoint_path": checkpoint_path},
            )
        cache_key = f"{checkpoint_file}:{checkpoint_file.stat().st_mtime_ns}"
        cached = self._trained_runtime_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            payload = torch.load(str(checkpoint_file), map_location="cpu")
        except Exception as exc:  # pragma: no cover - depends on external runtime file
            raise TextStyleAdapterError(
                "ADAPTER_CHECKPOINT_LOAD_FAILED",
                "Failed to load the trained adapter checkpoint",
                {"checkpoint_path": checkpoint_path, "reason": str(exc)},
            ) from exc

        if not isinstance(payload, dict):
            raise TextStyleAdapterError(
                "ADAPTER_CHECKPOINT_INVALID",
                "Trained adapter checkpoint payload must be a dict",
                {"checkpoint_path": checkpoint_path},
            )

        input_dim = int(payload.get("input_dim", 0) or 0)
        output_dim = int(payload.get("output_dim", 0) or 0)
        if input_dim <= 0 or output_dim <= 0:
            raise TextStyleAdapterError(
                "ADAPTER_CHECKPOINT_INVALID",
                "Trained adapter checkpoint is missing input/output dimensions",
                {"checkpoint_path": checkpoint_path},
            )
        model = AdapterMLP(
            input_dim=input_dim,
            output_dim=output_dim,
            hidden_dims=list(payload.get("hidden_dims") or [128, 64]),
        )
        model_state_dict = payload.get("model_state_dict")
        if not isinstance(model_state_dict, dict):
            raise TextStyleAdapterError(
                "ADAPTER_CHECKPOINT_INVALID",
                "Trained adapter checkpoint is missing model_state_dict",
                {"checkpoint_path": checkpoint_path},
            )
        model.load_state_dict(model_state_dict)
        model.eval()

        sample_embeddings = np.asarray(payload.get("sample_embeddings") or [], dtype=np.float32)
        sample_records = payload.get("sample_records") or []
        if sample_embeddings.ndim != 2 or sample_embeddings.shape[0] == 0 or len(sample_records) != sample_embeddings.shape[0]:
            raise TextStyleAdapterError(
                "ADAPTER_CHECKPOINT_INVALID",
                "Trained adapter checkpoint is missing sample embeddings for nearest-neighbor lookup",
                {"checkpoint_path": checkpoint_path},
            )
        bundle = {
            "payload": payload,
            "model": model,
            "sample_embeddings": sample_embeddings,
            "sample_records": sample_records,
        }
        self._trained_runtime_cache = {cache_key: bundle}
        return bundle

    def _nearest_sample(self, bundle: dict[str, Any], embedding: np.ndarray) -> tuple[dict[str, Any], float]:
        sample_embeddings = np.asarray(bundle["sample_embeddings"], dtype=np.float32)
        prompt_norm = np.linalg.norm(embedding) or 1.0
        sample_norms = np.linalg.norm(sample_embeddings, axis=1)
        safe_sample_norms = np.where(sample_norms == 0.0, 1.0, sample_norms)
        cosine_scores = np.dot(sample_embeddings, embedding) / (safe_sample_norms * prompt_norm)
        best_index = int(np.argmax(cosine_scores))
        return dict(bundle["sample_records"][best_index]), float(cosine_scores[best_index])


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _has_any(keywords: list[str], candidates: set[str]) -> bool:
    return any(keyword in candidates for keyword in keywords)


def normalize_requested_adapter_mode(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = REQUESTED_ADAPTER_MODE_ALIASES.get(str(value).strip().lower())
    if normalized is None:
        raise TextStyleAdapterError(
            "ADAPTER_MODE_INVALID",
            "Unsupported requested adapter mode",
            {"requested_adapter_mode": value},
        )
    return normalized


def _clamp01(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


text_style_adapter = TextStyleAdapter()
