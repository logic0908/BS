#!/usr/bin/env bash
set -euo pipefail

cd /home/featurize/work/BS

PYTHONPATH="${PYTHONPATH:-}"
export PYTHONPATH=/home/featurize/work/BS/backend:$PYTHONPATH
export SVC_USE_CELERY=true
export SOVITS_MOCK=false
export SOVITS_DEVICE=cuda
export CUDA_VISIBLE_DEVICES=0
export NVIDIA_VISIBLE_DEVICES=0
export NUMBA_CACHE_DIR=/home/featurize/work/BS/runtime/numba_cache
export PYTORCH_NVML_BASED_CUDA_CHECK=1

export SOVITS_REPO_DIR=/home/featurize/work/BS/so-vits-svc
export SOVITS_INFER_SCRIPT=/home/featurize/work/BS/so-vits-svc/inference_main.py
unset SOVITS_MODEL_PATH
unset SOVITS_CONFIG_PATH
unset SOVITS_SPEAKER
export SOVITS_TRANSPOSE=0
export SOVITS_TIMEOUT_SECONDS=300

mkdir -p "$NUMBA_CACHE_DIR"

echo "Starting dedicated GPU Celery worker in solo mode."
echo "python=$(python -c 'import sys; print(sys.executable)')"
echo "PYTHONPATH=$PYTHONPATH"
echo "SVC_USE_CELERY=$SVC_USE_CELERY"
echo "SOVITS_MOCK=$SOVITS_MOCK"
echo "SOVITS_DEVICE=$SOVITS_DEVICE"
echo "CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"
echo "NVIDIA_VISIBLE_DEVICES=$NVIDIA_VISIBLE_DEVICES"
echo "NUMBA_CACHE_DIR=$NUMBA_CACHE_DIR"
echo "PYTORCH_NVML_BASED_CUDA_CHECK=$PYTORCH_NVML_BASED_CUDA_CHECK"
echo "Worker must share the same SOVITS_* environment contract as FastAPI."

celery -A app.core.celery_app.celery_app worker --loglevel=info -Q svc --pool=solo --concurrency=1
