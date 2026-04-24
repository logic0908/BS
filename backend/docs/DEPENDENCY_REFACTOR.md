# Dependency Refactor & Clean-up

This document outlines the recent backend dependency and directory cleanup.

## 1. Cleaned Directories
A cleanup script (`backend/scripts/clean_backend_tree.py`) was introduced to delete non-essential environment and cache files from the `backend/` directory, ensuring it remains clean and independent of the `base` conda environment:
- Removed cache directories: `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.coverage`, `htmlcov`.
- Removed misinstalled Python package files/directories inside `backend/` (e.g., `PIL`, `numpy`, `scipy`, `matplotlib`, `libs/torch`, `libs/sympy`, etc.).
- Removed temporary and compiled files (`*.pyc`, `*.pyo`, `*.tmp`, `*.log`, `*_extract.py`).

## 2. Dependency List Refactoring
The dependency files were refactored into three layers based on the minimum required principle:

- **`requirements-core.txt`** (formerly `requirements.txt`): Contains the base dependencies strictly needed to run the legacy extraction and standard FastAPI service (e.g., `fastapi`, `uvicorn`, `torch`, `numpy>=1.24,<3`, `openai-whisper`). Removed unused packages like `celery`, `redis`, `requests`.
- **`requirements-enhanced.txt`**: Inherits from `requirements-core.txt` and contains `whisperx==3.8.5` and its pinned dependencies (`torch==2.8.0`, `torchaudio==2.8.0`, `torchvision==0.23.0`).
- **`requirements-dev.txt`**: Contains development and testing dependencies (`pytest`, `pytest-mock`, `fastapi[all]`).

## 3. Base Environment Reconciliation
To cleanly fix the existing `conda base` environment without creating a new one or causing `ResolutionImpossible` conflicts:

A new script `backend/scripts/reconcile_base_requirements.sh` was added. Its responsibilities are:
1. Run an initial `pip check` to identify existing conflicts.
2. Uninstall irrelevant/conflicting packages (like `pyannote-*`, `celery`, `redis`).
3. Re-install/calibrate dependencies cleanly by running `pip install` on the three newly layered requirement files.
4. Run a final `pip check` to ensure the environment is healthy.

## 4. Verification
After the refactoring:
- The base environment retains only the needed packages.
- The `pytest` test suite can be run to ensure capabilities, feature extraction, and endpoint health check functionalities remain intact.
- Enhanced mode will still function as expected with NumPy 2.x and WhisperX 3.8.5, as long as `tensorflow` and `ml_dtypes` are kept out of the environment.
