#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "runtime" / "eval_reports" / "subjective_eval_pack"
DEFAULT_MANIFEST = PROJECT_ROOT / "runtime" / "eval_reports" / "subjective_eval_manifest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a subjective listening-evaluation pack without copying runtime audio into git.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Input or output manifest path")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Pack directory")
    parser.add_argument("--init-template", action="store_true", help="Write an empty/example manifest and CSV templates")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.init_template or not args.manifest.exists():
        manifest = example_manifest()
        write_manifest(args.manifest, manifest)
    else:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))

    samples = manifest.get("samples") or []
    score_template_path = args.output_dir / "subjective_eval_scores.template.csv"
    pair_template_path = args.output_dir / "subjective_eval_pairwise.template.csv"
    readme_path = args.output_dir / "README.md"

    write_score_template(score_template_path)
    write_pairwise_template(pair_template_path)
    readme_path.write_text(render_pack_markdown(samples, args.manifest, score_template_path, pair_template_path), encoding="utf-8")

    print(f"[subjective-pack] manifest: {args.manifest}")
    print(f"[subjective-pack] score template: {score_template_path}")
    print(f"[subjective-pack] pairwise template: {pair_template_path}")
    return 0


def example_manifest() -> dict[str, Any]:
    return {
        "status": "template",
        "notes": [
            "Fill real audio paths only under runtime/eval_samples or runtime/debug; do not commit them.",
            "Keep subjective scores blank until real human listeners complete the form.",
        ],
        "samples": [
            {
                "sample_id": "case_001",
                "prompt": "温柔、明亮、流行感更强的女声风格",
                "baseline_none_path": "/abs/path/to/converted_none.wav",
                "internal_film_path": "/abs/path/to/converted_internal_film.wav",
                "condition_a_label": "baseline none",
                "condition_b_label": "internal_film strength=0.10",
                "notes": "待人工填写",
            }
        ],
    }


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_score_template(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "listener_id",
                "sample_id",
                "prompt",
                "condition",
                "naturalness_score",
                "clarity_score",
                "content_preservation_score",
                "prompt_match_score",
                "style_change_score",
                "overall_preference",
                "comments",
            ]
        )


def write_pairwise_template(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "listener_id",
                "sample_id",
                "prompt",
                "better_prompt_match",
                "better_naturalness",
                "style_difference_audible",
                "has_distortion_or_artifacts",
                "comments",
            ]
        )


def render_pack_markdown(
    samples: list[dict[str, Any]],
    manifest_path: Path,
    score_template_path: Path,
    pair_template_path: Path,
) -> str:
    lines = [
        "# Subjective Evaluation Pack",
        "",
        "本目录只导出听评所需的样例清单和表格模板，不复制音频、不提交 runtime 大文件。",
        "",
        f"- manifest: `{manifest_path}`",
        f"- score template: `{score_template_path}`",
        f"- pairwise template: `{pair_template_path}`",
        "",
        "## Sample List",
        "",
        "| sample_id | prompt | condition A | condition B | baseline_none_path | internal_film_path | notes |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not samples:
        lines.append("| `pending` | `pending` |  |  |  |  | 模板已生成，待人工填写 |")
    for sample in samples:
        lines.append(
            "| `{sample_id}` | {prompt} | `{condition_a_label}` | `{condition_b_label}` | `{baseline_none_path}` | `{internal_film_path}` | {notes} |".format(
                sample_id=sample.get("sample_id", ""),
                prompt=sample.get("prompt", ""),
                condition_a_label=sample.get("condition_a_label", "baseline none"),
                condition_b_label=sample.get("condition_b_label", "internal_film strength=0.10"),
                baseline_none_path=sample.get("baseline_none_path", ""),
                internal_film_path=sample.get("internal_film_path", ""),
                notes=sample.get("notes", "待人工填写"),
            )
        )
    lines.extend(
        [
            "",
            "## Listener Instructions",
            "",
            "- 先听完整 A/B 两个版本，再填写各条件的 1-5 分。",
            "- 不确定时可以在 `comments` 中记录“风格差异不明显”。",
            "- 没有真实人工评分时，不要补填任何分数。",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
