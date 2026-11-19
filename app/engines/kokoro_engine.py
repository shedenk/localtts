from __future__ import annotations

import gc
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.engines.base import BaseTTSEngine, TTSResult, VoiceInfo

MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

DEFAULT_VOICES: list[VoiceInfo] = [
    VoiceInfo(id="af_heart", name="Heart (US)", language="en-us", gender="female"),
    VoiceInfo(id="af_bella", name="Bella (US)", language="en-us", gender="female"),
    VoiceInfo(id="af_nicole", name="Nicole (US)", language="en-us", gender="female"),
    VoiceInfo(id="af_sarah", name="Sarah (US)", language="en-us", gender="female"),
    VoiceInfo(id="af_sky", name="Sky (US)", language="en-us", gender="female"),
    VoiceInfo(id="am_adam", name="Adam (US)", language="en-us", gender="male"),
    VoiceInfo(id="am_michael", name="Michael (US)", language="en-us", gender="male"),
    VoiceInfo(id="bf_emma", name="Emma (UK)", language="en-gb", gender="female"),
    VoiceInfo(id="bf_isabella", name="Isabella (UK)", language="en-gb", gender="female"),
    VoiceInfo(id="bm_george", name="George (UK)", language="en-gb", gender="male"),
    VoiceInfo(id="bm_lewis", name="Lewis (UK)", language="en-gb", gender="male"),
]

LANG_MAP = {
    "en": "en-us",
    "en-us": "en-us",
    "en-gb": "en-gb",
}


def _download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with httpx.stream("GET", url, follow_redirects=True, timeout=180.0) as resp:
        resp.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=1024 * 256):
                f.write(chunk)
    tmp.replace(dest)


class KokoroEngine(BaseTTSEngine):
    name = "kokoro"
    display_name = "Kokoro-82M (ONNX)"
    description = "Super-fast & lightweight 82M TTS running on CPU/ONNX. Great default for macOS & VPS."
    supports_cloning = False
    supports_voice_design = False
    install_hint = "pip install kokoro-onnx"
    source_url = "https://github.com/thewh1teagle/kokoro-onnx"
    license_name = "MIT / Apache-2.0"

    def __init__(self) -> None:
        super().__init__()
        self._model: Any = None

    def is_available(self) -> bool:
        try:
            import kokoro_onnx  # noqa: F401
            return True
        except ImportError:
            return False

    def _model_paths(self) -> tuple[Path, Path]:
        base = get_settings().models_path / "kokoro"
        return base / "kokoro-v1.0.onnx", base / "voices-v1.0.bin"

    def load(self) -> None:
        if self._loaded and self._model is not None:
            return
        from kokoro_onnx import Kokoro  # type: ignore

        model_path, voices_path = self._model_paths()
        if not model_path.exists():
            _download_file(MODEL_URL, model_path)
        if not voices_path.exists():
            _download_file(VOICES_URL, voices_path)

        self._model = Kokoro(str(model_path), str(voices_path))
        self._loaded = True
        self.last_used = time.time()

    def unload(self) -> None:
        self._model = None
        self._loaded = False
        gc.collect()

    def list_voices(self) -> list[VoiceInfo]:
        if self._loaded and self._model is not None:
            try:
                known = {v.id: v for v in DEFAULT_VOICES}
                result: list[VoiceInfo] = []
                for vid in sorted(self._model.get_voices()):
                    if not vid.startswith(("af_", "am_", "bf_", "bm_")):
                        continue
                    if vid in known:
                        result.append(known[vid])
                    else:
                        gender = "female" if vid[1] == "f" else "male"
                        lang = "en-gb" if vid.startswith("b") else "en-us"
                        result.append(VoiceInfo(id=vid, name=vid, language=lang, gender=gender))
                return result
            except Exception:
                pass
        return DEFAULT_VOICES

    def synthesize(
        self,
        text: str,
        voice: str = "af_heart",
        language: str = "en-us",
        speed: float = 1.0,
        ref_audio_path: str | None = None,
        ref_text: str = "",
        instruct: str = "",
    ) -> TTSResult:
        self.load()
        self.last_used = time.time()

        chosen_voice = voice or "af_heart"
        # Map OpenAI preset names to Kokoro voices seamlessly
        openai_map = {
            "alloy": "af_heart",
            "echo": "am_adam",
            "fable": "bf_emma",
            "onyx": "am_michael",
            "nova": "af_bella",
            "shimmer": "af_sky",
        }
        chosen_voice = openai_map.get(chosen_voice.lower(), chosen_voice)

        lang_code = LANG_MAP.get(language.lower().strip(), "en-us")
        if chosen_voice.startswith("bf_") or chosen_voice.startswith("bm_"):
            if language.lower() in ("en", ""):
                lang_code = "en-gb"
        elif chosen_voice.startswith("j"):
            lang_code = "ja"
        elif chosen_voice.startswith("z"):
            lang_code = "cmn"
        elif chosen_voice.startswith("f"):
            lang_code = "fr-fr"
        elif chosen_voice.startswith("i"):
            lang_code = "it"
        elif chosen_voice.startswith("e"):
            lang_code = "es"
        elif chosen_voice.startswith("p"):
            lang_code = "pt-br"
        elif chosen_voice.startswith("h"):
            lang_code = "hi"

        samples, sample_rate = self._model.create(
            text,
            voice=chosen_voice,
            speed=float(speed),
            lang=lang_code,
        )
        self.last_used = time.time()
        return TTSResult(samples=samples, sample_rate=int(sample_rate))
