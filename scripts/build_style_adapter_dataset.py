#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "style_adapter_pairs" / "metadata.jsonl"
DEFAULT_REPORT_OUTPUT = PROJECT_ROOT / "runtime" / "eval_reports" / "dataset_build_report.json"
DEFAULT_SEARCH_REPORT_OUTPUT = PROJECT_ROOT / "runtime" / "eval_reports" / "dataset_search_report.json"
DEFAULT_PROMPT_MAPPING = PROJECT_ROOT / "config" / "style_prompt_mapping.json"
DEFAULT_GTSINGER_HF_REPO = "AaronZ345/GTSinger"
DEFAULT_GTSINGER_HF_FILE = "processed/All/metadata.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build unified style-adapter metadata from public singing datasets.")
    parser.add_argument("--dataset", choices=("gtsinger", "opencpop", "auto"), default="auto")
    parser.add_argument("--input-root", type=Path, help="Dataset local root (optional)")
    parser.add_argument("--metadata-source", type=Path, help="Source metadata file path (json/jsonl/csv/parquet)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-items", type=int, default=0, help="Maximum output rows (0 means no hard cap)")
    parser.add_argument("--max-hours", type=float, default=0.0, help="Maximum cumulative hours (0 means no cap)")
    parser.add_argument("--min-duration", type=float, default=0.0, help="Minimum duration in seconds")
    parser.add_argument("--max-duration", type=float, default=0.0, help="Maximum duration in seconds (0 means no cap)")
    parser.add_argument("--languages", default="", help="Comma-separated language filters")
    parser.add_argument("--singers", default="", help="Comma-separated singer filters")
    parser.add_argument("--style-labels", default="", help="Comma-separated style-label filters")
    parser.add_argument("--split", default="train,val,test", help="Output split names, e.g. train,val,test")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--search-report-output", type=Path, default=DEFAULT_SEARCH_REPORT_OUTPUT)
    parser.add_argument("--prompt-mapping", type=Path, default=DEFAULT_PROMPT_MAPPING)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started_at = utc_now()
    prompt_mapping = load_prompt_mapping(args.prompt_mapping)
    warnings: list[str] = []

    dataset_name = normalize_dataset_name(args.dataset, args.metadata_source)
    if dataset_name not in {"gtsinger", "opencpop"}:
        raise SystemExit(f"[dataset-build] unsupported dataset: {dataset_name}")

    metadata_source, source_resolution = resolve_metadata_source(
        dataset_name=dataset_name,
        metadata_source=args.metadata_source,
        input_root=args.input_root,
    )
    warnings.extend(source_resolution.get("warnings", []))

    if metadata_source is None or not metadata_source.exists():
        report = {
            "status": "failed",
            "dataset": dataset_name,
            "reason": "metadata_source_not_found",
            "metadata_source": str(metadata_source) if metadata_source else None,
            "source_resolution": source_resolution,
            "started_at": started_at,
            "finished_at": utc_now(),
            "warnings": sorted(set(warnings)),
        }
        write_json(args.report_output, report)
        write_markdown(args.report_output.with_suffix(".md"), render_failed_build_report_md(report))
        search_report = build_dataset_search_report(
            dataset_name=dataset_name,
            metadata_source=metadata_source,
            source_resolution=source_resolution,
            rows_total=0,
            rows_selected=0,
            estimated_hours=0.0,
            audio_available=False,
            warnings=warnings,
        )
        write_json(args.search_report_output, search_report)
        write_markdown(args.search_report_output.with_suffix(".md"), render_dataset_search_report_md(search_report))
        print("[dataset-build] metadata source not found. Reports were written with failure details.")
        return 0

    raw_rows = load_rows_by_dataset(dataset_name=dataset_name, metadata_source=metadata_source)
    built_rows, build_stats = build_unified_rows(
        dataset_name=dataset_name,
        rows=raw_rows,
        args=args,
        prompt_mapping=prompt_mapping,
        metadata_source=metadata_source,
    )
    assign_splits(built_rows, parse_csv_list(args.split) or ["train", "val", "test"], args.seed)

    if args.max_items > 0:
        built_rows = built_rows[: args.max_items]

    output_rows = built_rows
    if not args.dry_run:
        write_jsonl(args.output, output_rows)
    else:
        # dry-run still writes lightweight output so downstream scripts can validate schema.
        write_jsonl(args.output, output_rows)

    sample_rows = output_rows[: min(len(output_rows), 5)]
    counters = summarize_rows(output_rows)
    finished_at = utc_now()
    audio_available = counters["audio_available_count"] > 0

    build_report = {
        "status": "ok" if output_rows else "no_rows_after_filter",
        "dry_run": bool(args.dry_run),
        "dataset": dataset_name,
        "metadata_source": str(metadata_source),
        "output_path": str(args.output),
        "report_output": str(args.report_output),
        "started_at": started_at,
        "finished_at": finished_at,
        "total_seconds": seconds_between(started_at, finished_at),
        "rows_total_raw": len(raw_rows),
        "rows_selected": len(output_rows),
        "audio_available": audio_available,
        "audio_available_count": counters["audio_available_count"],
        "paired_training": False,
        "filters": {
            "max_items": args.max_items,
            "max_hours": args.max_hours,
            "min_duration": args.min_duration,
            "max_duration": args.max_duration,
            "languages": parse_csv_list(args.languages),
            "singers": parse_csv_list(args.singers),
            "style_labels": parse_csv_list(args.style_labels),
        },
        "split_counts": counters["split_counts"],
        "style_label_counts_top20": counters["style_label_counts_top20"],
        "singer_counts_top20": counters["singer_counts_top20"],
        "language_counts": counters["language_counts"],
        "duration_seconds_total": counters["duration_seconds_total"],
        "duration_seconds_mean": counters["duration_seconds_mean"],
        "estimated_hours": counters["estimated_hours"],
        "source_resolution": source_resolution,
        "build_stats": build_stats,
        "warnings": sorted(set(warnings + build_stats.get("warnings", []))),
        "sample_rows": sample_rows,
        "notes": [
            "This stage only builds metadata. It does not download full audio assets.",
            "If audio_available=false, this metadata is suitable for schema validation/dry-run only.",
            "paired_training=false means weak supervision or pseudo-paired setup; do not overclaim strong style transfer evidence.",
        ],
    }

    write_json(args.report_output, build_report)
    write_markdown(args.report_output.with_suffix(".md"), render_dataset_build_report_md(build_report))

    search_report = build_dataset_search_report(
        dataset_name=dataset_name,
        metadata_source=metadata_source,
        source_resolution=source_resolution,
        rows_total=len(raw_rows),
        rows_selected=len(output_rows),
        estimated_hours=counters["estimated_hours"],
        audio_available=audio_available,
        warnings=warnings + build_stats.get("warnings", []),
    )
    write_json(args.search_report_output, search_report)
    write_markdown(args.search_report_output.with_suffix(".md"), render_dataset_search_report_md(search_report))

    print(f"[dataset-build] dataset={dataset_name} rows={len(output_rows)} output={args.output}")
    print(f"[dataset-build] reports: {args.report_output} and {args.search_report_output}")
    return 0


def normalize_dataset_name(dataset_arg: str, metadata_source: Path | None) -> str:
    if dataset_arg != "auto":
        return dataset_arg
    if metadata_source:
        lowered = str(metadata_source).lower()
        if "gtsinger" in lowered:
            return "gtsinger"
        if "opencpop" in lowered:
            return "opencpop"
    return "gtsinger"


def resolve_metadata_source(
    *,
    dataset_name: str,
    metadata_source: Path | None,
    input_root: Path | None,
) -> tuple[Path | None, dict[str, Any]]:
    details: dict[str, Any] = {
        "dataset_name": dataset_name,
        "requested_metadata_source": str(metadata_source) if metadata_source else None,
        "input_root": str(input_root) if input_root else None,
        "resolved_by": None,
        "warnings": [],
    }
    if metadata_source:
        candidate = to_abs_no_resolve(metadata_source.expanduser())
        if candidate.exists():
            details["resolved_by"] = "metadata_source_argument"
            return candidate, details
        details["warnings"].append("metadata_source_argument_missing")

    if input_root:
        root = input_root.expanduser()
        candidates = []
        if root.is_file():
            candidates.append(root)
        else:
            if dataset_name == "gtsinger":
                candidates.append(root / "processed" / "All" / "metadata.json")
            elif dataset_name == "opencpop":
                candidates.extend(
                    [
                        root / "metadata.json",
                        root / "metadata.jsonl",
                        root / "train.csv",
                        root / "train.parquet",
                    ]
                )
        for candidate in candidates:
            if candidate.exists():
                details["resolved_by"] = "input_root_scan"
                return to_abs_no_resolve(candidate), details

    if dataset_name == "gtsinger":
        downloaded = try_hf_single_file_download(DEFAULT_GTSINGER_HF_REPO, DEFAULT_GTSINGER_HF_FILE)
        if downloaded and downloaded.exists():
            details["resolved_by"] = "hf_cli_single_file_download"
            details["hf_repo"] = DEFAULT_GTSINGER_HF_REPO
            details["hf_file"] = DEFAULT_GTSINGER_HF_FILE
            return downloaded, details
        if downloaded is None:
            details["warnings"].append("hf_cli_single_file_download_failed")

    return None, details


def try_hf_single_file_download(repo_id: str, filename: str) -> Path | None:
    cmd = [
        "hf",
        "download",
        repo_id,
        filename,
        "--repo-type",
        "dataset",
        "--quiet",
    ]
    try:
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    output = (completed.stdout or "").strip()
    if not output:
        return None
    path = Path(output)
    if path.exists():
        return to_abs_no_resolve(path)
    return None


def load_rows_by_dataset(dataset_name: str, metadata_source: Path) -> list[dict[str, Any]]:
    if dataset_name == "gtsinger":
        payload = json.loads(metadata_source.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise SystemExit("[dataset-build] GTSinger metadata must be a JSON list.")
        return [row for row in payload if isinstance(row, dict)]
    if dataset_name == "opencpop":
        return load_generic_rows(metadata_source)
    raise SystemExit(f"[dataset-build] unsupported dataset loader: {dataset_name}")


def load_generic_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            for key in ("data", "rows", "items", "samples"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [row for row in value if isinstance(row, dict)]
        raise SystemExit("[dataset-build] JSON metadata source must contain a list-like payload.")
    if suffix == ".jsonl":
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
        return rows
    if suffix == ".csv":
        with path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return [dict(row) for row in reader]
    if suffix == ".parquet":
        try:
            import pandas as pd  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise SystemExit(f"[dataset-build] reading parquet requires pandas/pyarrow: {exc}") from exc
        frame = pd.read_parquet(path)
        return frame.to_dict(orient="records")
    raise SystemExit(f"[dataset-build] unsupported metadata-source suffix: {suffix}")


def build_unified_rows(
    *,
    dataset_name: str,
    rows: list[dict[str, Any]],
    args: argparse.Namespace,
    prompt_mapping: dict[str, Any],
    metadata_source: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    languages_filter = {normalize_token(v) for v in parse_csv_list(args.languages)}
    singers_filter = {normalize_token(v) for v in parse_csv_list(args.singers)}
    style_filter = {normalize_token(v) for v in parse_csv_list(args.style_labels)}

    selected: list[dict[str, Any]] = []
    filtered = Counter()
    cumulative_seconds = 0.0
    warnings: list[str] = []
    metadata_root = infer_metadata_root(dataset_name=dataset_name, metadata_source=metadata_source)
    input_root = args.input_root.resolve() if args.input_root else None

    for idx, row in enumerate(rows, start=1):
        if dataset_name == "gtsinger":
            built = build_gtsinger_row(
                row=row,
                idx=idx,
                metadata_root=metadata_root,
                input_root=input_root,
                prompt_mapping=prompt_mapping,
            )
        else:
            built = build_generic_row(
                row=row,
                idx=idx,
                dataset_name=dataset_name,
                metadata_root=metadata_root,
                input_root=input_root,
                prompt_mapping=prompt_mapping,
            )

        if built is None:
            filtered["invalid_row"] += 1
            continue

        language_norm = normalize_token(built.get("language"))
        singer_norm = normalize_token(built.get("singer"))
        style_norm = normalize_token(built.get("style_label"))
        duration = float(built.get("duration_seconds", 0.0) or 0.0)

        if languages_filter and language_norm not in languages_filter and code_from_language(built.get("language")) not in languages_filter:
            filtered["language"] += 1
            continue
        if singers_filter and singer_norm not in singers_filter:
            filtered["singer"] += 1
            continue
        if style_filter and not any(token in style_norm for token in style_filter):
            filtered["style_label"] += 1
            continue
        if args.min_duration > 0 and duration < args.min_duration:
            filtered["min_duration"] += 1
            continue
        if args.max_duration > 0 and duration > args.max_duration:
            filtered["max_duration"] += 1
            continue
        if args.max_hours > 0 and (cumulative_seconds + duration) > args.max_hours * 3600.0:
            filtered["max_hours"] += 1
            continue

        selected.append(built)
        cumulative_seconds += duration

        if args.max_items > 0 and len(selected) >= args.max_items:
            break

    return selected, {
        "filtered_counts": dict(filtered),
        "warnings": warnings,
    }


def build_gtsinger_row(
    *,
    row: dict[str, Any],
    idx: int,
    metadata_root: Path,
    input_root: Path | None,
    prompt_mapping: dict[str, Any],
) -> dict[str, Any] | None:
    wav_rel = str(row.get("wav_fn") or "").strip()
    if not wav_rel:
        return None
    wav_path = resolve_audio_path(wav_rel=wav_rel, metadata_root=metadata_root, input_root=input_root)
    language = str(row.get("language") or "unknown").strip() or "unknown"
    singer = str(row.get("singer") or "unknown").strip() or "unknown"
    technique = infer_technique_from_wav_path(wav_rel)
    emotion = normalize_token(row.get("emotion"))
    pace = normalize_token(row.get("pace"))
    vocal_range = normalize_token(row.get("range"))
    singing_method = normalize_token(row.get("singing_method"))

    style_tokens = [technique, emotion, pace, vocal_range, singing_method]
    style_label = "_".join(token for token in style_tokens if token and token != "unknown")
    if not style_label:
        style_label = "unknown"

    prompt = compose_prompt(
        mapping=prompt_mapping,
        style_labels=[technique, style_label],
        emotion=emotion,
        pace=pace,
        vocal_range=vocal_range,
        singing_method=singing_method,
    )

    duration = estimate_duration_seconds(row)
    language_code = code_from_language(language)
    audio_exists = wav_path.exists()
    notes = "auto converted from GTSinger metadata; weakly-supervised pseudo-paired sample"
    if not audio_exists:
        notes += "; audio file not found locally"

    return {
        "sample_id": f"gtsinger_{idx:06d}",
        "dataset": "GTSinger",
        "input_audio_path": str(wav_path),
        "target_audio_path": str(wav_path),
        "style_prompt": prompt,
        "style_label": style_label,
        "singer": singer,
        "language": language_code,
        "technique": technique,
        "duration_seconds": round(duration, 6),
        "sample_rate": 48000,
        "split": "unspecified",
        "notes": notes,
    }


def build_generic_row(
    *,
    row: dict[str, Any],
    idx: int,
    dataset_name: str,
    metadata_root: Path,
    input_root: Path | None,
    prompt_mapping: dict[str, Any],
) -> dict[str, Any] | None:
    audio_rel = first_non_empty(row.get("wav_fn"), row.get("audio"), row.get("audio_path"), row.get("path"))
    if not audio_rel:
        return None
    audio_path = resolve_audio_path(wav_rel=audio_rel, metadata_root=metadata_root, input_root=input_root)
    language = first_non_empty(row.get("language"), row.get("lang"), "zh")
    singer = first_non_empty(row.get("singer"), row.get("speaker"), "unknown")
    style_label = normalize_token(first_non_empty(row.get("style_label"), row.get("technique"), row.get("label"), "unknown"))
    technique = normalize_token(first_non_empty(row.get("technique"), style_label, "unknown"))
    prompt = compose_prompt(
        mapping=prompt_mapping,
        style_labels=[style_label, technique],
        emotion=normalize_token(row.get("emotion")),
        pace=normalize_token(row.get("pace")),
        vocal_range=normalize_token(row.get("range")),
        singing_method=normalize_token(row.get("singing_method")),
    )
    duration = float(row.get("duration_seconds") or row.get("duration") or 0.0)
    if duration <= 0:
        duration = 0.0
    notes = "auto converted from generic metadata; weakly-supervised pseudo-paired sample"
    if not audio_path.exists():
        notes += "; audio file not found locally"
    return {
        "sample_id": f"{dataset_name}_{idx:06d}",
        "dataset": dataset_name.upper(),
        "input_audio_path": str(audio_path),
        "target_audio_path": str(audio_path),
        "style_prompt": prompt,
        "style_label": style_label or "unknown",
        "singer": singer,
        "language": code_from_language(language),
        "technique": technique or "unknown",
        "duration_seconds": round(duration, 6),
        "sample_rate": int(row.get("sample_rate") or 44100),
        "split": "unspecified",
        "notes": notes,
    }


def resolve_audio_path(*, wav_rel: str, metadata_root: Path, input_root: Path | None) -> Path:
    if Path(wav_rel).is_absolute():
        return Path(wav_rel).expanduser().resolve()
    if input_root:
        return to_abs_no_resolve(input_root / wav_rel)
    return to_abs_no_resolve(metadata_root / wav_rel)


def infer_metadata_root(*, dataset_name: str, metadata_source: Path) -> Path:
    if dataset_name != "gtsinger":
        return metadata_source.parent
    marker = "/processed/All/metadata.json"
    if marker in metadata_source.as_posix():
        return metadata_source.parent.parent.parent
    if "/processed/" in metadata_source.as_posix():
        # Fallback for language-level processed metadata.
        return metadata_source.parent.parent
    # Last resort: keep parent, but this may not point to actual audio assets.
    return metadata_source.parent


def infer_technique_from_wav_path(wav_rel: str) -> str:
    parts = [part.strip() for part in wav_rel.split("/") if part.strip()]
    folder_name = parts[2] if len(parts) > 2 else ""
    group_name = parts[4] if len(parts) > 4 else ""
    folder_map = {
        "breathy": "breathy",
        "glissando": "glissando",
        "vibrato": "vibrato",
        "pharyngeal": "pharyngeal",
        "mixed_voice_and_falsetto": "mixed_voice_and_falsetto",
    }
    folder_key = normalize_token(folder_name)
    group_key = normalize_token(group_name)
    if "control_group" in group_key:
        return "control"
    if "falsetto_group" in group_key:
        return "falsetto"
    if "mixed_voice_group" in group_key:
        return "mixed_voice"
    if "pharyngeal_group" in group_key:
        return "pharyngeal"
    if "vibrato_group" in group_key:
        return "vibrato"
    if "glissando_group" in group_key:
        return "glissando"
    if "breathy_group" in group_key:
        return "breathy"
    return folder_map.get(folder_key, folder_key or "unknown")


def compose_prompt(
    *,
    mapping: dict[str, Any],
    style_labels: list[str],
    emotion: str,
    pace: str,
    vocal_range: str,
    singing_method: str,
) -> str:
    fragments: list[str] = []
    style_map = mapping.get("style_label_to_prompt_fragments", {})
    emotion_map = mapping.get("emotion_to_prompt_fragments", {})
    pace_map = mapping.get("pace_to_prompt_fragments", {})
    range_map = mapping.get("range_to_prompt_fragments", {})
    method_map = mapping.get("singing_method_to_prompt_fragments", {})
    default_fragments = mapping.get("default_prompt_fragments", ["自然", "稳定", "歌唱性"])

    for label in style_labels:
        key = normalize_token(label)
        fragments.extend(as_list(style_map.get(key)))
    fragments.extend(as_list(emotion_map.get(normalize_token(emotion))))
    fragments.extend(as_list(pace_map.get(normalize_token(pace))))
    fragments.extend(as_list(range_map.get(normalize_token(vocal_range))))
    fragments.extend(as_list(method_map.get(normalize_token(singing_method))))
    if not fragments:
        fragments = list(default_fragments)
    deduped = dedupe_preserve_order([frag.strip() for frag in fragments if frag and str(frag).strip()])
    return "、".join(deduped[:6])


def estimate_duration_seconds(row: dict[str, Any]) -> float:
    for key in ("ph_durs", "word_durs", "ep_notedurs"):
        value = row.get(key)
        if isinstance(value, list) and value:
            try:
                return float(sum(float(item) for item in value))
            except Exception:
                continue
    return 0.0


def assign_splits(rows: list[dict[str, Any]], split_names: list[str], seed: int) -> None:
    if not rows:
        return
    if not split_names:
        split_names = ["train", "val", "test"]
    split_names = [name.strip() for name in split_names if name.strip()]
    if not split_names:
        split_names = ["train", "val", "test"]

    indices = list(range(len(rows)))
    random.Random(seed).shuffle(indices)

    if len(split_names) == 1:
        for idx in indices:
            rows[idx]["split"] = split_names[0]
        return
    if len(split_names) == 2:
        for rank, idx in enumerate(indices):
            frac = rank / max(len(indices), 1)
            rows[idx]["split"] = split_names[0] if frac < 0.9 else split_names[1]
        return

    for rank, idx in enumerate(indices):
        frac = rank / max(len(indices), 1)
        if frac < 0.8:
            rows[idx]["split"] = split_names[0]
        elif frac < 0.9:
            rows[idx]["split"] = split_names[1]
        else:
            rows[idx]["split"] = split_names[2]


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    split_counts = Counter(row.get("split", "unspecified") for row in rows)
    style_counts = Counter(normalize_token(row.get("style_label")) for row in rows)
    singer_counts = Counter(str(row.get("singer") or "unknown") for row in rows)
    language_counts = Counter(str(row.get("language") or "unknown") for row in rows)
    durations = [float(row.get("duration_seconds") or 0.0) for row in rows]
    audio_available_count = 0
    for row in rows:
        if Path(str(row.get("input_audio_path") or "")).exists():
            audio_available_count += 1
    duration_total = sum(durations)
    return {
        "split_counts": dict(split_counts),
        "style_label_counts_top20": dict(style_counts.most_common(20)),
        "singer_counts_top20": dict(singer_counts.most_common(20)),
        "language_counts": dict(language_counts),
        "duration_seconds_total": round(duration_total, 6),
        "duration_seconds_mean": round(duration_total / max(len(durations), 1), 6) if durations else 0.0,
        "estimated_hours": round(duration_total / 3600.0, 6),
        "audio_available_count": audio_available_count,
    }


def build_dataset_search_report(
    *,
    dataset_name: str,
    metadata_source: Path | None,
    source_resolution: dict[str, Any],
    rows_total: int,
    rows_selected: int,
    estimated_hours: float,
    audio_available: bool,
    warnings: list[str],
) -> dict[str, Any]:
    now = utc_now()
    entries: list[dict[str, Any]] = []

    if dataset_name == "gtsinger":
        entries.append(
            {
                "dataset_name": "GTSinger",
                "source": "https://huggingface.co/datasets/AaronZ345/GTSinger",
                "local_path": str(metadata_source) if metadata_source else "",
                "license_or_terms_summary": "CC BY-NC-SA 4.0; non-commercial share-alike; follow dataset_license.md terms.",
                "download_status": "metadata_only_downloaded" if metadata_source and metadata_source.exists() else "failed",
                "usable_for_training": rows_selected > 0,
                "reason": "Processed metadata parsed successfully." if rows_selected > 0 else "No rows selected after filtering.",
                "number_of_audio_files": rows_total,
                "estimated_hours": estimated_hours,
                "has_style_labels": True,
                "has_singer_labels": True,
                "has_text_or_lyrics": True,
                "has_phoneme_or_note_alignment": True,
            }
        )
    else:
        entries.append(
            {
                "dataset_name": "Opencpop",
                "source": "https://huggingface.co/datasets/espnet/ace-opencpop-segments",
                "local_path": str(metadata_source) if metadata_source else "",
                "license_or_terms_summary": "HF card shows cc-by-nc-4.0 for ace-opencpop-segments.",
                "download_status": "metadata_only_downloaded" if metadata_source and metadata_source.exists() else "failed",
                "usable_for_training": rows_selected > 0,
                "reason": "Metadata parsed." if rows_selected > 0 else "No rows selected after filtering.",
                "number_of_audio_files": rows_total,
                "estimated_hours": estimated_hours,
                "has_style_labels": False,
                "has_singer_labels": True,
                "has_text_or_lyrics": True,
                "has_phoneme_or_note_alignment": False,
            }
        )

    entries.append(
        {
            "dataset_name": "MUSDB18",
            "source": "https://sigsep.github.io/datasets/musdb.html",
            "local_path": "",
            "license_or_terms_summary": "Educational/academic use terms; not used as main style-control dataset in this stage.",
            "download_status": "not_attempted_stage1",
            "usable_for_training": False,
            "reason": "Stage-1 focuses on GTSinger metadata probing and schema build only.",
            "number_of_audio_files": 0,
            "estimated_hours": 0.0,
            "has_style_labels": False,
            "has_singer_labels": False,
            "has_text_or_lyrics": False,
            "has_phoneme_or_note_alignment": False,
        }
    )

    entries.append(
        {
            "dataset_name": "Opencpop",
            "source": "https://wenet.org.cn/opencpop/",
            "local_path": "",
            "license_or_terms_summary": "Official Opencpop homepage inspected in prior runs; this stage did not perform full download.",
            "download_status": "not_attempted_stage1",
            "usable_for_training": False,
            "reason": "Reserved as Chinese prompt supplement in later stage, not primary multi-style source.",
            "number_of_audio_files": 0,
            "estimated_hours": 0.0,
            "has_style_labels": False,
            "has_singer_labels": True,
            "has_text_or_lyrics": True,
            "has_phoneme_or_note_alignment": True,
        }
    )

    return {
        "status": "ok",
        "generated_at": now,
        "dataset_focus": dataset_name,
        "audio_available": bool(audio_available),
        "metadata_source": str(metadata_source) if metadata_source else None,
        "source_resolution": source_resolution,
        "entries": entries,
        "warnings": sorted(set(warnings)),
        "notes": [
            "This report records metadata-stage probing only (no full-audio bulk download).",
            "Do not claim full training readiness when audio_available=false.",
        ],
    }


def render_dataset_search_report_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Dataset Search Report",
        "",
        f"- generated_at: `{payload.get('generated_at', '')}`",
        f"- dataset_focus: `{payload.get('dataset_focus', '')}`",
        f"- audio_available: `{payload.get('audio_available', False)}`",
        f"- metadata_source: `{payload.get('metadata_source', '')}`",
        "",
        "| dataset_name | source | local_path | license_or_terms_summary | download_status | usable_for_training | reason | number_of_audio_files | estimated_hours | has_style_labels | has_singer_labels | has_text_or_lyrics | has_phoneme_or_note_alignment |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for entry in payload.get("entries", []):
        lines.append(
            "| {dataset_name} | {source} | `{local_path}` | {license_or_terms_summary} | `{download_status}` | `{usable_for_training}` | {reason} | {number_of_audio_files} | {estimated_hours} | `{has_style_labels}` | `{has_singer_labels}` | `{has_text_or_lyrics}` | `{has_phoneme_or_note_alignment}` |".format(
                **entry
            )
        )
    lines.extend(["", "## Warnings", ""])
    warnings = payload.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"- `{warning}`")
    else:
        lines.append("- None")
    return "\n".join(lines)


def render_dataset_build_report_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Dataset Build Report",
        "",
        f"- status: `{payload.get('status', '')}`",
        f"- dry_run: `{payload.get('dry_run', False)}`",
        f"- dataset: `{payload.get('dataset', '')}`",
        f"- metadata_source: `{payload.get('metadata_source', '')}`",
        f"- output_path: `{payload.get('output_path', '')}`",
        f"- rows_total_raw: `{payload.get('rows_total_raw', 0)}`",
        f"- rows_selected: `{payload.get('rows_selected', 0)}`",
        f"- audio_available: `{payload.get('audio_available', False)}`",
        f"- paired_training: `{payload.get('paired_training', False)}`",
        f"- estimated_hours: `{payload.get('estimated_hours', 0.0)}`",
        "",
        "## Split Counts",
        "",
    ]
    split_counts = payload.get("split_counts", {})
    if split_counts:
        for key, value in split_counts.items():
            lines.append(f"- `{key}`: {value}")
    else:
        lines.append("- None")

    lines.extend(["", "## Top Style Labels", ""])
    for key, value in (payload.get("style_label_counts_top20", {}) or {}).items():
        lines.append(f"- `{key}`: {value}")
    if not payload.get("style_label_counts_top20"):
        lines.append("- None")

    lines.extend(["", "## Top Singers", ""])
    for key, value in (payload.get("singer_counts_top20", {}) or {}).items():
        lines.append(f"- `{key}`: {value}")
    if not payload.get("singer_counts_top20"):
        lines.append("- None")

    lines.extend(["", "## Warnings", ""])
    warnings = payload.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"- `{warning}`")
    else:
        lines.append("- None")
    return "\n".join(lines)


def render_failed_build_report_md(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Dataset Build Report",
            "",
            f"- status: `{payload.get('status', 'failed')}`",
            f"- dataset: `{payload.get('dataset', '')}`",
            f"- reason: `{payload.get('reason', '')}`",
            f"- metadata_source: `{payload.get('metadata_source', '')}`",
            "",
        ]
    )


def parse_csv_list(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]


def normalize_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("-", "_").replace(" ", "_")
    return text


def code_from_language(language: Any) -> str:
    mapping = {
        "chinese": "zh",
        "zh": "zh",
        "english": "en",
        "en": "en",
        "japanese": "ja",
        "ja": "ja",
        "korean": "ko",
        "ko": "ko",
        "russian": "ru",
        "ru": "ru",
        "spanish": "es",
        "es": "es",
        "french": "fr",
        "fr": "fr",
        "german": "de",
        "de": "de",
        "italian": "it",
        "it": "it",
    }
    token = normalize_token(language)
    return mapping.get(token, token or "unknown")


def load_prompt_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        key = normalize_token(value)
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value).strip() if value is not None else ""
        if text:
            return text
    return ""


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def seconds_between(started_at: str, finished_at: str) -> float:
    try:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(finished_at)
        return round(max((end - start).total_seconds(), 0.0), 6)
    except Exception:
        return math.nan


def to_abs_no_resolve(path: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded
    return (Path.cwd() / expanded).absolute()


if __name__ == "__main__":
    raise SystemExit(main())
