#!/usr/bin/env bash
set -e

cd /home/featurize/work/BS

INPUT="${1:-/home/featurize/work/BS/StyleSinger/test/test.wav}"
OUTPUT="${2:-/tmp/sovits_real_test_cuda.wav}"
DEBUG_COMMAND_PATH="/home/featurize/work/BS/runtime/debug/check_sovits_env/sovits_command.txt"

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

python scripts/check_sovits_env.py \
  --input "$INPUT" \
  --output "$OUTPUT" \
  --run

if [[ -f "$OUTPUT" ]] && [[ "$(wc -c < "$OUTPUT")" -gt 1024 ]]; then
  echo "Real So-VITS-SVC CUDA check passed."
  echo "output=$OUTPUT"
else
  echo "Real So-VITS-SVC CUDA check failed."
  echo "Inspect debug command log: $DEBUG_COMMAND_PATH"
  exit 1
fi
