from __future__ import annotations

import gc
import time
from typing import Any

from app.config import get_settings
from app.core.hardware import detect_device
from app.engines.base import BaseTTSEngine, TTSResult, VoiceInfo

OMNIVOICE_VOICES = [
    VoiceInfo(id="id_female", name="Sari (Indonesia)", language="id", gender="female"),
    VoiceInfo(id="id_male", name="Budi (Indonesia)", language="id", gender="male"),
    VoiceInfo(id="en_female", name="Clara (English)", language="en", gender="female"),
    VoiceInfo(id="en_male", name="Daniel (English)", language="en", gender="male"),
]


class OmniVoiceEngine(BaseTTSEngine):
    name = "omnivoice"
    display_name = "OmniVoice (k2-fsa)"
    description = "600+ languages (incl. Indonesian), zero-shot voice cloning & voice design."
    supports_cloning = True
    supports_voice_design = True
    min_ram_gb = 6.0
    install_hint = "uv pip install torch torchaudio omnivoice"
    source_url = "https://github.com/k2-fsa/OmniVoice"
    license_name = "Apache-2.0"

    def __init__(self) -> None:
        super().__init__()
        self._model: Any = None

    def is_available(self) -> bool:
        try:
            import omnivoice  # noqa: F401
            import torch  # noqa: F401
            return True
        except ImportError:
            return False

    def load(self) -> None:
        if self._loaded and self._model is not None:
            return
        import torch  # type: ignore
        from omnivoice import OmniVoice  # type: ignore

        settings = get_settings()
        dev = detect_device()
        dtype = torch.float16 if dev == "cuda" else torch.float32
        device_map = "cuda:0" if dev == "cuda" else dev

        self._model = OmniVoice.from_pretrained(
            settings.omnivoice_model_id,
            device_map=device_map,
            dtype=dtype,
            load_asr=True,
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
        return OMNIVOICE_VOICES

    def synthesize(
        self,
        text: str,
        voice: str = "default",
        language: str = "id",
        speed: float = 1.0,
        ref_audio_path: str | None = None,
        ref_text: str = "",
        instruct: str = "",
    ) -> TTSResult:
        self.load()
        self.last_used = time.time()

        kwargs: dict[str, Any] = {"text": text}
        if language and language != "auto":
            kwargs["language"] = language
        if speed != 1.0:
            kwargs["speed"] = float(speed)

        if ref_audio_path:
            kwargs["ref_audio"] = ref_audio_path
            if ref_text:
                kwargs["ref_text"] = ref_text
        elif instruct:
            kwargs["instruct"] = instruct
        elif voice in ("id_female", "en_female", "female_warm"):
            kwargs["instruct"] = "female, warm, clear, natural speaking voice"
        elif voice in ("id_male", "en_male", "male_calm"):
            kwargs["instruct"] = "male, calm, clear, natural speaking voice"

        audio = self._model.generate(**kwargs)
        # OmniVoice typically returns (samples, sr) or tensor
        if isinstance(audio, tuple):
            samples, sr = audio[0], int(audio[1])
        else:
            samples, sr = audio, 24000

        if hasattr(samples, "detach"):
            samples = samples.detach().cpu().numpy()

        self.last_used = time.time()
        return TTSResult(samples=samples, sample_rate=sr)
