from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.audio_style_analysis import compare_audio_style  # noqa: E402


EVALUATION_DIR = PROJECT_ROOT / "evaluation"
DOCS_DIR = PROJECT_ROOT / "docs"
RUNTIME_DIR = PROJECT_ROOT / "runtime"
TASK_STORE_DIR = RUNTIME_DIR / "task_store" / "tasks"
DEFAULT_PAIRS_PATH = EVALUATION_DIR / "objective_pairs.json"
DEFAULT_RESULTS_PATH = EVALUATION_DIR / "objective_results.json"
DEFAULT_REPORT_PATH = DOCS_DIR / "objective_evaluation_report.md"
DEFAULT_SMOKE_REPORT_PATH = RUNTIME_DIR / "model_search" / "final_male_powerful_smoke_test.json"
DEFAULT_SMOKE_INPUT_PATH = PROJECT_ROOT / "StyleSinger" / "test" / "test.wav"


@dataclass
class ObjectivePair:
    case_id: str
    prompt_text: str
    model_preset_id: str
    input_path: str
    output_path: str
    source: str
    notes: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run objective evaluation on existing audio pairs.")
    parser.add_argument(
        "--pairs",
        default=str(DEFAULT_PAIRS_PATH),
        help="Path to evaluation/objective_pairs.json. If missing, auto-discover from smoke report and task logs.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_RESULTS_PATH),
        help="Path to write evaluation/objective_results.json",
    )
    parser.add_argument(
        "--report",
        default=str(DEFAULT_REPORT_PATH),
        help="Path to write docs/objective_evaluation_report.md",
    )
    parser.add_argument(
        "--max-auto-task-pairs",
        type=int,
        default=3,
        help="When auto-discovering, include at most this many succeeded task pairs in addition to smoke evidence.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pairs_path = Path(args.pairs)
    output_path = Path(args.output)
    report_path = Path(args.report)

    EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    if pairs_path.exists():
        pairs = load_pairs_from_config(pairs_path)
        source_mode = f"config:{pairs_path.relative_to(PROJECT_ROOT)}"
    else:
        pairs = auto_discover_pairs(max_auto_task_pairs=args.max_auto_task_pairs)
        source_mode = "auto_discovery"

    if not pairs:
        print("[objective-eval] no valid objective pairs found; nothing to evaluate")
        return 1

    results = [evaluate_pair(pair) for pair in pairs]
    payload = build_results_payload(results=results, pairs=pairs, source_mode=source_mode)
    write_json(output_path, payload)
    report_path.write_text(render_markdown_report(payload), encoding="utf-8")

    print(f"[objective-eval] evaluated {len(results)} case(s)")
    print(f"[objective-eval] wrote {output_path}")
    print(f"[objective-eval] wrote {report_path}")
    return 0


def load_pairs_from_config(path: Path) -> list[ObjectivePair]:
    payload = read_json(path)
    raw_pairs = payload.get("pairs")
    if not isinstance(raw_pairs, list):
        raise ValueError(f"{path} must contain a top-level 'pairs' list")

    pairs: list[ObjectivePair] = []
    for index, item in enumerate(raw_pairs):
        if not isinstance(item, dict):
            raise ValueError(f"pairs[{index}] must be an object")
        pair = ObjectivePair(
            case_id=str(item["case_id"]),
            prompt_text=str(item["prompt_text"]),
            model_preset_id=str(item["model_preset_id"]),
            input_path=str(item["input_path"]),
            output_path=str(item["output_path"]),
            source=str(item.get("source", "objective_pairs")),
            notes=str(item.get("notes", "")),
        )
        validate_pair_paths(pair)
        pairs.append(pair)
    return pairs


def auto_discover_pairs(*, max_auto_task_pairs: int) -> list[ObjectivePair]:
    pairs: list[ObjectivePair] = []
    smoke_pair = build_default_smoke_pair()
    if smoke_pair is not None:
        pairs.append(smoke_pair)

    pairs.extend(discover_succeeded_task_pairs(limit=max_auto_task_pairs))
    return dedupe_pairs(pairs)


def build_default_smoke_pair() -> ObjectivePair | None:
    if not DEFAULT_SMOKE_REPORT_PATH.exists():
        return None
    payload = read_json(DEFAULT_SMOKE_REPORT_PATH)
    input_candidate = str(payload.get("input") or DEFAULT_SMOKE_INPUT_PATH)
    output_candidate = first_existing_path(
        [
            payload.get("output"),
            payload.get("selected_output"),
            resolve_output_from_sovits_debug(payload.get("sovits_debug_json_path")),
        ]
    )
    if output_candidate is None:
        return None
    pair = ObjectivePair(
        case_id="final_male_powerful_smoke",
        prompt_text="低沉、成熟、厚重男声",
        model_preset_id="final_male_powerful",
        input_path=input_candidate,
        output_path=output_candidate,
        source="smoke_report",
        notes="Built from runtime/model_search/final_male_powerful_smoke_test.json",
    )
    validate_pair_paths(pair)
    return pair


def discover_succeeded_task_pairs(*, limit: int) -> list[ObjectivePair]:
    if not TASK_STORE_DIR.exists():
        return []

    candidates: list[tuple[float, ObjectivePair]] = []
    for path in TASK_STORE_DIR.glob("*.json"):
        payload = read_json(path)
        if payload.get("status") != "succeeded":
            continue
        if payload.get("inference_mode") != "real":
            continue

        task_id = str(payload.get("task_id") or path.stem)
        debug_dir = RUNTIME_DIR / "debug" / task_id
        prompt_payload = read_optional_json(debug_dir / "prompt.json")
        prompt_text = str((prompt_payload or {}).get("prompt_text") or "").strip()
        if not prompt_text:
            continue

        input_path = debug_dir / "vocals.wav"
        output_path = first_existing_path(
            [
                payload.get("output_path"),
                (payload.get("engine_details") or {}).get("final_output_path"),
            ]
        )
        if not input_path.exists() or output_path is None:
            continue

        engine_details = payload.get("engine_details") or {}
        model_preset_id = (
            engine_details.get("effective_model_preset_id")
            or engine_details.get("requested_model_preset_id")
            or engine_details.get("model_preset_id")
            or "unknown"
        )
        pair = ObjectivePair(
            case_id=f"task_{task_id}",
            prompt_text=prompt_text,
            model_preset_id=str(model_preset_id),
            input_path=str(input_path),
            output_path=output_path,
            source="task_store",
            notes=f"Derived from runtime/task_store/tasks/{path.name}",
        )
        candidates.append((path.stat().st_mtime, pair))

    pairs = [pair for _, pair in sorted(candidates, key=lambda item: item[0], reverse=True)]
    return dedupe_pairs(pairs)[:limit]


def dedupe_pairs(pairs: list[ObjectivePair]) -> list[ObjectivePair]:
    deduped: list[ObjectivePair] = []
    seen: set[tuple[str, str, str]] = set()
    for pair in pairs:
        key = (pair.case_id, pair.input_path, pair.output_path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(pair)
    return deduped


def validate_pair_paths(pair: ObjectivePair) -> None:
    input_path = Path(pair.input_path).expanduser()
    output_path = Path(pair.output_path).expanduser()
    if not input_path.exists():
        raise FileNotFoundError(f"input_path does not exist for {pair.case_id}: {input_path}")
    if not output_path.exists():
        raise FileNotFoundError(f"output_path does not exist for {pair.case_id}: {output_path}")


def evaluate_pair(pair: ObjectivePair) -> dict[str, Any]:
    started = time.perf_counter()
    report = compare_audio_style(
        input_audio_path=pair.input_path,
        output_audio_path=pair.output_path,
        prompt_text=pair.prompt_text,
        model_preset_id=pair.model_preset_id,
    )
    analysis_elapsed_seconds = round(time.perf_counter() - started, 3)

    input_report = report.get("input") or {}
    output_report = report.get("output") or {}
    summary = report.get("summary") or {}

    duration_input = coerce_number(input_report.get("duration_seconds"))
    duration_output = coerce_number(output_report.get("duration_seconds"))
    f0_input = coerce_number(input_report.get("f0_median"))
    f0_output = coerce_number(output_report.get("f0_median"))
    voiced_input = coerce_number(input_report.get("voiced_ratio"))
    voiced_output = coerce_number(output_report.get("voiced_ratio"))
    rms_input = coerce_number(input_report.get("rms_mean"))
    rms_output = coerce_number(output_report.get("rms_mean"))
    centroid_input = coerce_number(input_report.get("spectral_centroid_mean"))
    centroid_output = coerce_number(output_report.get("spectral_centroid_mean"))
    brightness_input = coerce_number(input_report.get("brightness_score"))
    brightness_output = coerce_number(output_report.get("brightness_score"))
    energy_input = coerce_number(input_report.get("energy_score"))
    energy_output = coerce_number(output_report.get("energy_score"))
    softness_input = coerce_number(input_report.get("softness_score"))
    softness_output = coerce_number(output_report.get("softness_score"))
    thickness_input = coerce_number(input_report.get("thickness_score"))
    thickness_output = coerce_number(output_report.get("thickness_score"))
    pitch_input = coerce_number(input_report.get("pitch_height_score"))
    pitch_output = coerce_number(output_report.get("pitch_height_score"))
    style_score = coerce_number(summary.get("score"))

    result = {
        "case_id": pair.case_id,
        "prompt_text": pair.prompt_text,
        "model_preset_id": pair.model_preset_id,
        "input_path": pair.input_path,
        "output_path": pair.output_path,
        "input_path_basename": Path(pair.input_path).name,
        "output_path_basename": Path(pair.output_path).name,
        "source": pair.source,
        "notes": pair.notes,
        "analysis_ok": bool(report.get("ok")),
        "analysis_elapsed_seconds": analysis_elapsed_seconds,
        "duration_input": duration_input,
        "duration_output": duration_output,
        "duration_delta": safe_delta(duration_output, duration_input),
        "duration_delta_seconds": safe_delta(duration_output, duration_input),
        "duration_delta_ratio": safe_ratio_delta(duration_input, duration_output),
        "style_evidence_score": style_score,
        "style_evidence_level": summary.get("level"),
        "matched_count": int(summary.get("matched_count") or 0),
        "total_count": int(summary.get("total_count") or 0),
        "f0_median_input": f0_input,
        "f0_median_output": f0_output,
        "f0_median_delta": safe_delta(f0_output, f0_input),
        "voiced_ratio_input": voiced_input,
        "voiced_ratio_output": voiced_output,
        "voiced_ratio_delta": safe_delta(voiced_output, voiced_input),
        "rms_mean_input": rms_input,
        "rms_mean_output": rms_output,
        "rms_mean_delta": safe_delta(rms_output, rms_input),
        "spectral_centroid_input": centroid_input,
        "spectral_centroid_output": centroid_output,
        "spectral_centroid_delta": safe_delta(centroid_output, centroid_input),
        "brightness_score_input": brightness_input,
        "brightness_score_output": brightness_output,
        "brightness_score_delta": safe_delta(brightness_output, brightness_input),
        "energy_score_input": energy_input,
        "energy_score_output": energy_output,
        "energy_score_delta": safe_delta(energy_output, energy_input),
        "softness_score_input": softness_input,
        "softness_score_output": softness_output,
        "softness_score_delta": safe_delta(softness_output, softness_input),
        "thickness_score_input": thickness_input,
        "thickness_score_output": thickness_output,
        "thickness_score_delta": safe_delta(thickness_output, thickness_input),
        "pitch_height_score_input": pitch_input,
        "pitch_height_score_output": pitch_output,
        "pitch_height_score_delta": safe_delta(pitch_output, pitch_input),
        "summary_text": summary.get("text"),
        "warnings": list(report.get("warnings") or []),
        "content_preservation_note": "So-VITS-SVC 类 SVC 更偏向保留源音频的旋律、节奏与语调骨架，因此前后差异通常不会像 TTS 重合成那样剧烈。",
        "style_response_note": build_style_response_note(style_score, summary.get("level")),
    }

    smoke_metadata = load_smoke_metadata_for_pair(pair)
    if smoke_metadata:
        result["smoke_metadata"] = smoke_metadata

    return result


def build_results_payload(*, results: list[dict[str, Any]], pairs: list[ObjectivePair], source_mode: str) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_objective_evaluation.py",
        "source_mode": source_mode,
        "sample_count": len(results),
        "limited_sample_notice": len(results) < 5,
        "pair_config_used": DEFAULT_PAIRS_PATH.exists(),
        "pairs": [asdict(pair) for pair in pairs],
        "results": results,
    }


def build_style_response_note(score: float | None, level: str | None) -> str:
    if score is None:
        return "当前未得到足够稳定的可比指标，暂不对提示词响应程度作结论。"
    if score >= 0.75 or level == "strong":
        return "客观指标显示输出在多个维度上朝提示词方向变化，但这仍是启发式辅助结论，不能替代人工听评。"
    if score >= 0.4 or level == "partial":
        return "客观指标显示输出存在一定提示词响应趋势，但变化幅度有限，仍需结合主观试听判断是否足够明显。"
    return "客观指标显示本次输出的风格响应较弱，可作为后续优化 preset、提示词映射和控制强度的依据。"


def load_smoke_metadata_for_pair(pair: ObjectivePair) -> dict[str, Any] | None:
    if pair.model_preset_id != "final_male_powerful":
        return None
    if pair.case_id != "final_male_powerful_smoke":
        return None
    if not DEFAULT_SMOKE_REPORT_PATH.exists():
        return None
    smoke_report = read_json(DEFAULT_SMOKE_REPORT_PATH)
    smoke_debug = read_optional_json(Path(str(smoke_report.get("sovits_debug_json_path") or "")))
    return {
        "task_id": smoke_report.get("task_id"),
        "success": smoke_report.get("success"),
        "command_return_code": smoke_report.get("command_return_code"),
        "called_inference_main": smoke_report.get("called_inference_main"),
        "command_matches_preset": smoke_report.get("command_matches_preset"),
        "speaker_matches_preset": smoke_report.get("speaker_matches_preset"),
        "soundfile_readable": smoke_report.get("soundfile_readable"),
        "duration_seconds": smoke_report.get("duration_seconds"),
        "inference_elapsed_seconds": (smoke_debug or {}).get("elapsed_seconds"),
        "license": read_install_report_license("final_male_powerful"),
    }


def read_install_report_license(preset_id: str) -> str | None:
    install_report_path = PROJECT_ROOT / "local_models" / "sovits-final" / preset_id / "install_report.json"
    payload = read_optional_json(install_report_path)
    return None if payload is None else payload.get("license")


def render_markdown_report(payload: dict[str, Any]) -> str:
    results = payload.get("results") or []
    lines = [
        "# Objective Evaluation Report",
        "",
        "本报告基于当前仓库内可复查的真实 smoke test 结果、已成功转换任务产物以及 `compare_audio_style` 生成的启发式客观指标自动整理。",
        "",
        "## 当前范围",
        "",
        f"- 评估样本数：`{payload.get('sample_count', 0)}`",
        f"- 结果文件：`evaluation/objective_results.json`",
        f"- 生成脚本：`{payload.get('script')}`",
        "- 说明：客观指标只用于辅助解释风格变化趋势，不能替代人工听评。",
        "",
    ]

    if payload.get("limited_sample_notice"):
        lines.extend(
            [
                "## 样本数量说明",
                "",
                "- 当前可直接复查的真实样本数量有限，本报告只代表阶段性客观证据，不应外推为完整风格覆盖结论。",
                "- `final_female_soft` 与 `final_female_clear` 仍未配置真实模型，因此不纳入本轮音频客观评价。",
                "",
            ]
        )

    lines.extend(
        [
            "## 汇总表",
            "",
            "| case_id | preset | duration_delta (s) | style_evidence_score | level | matched/total | f0_median_delta | rms_mean_delta | spectral_centroid_delta | style_analysis_time (s) |",
            "| --- | --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in results:
        lines.append(
            "| {case_id} | `{preset}` | `{duration_delta}` | `{style_score}` | `{level}` | `{matched}/{total}` | `{f0_delta}` | `{rms_delta}` | `{centroid_delta}` | `{analysis_time}` |".format(
                case_id=item["case_id"],
                preset=item["model_preset_id"],
                duration_delta=format_number(item.get("duration_delta")),
                style_score=format_number(item.get("style_evidence_score")),
                level=item.get("style_evidence_level") or "n/a",
                matched=item.get("matched_count", 0),
                total=item.get("total_count", 0),
                f0_delta=format_number(item.get("f0_median_delta")),
                rms_delta=format_number(item.get("rms_mean_delta")),
                centroid_delta=format_number(item.get("spectral_centroid_delta")),
                analysis_time=format_number(item.get("analysis_elapsed_seconds")),
            )
        )

    lines.extend(["", "## 个案说明", ""])
    for item in results:
        lines.extend(
            [
                f"### {item['case_id']}",
                "",
                f"- prompt：`{item['prompt_text']}`",
                f"- preset：`{item['model_preset_id']}`",
                f"- 输入音频：`{item['input_path_basename']}`",
                f"- 输出音频：`{item['output_path_basename']}`",
                f"- style evidence：`{format_number(item.get('style_evidence_score'))}` / `{item.get('style_evidence_level')}`",
                f"- 总结：{item.get('summary_text') or 'n/a'}",
                f"- 内容保持说明：{item.get('content_preservation_note')}",
                f"- 风格响应说明：{item.get('style_response_note')}",
            ]
        )
        warnings = item.get("warnings") or []
        if warnings:
            lines.append(f"- warnings：`{' | '.join(str(w) for w in warnings)}`")
        smoke_metadata = item.get("smoke_metadata")
        if isinstance(smoke_metadata, dict):
            lines.append(
                "- smoke 证据："
                f" `success={smoke_metadata.get('success')}`"
                f" `command_return_code={smoke_metadata.get('command_return_code')}`"
                f" `called_inference_main={smoke_metadata.get('called_inference_main')}`"
                f" `command_matches_preset={smoke_metadata.get('command_matches_preset')}`"
                f" `speaker_matches_preset={smoke_metadata.get('speaker_matches_preset')}`"
                f" `soundfile_readable={smoke_metadata.get('soundfile_readable')}`"
                f" `duration_seconds={smoke_metadata.get('duration_seconds')}`"
                f" `license={smoke_metadata.get('license')}`"
            )
        lines.append("")

    lines.extend(
        [
            "## 结论边界",
            "",
            "- 当前报告只说明：系统已经具备可复查的客观风格证据提取能力。",
            "- 当前报告不能说明：系统已经完成全部风格覆盖，或客观指标等价于主观听感。",
            "- `TextStyleAdapter` 当前仍是参数级控制，不是 So-VITS-SVC 网络内部 Bias/Scale 注入。",
            "- `license_unknown` 模型只能按当前文档口径用于本地技术演示或内部复核，不能表述成授权边界完全清晰的公开商用模型。",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def resolve_output_from_sovits_debug(raw_path: Any) -> str | None:
    if not raw_path:
        return None
    payload = read_optional_json(Path(str(raw_path)))
    if payload is None:
        return None
    return first_existing_path(
        [
            payload.get("final_output_path"),
            payload.get("selected_output"),
            ((payload.get("result_metadata") or {}).get("final_output_path")),
            ((payload.get("result_metadata") or {}).get("selected_output")),
        ]
    )


def first_existing_path(candidates: list[Any]) -> str | None:
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(str(candidate)).expanduser()
        if path.exists():
            return str(path)
    return None


def safe_delta(after: float | None, before: float | None) -> float | None:
    if after is None or before is None:
        return None
    return round(after - before, 6)


def safe_ratio_delta(before: float | None, after: float | None) -> float | None:
    if before is None or after is None or before == 0:
        return None
    return round((after - before) / before, 6)


def coerce_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def format_number(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return str(value).lower()
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{numeric:.4f}".rstrip("0").rstrip(".")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
