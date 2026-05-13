#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import random
import signal
import time
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from huggingface_hub import HfApi, hf_hub_download


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METADATA_SOURCE = (
    Path.home()
    / ".cache/huggingface/hub/datasets--AaronZ345--GTSinger/snapshots/dc6c01fc093514f1e8137f98437328118c937128/processed/All/metadata.json"
)
DEFAULT_AUDIO_DIR = PROJECT_ROOT / "datasets" / "gtsinger_small" / "audio"
DEFAULT_META_DIR = PROJECT_ROOT / "datasets" / "gtsinger_small" / "metadata"
DEFAULT_STYLE_MAPPING = PROJECT_ROOT / "config" / "style_prompt_mapping.json"

DEFAULT_SCHEMA_JSON = PROJECT_ROOT / "runtime" / "eval_reports" / "gtsinger_metadata_schema.json"
DEFAULT_RESOLUTION_JSON = PROJECT_ROOT / "runtime" / "eval_reports" / "gtsinger_audio_path_resolution.json"
DEFAULT_DOWNLOAD_JSON = PROJECT_ROOT / "runtime" / "eval_reports" / "gtsinger_small_download_report.json"
DEFAULT_METADATA_REPORT_JSON = PROJECT_ROOT / "runtime" / "eval_reports" / "gtsinger_small_metadata_report.json"
DEFAULT_MANIFEST_JSON = DEFAULT_META_DIR / "download_manifest.json"

REPO_CANDIDATES = ["AaronZ345/GTSinger", "GTSinger/GTSinger"]


@dataclass
class ResolutionResult:
    sample_id: str
    row_index: int
    original_wav_fn: str
    guessed_repo_path: str
    repo_id: str
    exists_remote: bool
    download_attempted: bool
    local_path: str
    exists_local: bool
    error: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download or resume a small, trainable GTSinger subset for adapter experiments.")
    parser.add_argument("--metadata-source", type=Path, default=DEFAULT_METADATA_SOURCE)
    parser.add_argument("--audio-dir", type=Path, default=DEFAULT_AUDIO_DIR)
    parser.add_argument("--meta-dir", type=Path, default=DEFAULT_META_DIR)
    parser.add_argument("--style-mapping", type=Path, default=DEFAULT_STYLE_MAPPING)
    parser.add_argument("--target-count", type=int, default=100, help="Readable audio target (>=100 for small-run readiness)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--flush-every", type=int, default=10, help="Flush manifest + metadata.small.jsonl every N newly readable samples")
    parser.add_argument("--file-timeout-seconds", type=int, default=90, help="Per-file remote resolution/download timeout")
    parser.add_argument("--time-budget-seconds", type=int, default=900, help="Total wall-clock budget for one resume run")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started_at = utc_now()
    started_monotonic = time.monotonic()
    if not args.metadata_source.exists():
        raise SystemExit(f"[gtsinger-small] metadata source not found: {args.metadata_source}")

    rows = json.loads(args.metadata_source.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("[gtsinger-small] metadata root must be a list.")
    rows = [row for row in rows if isinstance(row, dict)]
    prompt_mapping = load_prompt_mapping(args.style_mapping)

    args.audio_dir.mkdir(parents=True, exist_ok=True)
    args.meta_dir.mkdir(parents=True, exist_ok=True)
    metadata_small_path = PROJECT_ROOT / "data" / "style_adapter_pairs" / "metadata.small.jsonl"

    download_records = load_resume_records(
        manifest_path=DEFAULT_MANIFEST_JSON,
        rows=rows,
        prompt_mapping=prompt_mapping,
    )
    candidate_order = sample_candidates(rows, len(rows), args.seed)
    order_position = {idx: pos for pos, idx in enumerate(candidate_order)}
    processed_positions = [
        order_position[record["row_index"]]
        for record in download_records
        if isinstance(record.get("row_index"), int) and record["row_index"] in order_position
    ]
    start_pos = (max(processed_positions) + 1) if processed_positions else 0

    readable_before = readable_audio_count(download_records)
    last_flush_readable = readable_before
    reached_target = readable_before >= args.target_count
    stopped_due_to_budget = False

    for idx in candidate_order[start_pos:]:
        if readable_audio_count(download_records) >= args.target_count:
            reached_target = True
            break
        if time.monotonic() - started_monotonic >= max(args.time_budget_seconds, 1):
            stopped_due_to_budget = True
            break
        sample_id = f"gtsinger_{idx + 1:06d}"
        if any(record.get("sample_id") == sample_id for record in download_records):
            continue
        record = fetch_or_validate_candidate(
            row_index=idx,
            row=rows[idx],
            prompt_mapping=prompt_mapping,
            audio_dir=args.audio_dir,
            timeout_seconds=max(args.file_timeout_seconds, 1),
        )
        download_records.append(record)
        current_readable = readable_audio_count(download_records)
        if current_readable >= args.target_count:
            reached_target = True
            flush_outputs(
                rows=rows,
                records=download_records,
                metadata_small_path=metadata_small_path,
                seed=args.seed,
                args=args,
                started_at=started_at,
            )
            break
        if current_readable - last_flush_readable >= max(args.flush_every, 1):
            flush_outputs(
                rows=rows,
                records=download_records,
                metadata_small_path=metadata_small_path,
                seed=args.seed,
                args=args,
                started_at=started_at,
            )
            last_flush_readable = current_readable
            print(f"[gtsinger-small] flushed readable_audio_count={current_readable}")

    flush_outputs(
        rows=rows,
        records=download_records,
        metadata_small_path=metadata_small_path,
        seed=args.seed,
        args=args,
        started_at=started_at,
    )
    metadata_rows = metadata_rows_from_records(download_records, args.seed)
    gap = max(args.target_count - len(metadata_rows), 0)
    if gap > 0 and not reached_target:
        print(f"[gtsinger-small] target not reached within current run. readable_audio_gap={gap}")
    if stopped_due_to_budget:
        print(f"[gtsinger-small] stopped_due_to_time_budget={args.time_budget_seconds}s")
    print(f"[gtsinger-small] readable_audio_count={len(metadata_rows)} metadata={metadata_small_path}")
    print(f"[gtsinger-small] reports: {DEFAULT_DOWNLOAD_JSON}, {DEFAULT_METADATA_REPORT_JSON}, {DEFAULT_MANIFEST_JSON}")
    return 0


def load_resume_records(
    *,
    manifest_path: Path,
    rows: list[dict[str, Any]],
    prompt_mapping: dict[str, Any],
) -> list[dict[str, Any]]:
    if not manifest_path.exists():
        return []
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_records = payload.get("records", []) if isinstance(payload, dict) else []
    deduped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in raw_records:
        if not isinstance(item, dict):
            continue
        sample_id = str(item.get("sample_id") or "").strip()
        if not sample_id:
            continue
        if sample_id not in deduped:
            order.append(sample_id)
        deduped[sample_id] = normalize_resume_record(item, rows, prompt_mapping)
    return [deduped[sample_id] for sample_id in order]


def normalize_resume_record(
    record: dict[str, Any],
    rows: list[dict[str, Any]],
    prompt_mapping: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(record)
    row_index = normalized.get("row_index")
    local_path = Path(str(normalized.get("local_path") or ""))
    local_exists = local_path.exists()
    normalized["exists_local"] = local_exists
    audio_info = inspect_audio(local_path) if local_exists else {
        "readable": False,
        "sample_rate": None,
        "duration_seconds": 0.0,
        "channels": None,
        "has_nan_or_inf": None,
        "error": "local_missing",
    }
    normalized["audio_check"] = audio_info
    is_valid = bool(audio_info["readable"] and audio_info["duration_seconds"] > 0 and (not audio_info["has_nan_or_inf"]))
    normalized["is_valid_audio"] = is_valid
    if is_valid and normalized.get("metadata_row") is None and isinstance(row_index, int) and 0 <= row_index < len(rows):
        normalized["metadata_row"] = build_metadata_row(
            row=rows[row_index],
            row_index=row_index,
            local_audio_path=local_path,
            prompt_mapping=prompt_mapping,
        )
    if not is_valid and not normalized.get("error"):
        normalized["error"] = audio_info.get("error") or "audio_validation_failed"
    return normalized


def fetch_or_validate_candidate(
    *,
    row_index: int,
    row: dict[str, Any],
    prompt_mapping: dict[str, Any],
    audio_dir: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    wav = str(row.get("wav_fn") or "").strip()
    sample_id = f"gtsinger_{row_index + 1:06d}"
    local_path = (audio_dir / wav).absolute()
    record = {
        "sample_id": sample_id,
        "row_index": row_index,
        "original_wav_fn": wav,
        "guessed_repo_path": wav,
        "repo_id": "",
        "exists_remote": False,
        "download_attempted": False,
        "local_path": str(local_path),
        "exists_local": local_path.exists(),
        "error": "",
        "is_valid_audio": False,
        "audio_check": {},
        "metadata_row": None,
    }
    if not wav:
        record["error"] = "empty_wav_fn"
        return record

    local_audio_info = inspect_audio(local_path) if local_path.exists() else None
    if local_audio_info and local_audio_info["readable"] and local_audio_info["duration_seconds"] > 0 and (not local_audio_info["has_nan_or_inf"]):
        record["exists_local"] = True
        record["is_valid_audio"] = True
        record["audio_check"] = local_audio_info
        record["metadata_row"] = build_metadata_row(
            row=row,
            row_index=row_index,
            local_audio_path=local_path,
            prompt_mapping=prompt_mapping,
        )
        return record

    force_download = bool(local_audio_info and not local_audio_info["readable"])
    try:
        with time_limit(timeout_seconds):
            for repo_id in REPO_CANDIDATES:
                try:
                    local_path_str = hf_hub_download(
                        repo_id=repo_id,
                        filename=wav,
                        repo_type="dataset",
                        local_dir=str(audio_dir),
                        force_download=force_download,
                    )
                    resolved_local_path = Path(local_path_str).absolute()
                    record["repo_id"] = repo_id
                    record["exists_remote"] = True
                    record["download_attempted"] = True
                    record["local_path"] = str(resolved_local_path)
                    record["exists_local"] = resolved_local_path.exists()
                    if not resolved_local_path.exists():
                        record["error"] = "download_returned_missing_file"
                        break
                    audio_info = inspect_audio(resolved_local_path)
                    record["audio_check"] = audio_info
                    if audio_info["readable"] and audio_info["duration_seconds"] > 0 and (not audio_info["has_nan_or_inf"]):
                        record["is_valid_audio"] = True
                        record["metadata_row"] = build_metadata_row(
                            row=row,
                            row_index=row_index,
                            local_audio_path=resolved_local_path,
                            prompt_mapping=prompt_mapping,
                        )
                        record["error"] = ""
                    else:
                        record["error"] = audio_info.get("error") or "audio_validation_failed"
                    break
                except Exception as exc:
                    record["download_attempted"] = True
                    record["repo_id"] = repo_id
                    record["error"] = f"{type(exc).__name__}:{exc}"
    except TimeoutError:
        record["download_attempted"] = True
        record["error"] = f"timeout>{timeout_seconds}s"
    return record


def metadata_rows_from_records(records: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    metadata_rows = [record["metadata_row"] for record in records if record.get("is_valid_audio") and isinstance(record.get("metadata_row"), dict)]
    assign_split_8_1_1(metadata_rows, seed)
    return metadata_rows


def readable_audio_count(records: list[dict[str, Any]]) -> int:
    return sum(1 for record in records if record.get("is_valid_audio"))


def flush_outputs(
    *,
    rows: list[dict[str, Any]],
    records: list[dict[str, Any]],
    metadata_small_path: Path,
    seed: int,
    args: argparse.Namespace,
    started_at: str,
) -> None:
    metadata_rows = metadata_rows_from_records(records, seed)
    manifest_payload = {
        "status": "ok",
        "generated_at": utc_now(),
        "metadata_source": str(args.metadata_source),
        "target_count": int(args.target_count),
        "seed": int(args.seed),
        "flush_every": int(args.flush_every),
        "file_timeout_seconds": int(args.file_timeout_seconds),
        "time_budget_seconds": int(args.time_budget_seconds),
        "readable_audio_count": len(metadata_rows),
        "records": records,
    }
    write_json(DEFAULT_MANIFEST_JSON, manifest_payload)
    write_jsonl(metadata_small_path, metadata_rows)

    resolution_entries = [
        ResolutionResult(
            sample_id=str(record.get("sample_id") or ""),
            row_index=int(record.get("row_index") or 0),
            original_wav_fn=str(record.get("original_wav_fn") or ""),
            guessed_repo_path=str(record.get("guessed_repo_path") or ""),
            repo_id=str(record.get("repo_id") or ""),
            exists_remote=bool(record.get("exists_remote")),
            download_attempted=bool(record.get("download_attempted")),
            local_path=str(record.get("local_path") or ""),
            exists_local=bool(record.get("exists_local")),
            error=str(record.get("error") or ""),
        )
        for record in records
        if isinstance(record, dict) and isinstance(record.get("row_index"), int)
    ]
    download_report = build_download_report(
        started_at=started_at,
        rows_total=len(rows),
        resolution_entries=resolution_entries,
        download_records=records,
        args=args,
    )
    write_json(DEFAULT_DOWNLOAD_JSON, download_report)
    write_md(DEFAULT_DOWNLOAD_JSON.with_suffix(".md"), render_download_md(download_report))

    metadata_report = build_metadata_report(metadata_rows, metadata_small_path)
    write_json(DEFAULT_METADATA_REPORT_JSON, metadata_report)
    write_md(DEFAULT_METADATA_REPORT_JSON.with_suffix(".md"), render_metadata_md(metadata_report))


@contextmanager
def time_limit(seconds: int):
    if seconds <= 0:
        yield
        return

    def _raise_timeout(signum, frame):
        raise TimeoutError("operation timed out")

    previous = signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, float(seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous)


def build_schema_report(rows: list[dict[str, Any]], metadata_source: Path) -> dict[str, Any]:
    all_keys: Counter[str] = Counter()
    path_fields = ["wav_fn", "wav_path", "audio", "audio_path", "path", "file", "filename"]
    style_fields = ["style", "technique", "global_style", "singer", "language", "emotion", "tag", "singing_method", "pace", "range", "tech"]
    path_stats = {field: 0 for field in path_fields}
    style_stats = {field: 0 for field in style_fields}
    wav_examples: list[str] = []
    for row in rows:
        for key in row.keys():
            all_keys[key] += 1
        for field in path_fields:
            value = row.get(field)
            if isinstance(value, str) and value.strip():
                path_stats[field] += 1
                if field == "wav_fn" and len(wav_examples) < 10:
                    wav_examples.append(value.strip())
        for field in style_fields:
            value = row.get(field)
            if value is not None and str(value).strip():
                style_stats[field] += 1

    remote_candidates = []
    for wav in wav_examples:
        remote_candidates.append(
            {
                "original_wav_fn": wav,
                "repo_candidates": [f"{repo}:{wav}" for repo in REPO_CANDIDATES],
            }
        )
    return {
        "status": "ok",
        "generated_at": utc_now(),
        "metadata_source": str(metadata_source),
        "top_level_structure": "list",
        "sample_count": len(rows),
        "field_names": sorted(all_keys.keys()),
        "field_frequency": dict(all_keys),
        "audio_path_field_candidates": path_stats,
        "style_field_candidates": style_stats,
        "real_path_examples": wav_examples,
        "remote_file_candidates": remote_candidates,
    }


def sample_candidates(rows: list[dict[str, Any]], count: int, seed: int) -> list[int]:
    groups: dict[str, list[int]] = {}
    for idx, row in enumerate(rows):
        wav = str(row.get("wav_fn") or "").strip()
        if not wav:
            continue
        tech = infer_technique(wav)
        groups.setdefault(tech, []).append(idx)
    rnd = random.Random(seed)
    for values in groups.values():
        rnd.shuffle(values)
    round_robin: list[int] = []
    keys = sorted(groups.keys())
    pointers = {k: 0 for k in keys}
    while len(round_robin) < count:
        progressed = False
        for key in keys:
            ptr = pointers[key]
            values = groups[key]
            if ptr < len(values):
                round_robin.append(values[ptr])
                pointers[key] += 1
                progressed = True
                if len(round_robin) >= count:
                    break
        if not progressed:
            break
    return round_robin


def resolve_paths(*, api: HfApi, rows: list[dict[str, Any]], candidates: list[int]) -> list[ResolutionResult]:
    entries: list[ResolutionResult] = []
    for rank, idx in enumerate(candidates, start=1):
        row = rows[idx]
        wav = str(row.get("wav_fn") or "").strip()
        sample_id = f"gtsinger_{idx + 1:06d}"
        chosen_repo = ""
        exists_remote = False
        err = ""
        if wav:
            for repo in REPO_CANDIDATES:
                try:
                    if api.file_exists(repo_id=repo, filename=wav, repo_type="dataset"):
                        chosen_repo = repo
                        exists_remote = True
                        break
                except Exception as exc:
                    err = f"{type(exc).__name__}:{exc}"
        if not chosen_repo:
            chosen_repo = REPO_CANDIDATES[0]
        entries.append(
            ResolutionResult(
                sample_id=sample_id,
                row_index=idx,
                original_wav_fn=wav,
                guessed_repo_path=wav,
                repo_id=chosen_repo,
                exists_remote=exists_remote,
                download_attempted=False,
                local_path="",
                exists_local=False,
                error=err if not exists_remote else "",
            )
        )
    return entries


def download_and_validate(
    *,
    rows: list[dict[str, Any]],
    candidates: list[ResolutionResult],
    prompt_mapping: dict[str, Any],
    audio_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid_rows: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for candidate in candidates:
        row = rows[candidate.row_index]
        record = candidate.__dict__.copy()
        record["download_attempted"] = True
        record["exists_local"] = False
        record["local_path"] = ""
        record["is_valid_audio"] = False
        record["audio_check"] = {}
        record["metadata_row"] = None
        if not candidate.exists_remote:
            record["error"] = record["error"] or "remote_not_found"
            records.append(record)
            continue

        try:
            local_path_str = hf_hub_download(
                repo_id=candidate.repo_id,
                filename=candidate.guessed_repo_path,
                repo_type="dataset",
                local_dir=str(audio_dir),
            )
            local_path = Path(local_path_str).absolute()
            record["local_path"] = str(local_path)
            record["exists_local"] = local_path.exists()
            if not local_path.exists():
                record["error"] = "download_returned_missing_file"
                records.append(record)
                continue
            audio_info = inspect_audio(local_path)
            record["audio_check"] = audio_info
            if audio_info["readable"] and audio_info["duration_seconds"] > 0 and (not audio_info["has_nan_or_inf"]):
                record["is_valid_audio"] = True
                metadata_row = build_metadata_row(row=row, row_index=candidate.row_index, local_audio_path=local_path, prompt_mapping=prompt_mapping)
                record["metadata_row"] = metadata_row
                valid_rows.append(metadata_row)
            else:
                record["error"] = "audio_validation_failed"
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}:{exc}"
        records.append(record)
    return valid_rows, records


def inspect_audio(path: Path) -> dict[str, Any]:
    try:
        data, sample_rate = sf.read(path, always_2d=True)
    except Exception as exc:
        return {
            "readable": False,
            "sample_rate": None,
            "duration_seconds": 0.0,
            "channels": None,
            "has_nan_or_inf": None,
            "error": f"{type(exc).__name__}:{exc}",
        }
    duration = float(data.shape[0]) / float(sample_rate) if sample_rate > 0 else 0.0
    has_bad = bool((~np.isfinite(data)).any())
    return {
        "readable": True,
        "sample_rate": int(sample_rate),
        "duration_seconds": round(duration, 6),
        "channels": int(data.shape[1]),
        "has_nan_or_inf": has_bad,
        "error": "",
    }


def build_metadata_row(*, row: dict[str, Any], row_index: int, local_audio_path: Path, prompt_mapping: dict[str, Any]) -> dict[str, Any]:
    wav = str(row.get("wav_fn") or "").strip()
    technique = infer_technique(wav)
    emotion = normalize_token(row.get("emotion"))
    pace = normalize_token(row.get("pace"))
    vocal_range = normalize_token(row.get("range"))
    singing_method = normalize_token(row.get("singing_method"))
    style_label = "_".join(token for token in [technique, emotion, pace, vocal_range, singing_method] if token and token != "unknown") or "unknown"
    prompt = compose_prompt(
        mapping=prompt_mapping,
        style_labels=[technique, style_label],
        emotion=emotion,
        pace=pace,
        vocal_range=vocal_range,
        singing_method=singing_method,
    )
    audio_info = inspect_audio(local_audio_path)
    language = code_from_language(row.get("language"))
    return {
        "sample_id": f"gtsinger_{row_index + 1:06d}",
        "dataset": "GTSinger",
        "input_audio_path": str(local_audio_path.absolute()),
        "target_audio_path": str(local_audio_path.absolute()),
        "style_prompt": prompt,
        "style_label": style_label,
        "singer": str(row.get("singer") or "unknown"),
        "language": language,
        "technique": technique,
        "duration_seconds": audio_info["duration_seconds"],
        "sample_rate": audio_info["sample_rate"] or 48000,
        "split": "train",
        "notes": "metadata + downloaded small audio subset",
    }


def assign_split_8_1_1(rows: list[dict[str, Any]], seed: int) -> None:
    indices = list(range(len(rows)))
    random.Random(seed).shuffle(indices)
    for rank, idx in enumerate(indices):
        frac = rank / max(len(indices), 1)
        if frac < 0.8:
            rows[idx]["split"] = "train"
        elif frac < 0.9:
            rows[idx]["split"] = "val"
        else:
            rows[idx]["split"] = "test"


def build_download_report(
    *,
    started_at: str,
    rows_total: int,
    resolution_entries: list[ResolutionResult],
    download_records: list[dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    remote_found = sum(1 for entry in resolution_entries if entry.exists_remote)
    attempted = sum(1 for record in download_records if record.get("download_attempted"))
    local_ok = sum(1 for record in download_records if record.get("exists_local"))
    valid = sum(1 for record in download_records if record.get("is_valid_audio"))
    return {
        "status": "ok",
        "generated_at": utc_now(),
        "started_at": started_at,
        "finished_at": utc_now(),
        "metadata_source": str(args.metadata_source),
        "rows_total": rows_total,
        "candidate_count": len(resolution_entries),
        "remote_found_count": remote_found,
        "download_attempted_count": attempted,
        "exists_local_count": local_ok,
        "valid_audio_count": valid,
        "target_count": args.target_count,
        "probe_count": int(getattr(args, "probe_count", 0)),
        "max_count": int(getattr(args, "max_count", max(len(resolution_entries), args.target_count))),
        "flush_every": int(getattr(args, "flush_every", 0)),
        "file_timeout_seconds": int(getattr(args, "file_timeout_seconds", 0)),
        "time_budget_seconds": int(getattr(args, "time_budget_seconds", 0)),
        "small_run_ready_precheck": valid >= 100,
        "notes": [
            "This stage downloads only a small subset, not the full GTSinger corpus.",
            "Only readable local audio files are eligible for final metadata.",
        ],
    }


def build_metadata_report(rows: list[dict[str, Any]], metadata_path: Path) -> dict[str, Any]:
    style_counter = Counter(str(row.get("style_label") or "unknown") for row in rows)
    singer_counter = Counter(str(row.get("singer") or "unknown") for row in rows)
    duration_list = [float(row.get("duration_seconds") or 0.0) for row in rows]
    split_counter = Counter(str(row.get("split") or "unspecified") for row in rows)
    audio_exists_count = sum(1 for row in rows if Path(str(row.get("input_audio_path") or "")).exists())
    technique_count = len({str(row.get("technique") or "unknown") for row in rows})
    small_run_ready = (
        audio_exists_count >= 100
        and split_counter.get("train", 0) >= 80
        and technique_count >= 2
        and len(rows) > 0
        and all(float(row.get("duration_seconds") or 0.0) > 0 for row in rows)
    )
    gaps = []
    if audio_exists_count < 100:
        gaps.append("audio_exists_count<100")
    if split_counter.get("train", 0) < 80:
        gaps.append("train_size<80")
    if technique_count < 2:
        gaps.append("technique_variety<2")
    if not rows:
        gaps.append("metadata_empty")
    if any(float(row.get("duration_seconds") or 0.0) <= 0 for row in rows):
        gaps.append("contains_zero_duration_audio")

    return {
        "status": "ok",
        "generated_at": utc_now(),
        "metadata_path": str(metadata_path),
        "rows": len(rows),
        "audio_exists_count": audio_exists_count,
        "small_run_ready": small_run_ready,
        "small_run_gaps": gaps,
        "split_counts": dict(split_counter),
        "style_label_counts_top20": dict(style_counter.most_common(20)),
        "singer_counts_top20": dict(singer_counter.most_common(20)),
        "duration_seconds_total": round(sum(duration_list), 6),
        "duration_seconds_mean": round((sum(duration_list) / len(duration_list)) if duration_list else 0.0, 6),
        "duration_seconds_min": round(min(duration_list), 6) if duration_list else 0.0,
        "duration_seconds_max": round(max(duration_list), 6) if duration_list else 0.0,
        "technique_count": technique_count,
    }


def render_schema_md(payload: dict[str, Any]) -> str:
    lines = [
        "# GTSinger Metadata Schema",
        "",
        f"- top_level_structure: `{payload.get('top_level_structure', '')}`",
        f"- sample_count: `{payload.get('sample_count', 0)}`",
        "",
        "## Audio Path Candidate Fields",
        "",
    ]
    for key, value in payload.get("audio_path_field_candidates", {}).items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Style Candidate Fields", ""])
    for key, value in payload.get("style_field_candidates", {}).items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Real Path Examples", ""])
    for item in payload.get("real_path_examples", []):
        lines.append(f"- `{item}`")
    return "\n".join(lines)


def render_resolution_md(payload: dict[str, Any]) -> str:
    lines = [
        "# GTSinger Audio Path Resolution",
        "",
        f"- candidate_count: `{payload.get('candidate_count', 0)}`",
        "",
        "| sample_id | original_wav_fn | guessed_repo_path | repo_id | exists_remote | download_attempted | local_path | exists_local | error |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("entries", [])[:200]:
        lines.append(
            "| `{sample_id}` | `{original_wav_fn}` | `{guessed_repo_path}` | `{repo_id}` | `{exists_remote}` | `{download_attempted}` | `{local_path}` | `{exists_local}` | {error} |".format(
                sample_id=row.get("sample_id", ""),
                original_wav_fn=row.get("original_wav_fn", ""),
                guessed_repo_path=row.get("guessed_repo_path", ""),
                repo_id=row.get("repo_id", ""),
                exists_remote=row.get("exists_remote", False),
                download_attempted=row.get("download_attempted", False),
                local_path=row.get("local_path", ""),
                exists_local=row.get("exists_local", False),
                error=row.get("error", ""),
            )
        )
    if len(payload.get("entries", [])) > 200:
        lines.append("")
        lines.append(f"- truncated in markdown: showing first 200 of {len(payload.get('entries', []))} entries")
    return "\n".join(lines)


def render_download_md(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# GTSinger Small Download Report",
            "",
            f"- rows_total: `{payload.get('rows_total', 0)}`",
            f"- candidate_count: `{payload.get('candidate_count', 0)}`",
            f"- remote_found_count: `{payload.get('remote_found_count', 0)}`",
            f"- download_attempted_count: `{payload.get('download_attempted_count', 0)}`",
            f"- exists_local_count: `{payload.get('exists_local_count', 0)}`",
            f"- valid_audio_count: `{payload.get('valid_audio_count', 0)}`",
            f"- small_run_ready_precheck: `{payload.get('small_run_ready_precheck', False)}`",
            "",
        ]
    )


def render_metadata_md(payload: dict[str, Any]) -> str:
    lines = [
        "# GTSinger Small Metadata Report",
        "",
        f"- metadata_path: `{payload.get('metadata_path', '')}`",
        f"- rows: `{payload.get('rows', 0)}`",
        f"- audio_exists_count: `{payload.get('audio_exists_count', 0)}`",
        f"- small_run_ready: `{payload.get('small_run_ready', False)}`",
        "",
        "## Split Counts",
        "",
    ]
    for key, value in payload.get("split_counts", {}).items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Style Label Top20", ""])
    for key, value in payload.get("style_label_counts_top20", {}).items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Singer Top20", ""])
    for key, value in payload.get("singer_counts_top20", {}).items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Gaps", ""])
    gaps = payload.get("small_run_gaps", [])
    if gaps:
        for gap in gaps:
            lines.append(f"- `{gap}`")
    else:
        lines.append("- None")
    return "\n".join(lines)


def infer_technique(wav_fn: str) -> str:
    parts = [part.strip() for part in wav_fn.split("/") if part.strip()]
    group = normalize_token(parts[4]) if len(parts) > 4 else ""
    if group:
        if "control_group" in group:
            return "control"
        if "breathy_group" in group:
            return "breathy"
        if "glissando_group" in group:
            return "glissando"
        if "vibrato_group" in group:
            return "vibrato"
        if "pharyngeal_group" in group:
            return "pharyngeal"
        if "mixed_voice_group" in group:
            return "mixed_voice"
        if "falsetto_group" in group:
            return "falsetto"
    folder = normalize_token(parts[2]) if len(parts) > 2 else ""
    return folder or "unknown"


def load_prompt_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


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


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def normalize_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        key = normalize_token(value)
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
