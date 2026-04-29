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
export SOVITS_MODEL_PATH=/home/featurize/work/BS/local_models/sovits-test/minecraft_villager/G_4000.pth
export SOVITS_CONFIG_PATH=/home/featurize/work/BS/local_models/sovits-test/minecraft_villager/config.json
export SOVITS_SPEAKER=villager
export SOVITS_TRANSPOSE=0
export SOVITS_TIMEOUT_SECONDS=300
export NUMBA_CACHE_DIR=/home/featurize/work/BS/runtime/numba_cache

mkdir -p "$NUMBA_CACHE_DIR"

echo "Starting backend in real So-VITS-SVC demo mode."
echo "SOVITS_MOCK=$SOVITS_MOCK"
echo "SOVITS_DEVICE=$SOVITS_DEVICE"
echo "model=$(basename "$SOVITS_MODEL_PATH")"
echo "speaker=$SOVITS_SPEAKER"
echo "python=$(python -c 'import sys; print(sys.executable)')"

cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
