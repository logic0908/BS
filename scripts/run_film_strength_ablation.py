#!/usr/bin/env python
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Iterator

import soundfile as sf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.svc_task_service import svc_task_service  # noqa: E402


DEFAULT_OUTPUT = PROJECT_ROOT / "runtime" / "eval_reports" / "film_strength_ablation.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or dry-run internal FiLM strength ablation without changing the main inference chain.")
    parser.add_argument("--input", required=True, help="Input vocal wav path")
    parser.add_argument("--prompt", required=True, help="Shared prompt for all conditions")
    parser.add_argument("--strengths", nargs="+", required=True, help="Strength list such as 0 0.05 0.10 0.15")
    parser.add_argument("--preset", default="final_primary", help="Requested preset id")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-cases", type=int, default=0, help="Optional cap for the number of conditions to execute")
    parser.add_argument("--skip-existing", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    strengths = [float(value) for value in args.strengths]
    if args.max_cases and args.max_cases > 0:
        strengths = strengths[: args.max_cases]

    payload = {
        "status": "dry_run" if args.dry_run else "planned",
        "input": args.input,
        "prompt": args.prompt,
        "preset": args.preset,
        "results": [],
        "warnings": [],
    }
    input_probe = probe_audio(args.input)
    if input_probe.get("warning"):
        payload["warnings"].append(input_probe["warning"])
    payload["input_probe"] = input_probe

    for strength in strengths:
        condition_mode = "none" if strength == 0 else "internal_film"
        label = "none" if strength == 0 else f"internal_film_{strength:.2f}"
        output_dir = PROJECT_ROOT / "runtime" / "eval_samples" / "film_strength" / label
        output_path = output_dir / "converted.wav"

        if args.skip_existing and output_path.exists() and not args.dry_run:
            record = {
                "label": label,
                "condition_mode": condition_mode,
                "film_strength": strength,
                "output_path": str(output_path),
                "skipped_existing": True,
            }
            payload["results"].append(record)
            continue

        if args.dry_run or not Path(args.input).exists():
            payload["results"].append(
                {
                    "label": label,
                    "condition_mode": condition_mode,
                    "film_strength": strength,
                    "output_path": str(output_path),
                    "conditioning_report_path": str(output_dir / "conditioning_report.json"),
                    "executed_internal_film": None if strength == 0 else "dry_run",
                    "sample_rate": input_probe.get("sample_rate"),
                    "duration_seconds": input_probe.get("duration_seconds"),
                    "has_nan_or_inf": input_probe.get("has_nan_or_inf"),
                    "task_metadata": {
                        "requested_model_preset_id": args.preset,
                        "effective_model_preset_id": args.preset,
                        "preset_fallback_used": False,
                    },
                    "dry_run": True,
                }
            )
            continue

        record = run_single_case(
            input_path=args.input,
            prompt=args.prompt,
            preset=args.preset,
            condition_mode=condition_mode,
            film_strength=strength,
            output_path=output_path,
        )
        payload["status"] = "completed"
        payload["results"].append(record)

    write_outputs(args.output, payload, render_markdown(payload))
    print(f"[film-strength] wrote reports rooted at {args.output}")
    return 0


def run_single_case(
    *,
    input_path: str,
    prompt: str,
    preset: str,
    condition_mode: str,
    film_strength: float,
    output_path: Path,
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    upload = svc_task_service.create_upload(input_path=input_path, is_vocal_only=True)
    task_id = svc_task_service.create_task(upload.vocals_id, task_backend_mode="local")
    with temporary_env(
        {
            "SVC_USE_CELERY": "false",
            "SOVITS_MOCK": "false",
            "SOVITS_CONDITION_MODE": condition_mode,
            "SOVITS_FILM_STRENGTH": f"{film_strength:.2f}",
        }
    ):
        svc_task_service.process_task(
            task_id=task_id,
            prompt_text=prompt,
            style_prompt=prompt,
            style_strength=max(film_strength, 0.10),
            model_preset_id=preset,
            allow_preset_fallback=False,
            output_path=str(output_path),
            requested_adapter_mode="no_adapter",
        )
    task = svc_task_service.get_task(task_id)
    debug_dir = PROJECT_ROOT / "runtime" / "debug" / task_id
    conditioning_report_path = debug_dir / "conditioning_report.json"
    conditioning_report = read_json(conditioning_report_path)
    sovits_debug = read_json(debug_dir / "sovits_debug.json")
    runtime_config = dict(sovits_debug.get("runtime_config") or {})
    probe = probe_audio(str(output_path))
    engine_details = dict((task.engine_details or {})) if task else {}
    return {
        "task_id": task_id,
        "label": "none" if condition_mode == "none" else f"internal_film_{film_strength:.2f}",
        "condition_mode": condition_mode,
        "film_strength": film_strength,
        "output_path": str(output_path),
        "conditioning_report_path": str(conditioning_report_path),
        "executed_internal_film": conditioning_report.get("executed_internal_film", runtime_config.get("called_conditioned_inference")),
        "sample_rate": probe.get("sample_rate"),
        "duration_seconds": probe.get("duration_seconds"),
        "has_nan_or_inf": probe.get("has_nan_or_inf"),
        "task_metadata": {
            "requested_model_preset_id": engine_details.get("requested_model_preset_id"),
            "effective_model_preset_id": engine_details.get("effective_model_preset_id"),
            "preset_fallback_used": engine_details.get("preset_fallback_used"),
            "command_or_debug_dir": str(debug_dir / "sovits_command.txt"),
            "mock_enabled": runtime_config.get("mock_enabled"),
            "called_conditioned_inference": runtime_config.get("called_conditioned_inference"),
        },
        "dry_run": False,
    }


def probe_audio(path: str) -> dict[str, Any]:
    audio_path = Path(path)
    if not audio_path.exists():
        return {"path": path, "warning": "input_missing_for_dry_run"}
    try:
        waveform, sample_rate = sf.read(audio_path, always_2d=True)
    except Exception as exc:
        return {"path": path, "warning": f"audio_unreadable:{type(exc).__name__}"}
    mono = waveform.mean(axis=1)
    return {
        "path": path,
        "sample_rate": int(sample_rate),
        "duration_seconds": round(float(mono.shape[0]) / float(sample_rate), 6),
        "has_nan_or_inf": bool((~(mono == mono)).any() or (~(abs(mono) < float("inf"))).any()),
    }


@contextlib.contextmanager
def temporary_env(overrides: dict[str, str]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def write_outputs(json_path: Path, payload: dict[str, Any], markdown: str) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    json_path.with_suffix(".md").write_text(markdown, encoding="utf-8")


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Film Strength Ablation",
        "",
        f"- status: `{payload.get('status', 'unknown')}`",
        f"- preset: `{payload.get('preset', '')}`",
        f"- prompt: {payload.get('prompt', '')}",
        "",
        "| label | condition_mode | film_strength | output_path | executed_internal_film | sample_rate | duration_seconds | has_nan_or_inf | requested_preset | effective_preset | preset_fallback_used |",
        "| --- | --- | ---: | --- | --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in payload.get("results") or []:
        meta = row.get("task_metadata") or {}
        lines.append(
            "| `{label}` | `{condition_mode}` | `{film_strength}` | `{output_path}` | `{executed_internal_film}` | `{sample_rate}` | `{duration_seconds}` | `{has_nan_or_inf}` | `{requested}` | `{effective}` | `{fallback}` |".format(
                label=row.get("label", ""),
                condition_mode=row.get("condition_mode", ""),
                film_strength=row.get("film_strength", ""),
                output_path=row.get("output_path", ""),
                executed_internal_film=row.get("executed_internal_film", ""),
                sample_rate=row.get("sample_rate", ""),
                duration_seconds=row.get("duration_seconds", ""),
                has_nan_or_inf=row.get("has_nan_or_inf", ""),
                requested=meta.get("requested_model_preset_id", ""),
                effective=meta.get("effective_model_preset_id", ""),
                fallback=meta.get("preset_fallback_used", ""),
            )
        )
    lines.extend(
        [
            "",
            "- 若本次仅执行 dry-run，则该表只说明实验配置、输出目录和记录字段已补齐，不能当作效果结论。",
            "",
        ]
    )
    return "\n".join(lines)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
