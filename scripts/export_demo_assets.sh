#!/usr/bin/env bash
set -e

cd /home/featurize/work/BS

mkdir -p demo/debug

INPUT_SRC="/home/featurize/work/BS/StyleSinger/test/test.wav"
INPUT_DST="/home/featurize/work/BS/demo/input_valid.wav"
OUTPUT_SRC="/tmp/sovits_real_test_cuda.wav"
OUTPUT_DST="/home/featurize/work/BS/demo/output_sovits_real.wav"
DEBUG_SRC="/home/featurize/work/BS/runtime/debug/check_sovits_env/sovits_command.txt"
DEBUG_DST="/home/featurize/work/BS/demo/debug/sovits_command.txt"

if [[ -f "$INPUT_SRC" ]]; then
  cp "$INPUT_SRC" "$INPUT_DST"
  echo "[ok] copied input to $INPUT_DST"
else
  echo "[warn] missing input source: $INPUT_SRC"
fi

if [[ -f "$OUTPUT_SRC" ]]; then
  cp "$OUTPUT_SRC" "$OUTPUT_DST"
  echo "[ok] copied output to $OUTPUT_DST"
else
  echo "[warn] missing real output: $OUTPUT_SRC"
  echo "[hint] Run: bash scripts/run_sovits_real_cuda_check.sh"
fi

if [[ -f "$DEBUG_SRC" ]]; then
  cp "$DEBUG_SRC" "$DEBUG_DST"
  echo "[ok] copied debug log to $DEBUG_DST"
else
  echo "[warn] missing debug log: $DEBUG_SRC"
fi

cat > /home/featurize/work/BS/demo/README.md <<'EOF'
# Demo Assets

- `input_valid.wav`：真实可读输入音频。
- `output_sovits_real.wav`：真实 So-VITS-SVC CUDA 输出。
- `debug/sovits_command.txt`：真实推理命令、stdout/stderr、return_code、selected_output 等记录。

说明：

- 当前 `villager` 模型是技术验收模型，用于证明真实 So-VITS-SVC CUDA 推理链路可用。
- 它不代表最终“清亮女声 / 厚重女声”等目标效果模型。
EOF

for path in demo/input_valid.wav demo/output_sovits_real.wav demo/debug/sovits_command.txt; do
  if [[ -e "$path" ]]; then
    ls -lh "$path"
  else
    echo "[warn] not exported: $path"
  fi
done
