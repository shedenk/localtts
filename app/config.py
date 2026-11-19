from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "LocalTTS"
    host: str = "0.0.0.0"
    port: int = 8000

    # UI Auth
    auth_username: str = ""
    auth_password: str = ""
    session_secret: str = "tts-local-dev-secret-change-in-production"

    # API Auth (empty = open access)
    api_key: str = ""
    api_key_header: str = "X-API-Key"

    # Hardware & Engines
    device: str = "auto"
    enabled_engines: str = "kokoro,edge,whisper,omnivoice,qwen3"
    idle_unload_seconds: int = 300

    # Storage
    data_dir: str = "./data"
    models_dir: str = "./models"

    # Model IDs
    whisper_default_model: str = "base"
    qwen3_model_id: str = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
    omnivoice_model_id: str = "k2-fsa/OmniVoice"

    @property
    def ui_auth_enabled(self) -> bool:
        return bool(self.auth_username.strip() and self.auth_password.strip())

    @property
    def api_auth_enabled(self) -> bool:
        return bool(self.api_key.strip())

    @property
    def enabled_engine_list(self) -> list[str]:
        return [e.strip().lower() for e in self.enabled_engines.split(",") if e.strip()]

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir).resolve()

    @property
    def models_path(self) -> Path:
        return Path(self.models_dir).resolve()

    @property
    def outputs_path(self) -> Path:
        return self.data_path / "outputs"

    @property
    def voices_path(self) -> Path:
        return self.data_path / "voices"

    @property
    def samples_path(self) -> Path:
        return self.data_path / "samples"

    @property
    def db_path(self) -> Path:
        return self.data_path / "tts_local.db"

    def ensure_dirs(self) -> None:
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.outputs_path.mkdir(parents=True, exist_ok=True)
        self.voices_path.mkdir(parents=True, exist_ok=True)
        self.samples_path.mkdir(parents=True, exist_ok=True)
        hf_cache = self.models_path / "hf"
        hf_cache.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("HF_HOME", str(hf_cache))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
