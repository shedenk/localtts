from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

from app.config import get_settings
from app.engines.base import BaseEngine, BaseTTSEngine, BaseSTTEngine
from app.engines.kokoro_engine import KokoroEngine
from app.engines.edge_engine import EdgeTTSEngine
from app.engines.whisper_engine import WhisperEngine
from app.engines.omnivoice_engine import OmniVoiceEngine
from app.engines.qwen3_engine import Qwen3TTSEngine


class EngineManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._engines: dict[str, BaseEngine] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        enabled = set(get_settings().enabled_engine_list)
        all_engines: list[BaseEngine] = [
            KokoroEngine(),
            EdgeTTSEngine(),
            OmniVoiceEngine(),
            Qwen3TTSEngine(),
            WhisperEngine(),
        ]
        for eng in all_engines:
            if not enabled or eng.name in enabled:
                self._engines[eng.name] = eng

    def reload_enabled_engines(self) -> None:
        """Reload registered engines according to current settings.enabled_engine_list."""
        with self._lock:
            enabled = set(get_settings().enabled_engine_list)
            all_engines: list[BaseEngine] = [
                KokoroEngine(),
                EdgeTTSEngine(),
                OmniVoiceEngine(),
                Qwen3TTSEngine(),
                WhisperEngine(),
            ]
            self._engines.clear()
            for eng in all_engines:
                if not enabled or eng.name in enabled:
                    self._engines[eng.name] = eng

    def get(self, name: str) -> BaseEngine:
        key = name.strip().lower()
        # Aliases for convenience (e.g. OpenAI model names)
        aliases = {
            "tts-1": "kokoro",
            "tts-1-hd": "kokoro",
            "kokoro-82m": "kokoro",
            "edge-tts": "edge",
            "qwen3-tts": "qwen3",
            "whisper-1": "whisper",
            "faster-whisper": "whisper",
        }
        key = aliases.get(key, key)
        if key not in self._engines:
            raise KeyError(f"Engine '{name}' is not enabled or unknown.")
        return self._engines[key]

    def get_tts(self, name: str) -> BaseTTSEngine:
        eng = self.get(name)
        if not isinstance(eng, BaseTTSEngine):
            raise ValueError(f"Engine '{name}' is not a TTS engine.")
        return eng

    def get_stt(self, name: str = "whisper") -> BaseSTTEngine:
        eng = self.get(name)
        if not isinstance(eng, BaseSTTEngine):
            raise ValueError(f"Engine '{name}' is not an STT engine.")
        return eng

    def list_all(self) -> list[dict[str, Any]]:
        result = []
        for eng in self._engines.values():
            info = eng.info()
            if isinstance(eng, BaseTTSEngine):
                info["voices"] = [v.__dict__ for v in eng.list_voices()]
            result.append(info)
        return result

    def load_engine(self, name: str) -> dict[str, Any]:
        with self._lock:
            eng = self.get(name)
            if not eng.is_available():
                raise RuntimeError(
                    f"Engine '{eng.display_name}' dependencies not installed. Run: {eng.install_hint}"
                )
            eng.load()
            return eng.info()

    def unload_engine(self, name: str) -> dict[str, Any]:
        with self._lock:
            eng = self.get(name)
            eng.unload()
            return eng.info()

    def unload_idle(self) -> list[str]:
        timeout = get_settings().idle_unload_seconds
        if timeout <= 0:
            return []
        now = time.time()
        unloaded: list[str] = []
        with self._lock:
            for name, eng in self._engines.items():
                if eng.is_loaded() and eng.last_used > 0 and (now - eng.last_used) >= timeout:
                    eng.unload()
                    unloaded.append(name)
        return unloaded

    def unload_all(self) -> None:
        with self._lock:
            for eng in self._engines.values():
                if eng.is_loaded():
                    eng.unload()


_manager: EngineManager | None = None


def get_manager() -> EngineManager:
    global _manager
    if _manager is None:
        _manager = EngineManager()
    return _manager


async def idle_cleanup_loop(stop_event: asyncio.Event) -> None:
    mgr = get_manager()
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            mgr.unload_idle()
