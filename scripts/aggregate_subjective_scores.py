from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = PROJECT_ROOT / "evaluation"
DOCS_DIR = PROJECT_ROOT / "docs"
INPUT_CSV_PATH = EVALUATION_DIR / "subjective_scores.csv"
OUTPUT_JSON_PATH = EVALUATION_DIR / "subjective_summary.json"
OUTPUT_MD_PATH = DOCS_DIR / "subjective_evaluation_results.md"
SCORE_FIELDS = [
    "naturalness_score",
    "prompt_match_score",
    "style_change_score",
    "audio_quality_score",
]
VALID_PREFERENCES = {"before", "after", "no_difference"}


def main() -> int:
    if not INPUT_CSV_PATH.exists():
        print("未找到真实主观听评数据，已跳过主观结果统计。")
        return 0

    rows, warnings = load_rows(INPUT_CSV_PATH)
    summary = aggregate_rows(rows)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_csv": str(INPUT_CSV_PATH.relative_to(PROJECT_ROOT)),
        "listener_warning_count": len(warnings),
        "warnings": warnings,
        "case_count": len(summary),
        "cases": summary,
    }

    OUTPUT_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT_MD_PATH.write_text(render_markdown(payload), encoding="utf-8")

    print(f"[subjective-agg] processed {len(rows)} row(s) across {len(summary)} case(s)")
    print(f"[subjective-agg] wrote {OUTPUT_JSON_PATH}")
    print(f"[subjective-agg] wrote {OUTPUT_MD_PATH}")
    return 0


def load_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = required_columns() - set(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(f"subjective_scores.csv missing required columns: {sorted(missing_columns)}")

        for index, row in enumerate(reader, start=2):
            if not any((value or "").strip() for value in row.values()):
                continue
            normalized = {key: (value or "").strip() for key, value in row.items()}
            if not normalized["listener_id"]:
                warnings.append(f"line {index}: listener_id is empty")
            for field in SCORE_FIELDS:
                normalized[field] = validate_score(normalized[field], field_name=field, line_number=index)
            preference = normalized["preference"]
            if preference not in VALID_PREFERENCES:
                raise ValueError(
                    f"line {index}: preference must be one of {sorted(VALID_PREFERENCES)}, got {preference!r}"
                )
            rows.append(normalized)
    return rows, warnings


def aggregate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["case_id"]].append(row)

    summaries: list[dict[str, Any]] = []
    for case_id in sorted(grouped):
        case_rows = grouped[case_id]
        first = case_rows[0]
        preference_counts = Counter(row["preference"] for row in case_rows)
        listener_count = len(case_rows)
        case_summary = {
            "case_id": case_id,
            "prompt_text": first["prompt_text"],
            "model_preset_id": first["model_preset_id"],
            "listener_count": listener_count,
            "preference_counts": dict(preference_counts),
            "preference_ratios": {
                key: round(preference_counts.get(key, 0) / listener_count, 6) for key in sorted(VALID_PREFERENCES)
            },
        }
        for field in SCORE_FIELDS:
            values = [float(row[field]) for row in case_rows]
            case_summary[field] = {
                "mean": round(statistics.fmean(values), 6),
                "std": round(statistics.stdev(values), 6) if len(values) > 1 else 0.0,
            }
        summaries.append(case_summary)
    return summaries


def validate_score(raw_value: str, *, field_name: str, line_number: int) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"line {line_number}: {field_name} must be an integer from 1 to 5") from exc
    if value < 1 or value > 5:
        raise ValueError(f"line {line_number}: {field_name} must be in [1, 5], got {value}")
    return value


def required_columns() -> set[str]:
    return {
        "case_id",
        "prompt_text",
        "model_preset_id",
        "listener_id",
        *SCORE_FIELDS,
        "preference",
        "comments",
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Subjective Evaluation Results",
        "",
        "本文件由 `python scripts/aggregate_subjective_scores.py` 根据真实听评 CSV 自动生成。",
        "",
        f"- 数据源：`{payload['source_csv']}`",
        f"- case 数量：`{payload['case_count']}`",
        f"- listener warning 数量：`{payload['listener_warning_count']}`",
        "",
        "## 汇总表",
        "",
        "| case_id | preset | listeners | naturalness mean±std | prompt match mean±std | style change mean±std | audio quality mean±std | after ratio | before ratio | no_difference ratio |",
        "| --- | --- | ---: | --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for case in payload["cases"]:
        lines.append(
            "| {case_id} | `{preset}` | `{listener_count}` | `{naturalness}` | `{prompt_match}` | `{style_change}` | `{audio_quality}` | `{after}` | `{before}` | `{no_diff}` |".format(
                case_id=case["case_id"],
                preset=case["model_preset_id"],
                listener_count=case["listener_count"],
                naturalness=format_stat(case["naturalness_score"]),
                prompt_match=format_stat(case["prompt_match_score"]),
                style_change=format_stat(case["style_change_score"]),
                audio_quality=format_stat(case["audio_quality_score"]),
                after=format_ratio(case["preference_ratios"].get("after")),
                before=format_ratio(case["preference_ratios"].get("before")),
                no_diff=format_ratio(case["preference_ratios"].get("no_difference")),
            )
        )

    if payload["warnings"]:
        lines.extend(["", "## Warnings", ""])
        for warning in payload["warnings"]:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- 本文件只基于真实问卷 CSV 聚合，不会自动生成任何假的听评数据。",
            "- 若未来继续追加听评数据，请更新 `evaluation/subjective_scores.csv` 后重新运行脚本。",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def format_stat(payload: dict[str, Any]) -> str:
    mean = payload.get("mean")
    std = payload.get("std")
    return f"{mean:.3f} ± {std:.3f}"


def format_ratio(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"{float(value):.3f}"


if __name__ == "__main__":
    raise SystemExit(main())
