#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.audio_quality import analyze_audio_pair  # noqa: E402


DEFAULT_OUTPUT = PROJECT_ROOT / "runtime" / "eval_reports" / "objective_metrics.json"

CONDITIONS = (
    ("baseline_none", "baseline_none_path"),
    ("external_preset", "external_preset_path"),
    ("internal_film", "internal_film_path"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate objective audio metrics for baseline/external/internal comparison cases.")
    parser.add_argument("--cases", type=Path, help="JSON file with a {'cases': [...]} payload")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Objective metrics JSON output")
    parser.add_argument("--init-template", type=Path, help="Write an example cases JSON template and exit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.init_template:
        write_template(args.init_template)
        print(f"[audio-quality] wrote template to {args.init_template}")
        return 0

    if not args.cases:
        print("[audio-quality] provide --cases or use --init-template")
        return 0

    payload = json.loads(args.cases.read_text(encoding="utf-8"))
    cases = payload.get("cases") or []
    if not isinstance(cases, list):
        raise SystemExit("[audio-quality] cases JSON must contain a list under 'cases'")

    report = evaluate_cases(cases)
    write_outputs(args.output, report)
    print(f"[audio-quality] wrote JSON/CSV/Markdown reports rooted at {args.output}")
    return 0


def write_template(path: Path) -> None:
    template = {
        "cases": [
            {
                "sample_id": "case_001",
                "prompt": "温柔、明亮、流行感更强的女声风格",
                "input_path": "/abs/path/to/vocals.wav",
                "baseline_none_path": "/abs/path/to/converted_none.wav",
                "external_preset_path": "/abs/path/to/converted_external.wav",
                "internal_film_path": "/abs/path/to/converted_internal_film.wav",
            }
        ]
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")


def evaluate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    global_warnings: list[str] = []
    for case in cases:
        sample_id = str(case.get("sample_id") or f"case_{len(records) + 1:03d}")
        input_path = str(case.get("input_path") or "").strip()
        prompt = str(case.get("prompt") or "").strip()
        case_result = {
            "sample_id": sample_id,
            "prompt": prompt,
            "input_path": input_path,
            "conditions": [],
            "warnings": [],
        }
        if not input_path:
            case_result["warnings"].append("missing_input_path")
            records.append(case_result)
            continue
        for condition_name, key in CONDITIONS:
            candidate_path = str(case.get(key) or "").strip()
            if not candidate_path:
                case_result["warnings"].append(f"missing_{key}")
                continue
            output_path = Path(candidate_path)
            if not output_path.exists():
                case_result["warnings"].append(f"missing_file:{key}")
                continue
            pair_report = analyze_audio_pair(input_path, str(output_path))
            pair_report["condition"] = condition_name
            pair_report["output_path"] = str(output_path)
            case_result["conditions"].append(pair_report)
        global_warnings.extend(case_result["warnings"])
        records.append(case_result)

    summary_rows = build_summary_rows(records)
    return {
        "status": "ok" if any(row["conditions"] for row in records) else "template_only_or_missing_files",
        "case_count": len(records),
        "cases": records,
        "summary_rows": summary_rows,
        "warnings": sorted(set(global_warnings)),
        "notes": [
            "Objective metrics are quantitative references only and do not prove subjective preference.",
            "For singing voice conversion, PESQ/POLQA/STOI are intentionally not hard-required here.",
            "Optional metrics such as speaker similarity degrade to warnings when dependencies are unavailable.",
        ],
    }


def build_summary_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in records:
        for condition in case["conditions"]:
            input_audio = condition["input_audio"]
            output_audio = condition["output_audio"]
            comparisons = condition.get("comparisons") or {}
            style_metrics = comparisons.get("style_direction_metrics") or {}
            rows.append(
                {
                    "sample_id": case["sample_id"],
                    "prompt": case["prompt"],
                    "condition": condition["condition"],
                    "input_path": case["input_path"],
                    "output_path": condition["output_path"],
                    "duration_seconds": output_audio.get("duration_seconds"),
                    "sample_rate": output_audio.get("sample_rate"),
                    "rms_energy": output_audio.get("rms_energy"),
                    "peak_amplitude": output_audio.get("peak_amplitude"),
                    "clipping_ratio": output_audio.get("clipping_ratio"),
                    "silence_ratio": output_audio.get("silence_ratio"),
                    "spectral_centroid_mean": output_audio.get("spectral_centroid_mean"),
                    "spectral_centroid_std": output_audio.get("spectral_centroid_std"),
                    "f0_mean": output_audio.get("f0_mean"),
                    "f0_std": output_audio.get("f0_std"),
                    "f0_voiced_ratio": output_audio.get("f0_voiced_ratio"),
                    "mfcc_distance": comparisons.get("mfcc_distance"),
                    "mel_spectral_distance": comparisons.get("mel_spectral_distance"),
                    "speaker_embedding_similarity": comparisons.get("speaker_embedding_similarity"),
                    "brightness_delta": style_metrics.get("brightness_delta"),
                    "energy_delta": style_metrics.get("energy_delta"),
                    "pitch_height_delta": style_metrics.get("pitch_height_delta"),
                    "softness_delta": style_metrics.get("softness_delta"),
                    "thickness_delta": style_metrics.get("thickness_delta"),
                    "warnings": "; ".join(condition.get("warnings") or []),
                    "input_duration_seconds": input_audio.get("duration_seconds"),
                }
            )
    return rows


def write_outputs(json_path: Path, payload: dict[str, Any]) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path = json_path.with_suffix(".csv")
    md_path = json_path.with_suffix(".md")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, payload.get("summary_rows") or [])
    md_path.write_text(render_markdown(payload), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "sample_id",
        "prompt",
        "condition",
        "input_path",
        "output_path",
        "duration_seconds",
        "sample_rate",
        "rms_energy",
        "peak_amplitude",
        "clipping_ratio",
        "silence_ratio",
        "spectral_centroid_mean",
        "spectral_centroid_std",
        "f0_mean",
        "f0_std",
        "f0_voiced_ratio",
        "mfcc_distance",
        "mel_spectral_distance",
        "speaker_embedding_similarity",
        "brightness_delta",
        "energy_delta",
        "pitch_height_delta",
        "softness_delta",
        "thickness_delta",
        "warnings",
        "input_duration_seconds",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Objective Metrics",
        "",
        "这些指标用于辅助展示 baseline `none`、`external_preset`、`internal_film` 的量化差异，不等价于主观听感优劣。",
        "",
        f"- case_count: `{payload.get('case_count', 0)}`",
        f"- status: `{payload.get('status', 'unknown')}`",
        "",
        "## Summary Table",
        "",
        "| sample_id | condition | duration_seconds | sample_rate | rms_energy | peak_amplitude | clipping_ratio | silence_ratio | spectral_centroid_mean | f0_mean | mfcc_distance | speaker_embedding_similarity | brightness_delta | energy_delta | pitch_height_delta | softness_delta | thickness_delta |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    rows = payload.get("summary_rows") or []
    if not rows:
        lines.append("| `pending` | `pending` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |")
    for row in rows:
        lines.append(
            "| `{sample_id}` | `{condition}` | `{duration_seconds}` | `{sample_rate}` | `{rms_energy}` | `{peak_amplitude}` | `{clipping_ratio}` | `{silence_ratio}` | `{spectral_centroid_mean}` | `{f0_mean}` | `{mfcc_distance}` | `{speaker_embedding_similarity}` | `{brightness_delta}` | `{energy_delta}` | `{pitch_height_delta}` | `{softness_delta}` | `{thickness_delta}` |".format(
                **{key: row.get(key, "") for key in row}
            )
        )
    lines.extend(
        [
            "",
            "## Warnings",
            "",
        ]
    )
    warnings = payload.get("warnings") or []
    if not warnings:
        lines.append("- 无")
    else:
        for warning in warnings:
            lines.append(f"- `{warning}`")
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "- 客观指标只提供趋势线索，不能直接证明 `internal_film` 在主观上显著优于 baseline `none`。",
            "- 歌声转换的最终结论仍需结合听评、更多 prompt、更多样本和更多 preset 复核。",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
