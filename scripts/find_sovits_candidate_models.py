#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models_svc.sovits_assets import extract_speaker_list, summarize_sovits_config  # noqa: E402

try:
    from huggingface_hub import HfApi, hf_hub_download
except Exception as exc:  # pragma: no cover - exercised on machines missing the optional CLI package
    HfApi = None  # type: ignore[assignment]
    hf_hub_download = None  # type: ignore[assignment]
    HF_IMPORT_ERROR = exc
else:
    HF_IMPORT_ERROR = None


SEARCH_KEYWORDS = [
    "so-vits-svc 4.1 G_ config.json singer",
    "so-vits-svc Chinese singing G_ config.json",
    "so-vits-svc male singing config.json",
    "so-vits-svc female singing config.json",
    "so-vits-svc 4.0 4.1 vec768l12 config",
    "so-vits-svc 4.1",
    "so-vits-svc 4.0",
    "so-vits-svc singer",
]
SEED_REPOS = [
    "Sucial/so-vits-svc4.1-sanwu",
    "SuCicada/Lain-so-vits-svc-4.1",
    "chjn/so-vits-svc4.1-Satono-Diamond",
    "chjn/so-vits-svc4.1-TamamoCross",
    "None1145/So-VITS-SVC-Lappland-the-Decadenza",
    "None1145/So-VITS-SVC-Lappland",
    "None1145/So-VITS-SVC-Rosmontis",
    "superbobneko/pjsk-so-vits-svc4.1",
]
SUPPORTED_ENCODERS = {"vec768l12", "vec256l9", "hubertsoft", "cnhubertlarge"}
REJECT_NAME_PATTERNS = (
    "rvc",
    "ddsp",
    "diff-svc",
    "diffsvc",
    "diffusion-svc",
    "tts",
    "gpt-sovits",
    "gpt_sovits",
)
NON_DEMO_NAME_PATTERNS = ("no_singer", "minecraft", "villager", "fart", "barking", "tim_cook")
MODEL_FILE_RE = re.compile(r"(^|/)G_[^/]*\.pth$|(^|/)model[^/]*\.pth$", re.IGNORECASE)
CONFIG_FILE_RE = re.compile(r"(^|/)config\.json$", re.IGNORECASE)


@dataclass
class Candidate:
    repo_id: str
    url: str
    license: str = ""
    tags: list[str] = field(default_factory=list)
    model_file: str = ""
    config_file: str = ""
    readme_file: str = ""
    speaker_candidates: list[str] = field(default_factory=list)
    sampling_rate: int | None = None
    speech_encoder: str | None = None
    n_speakers: int | None = None
    compatibility_score: int = 0
    license_score: int = 0
    style_match_score: int = 0
    final_score: int = 0
    rejection_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_id": self.repo_id,
            "url": self.url,
            "license": self.license,
            "tags": self.tags,
            "model_file": self.model_file,
            "config_file": self.config_file,
            "readme_file": self.readme_file,
            "speaker_candidates": self.speaker_candidates,
            "sampling_rate": self.sampling_rate,
            "speech_encoder": self.speech_encoder,
            "n_speakers": self.n_speakers,
            "compatibility_score": self.compatibility_score,
            "license_score": self.license_score,
            "style_match_score": self.style_match_score,
            "final_score": self.final_score,
            "rejection_reason": self.rejection_reason,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Find public So-VITS-SVC 4.x candidate models.")
    parser.add_argument("--limit-per-query", type=int, default=25)
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "runtime" / "model_search"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if HfApi is None:
        payload = {
            "generated_at": _now(),
            "search_keywords": SEARCH_KEYWORDS,
            "candidates": [],
            "error": f"huggingface_hub import failed: {HF_IMPORT_ERROR}",
        }
        _write_outputs(output_dir, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    api = HfApi()
    repo_ids = _discover_repo_ids(api, args.limit_per_query)
    candidates = [_evaluate_repo(api, repo_id) for repo_id in repo_ids]
    candidates.sort(key=lambda item: item.final_score, reverse=True)
    payload = {
        "generated_at": _now(),
        "search_keywords": SEARCH_KEYWORDS,
        "supported_speech_encoders": sorted(SUPPORTED_ENCODERS),
        "candidates": [candidate.to_dict() for candidate in candidates],
    }
    _write_outputs(output_dir, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if any(not candidate.rejection_reason for candidate in candidates) else 1


def _discover_repo_ids(api: Any, limit_per_query: int) -> list[str]:
    discovered: list[str] = []
    for repo_id in SEED_REPOS:
        _append_unique(discovered, repo_id)
    for keyword in SEARCH_KEYWORDS:
        try:
            models = api.list_models(search=keyword, limit=limit_per_query, sort="downloads", direction=-1)
            for model in models:
                _append_unique(discovered, model.modelId)
        except Exception as exc:
            print(f"[warn] search failed for {keyword!r}: {exc}", file=sys.stderr)
    return discovered


def _evaluate_repo(api: Any, repo_id: str) -> Candidate:
    candidate = Candidate(repo_id=repo_id, url=f"https://huggingface.co/{repo_id}")
    lower_repo = repo_id.lower()
    if any(pattern in lower_repo for pattern in REJECT_NAME_PATTERNS):
        candidate.rejection_reason = "repo name looks like RVC/DDSP/Diff-SVC/TTS/GPT-SoVITS"
        return candidate
    if any(pattern in lower_repo for pattern in NON_DEMO_NAME_PATTERNS):
        candidate.rejection_reason = "repo is a technical/novelty voice, not a final graduation-demo singing model"
        return candidate

    try:
        info = api.model_info(repo_id, files_metadata=True)
    except Exception as exc:
        candidate.rejection_reason = f"model_info failed: {exc}"
        return candidate

    candidate.tags = list(getattr(info, "tags", []) or [])
    candidate.license = _extract_license(info)
    files = [sibling.rfilename for sibling in getattr(info, "siblings", []) or []]
    candidate.model_file = _select_model_file(files)
    candidate.config_file = _select_config_file(files)
    candidate.readme_file = _select_readme_file(files)
    if not candidate.config_file:
        candidate.rejection_reason = "missing config.json"
    elif not candidate.model_file:
        candidate.rejection_reason = "missing G_*.pth or model*.pth"

    config_payload = _download_config(repo_id, candidate.config_file) if candidate.config_file else None
    if config_payload:
        summary = summarize_sovits_config(config_payload)
        model_section = config_payload.get("model") if isinstance(config_payload.get("model"), dict) else {}
        candidate.speaker_candidates = extract_speaker_list(config_payload)
        candidate.sampling_rate = summary.get("sampling_rate")
        candidate.speech_encoder = summary.get("speech_encoder")
        candidate.n_speakers = int(model_section.get("n_speakers", len(candidate.speaker_candidates)) or 0)

    if not candidate.rejection_reason:
        candidate.rejection_reason = _compatibility_rejection(candidate)
    candidate.compatibility_score = _score_compatibility(candidate)
    candidate.license_score = _score_license(candidate)
    candidate.style_match_score = _score_style(candidate)
    candidate.final_score = candidate.compatibility_score + candidate.license_score + candidate.style_match_score
    if candidate.rejection_reason:
        candidate.final_score -= 1000
    return candidate


def _download_config(repo_id: str, config_file: str) -> dict[str, Any] | None:
    try:
        path = hf_hub_download(repo_id=repo_id, filename=config_file, repo_type="model")
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else None
    except Exception as exc:
        print(f"[warn] config download failed for {repo_id}/{config_file}: {exc}", file=sys.stderr)
        return None


def _extract_license(info: Any) -> str:
    card_data = getattr(info, "cardData", None)
    if isinstance(card_data, dict):
        return str(card_data.get("license") or "")
    if card_data is not None and getattr(card_data, "license", None):
        return str(card_data.license)
    for tag in getattr(info, "tags", []) or []:
        if str(tag).startswith("license:"):
            return str(tag).split(":", 1)[1]
    return ""


def _select_model_file(files: list[str]) -> str:
    matched = [path for path in files if MODEL_FILE_RE.search(path)]
    if not matched:
        return ""
    g_files = [path for path in matched if Path(path).name.lower().startswith("g_")]
    return sorted(g_files or matched, key=lambda path: (path.count("/"), path.lower()))[-1]


def _select_config_file(files: list[str]) -> str:
    matched = [path for path in files if CONFIG_FILE_RE.search(path)]
    return sorted(matched, key=lambda path: (path.count("/"), path.lower()))[0] if matched else ""


def _select_readme_file(files: list[str]) -> str:
    for name in ("README.md", "readme.md", "model_card.md", "MODEL_CARD.md"):
        if name in files:
            return name
    return ""


def _compatibility_rejection(candidate: Candidate) -> str:
    if not candidate.speaker_candidates:
        return "config has no speaker list"
    if candidate.speech_encoder not in SUPPORTED_ENCODERS:
        return f"unsupported speech_encoder={candidate.speech_encoder}"
    if candidate.n_speakers and candidate.n_speakers != len(candidate.speaker_candidates):
        return "n_speakers does not match speaker list"
    if not candidate.license:
        return "license missing"
    tags_blob = " ".join(candidate.tags).lower()
    if any(pattern in tags_blob for pattern in REJECT_NAME_PATTERNS):
        return "tags indicate incompatible model family"
    return ""


def _score_compatibility(candidate: Candidate) -> int:
    score = 0
    if candidate.model_file:
        score += 30
    if candidate.config_file:
        score += 25
    if candidate.speech_encoder in SUPPORTED_ENCODERS:
        score += 25
    if candidate.sampling_rate in {44100, 44000, 48000}:
        score += 10
    if "4.1" in candidate.repo_id or "4.1" in " ".join(candidate.tags):
        score += 15
    elif "4.0" in candidate.repo_id or "4.0" in " ".join(candidate.tags):
        score += 10
    return score


def _score_license(candidate: Candidate) -> int:
    license_name = candidate.license.lower()
    if not license_name:
        return 0
    if any(part in license_name for part in ("mit", "apache", "cc-by", "cc-by-sa", "cc-by-nc")):
        return 25
    if "gpl" in license_name:
        return 18
    return 10


def _score_style(candidate: Candidate) -> int:
    blob = " ".join([candidate.repo_id, *candidate.tags, *candidate.speaker_candidates]).lower()
    score = 0
    for token in ("zh", "chinese", "中文", "singing", "singer", "song", "svc", "audio-to-audio"):
        if token in blob:
            score += 8
    for token in ("female", "girl", "清亮", "sanwu", "lain", "lappland", "rosmontis"):
        if token in blob:
            score += 5
    for token in ("male", "boy", "男声", "少年", "thick", "deep"):
        if token in blob:
            score += 5
    return score


def _write_outputs(output_dir: Path, payload: dict[str, Any]) -> None:
    json_path = output_dir / "candidates.json"
    md_path = output_dir / "candidates.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# So-VITS-SVC Candidate Report",
        "",
        f"Generated: {payload.get('generated_at', '')}",
        "",
        "| rank | repo | model | config | speaker | encoder | license | score | rejection |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for index, candidate in enumerate(payload.get("candidates", []), 1):
        lines.append(
            "| {rank} | [{repo}]({url}) | {model} | {config} | {speaker} | {encoder} | {license} | {score} | {reject} |".format(
                rank=index,
                repo=candidate.get("repo_id", ""),
                url=candidate.get("url", ""),
                model=candidate.get("model_file", ""),
                config=candidate.get("config_file", ""),
                speaker=", ".join(candidate.get("speaker_candidates") or []),
                encoder=candidate.get("speech_encoder", ""),
                license=candidate.get("license", ""),
                score=candidate.get("final_score", 0),
                reject=candidate.get("rejection_reason", ""),
            )
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
