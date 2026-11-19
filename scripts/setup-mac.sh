#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== Local TTS & Whisper Hub — macOS Setup ==="

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew not found. Please install Homebrew first: https://brew.sh"
  exit 1
fi

for pkg in ffmpeg espeak-ng; do
  if ! brew list "$pkg" >/dev/null 2>&1; then
    echo "Installing $pkg via Homebrew..."
    brew install "$pkg"
  fi
done

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example (edit it to customize AUTH_USERNAME, AUTH_PASSWORD, API_KEY)."
fi

echo "Creating Python 3.12 virtualenv..."
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
echo "  ./scripts/run-mac.sh"
