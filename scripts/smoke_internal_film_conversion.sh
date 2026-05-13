#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/featurize/work/BS"
PRESET_ID="final_primary"
INPUT_PATH=""
STYLE_PROMPT="温柔、明亮、流行感更强的女声风格"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input)
      INPUT_PATH="$2"
      shift 2
      ;;
    --preset)
      PRESET_ID="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$INPUT_PATH" ]]; then
  INPUT_PATH="$(python - <<'PY'
from glob import glob

patterns = [
    "runtime/debug/*/vocals.wav",
    "runtime/uploads/*.wav",
    "tests/fixtures/*.wav",
    "backend/tests/fixtures/*.wav",
]
for pattern in patterns:
    matches = sorted(glob(pattern))
    if matches:
        print(matches[0])
        raise SystemExit(0)
raise SystemExit(1)
PY
)" || true
fi

if [[ -z "$INPUT_PATH" || ! -f "$INPUT_PATH" ]]; then
  echo "No test wav found. Please provide --input xxx.wav" >&2
  exit 1
fi

export PYTHONPATH="$PROJECT_ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
export SOVITS_MOCK=false
export SVC_MODEL_PRESET_ID="${SVC_MODEL_PRESET_ID:-$PRESET_ID}"
export SOVITS_REPO_DIR="${SOVITS_REPO_DIR:-$PROJECT_ROOT/so-vits-svc}"
export SOVITS_INFER_SCRIPT="${SOVITS_INFER_SCRIPT:-$PROJECT_ROOT/so-vits-svc/inference_main.py}"
export SOVITS_CONDITIONED_INFER_SCRIPT="${SOVITS_CONDITIONED_INFER_SCRIPT:-$PROJECT_ROOT/backend/app/models_svc/inference_conditioned.py}"
export SOVITS_DEVICE="${SOVITS_DEVICE:-cuda}"
export SOVITS_TIMEOUT_SECONDS="${SOVITS_TIMEOUT_SECONDS:-600}"
export SOVITS_CONDITION_MODE="${SOVITS_CONDITION_MODE:-internal_film}"
export SOVITS_STYLE_DIM="${SOVITS_STYLE_DIM:-256}"
export SOVITS_FILM_STRENGTH="${SOVITS_FILM_STRENGTH:-0.10}"
export SOVITS_FILM_TARGET="${SOVITS_FILM_TARGET:-pre_decoder}"
export SOVITS_STYLE_EMB_FORMAT="${SOVITS_STYLE_EMB_FORMAT:-pt}"
export STYLE_ADAPTER_CHECKPOINT_PATH="${STYLE_ADAPTER_CHECKPOINT_PATH:-$PROJECT_ROOT/runtime/style_adapter/text_style_adapter_1000.pt}"

python "$PROJECT_ROOT/scripts/check_models_ready.py" --preset "$PRESET_ID"

python - "$PROJECT_ROOT" "$INPUT_PATH" "$PRESET_ID" "$STYLE_PROMPT" <<'PY'
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import numpy as np
import soundfile as sf

project_root = Path(sys.argv[1]).resolve()
input_path = Path(sys.argv[2]).resolve()
preset_id = sys.argv[3]
style_prompt = sys.argv[4]

if str(project_root / "backend") not in sys.path:
    sys.path.insert(0, str(project_root / "backend"))

from app.services.svc_task_service import TaskState, svc_task_service  # noqa: E402

task_id = f"smoke-internal_film-{uuid.uuid4()}"
upload = svc_task_service.create_upload(str(input_path), is_vocal_only=True)
task = TaskState(
    task_id=task_id,
    status="queued",
    message="任务已创建",
    engine="sovits",
    vocals_id=upload.vocals_id,
    stage="uploaded",
    progress=0,
    task_backend_mode="local",
)
svc_task_service._persist_task(task)

debug_dir = project_root / "runtime" / "debug" / task_id
output_path = debug_dir / "converted_internal_film.wav"
svc_task_service.process_task(
    task_id=task_id,
    prompt_text=style_prompt,
    style_prompt=style_prompt,
    style_strength=0.65,
    model_preset_id=preset_id,
    allow_preset_fallback=False,
    output_path=str(output_path),
)

if not output_path.exists():
    raise SystemExit("converted_internal_film.wav was not created")

task = svc_task_service.get_task(task_id)
metadata = dict((task.engine_details if task else {}) or {})
conditioning_report_path = debug_dir / "conditioning_report.json"
style_embedding_path = debug_dir / "style_embedding.pt"
summary_path = debug_dir / "smoke_summary.json"

conditioning_report = {}
if conditioning_report_path.exists():
    conditioning_report = json.loads(conditioning_report_path.read_text(encoding="utf-8"))

audio, sample_rate = sf.read(output_path, always_2d=False)
duration_seconds = round(float(len(audio)) / float(sample_rate), 3) if sample_rate else 0.0
finite = bool(np.isfinite(audio).all())

summary = {
    "task_id": task_id,
    "preset_id": preset_id,
    "input_audio_path": str(input_path),
    "input_vocals_path": str(metadata.get("input_vocals_path") or upload.vocals_path),
    "output_audio_path": str(output_path),
    "conditioning_report_path": str(conditioning_report_path),
    "style_emb_path": str(style_embedding_path),
    "sample_rate": int(sample_rate),
    "duration_seconds": duration_seconds,
    "has_nan_or_inf": not finite,
    "executed_internal_film": bool(conditioning_report.get("executed_internal_film")),
    "condition_mode": metadata.get("condition_mode"),
    "film_strength": metadata.get("film_strength"),
    "text_style_adapter_loaded": str(metadata.get("adapter_mode") or "") == "trained",
    "adapter_checkpoint": str(metadata.get("adapter_checkpoint_path") or ""),
    "style_prompt": metadata.get("style_prompt") or style_prompt,
    "conditioning_report_summary": {
        "executed_internal_film": conditioning_report.get("executed_internal_film"),
        "film_target": conditioning_report.get("film_target"),
        "style_emb_format": conditioning_report.get("style_emb_format"),
    },
}

project_root_runtime = str(project_root / "runtime" / "style_adapter" / "text_style_adapter_1000.pt")
if summary["adapter_checkpoint"] == project_root_runtime:
    summary["adapter_checkpoint"] = "runtime/style_adapter/text_style_adapter_1000.pt"
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

errors: list[str] = []
if not conditioning_report_path.exists():
    errors.append("conditioning_report.json missing")
if not style_embedding_path.exists():
    errors.append("style_embedding.pt missing")
if not summary["executed_internal_film"]:
    errors.append("conditioning_report.json does not contain executed_internal_film=true")
if not summary["text_style_adapter_loaded"]:
    errors.append("text_style_adapter_loaded is not true in task metadata")
if summary["adapter_checkpoint"] != "runtime/style_adapter/text_style_adapter_1000.pt":
    errors.append("adapter_checkpoint is not runtime/style_adapter/text_style_adapter_1000.pt")
if not finite:
    errors.append("output audio contains NaN/Inf")
if duration_seconds <= 0:
    errors.append("output audio duration is invalid")

print(json.dumps(summary, ensure_ascii=False, indent=2))
if errors:
    raise SystemExit("\n".join(errors))
PY
