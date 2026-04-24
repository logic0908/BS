#!/usr/bin/env bash

pip uninstall -y whisperx faster-whisper ctranslate2
pip uninstall -y torch torchaudio torchvision
pip uninstall -y pyannote-audio pyannote-database pyannote-core pyannote-metrics pyannote-pipeline

pip install --no-cache-dir "numpy>=2.1,<3"
pip install --no-cache-dir "torch==2.8.0" "torchaudio==2.8.0" "torchvision==0.23.0"
pip install --no-cache-dir "whisperx==3.8.5"
pip install --no-cache-dir -r requirements-core.txt
