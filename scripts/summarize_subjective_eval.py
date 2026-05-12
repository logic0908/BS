from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "runtime" / "eval_reports" / "subjective_eval_scores.csv"
DEFAULT_PAIRWISE_INPUT = PROJECT_ROOT / "runtime" / "eval_reports" / "subjective_eval_pairwise.csv"
DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "runtime" / "eval_reports" / "subjective_eval_summary.json"
DEFAULT_OUTPUT_MD = PROJECT_ROOT / "runtime" / "eval_reports" / "subjective_eval_summary.md"

NUMERIC_FIELDS = (
    "naturalness_score",
    "clarity_score",
    "content_preservation_score",
    "prompt_match_score",
    "style_change_score",
    "overall_preference",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize subjective listening-evaluation CSV/JSON files.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Score CSV or JSON file")
    parser.add_argument("--pairwise-input", type=Path, default=DEFAULT_PAIRWISE_INPUT, help="Optional pairwise CSV or JSON file")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    score_rows = load_rows(args.input)
    pairwise_rows = load_rows(args.pairwise_input) if args.pairwise_input.exists() else []
    payload = summarize(score_rows, pairwise_rows)
    write_json(args.output_json, payload)
    args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    if payload["status"] == "pending_human_scores":
        print("模板已生成，暂无结论。")
    else:
        print(f"已汇总 {payload['scored_rows']} 条主观评分记录。")
    return 0


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [dict(item) for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
            return [dict(item) for item in payload["rows"] if isinstance(item, dict)]
        return []

    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def summarize(score_rows: list[dict[str, Any]], pairwise_rows: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_scores = [normalize_score_row(row) for row in score_rows if row]
    usable_scores = [row for row in normalized_scores if any(row[field] is not None for field in NUMERIC_FIELDS)]
    if not usable_scores:
        return {
            "status": "pending_human_scores",
            "scored_rows": 0,
            "condition_summaries": [],
            "pairwise_summary": {},
            "message": "模板已生成，暂无结论。",
        }

    condition_groups: dict[str, list[dict[str, Any]]] = {}
    for row in usable_scores:
        condition_groups.setdefault(row["condition"] or "unknown", []).append(row)

    condition_summaries = []
    for condition, rows in sorted(condition_groups.items()):
        summary = {"condition": condition, "sample_count": len(rows)}
        for field in NUMERIC_FIELDS:
            values = [row[field] for row in rows if row[field] is not None]
            summary[field] = summarize_numeric(values)
        condition_summaries.append(summary)

    pairwise_summary = summarize_pairwise(pairwise_rows)
    return {
        "status": "ok",
        "scored_rows": len(usable_scores),
        "condition_summaries": condition_summaries,
        "pairwise_summary": pairwise_summary,
        "message": "主观听评结果仅反映当前已填写样本，不能外推为完整结论。",
    }


def normalize_score_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    for field in NUMERIC_FIELDS:
        normalized[field] = parse_optional_score(row.get(field))
    normalized["condition"] = str(row.get("condition") or "").strip()
    normalized["sample_id"] = str(row.get("sample_id") or "").strip()
    normalized["prompt"] = str(row.get("prompt") or "").strip()
    return normalized


def parse_optional_score(value: Any) -> int | None:
    text = str(value).strip() if value is not None else ""
    if not text:
        return None
    if text.isdigit() and 1 <= int(text) <= 5:
        return int(text)
    return None


def summarize_numeric(values: list[int]) -> dict[str, float | int | None]:
    if not values:
        return {"mean": None, "std": None, "n": 0}
    return {
        "mean": round(mean(values), 4),
        "std": round(pstdev(values), 4) if len(values) > 1 else 0.0,
        "n": len(values),
    }


def summarize_pairwise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"status": "pending"}

    counts = {
        "better_prompt_match": {},
        "better_naturalness": {},
        "style_difference_audible": {},
        "has_distortion_or_artifacts": {},
    }
    for row in rows:
        for key in counts:
            value = str(row.get(key) or "").strip() or "blank"
            counts[key][value] = counts[key].get(value, 0) + 1
    return {"status": "ok", **counts}


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Subjective Evaluation Summary",
        "",
        payload.get("message", ""),
        "",
    ]
    if payload.get("status") == "pending_human_scores":
        lines.extend(
            [
                "- 状态：`pending_human_scores`",
                "- 说明：模板已生成，暂无结论。",
                "",
            ]
        )
        return "\n".join(lines)

    lines.extend(
        [
            "## Condition Summary",
            "",
            "| condition | n | naturalness | clarity | content_preservation | prompt_match | style_change | overall_preference |",
            "| --- | ---: | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for summary in payload.get("condition_summaries") or []:
        lines.append(
            "| `{condition}` | `{sample_count}` | `{naturalness}` | `{clarity}` | `{content_preservation}` | `{prompt_match}` | `{style_change}` | `{overall_preference}` |".format(
                condition=summary.get("condition", ""),
                sample_count=summary.get("sample_count", 0),
                naturalness=format_metric(summary.get("naturalness_score")),
                clarity=format_metric(summary.get("clarity_score")),
                content_preservation=format_metric(summary.get("content_preservation_score")),
                prompt_match=format_metric(summary.get("prompt_match_score")),
                style_change=format_metric(summary.get("style_change_score")),
                overall_preference=format_metric(summary.get("overall_preference")),
            )
        )
    pairwise = payload.get("pairwise_summary") or {}
    lines.extend(
        [
            "",
            "## Pairwise Questions",
            "",
            f"- better_prompt_match: `{json.dumps(pairwise.get('better_prompt_match', {}), ensure_ascii=False)}`",
            f"- better_naturalness: `{json.dumps(pairwise.get('better_naturalness', {}), ensure_ascii=False)}`",
            f"- style_difference_audible: `{json.dumps(pairwise.get('style_difference_audible', {}), ensure_ascii=False)}`",
            f"- has_distortion_or_artifacts: `{json.dumps(pairwise.get('has_distortion_or_artifacts', {}), ensure_ascii=False)}`",
            "",
            "## Boundary",
            "",
            "- 若样本量有限或评分差异不稳定，不应表述为“显著优于”。",
            "- 主观听评结论必须和客观指标、样本覆盖范围一起解释。",
            "",
        ]
    )
    return "\n".join(lines)


def format_metric(metric: dict[str, Any] | None) -> str:
    if not metric or metric.get("n", 0) == 0:
        return "pending"
    return f"{metric['mean']:.2f} ± {metric['std']:.2f} (n={metric['n']})"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
