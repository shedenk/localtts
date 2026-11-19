from __future__ import annotations

import gc
import time
from typing import Any

from app.config import get_settings
from app.core.hardware import detect_device
from app.engines.base import BaseTTSEngine, TTSResult, VoiceInfo

QWEN3_VOICES = [
    VoiceInfo(id="Vivian", name="Vivian (English)", language="en", gender="female"),
    VoiceInfo(id="Serena", name="Serena (English)", language="en", gender="female"),
    VoiceInfo(id="Dylan", name="Dylan (English)", language="en", gender="male"),
    VoiceInfo(id="Eric", name="Eric (English)", language="en", gender="male"),
    VoiceInfo(id="Ryan", name="Ryan (English)", language="en", gender="male"),
    VoiceInfo(id="Aiden", name="Aiden (English)", language="en", gender="male"),
]


class Qwen3TTSEngine(BaseTTSEngine):
    name = "qwen3"
    display_name = "Qwen3-TTS (Alibaba)"
    description = "Expressive multilingual TTS (0.6B/1.7B) with 3s voice cloning & instruction control."
    supports_cloning = True
    supports_voice_design = True
    min_ram_gb = 6.0
    install_hint = "uv pip install torch torchaudio qwen-tts"
    source_url = "https://github.com/QwenLM/Qwen3-TTS"
    license_name = "Apache-2.0"

    def __init__(self) -> None:
        super().__init__()
        self._model: Any = None

    def is_available(self) -> bool:
        try:
            import qwen_tts  # noqa: F401
            import torch  # noqa: F401
            return True
        except ImportError:
            return False

    def load(self) -> None:
        if self._loaded and self._model is not None:
            return
        import torch  # type: ignore
        from qwen_tts import Qwen3TTSModel  # type: ignore

        settings = get_settings()
        dev = detect_device()
        dtype = torch.bfloat16 if dev == "cuda" else torch.float32
        device_map = "cuda:0" if dev == "cuda" else dev

        self._model = Qwen3TTSModel.from_pretrained(
            settings.qwen3_model_id,
            device_map=device_map,
            dtype=dtype,
        )
        self._loaded = True
        self.last_used = time.time()

    def unload(self) -> None:
        self._model = None
        self._loaded = False
        gc.collect()
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            elif hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
                torch.mps.empty_cache()
        except Exception:
            pass

    def list_voices(self) -> list[VoiceInfo]:
        return QWEN3_VOICES

    def synthesize(
        self,
        text: str,
        voice: str = "Vivian",
        language: str = "English",
        speed: float = 1.0,
        ref_audio_path: str | None = None,
        ref_text: str = "",
        instruct: str = "",
    ) -> TTSResult:
        self.load()
        self.last_used = time.time()

        lang_map = {
            "en": "English",
            "en-us": "English",
            "zh": "Chinese",
            "ja": "Japanese",
            "ko": "Korean",
            "de": "German",
            "fr": "French",
            "ru": "Russian",
            "pt": "Portuguese",
            "es": "Spanish",
            "it": "Italian",
        }
        lang_name = lang_map.get(language.lower().strip(), language or "Auto")

        if ref_audio_path and hasattr(self._model, "generate_voice_clone"):
            wavs, sr = self._model.generate_voice_clone(
                text=text,
                language=lang_name,
                ref_audio=ref_audio_path,
                ref_text=ref_text or "",
            )
        else:
            speaker = voice if voice in {v.id for v in QWEN3_VOICES} else "Vivian"
            wavs, sr = self._model.generate_custom_voice(
                text=text,
                language=lang_name,
                speaker=speaker,
                instruct=instruct or "",
            )

        samples = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
        if hasattr(samples, "detach"):
            samples = samples.detach().cpu().numpy()

        self.last_used = time.time()
        return TTSResult(samples=samples, sample_rate=int(sr))
