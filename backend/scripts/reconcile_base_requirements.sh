#!/usr/bin/env bash
# backend/scripts/reconcile_base_requirements.sh

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
BACKEND_DIR="$(dirname "$DIR")"

echo "Initial pip check..."
pip check || true

# Remove known problematic/unused packages that clutter the base environment
echo "Cleaning up irrelevant or conflicting packages..."
pip uninstall -y \
    pyannote-audio pyannote-database pyannote-core pyannote-metrics pyannote-pipeline \
    celery redis

echo "Checking core dependencies..."
pip install --no-cache-dir -r "$BACKEND_DIR/requirements-core.txt"

echo "Checking enhanced dependencies..."
pip install --no-cache-dir -r "$BACKEND_DIR/requirements-enhanced.txt"

echo "Checking dev dependencies..."
pip install --no-cache-dir -r "$BACKEND_DIR/requirements-dev.txt"

echo "Final pip check..."
pip check || true

echo "Reconciliation complete. If you encounter any ABI conflicts with WhisperX and NumPy 2, make sure tensorflow and ml_dtypes are uninstalled."
