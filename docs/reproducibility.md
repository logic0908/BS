# Reproducibility Guide

This repository is meant to be cloneable without bundling local model weights, datasets, runtime outputs, or generated audio artifacts. To reproduce the project after cloning, prepare the codebase first, then place the required local assets in the paths described below.

## 1. Prerequisites

- Linux with Python 3.11 available
- Node.js 20.19+ recommended for Vite 7
- `ffmpeg` and `ffprobe` installed
- Redis available if you want to run Celery workers
- CUDA-capable environment if you want to reproduce real So-VITS-SVC inference instead of mock mode

## 2. Clone the repository

```bash
git clone <your-github-url> BS
cd BS
```

## 3. Install Python dependencies

Backend dependencies are maintained under `backend/requirements*.txt`.

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```

If you also want backend test and tooling dependencies:

```bash
pip install -r backend/requirements-dev.txt
```

## 4. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

## 5. Prepare local model and dependency assets

The following assets are intentionally not committed:

- `local_models/`
- `runtime/`
- `datasets/`
- `StyleSinger/data/`
- `StyleSinger/checkpoints/`
- So-VITS-SVC working tree under `so-vits-svc/`

Place the required local assets in these expected locations:

- So-VITS-SVC repo:
  - `<repo>/so-vits-svc/`
- SVC model presets:
  - `<repo>/local_models/sovits-final/final_primary/`
  - `<repo>/local_models/sovits-final/final_male_powerful/`
  - `<repo>/local_models/sovits-final/final_male_youth/`
- Text encoder cache:
  - `<repo>/local_models/text-encoders/`
- Trained TextStyleAdapter checkpoint:
  - `<repo>/runtime/style_adapter/text_style_adapter_1000.pt`
- RMVPE model if you use the real inference path:
  - `<repo>/backend/models/rmvpe/rmvpe.pt`

For preset wiring, see:

- `backend/app/config/svc_model_presets.json`
- `backend/app/config/style_library.json`
- `backend/app/config/style_adapter_config.json`

## 6. Configure environment variables

Use `backend/.env.example` as the starting template. The example file contains absolute paths from the original machine, so you must replace them with paths valid on your own server.

Typical variables to review:

- `SOVITS_REPO_DIR`
- `SOVITS_INFER_SCRIPT`
- `SOVITS_CONDITIONED_INFER_SCRIPT`
- `SOVITS_MODEL_PATH`
- `SOVITS_CONFIG_PATH`
- `SOVITS_SPEAKER`
- `SOVITS_MOCK`
- `SOVITS_CONDITION_MODE`
- `STYLE_ADAPTER_CHECKPOINT_PATH`
- `REDIS_URL`
- `SVC_USE_CELERY`

Important project conventions:

- `SOVITS_MOCK=false` for real inference
- `SOVITS_CONDITION_MODE=internal_film` to keep the validated conditioned path
- `STYLE_ADAPTER_CHECKPOINT_PATH` should point to `runtime/style_adapter/text_style_adapter_1000.pt`

## 7. Run the backend

Direct FastAPI run:

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Repository helper script:

```bash
bash scripts/start_real_svc_demo.sh
```

## 8. Run the Celery worker

If you want async task execution:

```bash
bash scripts/start_celery_worker.sh
```

Equivalent core command:

```bash
PYTHONPATH=$(pwd)/backend:$PYTHONPATH celery -A app.core.celery_app.celery_app worker --loglevel=info -Q svc
```

## 9. Run the frontend

```bash
cd frontend
npm run dev -- --host 0.0.0.0
```

## 10. Run tests

Backend:

```bash
PYTHONPATH=$(pwd)/backend:$PYTHONPATH pytest backend/tests -q
```

Frontend test:

```bash
cd frontend
npm run test -- --run
```

Frontend build:

```bash
cd frontend
npm run build
```

## 11. Notes on what is intentionally not versioned

These items stay local and should not be expected from `git clone` alone:

- model weights and checkpoints (`*.pth`, `*.pt`, `*.ckpt`, `*.onnx`, `*.safetensors`)
- runtime outputs and debug folders
- uploaded or generated audio (`*.wav`, `*.mp3`, `*.flac`)
- datasets and local caches
- frontend build output and `node_modules`

If a clone succeeds but inference fails, first verify local model placement and environment-variable paths before debugging application logic.
