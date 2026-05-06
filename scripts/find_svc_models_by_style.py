#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = PROJECT_ROOT / "backend"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "runtime" / "model_search_v1_1"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from app.services import style_library, svc_model_presets  # noqa: E402


TARGET_PRESETS = {
    "final_male_youth": ["male", "youth", "bright"],
    "final_male_powerful": ["male", "powerful", "rock", "thick"],
    "final_female_soft": ["female", "soft", "breathy"],
    "final_female_clear": ["female", "clear", "bright", "pop"],
}

SEARCH_KEYWORDS = [
    "so-vits-svc 4.1 G_ config.json male",
    "so-vits-svc 4.1 G_ config.json female",
    "so-vits-svc 4.1 singer config.json",
    "so-vits-svc 4.0 G_*.pth config.json",
    "so-vits-svc model config.json speaker",
    "so-vits-svc 4.1 vec768l12",
    "so-vits-svc 4.1 男声 模型 config.json",
    "so-vits-svc 4.1 女声 模型 config.json",
    "so-vits-svc 歌声 模型 G_ config",
]

CURATED_REMOTE_CANDIDATES: list[dict[str, Any]] = [
    {
        "preset_target": "final_primary",
        "source_platform": "huggingface",
        "source_repo": "SuCicada/Lain-so-vits-svc-4.1",
        "source_url": "https://huggingface.co/SuCicada/Lain-so-vits-svc-4.1",
        "files_found": ["G_2400_infer.pth", "config.json", "diffusion/model_12000.pt", "kmeans_10000.pt"],
        "possible_weight_files": ["G_2400_infer.pth"],
        "possible_config_files": ["config.json"],
        "speaker_candidates": ["lain"],
        "speech_encoder": "vec768l12",
        "sampling_rate": 44100,
        "license": "gpl",
        "license_risk": "medium",
        "style_tags": ["baseline", "female", "clear"],
        "style_match_score": 0.58,
        "notes": "Current default baseline; usable but not a universal style model.",
    },
    {
        "preset_target": "final_male_powerful",
        "source_platform": "huggingface",
        "source_repo": "andreyaniv/andre-yaniv-so-vits-svc",
        "source_url": "https://huggingface.co/andreyaniv/andre-yaniv-so-vits-svc",
        "files_found": ["G_15000.pth", "config.json", "README.md"],
        "possible_weight_files": ["G_15000.pth"],
        "possible_config_files": ["config.json"],
        "speaker_candidates": ["AY"],
        "speech_encoder": "vec256l9",
        "sampling_rate": 44100,
        "license": "license_unknown",
        "license_risk": "medium",
        "style_tags": ["male", "powerful"],
        "style_match_score": 0.82,
        "notes": "Already smoke-tested locally in this workspace; license remains unclear.",
    },
    {
        "preset_target": "final_male_youth",
        "source_platform": "huggingface",
        "source_repo": "Kuugo/Nova-Adult_So-Vits-SVC",
        "source_url": "https://huggingface.co/Kuugo/Nova-Adult_So-Vits-SVC",
        "files_found": ["G_10000.pth", "config.json", "diffusion/model_10000.pt", "kmeans_10000.pt"],
        "possible_weight_files": ["G_10000.pth"],
        "possible_config_files": ["config.json"],
        "speaker_candidates": ["Nova_Adult"],
        "speech_encoder": "vec768l12",
        "sampling_rate": 44100,
        "license": "license_unknown",
        "license_risk": "medium",
        "style_tags": ["male", "youth", "bright"],
        "style_match_score": 0.78,
        "notes": "Best structural match for male_youth; requires download approval, license review, and smoke test.",
    },
    {
        "preset_target": "final_female_soft",
        "source_platform": "huggingface",
        "source_repo": "chjn/so-vits-svc4.1-CopanoRickey",
        "source_url": "https://huggingface.co/chjn/so-vits-svc4.1-CopanoRickey",
        "files_found": ["CopanoRickey/CopanoRickey.pth", "CopanoRickey/config.json", "README.md"],
        "possible_weight_files": ["CopanoRickey/CopanoRickey.pth"],
        "possible_config_files": ["CopanoRickey/config.json"],
        "speaker_candidates": ["CopanoRickey"],
        "speech_encoder": "vec768l12",
        "sampling_rate": 44100,
        "license": "cc-by-nc-4.0",
        "license_risk": "high",
        "style_tags": ["female", "soft"],
        "style_match_score": 0.7,
        "notes": "Technically compatible but based on game character audio; avoid public demo unless license is acceptable.",
    },
    {
        "preset_target": "final_female_clear",
        "source_platform": "huggingface",
        "source_repo": "Sucial/so-vits-svc4.1-sanwu",
        "source_url": "https://huggingface.co/Sucial/so-vits-svc4.1-sanwu",
        "files_found": ["sanwu_100800.pth", "config.json", "README.md"],
        "possible_weight_files": ["sanwu_100800.pth"],
        "possible_config_files": ["config.json"],
        "speaker_candidates": ["sanwu"],
        "speech_encoder": "vec768l12",
        "sampling_rate": 44100,
        "license": "cc-by-sa-4.0",
        "license_risk": "high",
        "style_tags": ["female", "clear", "bright"],
        "style_match_score": 0.74,
        "notes": "Technically promising but likely real-person/known-singer style risk; not recommended for default demo.",
    },
    {
        "preset_target": "final_female_clear",
        "source_platform": "huggingface",
        "source_repo": "Shinku0721/Shinku_Yuuki_so-vits-svc_4.1_model",
        "source_url": "https://huggingface.co/Shinku0721/Shinku_Yuuki_so-vits-svc_4.1_model",
        "files_found": ["G_200000.pth", "config.json", "diffusion/model_50000.pt"],
        "possible_weight_files": ["G_200000.pth"],
        "possible_config_files": ["config.json"],
        "speaker_candidates": ["shinku", "yuuki"],
        "speech_encoder": "vec768l12",
        "sampling_rate": 44100,
        "license": "cc-by-nc-sa-4.0",
        "license_risk": "high",
        "style_tags": ["female", "clear", "ja"],
        "style_match_score": 0.66,
        "notes": "Technically compatible; non-commercial and attribution/share-alike constraints.",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search and screen So-VITS-SVC model candidates without downloading large assets.")
    parser.add_argument("--style", default="", help="Style prompt or tag, used to show the preferred preset match.")
    parser.add_argument("--search-root", action="append", default=[], help="Optional local directory to scan for config.json + G_*.pth candidates.")
    parser.add_argument("--include-remote-candidates", action="store_true", help="Print the curated remote candidate shortlist.")
    parser.add_argument("--write-report", action="store_true", help="Write candidates_raw.json, candidates_filtered.json and candidates.md.")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--offline", action="store_true", help="Do not call the Hugging Face API; use curated/search-session candidates only.")
    return parser.parse_args()


def find_local_candidates(search_roots: list[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for raw_root in search_roots:
        root = Path(raw_root).expanduser()
        if not root.exists():
            continue
        for config_path in root.rglob("config.json"):
            model_candidates = sorted(config_path.parent.glob("G_*.pth")) + sorted(config_path.parent.glob("model*.pth"))
            if not model_candidates:
                continue
            candidates.append(
                {
                    "preset_target": "manual_review",
                    "source_platform": "local",
                    "source_repo": str(config_path.parent),
                    "source_url": "",
                    "files_found": [path.name for path in model_candidates] + ["config.json"],
                    "possible_weight_files": [path.name for path in model_candidates],
                    "possible_config_files": ["config.json"],
                    "speaker_candidates": _extract_speakers(config_path),
                    "speech_encoder": _extract_config_value(config_path, ["model", "speech_encoder"]),
                    "sampling_rate": _extract_config_value(config_path, ["data", "sampling_rate"]),
                    "license": "local_unknown",
                    "license_risk": "medium",
                    "style_tags": [],
                    "style_match_score": 0.0,
                    "notes": "Local candidate; verify license and smoke test before binding.",
                }
            )
    return candidates


def hydrate_remote_candidates(candidates: list[dict[str, Any]], offline: bool) -> list[dict[str, Any]]:
    if offline:
        return candidates
    hydrated: list[dict[str, Any]] = []
    for item in candidates:
        repo_id = str(item.get("source_repo") or "")
        if item.get("source_platform") != "huggingface" or not repo_id:
            hydrated.append(item)
            continue
        try:
            payload = _fetch_json(f"https://huggingface.co/api/models/{repo_id}")
            files = [entry.get("rfilename") for entry in payload.get("siblings", []) if entry.get("rfilename")]
            item = {
                **item,
                "files_found": files or item.get("files_found", []),
                "license": payload.get("cardData", {}).get("license") or item.get("license") or "license_unknown",
                "downloads": payload.get("downloads"),
                "likes": payload.get("likes"),
                "last_modified": payload.get("lastModified"),
            }
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            item = {**item, "api_error": str(exc)}
        hydrated.append(item)
    return hydrated


def screen_candidate(item: dict[str, Any]) -> dict[str, Any]:
    files = [str(path) for path in item.get("files_found", [])]
    weights = [path for path in files if Path(path).name.startswith("G_") and path.endswith(".pth")]
    if not weights:
        weights = [path for path in files if Path(path).name.startswith("model") and path.endswith(".pth")]
    configs = [path for path in files if Path(path).name == "config.json"]
    license_name = str(item.get("license") or "license_unknown").lower()
    source_repo = str(item.get("source_repo") or "").lower()
    has_weight = bool(weights or item.get("possible_weight_files"))
    has_config = bool(configs or item.get("possible_config_files"))
    has_speaker = bool(item.get("speaker_candidates"))
    incompatible_name = any(token in source_repo for token in ("rvc", "gpt-sovits", "ddsp", "tts"))
    high_risk = item.get("license_risk") == "high" or any(token in source_repo for token in ("tim_cook", "juice", "abe", "suga"))
    compatible = has_weight and has_config and has_speaker and not incompatible_name
    score = 0
    score += 30 if has_weight else 0
    score += 25 if has_config else 0
    score += 15 if has_speaker else 0
    score += 15 if item.get("speech_encoder") == "vec768l12" else 5 if item.get("speech_encoder") else 0
    score += 10 if license_name not in {"", "unknown", "license_unknown"} else 0
    score += int(float(item.get("style_match_score") or 0) * 10)
    exclusion_reason = ""
    if incompatible_name:
        exclusion_reason = "incompatible model family"
    elif not has_weight:
        exclusion_reason = "missing G_*.pth/model*.pth"
    elif not has_config:
        exclusion_reason = "missing config.json"
    elif not has_speaker:
        exclusion_reason = "config speaker not parsed"
    elif high_risk:
        exclusion_reason = "license or source risk too high for default public demo"
    recommended_action = "reject" if exclusion_reason else "download_after_license_review_and_smoke_test"
    if item.get("source_repo") == "andreyaniv/andre-yaniv-so-vits-svc":
        recommended_action = "keep_configured_but_not_demo_quality_until_license_review"
    return {
        **item,
        "has_model_weight": has_weight,
        "has_config_json": has_config,
        "possible_weight_files": item.get("possible_weight_files") or weights,
        "possible_config_files": item.get("possible_config_files") or configs,
        "compatibility_score": min(score, 100),
        "exclusion_reason": exclusion_reason,
        "recommended_action": recommended_action,
        "is_filtered_in": bool(compatible and not high_risk),
    }


def write_reports(report_dir: Path, raw: list[dict[str, Any]], screened: list[dict[str, Any]]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    filtered = [item for item in screened if item.get("is_filtered_in")]
    (report_dir / "candidates_raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (report_dir / "candidates_filtered.json").write_text(json.dumps(filtered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# So-VITS-SVC Model Search v1.1",
        "",
        f"- generated_at: {datetime.now(timezone.utc).isoformat()}",
        f"- searched_keywords: {', '.join(SEARCH_KEYWORDS)}",
        f"- raw_candidates: {len(raw)}",
        f"- filtered_candidates: {len(filtered)}",
        "",
        "| preset_target | source_repo | files | speaker | encoder | license | score | action | exclusion |",
        "| --- | --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for item in screened:
        files = ", ".join(str(path) for path in item.get("possible_weight_files", [])[:3])
        speakers = ", ".join(str(s) for s in item.get("speaker_candidates", []))
        lines.append(
            f"| `{item.get('preset_target')}` | `{item.get('source_repo')}` | {files} | {speakers} | "
            f"{item.get('speech_encoder') or ''} | {item.get('license') or ''} | {item.get('compatibility_score')} | "
            f"{item.get('recommended_action')} | {item.get('exclusion_reason') or ''} |"
        )
    (report_dir / "candidates.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "BS-model-audit/1.1"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_speakers(config_path: Path) -> list[str]:
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        return [str(key) for key in dict(payload.get("spk") or {}).keys()]
    except Exception:
        return []


def _extract_config_value(config_path: Path, keys: list[str]) -> Any:
    try:
        value: Any = json.loads(config_path.read_text(encoding="utf-8"))
        for key in keys:
            value = value[key]
        return value
    except Exception:
        return None


def main() -> int:
    args = parse_args()
    matched_style = style_library.retrieve_style(args.style or "默认")
    presets_status = svc_model_presets.collect_presets_status()
    raw = CURATED_REMOTE_CANDIDATES + find_local_candidates(args.search_root)
    raw = hydrate_remote_candidates(raw, offline=args.offline)
    screened = [screen_candidate(item) for item in raw]

    print("Preferred style match:")
    print(json.dumps(
        {
            "prompt": args.style,
            "style_id": matched_style.get("style_id"),
            "style_label": matched_style.get("style_label"),
            "model_preset_id": matched_style.get("model_preset_id"),
            "model_preset_ready": matched_style.get("model_preset_ready"),
            "model_preset_notice": matched_style.get("model_preset_notice"),
        },
        ensure_ascii=False,
        indent=2,
    ))
    print()
    print("Preset status:")
    print(json.dumps(presets_status, ensure_ascii=False, indent=2))
    if args.include_remote_candidates:
        print()
        print("Screened remote/local candidates:")
        print(json.dumps(screened, ensure_ascii=False, indent=2))
    if args.write_report:
        write_reports(Path(args.report_dir), raw, screened)
        print()
        print(f"Wrote report files to {args.report_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
