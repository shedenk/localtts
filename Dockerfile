FROM python:3.12-slim

ARG INSTALL_ALL_ENGINES=false

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PORT=8000 \
    DATA_DIR=/app/data \
    MODELS_DIR=/app/models \
    HF_HOME=/app/models/hf

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libsndfile1 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml ./
RUN uv venv /app/.venv && \
    if [ "$INSTALL_ALL_ENGINES" = "true" ]; then \
      uv sync --no-install-project --extra omnivoice && \
      uv venv /app/.venv-qwen3 --python 3.12 && \
      uv pip install --python /app/.venv-qwen3/bin/python torch torchaudio qwen-tts; \
    else \
      uv sync --no-install-project; \
    fi

COPY app ./app
COPY web ./web
COPY .env.example ./

RUN mkdir -p /app/data /app/models

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${PORT}/health || exit 1

CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
