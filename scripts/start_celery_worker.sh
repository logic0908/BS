#!/usr/bin/env bash
set -e

cd /home/featurize/work/BS

CONDA_SH="/environment/miniconda3/etc/profile.d/conda.sh"

if [[ -f "$CONDA_SH" ]]; then
  # shellcheck disable=SC1091
  source "$CONDA_SH"
  if command -v conda >/dev/null 2>&1; then
    if conda activate base 2>/dev/null; then
      echo "[info] Activated conda base environment for Celery worker."
    else
      echo "[warn] conda activate base unavailable; continuing with current python: $(python -c 'import sys; print(sys.executable)')"
    fi
  else
    echo "[warn] conda command not available after sourcing conda.sh; continuing with current python: $(python -c 'import sys; print(sys.executable)')"
  fi
else
  echo "[warn] $CONDA_SH not found; continuing with current python: $(python -c 'import sys; print(sys.executable)')"
fi

export PYTHONPATH="/home/featurize/work/BS/backend${PYTHONPATH:+:$PYTHONPATH}"
export SVC_USE_CELERY=true
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

echo "Starting Celery worker in real So-VITS-SVC mode."
echo "python=$(python -c 'import sys; print(sys.executable)')"
echo "PYTHONPATH=$PYTHONPATH"
echo "SVC_USE_CELERY=$SVC_USE_CELERY"
echo "SOVITS_MOCK=$SOVITS_MOCK"
echo "SOVITS_DEVICE=$SOVITS_DEVICE"
echo "SOVITS_REPO_DIR=$SOVITS_REPO_DIR"
echo "SOVITS_INFER_SCRIPT=$SOVITS_INFER_SCRIPT"
echo "NUMBA_CACHE_DIR=$NUMBA_CACHE_DIR"
echo "Worker must share the same base environment and SOVITS_* variables as FastAPI."

celery -A app.core.celery_app.celery_app worker --loglevel=info -Q svc
