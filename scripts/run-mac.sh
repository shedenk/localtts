#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  echo ".venv not found. Running ./scripts/setup-mac.sh first..."
  ./scripts/setup-mac.sh
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
fi

PORT_VAL=$(grep -E '^PORT=' .env | cut -d '=' -f2 | tr -d '[:space:]' || true)
PORT_VAL=${PORT_VAL:-8000}

echo "Starting Local TTS & Whisper Hub on http://localhost:${PORT_VAL} ..."
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT_VAL}"
