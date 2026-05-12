#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OBJECTIVE_JSON = PROJECT_ROOT / "runtime" / "eval_reports" / "objective_metrics.json"
DEFAULT_OBJECTIVE_MD = PROJECT_ROOT / "runtime" / "eval_reports" / "objective_metrics.md"
DEFAULT_DOC_OUTPUT = PROJECT_ROOT / "docs" / "objective_evaluation_report.md"
DEFAULT_PROMPT_CONFIG = PROJECT_ROOT / "config" / "eval_prompts.json"
DEFAULT_PROMPT_JSON = PROJECT_ROOT / "runtime" / "eval_reports" / "eval_prompt_matrix.json"
DEFAULT_PROMPT_MD = PROJECT_ROOT / "runtime" / "eval_reports" / "eval_prompt_matrix.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export evaluation markdown artifacts for objective metrics and prompt matrix.")
    parser.add_argument("--objective-json", type=Path, default=DEFAULT_OBJECTIVE_JSON)
    parser.add_argument("--objective-md", type=Path, default=DEFAULT_OBJECTIVE_MD)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOC_OUTPUT)
    parser.add_argument("--prompt-config", type=Path, default=DEFAULT_PROMPT_CONFIG)
    parser.add_argument("--prompt-output-json", type=Path, default=DEFAULT_PROMPT_JSON)
    parser.add_argument("--prompt-output-md", type=Path, default=DEFAULT_PROMPT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    export_objective_report(args.objective_json, args.objective_md, args.docs_output)
    export_prompt_matrix(args.prompt_config, args.prompt_output_json, args.prompt_output_md)
    print("[eval-report] exported objective report and prompt matrix")
    return 0


def export_objective_report(objective_json: Path, objective_md: Path, docs_output: Path) -> None:
    if objective_json.exists():
        payload = json.loads(objective_json.read_text(encoding="utf-8"))
        markdown = objective_md.read_text(encoding="utf-8") if objective_md.exists() else render_objective_doc(payload)
    else:
        payload = {}
        markdown = render_objective_doc(payload)
    objective_md.parent.mkdir(parents=True, exist_ok=True)
    objective_md.write_text(markdown, encoding="utf-8")
    docs_output.write_text(render_objective_doc(payload), encoding="utf-8")


def export_prompt_matrix(prompt_config: Path, output_json: Path, output_md: Path) -> None:
    if not prompt_config.exists():
        payload = {
            "status": "missing_prompt_config",
            "message": f"Prompt config not found: {prompt_config}",
            "prompts": [],
        }
    else:
        config = json.loads(prompt_config.read_text(encoding="utf-8"))
        prompts = config.get("prompts") or []
        payload = {
            "status": "ok",
            "default_preset": config.get("default_preset"),
            "prompt_count": len(prompts),
            "prompts": prompts,
        }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_prompt_matrix_md(payload), encoding="utf-8")


def render_objective_doc(payload: dict[str, Any]) -> str:
    rows = payload.get("summary_rows") or []
    lines = [
        "# Objective Evaluation Report",
        "",
        "本报告汇总 `baseline none`、`external_preset`、`internal_film` 的可量化参考指标，用于论文和答辩中的辅助说明。",
        "",
        "## 边界说明",
        "",
        "- 指标只用于量化参考，不直接证明主观听感更好。",
        "- 歌声转换场景下，若没有 clean reference 或可用许可实现，不强制计算 PESQ/POLQA/STOI。",
        "- `speaker_embedding_similarity`、`f0`、`mfcc_distance` 等指标在依赖缺失时只输出 warning，不中断整体报告。",
        "",
        f"- 当前状态：`{payload.get('status', 'pending')}`",
        f"- 当前 case 数：`{payload.get('case_count', 0)}`",
        "",
        "## 汇总表",
        "",
        "| sample_id | condition | rms_energy | clipping_ratio | silence_ratio | spectral_centroid_mean | f0_mean | mfcc_distance | speaker_similarity | brightness_delta | energy_delta | pitch_height_delta |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    if not rows:
        lines.append("| `pending` | `pending` |  |  |  |  |  |  |  |  |  |  |")
    for row in rows:
        lines.append(
            "| `{sample_id}` | `{condition}` | `{rms_energy}` | `{clipping_ratio}` | `{silence_ratio}` | `{spectral_centroid_mean}` | `{f0_mean}` | `{mfcc_distance}` | `{speaker_embedding_similarity}` | `{brightness_delta}` | `{energy_delta}` | `{pitch_height_delta}` |".format(
                sample_id=row.get("sample_id", ""),
                condition=row.get("condition", ""),
                rms_energy=row.get("rms_energy", ""),
                clipping_ratio=row.get("clipping_ratio", ""),
                silence_ratio=row.get("silence_ratio", ""),
                spectral_centroid_mean=row.get("spectral_centroid_mean", ""),
                f0_mean=row.get("f0_mean", ""),
                mfcc_distance=row.get("mfcc_distance", ""),
                speaker_embedding_similarity=row.get("speaker_embedding_similarity", ""),
                brightness_delta=row.get("brightness_delta", ""),
                energy_delta=row.get("energy_delta", ""),
                pitch_height_delta=row.get("pitch_height_delta", ""),
            )
        )
    lines.extend(
        [
            "",
            "## 解释方式",
            "",
            "- `brightness_delta / energy_delta / pitch_height_delta / softness_delta / thickness_delta` 为启发式风格方向指标。",
            "- 它们只能说明输出是否朝 prompt 预期方向发生变化，不能替代人工听评或证明“显著更优”。",
            "",
            "## 当前结论边界",
            "",
            "- 可以说：系统已经具备对 baseline / external / internal 条件的批量客观统计框架。",
            "- 不能说：仅凭本报告就能证明 internal FiLM 一定显著优于 baseline none。",
            "",
        ]
    )
    return "\n".join(lines)


def render_prompt_matrix_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Eval Prompt Matrix",
        "",
        f"- status: `{payload.get('status', 'pending')}`",
        f"- default_preset: `{payload.get('default_preset', 'n/a')}`",
        f"- prompt_count: `{payload.get('prompt_count', 0)}`",
        "",
        "| prompt_id | prompt | brightness | energy | pitch_height | softness | thickness | emotion_intensity | final_primary | final_male_youth | final_male_powerful | final_female_soft | final_female_clear |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    prompts = payload.get("prompts") or []
    if not prompts:
        lines.append("| `pending` | `pending` |  |  |  |  |  |  |  |  |  |  |  |")
        return "\n".join(lines)
    for prompt in prompts:
        direction = prompt.get("expected_style_direction") or {}
        availability = prompt.get("preset_availability") or {}
        lines.append(
            "| `{prompt_id}` | {text} | `{brightness}` | `{energy}` | `{pitch_height}` | `{softness}` | `{thickness}` | `{emotion_intensity}` | `{final_primary}` | `{final_male_youth}` | `{final_male_powerful}` | `{final_female_soft}` | `{final_female_clear}` |".format(
                prompt_id=prompt.get("prompt_id", ""),
                text=prompt.get("text", ""),
                brightness=direction.get("brightness", "neutral"),
                energy=direction.get("energy", "neutral"),
                pitch_height=direction.get("pitch_height", "neutral"),
                softness=direction.get("softness", "neutral"),
                thickness=direction.get("thickness", "neutral"),
                emotion_intensity=direction.get("emotion_intensity", "neutral"),
                final_primary=availability.get("final_primary", ""),
                final_male_youth=availability.get("final_male_youth", ""),
                final_male_powerful=availability.get("final_male_powerful", ""),
                final_female_soft=availability.get("final_female_soft", ""),
                final_female_clear=availability.get("final_female_clear", ""),
            )
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
