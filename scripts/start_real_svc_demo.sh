#!/usr/bin/env bash
set -e

cd /home/featurize/work/BS

CONDA_SH="/environment/miniconda3/etc/profile.d/conda.sh"

if [[ -f "$CONDA_SH" ]]; then
  # shellcheck disable=SC1091
  source "$CONDA_SH"
  if command -v conda >/dev/null 2>&1; then
    if conda activate base 2>/dev/null; then
      echo "[info] Activated conda base environment."
    else
      echo "[warn] conda activate base unavailable; continuing with current python: $(python -c 'import sys; print(sys.executable)')"
    fi
  else
    echo "[warn] conda command not available after sourcing conda.sh; continuing with current python: $(python -c 'import sys; print(sys.executable)')"
  fi
else
  echo "[warn] $CONDA_SH not found; continuing with current python: $(python -c 'import sys; print(sys.executable)')"
fi

python scripts/patch_fairseq_py311.py

export SOVITS_MOCK=false
export SOVITS_DEVICE=cuda
export SOVITS_REPO_DIR=/home/featurize/work/BS/so-vits-svc
export SOVITS_INFER_SCRIPT=/home/featurize/work/BS/so-vits-svc/inference_main.py
unset SOVITS_MODEL_PATH
unset SOVITS_CONFIG_PATH
unset SOVITS_SPEAKER
export SOVITS_TRANSPOSE=0
export SOVITS_TIMEOUT_SECONDS=300
export NUMBA_CACHE_DIR=/home/featurize/work/BS/runtime/numba_cache

mkdir -p "$NUMBA_CACHE_DIR"

PRESET_SUMMARY="$(python - <<'PY'
import json
from pathlib import Path

path = Path("/home/featurize/work/BS/backend/app/config/svc_model_presets.json")
if not path.exists():
    raise SystemExit(1)
payload = json.loads(path.read_text(encoding="utf-8"))
active_id = str(payload.get("active_preset_id") or "")
for preset in payload.get("presets", []):
    if str(preset.get("preset_id") or "") != active_id:
        continue
    model_path = str(preset.get("model_path") or "")
    print(f"preset_id={active_id}")
    print(f"model_basename={Path(model_path).name}")
    print(f"speaker={preset.get('speaker', '')}")
    print(f"source_repo={preset.get('source_repo', '')}")
    print(f"license={preset.get('license', '')}")
    raise SystemExit(0)
raise SystemExit(1)
PY
)" || PRESET_SUMMARY=""

echo "Starting backend in real So-VITS-SVC demo mode."
echo "SOVITS_MOCK=$SOVITS_MOCK"
echo "SOVITS_DEVICE=$SOVITS_DEVICE"
echo "active svc_model_presets.json preset takes priority over env fallback."
if [[ -n "$PRESET_SUMMARY" ]]; then
  while IFS= read -r line; do
    [[ -n "$line" ]] && echo "$line"
  done <<< "$PRESET_SUMMARY"
else
  echo "preset_id="
  echo "model_basename=$(basename "${SOVITS_MODEL_PATH:-}")"
  echo "speaker=${SOVITS_SPEAKER:-}"
  echo "source_repo="
  echo "license="
fi
echo "python=$(python -c 'import sys; print(sys.executable)')"

cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
