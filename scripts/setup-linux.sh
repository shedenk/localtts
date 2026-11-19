#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== Local TTS & Whisper Hub — Linux Setup ==="

if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y ffmpeg espeak-ng libsndfile1 curl git
elif command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y ffmpeg espeak-ng libsndfile curl git
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

uv venv --python 3.12 --allow-existing

if [[ "${1:-}" == "--all" ]]; then
  echo "Installing All Engines (Kokoro + Edge-TTS + Faster-Whisper + OmniVoice + Qwen3-TTS)..."
  uv sync --extra omnivoice
  uv pip install --no-deps qwen-tts
else
  echo "Installing Standard mode (Kokoro + Edge-TTS + Faster-Whisper)..."
  echo "Tip: OmniVoice & Qwen3-TTS bisa diinstall langsung dari UI nanti sesuai spek!"
  uv sync
fi

echo "Pre-generating short EN/ID voice samples (Kokoro & Edge-TTS)..."
.venv/bin/python scripts/generate_samples.py kokoro edge || true

echo ""
echo "Setup complete! Start the server with:"
echo "  .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000"
