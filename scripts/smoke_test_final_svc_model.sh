#!/usr/bin/env bash
set -u

PROJECT_ROOT="/home/featurize/work/BS"
PRESET_ID="final_primary"
INPUT="$PROJECT_ROOT/StyleSinger/test/test.wav"
OUTPUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --preset-id)
      PRESET_ID="$2"
      shift 2
      ;;
    --input)
      INPUT="$2"
      shift 2
      ;;
    --output)
      OUTPUT="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

mkdir -p "$PROJECT_ROOT/runtime/model_search" "$PROJECT_ROOT/runtime/numba_cache"
if [[ -z "$OUTPUT" ]]; then
  OUTPUT="/tmp/${PRESET_ID}_smoke_test.wav"
fi
rm -f "$OUTPUT"
TASK_ID="smoke-${PRESET_ID}-$(date +%s)"
TASK_DEBUG_DIR="$PROJECT_ROOT/runtime/debug/$TASK_ID"
rm -rf "$TASK_DEBUG_DIR"
mkdir -p "$TASK_DEBUG_DIR"

PRESET_JSON="$(python - "$PRESET_ID" <<'PY'
import json
import sys
from pathlib import Path

project = Path("/home/featurize/work/BS")
preset_id = sys.argv[1]
payload = json.loads((project / "backend/app/config/svc_model_presets.json").read_text(encoding="utf-8"))
for preset in payload.get("presets", []):
    if preset.get("preset_id") == preset_id:
        print(json.dumps(preset, ensure_ascii=False))
        raise SystemExit(0)
print(json.dumps({"error": f"preset not found: {preset_id}"}, ensure_ascii=False))
raise SystemExit(1)
PY
)"
if [[ $? -ne 0 ]]; then
  echo "$PRESET_JSON" >&2
  exit 1
fi

export SOVITS_MOCK=false
export SVC_MODEL_PRESET_ID="$PRESET_ID"
export SOVITS_DEVICE=cuda
export SOVITS_REPO_DIR="$PROJECT_ROOT/so-vits-svc"
export SOVITS_INFER_SCRIPT="$PROJECT_ROOT/so-vits-svc/inference_main.py"
export SOVITS_MODEL_PATH="$(python -c 'import json,sys; print(json.loads(sys.argv[1]).get("model_path",""))' "$PRESET_JSON")"
export SOVITS_CONFIG_PATH="$(python -c 'import json,sys; print(json.loads(sys.argv[1]).get("config_path",""))' "$PRESET_JSON")"
export SOVITS_SPEAKER="$(python -c 'import json,sys; print(json.loads(sys.argv[1]).get("speaker",""))' "$PRESET_JSON")"
export SOVITS_TIMEOUT_SECONDS=300
export NUMBA_CACHE_DIR="$PROJECT_ROOT/runtime/numba_cache"

STARTED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
CHECK_STDOUT="$PROJECT_ROOT/runtime/model_search/final_model_smoke_test.stdout.jsonl"
CHECK_STDERR="$PROJECT_ROOT/runtime/model_search/final_model_smoke_test.stderr.log"
python "$PROJECT_ROOT/scripts/check_sovits_env.py" \
  --input "$INPUT" \
  --output "$OUTPUT" \
  --task-id "$TASK_ID" \
  --style-preset-id "$PRESET_ID" \
  --allow-unconfigured-preset-smoke \
  --run >"$CHECK_STDOUT" 2>"$CHECK_STDERR"
RETURN_CODE=$?

python - "$RETURN_CODE" "$PRESET_ID" "$INPUT" "$OUTPUT" "$STARTED_AT" "$CHECK_STDOUT" "$CHECK_STDERR" "$TASK_ID" "$PROJECT_ROOT" "$PRESET_JSON" <<'PY'
import json
import sys
from pathlib import Path

return_code = int(sys.argv[1])
(
    preset_id,
    input_path,
    output_path,
    started_at,
    stdout_path,
    stderr_path,
    task_id,
    project_root,
    preset_json,
) = sys.argv[2:]
sys.path.insert(0, str(Path(project_root) / "backend"))
from app.services.svc_smoke_validation import build_smoke_report  # noqa: E402

preset_payload = json.loads(preset_json)
payload = build_smoke_report(
    project_root=Path(project_root),
    preset_id=preset_id,
    expected_speaker=str(preset_payload.get("speaker") or ""),
    input_path=input_path,
    output_path=output_path,
    started_at=started_at,
    stdout_path=stdout_path,
    stderr_path=stderr_path,
    task_id=task_id,
    return_code=return_code,
)
report_path = Path(f"/home/featurize/work/BS/runtime/model_search/{preset_id}_smoke_test.json")
report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
install_report_path = Path(f"/home/featurize/work/BS/local_models/sovits-final/{preset_id}/install_report.json")
try:
    install_payload = json.loads(install_report_path.read_text(encoding="utf-8")) if install_report_path.exists() else {}
except Exception:
    install_payload = {}
install_payload["preset_id"] = install_payload.get("preset_id") or preset_id
install_payload["smoke_test_status"] = "passed" if payload["success"] else "failed"
install_payload["smoke_test_output_path"] = output_path
install_payload["smoke_test_task_id"] = task_id
install_payload["smoke_test_return_code"] = return_code
install_payload["smoke_test_report_path"] = str(report_path)
install_report_path.write_text(json.dumps(install_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False, indent=2))
raise SystemExit(0 if payload["success"] else 1)
PY
