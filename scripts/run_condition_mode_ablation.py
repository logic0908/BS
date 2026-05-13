#!/usr/bin/env python
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterator

import soundfile as sf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.svc_task_service import svc_task_service  # noqa: E402


DEFAULT_OUTPUT = PROJECT_ROOT / "runtime" / "eval_reports" / "condition_mode_ablation_1000.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or dry-run none/external/internal condition-mode ablation.")
    parser.add_argument("--input", required=True, help="Input vocal wav path")
    parser.add_argument("--prompt", required=True, help="Prompt text")
    parser.add_argument("--preset", default="final_primary", help="Manual override preset id")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--film-strength", type=float, default=0.10)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include-combo", action="store_true", help="Also run external_preset + internal_film if desired")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    conditions = [
        {
            "label": "none",
            "condition_mode": "none",
            "requested_adapter_mode": "no_adapter",
            "notes": "原始 So-VITS-SVC 推理，不启用内部文本条件注入。",
        },
        {
            "label": "external_preset",
            "condition_mode": "none",
            "requested_adapter_mode": "rule_based_adapter",
            "notes": "逻辑层外部 preset/参数路径；若手动固定 final_primary，则不作为专用模型效果结论。",
        },
        {
            "label": "internal_film",
            "condition_mode": "internal_film",
            "requested_adapter_mode": "trained_adapter",
            "notes": "固定 final_primary/lain，启用 style_emb -> internal FiLM。",
        },
    ]
    if args.include_combo:
        conditions.append(
            {
                "label": "external_preset_plus_internal_film",
                "condition_mode": "internal_film",
                "requested_adapter_mode": "rule_based_adapter",
                "notes": "组合组，仅在代码当前支持时作为补充对照。",
            }
        )

    payload = {
        "status": "dry_run" if args.dry_run else "planned",
        "input": args.input,
        "prompt": args.prompt,
        "preset": args.preset,
        "film_strength": args.film_strength,
        "results": [],
        "warnings": [],
    }
    input_probe = probe_audio(args.input)
    if input_probe.get("warning"):
        payload["warnings"].append(input_probe["warning"])
    payload["input_probe"] = input_probe

    for condition in conditions:
        output_dir = PROJECT_ROOT / "runtime" / "eval_samples" / "condition_mode" / condition["label"]
        output_path = output_dir / "converted.wav"
        if args.dry_run or not Path(args.input).exists():
            payload["results"].append(
                {
                    "label": condition["label"],
                    "condition_mode": condition["condition_mode"],
                    "film_strength": args.film_strength if condition["condition_mode"] == "internal_film" else 0.0,
                    "requested_adapter_mode": condition["requested_adapter_mode"],
                    "requested_model_preset_id": args.preset,
                    "effective_model_preset_id": args.preset,
                    "preset_fallback_used": False,
                    "output_path": str(output_path),
                    "sample_rate": input_probe.get("sample_rate"),
                    "duration_seconds": input_probe.get("duration_seconds"),
                    "executed_internal_film": "dry_run" if condition["condition_mode"] == "internal_film" else False,
                    "real_model_execution": None,
                    "notes": condition["notes"],
                    "dry_run": True,
                }
            )
            continue

        record = run_single_case(
            input_path=args.input,
            prompt=args.prompt,
            preset=args.preset,
            label=condition["label"],
            condition_mode=condition["condition_mode"],
            requested_adapter_mode=condition["requested_adapter_mode"],
            film_strength=args.film_strength,
            notes=condition["notes"],
            output_path=output_path,
        )
        payload["status"] = "completed"
        payload["results"].append(record)

    write_outputs(args.output, payload, render_markdown(payload))
    print(f"[condition-mode] wrote reports rooted at {args.output}")
    return 0


def run_single_case(
    *,
    input_path: str,
    prompt: str,
    preset: str,
    label: str,
    condition_mode: str,
    requested_adapter_mode: str,
    film_strength: float,
    notes: str,
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
            "STYLE_ADAPTER_CHECKPOINT_PATH": str(PROJECT_ROOT / "runtime" / "style_adapter" / "text_style_adapter_1000.pt"),
        }
    ):
        svc_task_service.process_task(
            task_id=task_id,
            prompt_text=prompt,
            style_prompt=prompt,
            style_strength=film_strength,
            model_preset_id=preset,
            allow_preset_fallback=False,
            output_path=str(output_path),
            requested_adapter_mode=requested_adapter_mode,
        )
    task = svc_task_service.get_task(task_id)
    debug_dir = PROJECT_ROOT / "runtime" / "debug" / task_id
    conditioning_report = read_json(debug_dir / "conditioning_report.json")
    sovits_debug = read_json(debug_dir / "sovits_debug.json")
    runtime_config = dict(sovits_debug.get("runtime_config") or {})
    probe = probe_audio(str(output_path))
    engine_details = dict((task.engine_details or {})) if task else {}
    style_adapter_output_path = debug_dir / "style_adapter_output.json"
    style_adapter_output = read_json(style_adapter_output_path)
    adapter_mode = str(engine_details.get("adapter_mode") or style_adapter_output.get("adapter_mode") or "")
    adapter_type = str(engine_details.get("adapter_type") or style_adapter_output.get("adapter_type") or "")
    adapter_checkpoint = str(engine_details.get("adapter_checkpoint_path") or "")
    if not adapter_checkpoint:
        adapter_checkpoint = str(style_adapter_output.get("adapter_checkpoint_path") or "")
    canonical_checkpoint = str(PROJECT_ROOT / "runtime" / "style_adapter" / "text_style_adapter_1000.pt")
    if adapter_checkpoint == canonical_checkpoint:
        adapter_checkpoint = "runtime/style_adapter/text_style_adapter_1000.pt"
    text_style_adapter_loaded = bool(style_adapter_output.get("adapter_enabled")) and adapter_mode == "trained"
    if condition_mode == "internal_film" and not text_style_adapter_loaded:
        raise RuntimeError(
            "internal_film case did not load trained adapter; "
            f"adapter_mode={adapter_mode}, adapter_type={adapter_type}, style_adapter_output={style_adapter_output_path}"
        )
    return {
        "task_id": task_id,
        "label": label,
        "condition_mode": condition_mode,
        "film_strength": film_strength if condition_mode == "internal_film" else 0.0,
        "requested_adapter_mode": requested_adapter_mode,
        "requested_model_preset_id": engine_details.get("requested_model_preset_id"),
        "effective_model_preset_id": engine_details.get("effective_model_preset_id"),
        "preset_fallback_used": engine_details.get("preset_fallback_used"),
        "output_path": str(output_path),
        "sample_rate": probe.get("sample_rate"),
        "duration_seconds": probe.get("duration_seconds"),
        "executed_internal_film": conditioning_report.get("executed_internal_film", runtime_config.get("called_conditioned_inference", False)),
        "text_style_adapter_loaded": text_style_adapter_loaded,
        "adapter_checkpoint": adapter_checkpoint,
        "adapter_mode": adapter_mode,
        "adapter_type": adapter_type,
        "style_adapter_output_path": str(style_adapter_output_path),
        "real_model_execution": bool(task and task.status == "succeeded" and not runtime_config.get("mock_enabled", True)),
        "notes": notes,
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
        "# Condition Mode Ablation",
        "",
        f"- status: `{payload.get('status', 'unknown')}`",
        f"- preset override: `{payload.get('preset', '')}`",
        "",
        "| label | condition_mode | requested_adapter_mode | requested_model_preset_id | effective_model_preset_id | preset_fallback_used | executed_internal_film | text_style_adapter_loaded | adapter_mode | adapter_type | adapter_checkpoint | real_model_execution | notes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("results") or []:
        lines.append(
            "| `{label}` | `{condition_mode}` | `{requested_adapter_mode}` | `{requested_model_preset_id}` | `{effective_model_preset_id}` | `{preset_fallback_used}` | `{executed_internal_film}` | `{text_style_adapter_loaded}` | `{adapter_mode}` | `{adapter_type}` | `{adapter_checkpoint}` | `{real_model_execution}` | {notes} |".format(
                label=row.get("label", ""),
                condition_mode=row.get("condition_mode", ""),
                requested_adapter_mode=row.get("requested_adapter_mode", ""),
                requested_model_preset_id=row.get("requested_model_preset_id", ""),
                effective_model_preset_id=row.get("effective_model_preset_id", ""),
                preset_fallback_used=row.get("preset_fallback_used", ""),
                executed_internal_film=row.get("executed_internal_film", ""),
                text_style_adapter_loaded=row.get("text_style_adapter_loaded", ""),
                adapter_mode=row.get("adapter_mode", ""),
                adapter_type=row.get("adapter_type", ""),
                adapter_checkpoint=row.get("adapter_checkpoint", ""),
                real_model_execution=row.get("real_model_execution", ""),
                notes=row.get("notes", ""),
            )
        )
    lines.extend(
        [
            "",
            "- `external_preset` 若仅是逻辑层外部预设且未绑定独立真实专用模型，不能拿来声称“效果更好”。",
            "- 显式 `model_preset_id=final_primary` 时，报告需要保留 requested/effective preset 与 fallback 状态，避免偷偷切模型。",
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
