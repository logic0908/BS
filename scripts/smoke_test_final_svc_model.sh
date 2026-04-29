#!/usr/bin/env bash
set -u

PROJECT_ROOT="/home/featurize/work/BS"
PRESET_ID="final_primary"
INPUT="$PROJECT_ROOT/StyleSinger/test/test.wav"
OUTPUT="/tmp/sovits_final_model_test.wav"

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
rm -f "$OUTPUT"

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
python "$PROJECT_ROOT/scripts/check_sovits_env.py" --input "$INPUT" --output "$OUTPUT" --run >"$CHECK_STDOUT" 2>"$CHECK_STDERR"
RETURN_CODE=$?

python - "$RETURN_CODE" "$PRESET_ID" "$INPUT" "$OUTPUT" "$STARTED_AT" "$CHECK_STDOUT" "$CHECK_STDERR" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import soundfile as sf

return_code = int(sys.argv[1])
preset_id, input_path, output_path, started_at, stdout_path, stderr_path = sys.argv[2:]
output = Path(output_path)
soundfile_ok = False
duration = 0.0
soundfile_error = ""
if output.exists():
    try:
        info = sf.info(str(output))
        duration = float(info.frames) / float(info.samplerate) if info.samplerate else 0.0
        soundfile_ok = True
    except Exception as exc:
        soundfile_error = str(exc)

payload = {
    "preset_id": preset_id,
    "input": input_path,
    "output": output_path,
    "started_at": started_at,
    "finished_at": datetime.now(timezone.utc).isoformat(),
    "return_code": return_code,
    "output_exists": output.exists(),
    "output_size": output.stat().st_size if output.exists() else 0,
    "soundfile_readable": soundfile_ok,
    "soundfile_error": soundfile_error,
    "duration_seconds": round(duration, 3),
    "success": return_code == 0 and output.exists() and output.stat().st_size > 1024 and soundfile_ok and duration >= 0.5,
    "stdout_path": stdout_path,
    "stderr_path": stderr_path,
    "model_path": os.environ.get("SOVITS_MODEL_PATH", ""),
    "config_path": os.environ.get("SOVITS_CONFIG_PATH", ""),
    "speaker": os.environ.get("SOVITS_SPEAKER", ""),
}
report_path = Path("/home/featurize/work/BS/runtime/model_search/final_model_smoke_test.json")
report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False, indent=2))
raise SystemExit(0 if payload["success"] else 1)
PY
