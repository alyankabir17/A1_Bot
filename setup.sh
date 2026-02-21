#!/usr/bin/env bash
set -euo pipefail

# One-command local setup for Goethe A1 booking helper (Linux/macOS)
# Usage:
#   chmod +x setup.sh
#   ./setup.sh

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: $PYTHON_BIN not found. Install Python 3.9+ first." >&2
  exit 1
fi

"$PYTHON_BIN" -m venv "$VENV_DIR"
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip
pip install -r requirements.txt

echo
echo "Setup complete."
echo "Activate env with: source $VENV_DIR/bin/activate"
echo "Run helper with:   python booking_helper.py --config config.csv --start-monitoring-at now"
