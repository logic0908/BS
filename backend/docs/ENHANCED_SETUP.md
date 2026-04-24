# Enhanced Feature Extraction Setup

This project supports two feature extraction modes:

- `legacy`: plain Whisper + Parselmouth, fallback-friendly
- `enhanced`: WhisperX + RMVPE, strict dependency check, no silent fallback

## Why Enhanced Can Fail

The most common enhanced runtime failure in this project is not a missing module.
It is a native ABI conflict:

- `whisperx`
- `transformers`
- unexpected TensorFlow import path
- `ml_dtypes`
- NumPy 2.x incompatible native extension

Typical errors include:

- `_ARRAY_API not found`
- `numpy.core.umath failed to import`

To avoid this, WhisperX 3.8.5 officially requires NumPy 2.1+.
Previously, using `numpy<2` was an incorrect strategy that led to `ResolutionImpossible`.
The current correct strategy is:
- The enhanced stack uses NumPy 2 (e.g. `numpy>=2.1,<3`).
- Do not retain `tensorflow` or `ml_dtypes` in the base environment to avoid ABI conflicts with NumPy 2.

## RMVPE Source

- Engineering integration source: `xavriley/RMVPE`
- Vendored path: `backend/third_party/RMVPE`
- Pinned commit: `37a4b6254c4fa6eb73898177aa4e70749eb665f3`
- Algorithm / paper origin: `Dream-High/RMVPE`
- Paper: `RMVPE: A Robust Model for Vocal Pitch Estimation in Polyphonic Music`

## Required Dependencies

- Python packages:
  - `openai-whisper`
- RMVPE Python module:
  - automatically vendored into the project by `backend/scripts/setup_rmvpe.py`
  - must provide `from rmvpe import RMVPE`
- System dependency:
  - `ffmpeg`
- Model asset:
  - auto-downloaded to `backend/models/rmvpe/rmvpe.pt`
  - exposed as `RMVPE_MODEL_PATH`

## Install

### Pip

```bash
cd backend
pip install -r requirements-core.txt
```

This installs the base backend environment.

### Enhanced Dependencies

```bash
cd backend
pip install -r requirements-enhanced.txt
```

`requirements-enhanced.txt` configures the stack for WhisperX 3.8.5:

- `numpy>=2.1,<3`
- `whisperx==3.8.5`
- `torch==2.8.0`, `torchaudio==2.8.0`, `torchvision==0.23.0`

Do not rely on `pip install rmvpe` as a base environment step. This project vendors RMVPE locally instead.

Avoid installing these into the base environment because they may pull in old `ml-dtypes` builds compiled against NumPy 1.x, which will conflict with NumPy 2.x:

- `tensorflow`
- `tensorflow-cpu`
- `ml-dtypes`

### RMVPE Setup

Run:

```bash
python backend/scripts/setup_rmvpe.py
```

The setup script will:

- download `xavriley/RMVPE` into `backend/third_party/RMVPE` if missing
- pin it to commit `37a4b6254c4fa6eb73898177aa4e70749eb665f3`
- try `pip install -e backend/third_party/RMVPE`
- fall back to vendored import path if editable install is unavailable
- download the RMVPE model to `backend/models/rmvpe/rmvpe.pt`
- validate that `from rmvpe import RMVPE` and model loading both work

### ffmpeg

Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

## Environment

Copy the example env file and update the RMVPE model path:

```bash
cp .env.example .env
```

Required setting:

```bash
RMVPE_PYTHON_PATH=/home/featurize/work/BS/backend/third_party/RMVPE
RMVPE_MODEL_PATH=/home/featurize/work/BS/backend/models/rmvpe/rmvpe.pt
```

Optional settings:

```bash
FEATURE_EXTRACTION_MODE=enhanced
WHISPER_MODEL_SIZE=base
WHISPERX_MODEL_SIZE=small
WHISPERX_COMPUTE_TYPE=int8
PITCH_BACKEND=rmvpe
```

## Verify Installation

Run the stack checker:

```bash
python backend/scripts/check_enhanced_stack.py
```

Run the RMVPE setup script directly:

```bash
python backend/scripts/setup_rmvpe.py
```

Expected output:

- `OK: enhanced stack is ready`
- `rmvpe_module_ready=true`
- `rmvpe_model_ready=true`

If dependencies are missing, the script prints a missing list and exits with a non-zero status.

The checker verifies all of the following:

- `import whisperx`
- `numpy.__version__`
- whether `tensorflow` / `tensorflow-cpu` is installed
- whether `ml-dtypes` is installed
- whether WhisperX runtime is safe to use in the current environment
- `import rmvpe` from editable install or vendored path
- `ffmpeg -version`
- `RMVPE_MODEL_PATH` exists and is readable

The `/api/v1/capabilities` response also reports:

- `numpy_version`
- `tensorflow_installed`
- `ml_dtypes_installed`
- `whisperx_runtime_ok`
- `whisperx_runtime_reason`
