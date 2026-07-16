#!/usr/bin/env bash
# Create venv, install requirements, start gnomAD Parquet API.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
VENV="${VENV:-$ROOT/.venv}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8923}"
export GNOMAD_PARQUET_ROOT="${GNOMAD_PARQUET_ROOT:-/data/agent/gnomad/data}"

if [[ ! -d "$VENV" ]]; then
  echo "Creating venv: $VENV"
  "$PYTHON" -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

python -m pip install -U pip
python -m pip install -r api/requirements.txt

echo "GNOMAD_PARQUET_ROOT=$GNOMAD_PARQUET_ROOT"
echo "Starting uvicorn on ${HOST}:${PORT}"
exec python -m uvicorn api.app:app --host "$HOST" --port "$PORT"
