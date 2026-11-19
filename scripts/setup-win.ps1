$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "=== Local TTS & Whisper Hub — Windows Setup ===" -ForegroundColor Cyan

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Warning "ffmpeg not found in PATH. Install it via: winget install Gyan.FFmpeg"
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example"
}

uv venv --python 3.12 --allow-existing

if ($args -contains "--all") {
    Write-Host "Installing All Engines (Kokoro + Edge-TTS + Faster-Whisper + OmniVoice + Qwen3-TTS)..."
    uv sync --extra omnivoice
    uv pip install --no-deps qwen-tts
} else {
    Write-Host "Installing Standard mode (Kokoro + Edge-TTS + Faster-Whisper)..."
    Write-Host "Tip: OmniVoice & Qwen3-TTS bisa diinstall langsung dari UI nanti sesuai spek!"
    uv sync
}

Write-Host "Pre-generating short EN/ID voice samples (Kokoro & Edge-TTS)..."
.\.venv\Scripts\python.exe scripts\generate_samples.py kokoro edge

Write-Host ""
Write-Host "Setup complete! Start the server with:" -ForegroundColor Green
Write-Host "  .\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000"
