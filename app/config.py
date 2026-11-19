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

    # Limits (0 = unlimited)
    tts_max_chars: int = 5000
    stt_max_file_mb: int = 50

    # Default Webhook URL (optional, overridden by per-job webhook_url)
    webhook_url: str = ""
    # Allow localhost / 127.0.0.1 for local webhook/file_url testing (set false on strict public VPS)
    allow_local_urls: bool = True

    # Storage
    data_dir: str = "./data"
    models_dir: str = "./models"

    # Storage Auto-Clean & Retention (.env)
    auto_clean_disk_percent: int = 75       # Ambang batas disk usage (%) sebelum auto-clean (default 75%)
    auto_clean_retention_days: int = 30     # Hapus file audio output lebih dari X hari (default 30 hari)
    log_retention_days: int = 3             # Hapus/rotasi log sistem lebih dari X hari (default 3 hari)
    log_max_mb: int = 10                    # Maksimum ukuran file log dalam MB sebelum dirotasi (default 10 MB)

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

    @property
    def log_path(self) -> Path:
        return self.data_path / "localtts.log"

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


def update_env_file(updates: dict[str, Any], env_path: Path | str = ".env") -> dict[str, str]:
    path = Path(env_path)
    lines: list[str] = []
    found_keys: set[str] = set()

    if path.exists():
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    elif Path(".env.example").exists():
        raw_lines = Path(".env.example").read_text(encoding="utf-8").splitlines()
    else:
        raw_lines = []

    for line in raw_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _ = stripped.split("=", 1)
            k = k.strip()
            if k in updates:
                val = updates[k]
                if isinstance(val, bool):
                    v_str = "true" if val else "false"
                else:
                    v_str = str(val) if val is not None else ""
                lines.append(f"{k}={v_str}")
                found_keys.add(k)
            else:
                lines.append(line)
        else:
            lines.append(line)

    for k, val in updates.items():
        if k not in found_keys:
            if isinstance(val, bool):
                v_str = "true" if val else "false"
            else:
                v_str = str(val) if val is not None else ""
            lines.append(f"{k}={v_str}")

    content = "\n".join(lines).strip() + "\n"
    path.write_text(content, encoding="utf-8")

    # Update os.environ
    for k, val in updates.items():
        if isinstance(val, bool):
            os.environ[k] = "true" if val else "false"
        else:
            os.environ[k] = str(val) if val is not None else ""

    get_settings.cache_clear()
    return {k: str(val) for k, val in updates.items()}
