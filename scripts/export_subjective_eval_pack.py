#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TASK_STORE_DIR = PROJECT_ROOT / "runtime" / "task_store" / "tasks"
OUTPUT_PATH = PROJECT_ROOT / "runtime" / "eval_reports" / "latest_subjective_eval_pack.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a subjective evaluation markdown pack without copying audio files.")
    parser.add_argument("--limit", type=int, default=3, help="How many latest real tasks to include")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Markdown output path")
    args = parser.parse_args()

    tasks = load_latest_real_tasks(limit=max(args.limit, 1))
    if not tasks:
        print("[subjective-pack] no succeeded real tasks found under runtime/task_store/tasks")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_markdown(tasks), encoding="utf-8")
    print(f"[subjective-pack] wrote subjective evaluation pack to {args.output}")
    return 0


def load_latest_real_tasks(limit: int) -> list[dict[str, object]]:
    if not TASK_STORE_DIR.exists():
        return []

    records: list[dict[str, object]] = []
    for path in sorted(TASK_STORE_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("status") != "succeeded":
            continue
        engine_details = payload.get("engine_details") or {}
        inference_mode = payload.get("inference_mode") or engine_details.get("inference_mode")
        if inference_mode != "real":
            continue
        task_id = str(payload.get("task_id") or path.stem)
        debug_dir = PROJECT_ROOT / "runtime" / "debug" / task_id
        prompt_payload = read_json(debug_dir / "prompt.json")
        audio_quality_summary = engine_details.get("audio_quality_summary") or {}
        records.append(
            {
                "task_id": task_id,
                "prompt": prompt_payload.get("prompt_text") or "",
                "input_path": str(debug_dir / "input.wav"),
                "vocals_path": str(debug_dir / "vocals.wav"),
                "output_path": str(payload.get("output_path") or debug_dir / "converted.wav"),
                "gpu_telemetry_path": str(engine_details.get("gpu_telemetry_debug_path") or debug_dir / "gpu_telemetry.txt"),
                "audio_quality_summary": audio_quality_summary,
            }
        )
        if len(records) >= limit:
            break
    return records


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def render_markdown(tasks: list[dict[str, object]]) -> str:
    lines = [
        "# Subjective Evaluation Pack",
        "",
        "以下内容仅记录 demo 输入/输出与 debug 路径，不复制音频大文件。",
        "",
        "## Task Paths",
        "",
        "| task_id | prompt | input_path | vocals_path | output_path | gpu_telemetry_path |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for task in tasks:
        lines.append(
            "| `{task_id}` | {prompt} | `{input_path}` | `{vocals_path}` | `{output_path}` | `{gpu_telemetry_path}` |".format(
                task_id=task["task_id"],
                prompt=task["prompt"],
                input_path=task["input_path"],
                vocals_path=task["vocals_path"],
                output_path=task["output_path"],
                gpu_telemetry_path=task["gpu_telemetry_path"],
            )
        )

    lines.extend(
        [
            "",
            "## Audio Quality Summary",
            "",
            "| task_id | duration_consistency | low_energy_ratio | possible_dropouts |",
            "| --- | ---: | ---: | --- |",
        ]
    )
    for task in tasks:
        summary = task.get("audio_quality_summary") or {}
        lines.append(
            "| `{task_id}` | `{duration_consistency}` | `{low_energy_ratio}` | `{possible_dropouts}` |".format(
                task_id=task["task_id"],
                duration_consistency=summary.get("duration_consistency", "n/a"),
                low_energy_ratio=summary.get("low_energy_ratio", "n/a"),
                possible_dropouts=summary.get("possible_dropouts", "n/a"),
            )
        )

    lines.extend(
        [
            "",
            "## Subjective Evaluation Table",
            "",
            "| task_id | prompt | 风格符合度 1-5 | 自然度 1-5 | 歌词可懂度 1-5 | 原旋律保持 1-5 | 总体满意度 1-5 | 备注 |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for task in tasks:
        lines.append(
            "| `{task_id}` | {prompt} |  |  |  |  |  |  |".format(
                task_id=task["task_id"],
                prompt=task["prompt"],
            )
        )

    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
