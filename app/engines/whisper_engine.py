from __future__ import annotations

import gc
import io
import shutil
import subprocess
import time
from typing import Any

import soundfile as sf

from app.config import get_settings
from app.core.hardware import detect_device
from app.engines.base import BaseSTTEngine, STTResult

WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3-turbo"]


class WhisperEngine(BaseSTTEngine):
    name = "whisper"
    display_name = "Faster-Whisper (STT)"
    description = "Fast local Speech-to-Text via CTranslate2 supporting 99 languages including Indonesian."
    install_hint = "pip install faster-whisper"
    source_url = "https://github.com/SYSTRAN/faster-whisper"
    license_name = "MIT"

    def __init__(self) -> None:
        super().__init__()
        self._model: Any = None
        self._loaded_size: str = ""

    def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False

    def list_models(self) -> list[str]:
        return WHISPER_MODELS

    def load(self, model_size: str | None = None) -> None:
        target = model_size or get_settings().whisper_default_model
        if self._loaded and self._model is not None and self._loaded_size == target:
            return

        from faster_whisper import WhisperModel  # type: ignore

        self.unload()
        dev = detect_device()
        # CTranslate2 supports 'cuda' or 'cpu' (Apple Silicon runs fast on CPU int8)
        ct_device = "cuda" if dev == "cuda" else "cpu"
        compute_type = "float16" if ct_device == "cuda" else "int8"

        cache_dir = get_settings().models_path / "whisper"
        cache_dir.mkdir(parents=True, exist_ok=True)

        self._model = WhisperModel(
            target,
            device=ct_device,
            compute_type=compute_type,
            download_root=str(cache_dir),
        )
        self._loaded_size = target
        self._loaded = True
        self.last_used = time.time()

    def unload(self) -> None:
        self._model = None
        self._loaded = False
        self._loaded_size = ""
        gc.collect()

    def info(self) -> dict[str, Any]:
        data = super().info()
        data["loaded_model"] = self._loaded_size
        data["models"] = WHISPER_MODELS
        return data

    def transcribe(
        self,
        audio_path: str,
        model_size: str = "base",
        language: str | None = None,
    ) -> STTResult:
        self.load(model_size=model_size or get_settings().whisper_default_model)
        self.last_used = time.time()

        lang_arg = language.strip() if language and language.strip() not in ("", "auto") else None

        # Decode audio to 16kHz mono float32 numpy array via ffmpeg to avoid PyAV version issues
        ffmpeg_bin = shutil.which("ffmpeg")
        audio_input: Any = audio_path
        if ffmpeg_bin:
            proc = subprocess.run(
                [ffmpeg_bin, "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", "-f", "wav", "-acodec", "pcm_s16le", "pipe:1"],
                capture_output=True,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout:
                samples, _ = sf.read(io.BytesIO(proc.stdout), dtype="float32")
                audio_input = samples

        segments_iter, info = self._model.transcribe(
            audio_input,
            language=lang_arg,
            beam_size=5,
            vad_filter=True,
        )

        segments: list[dict[str, Any]] = []
        texts: list[str] = []
        for seg in segments_iter:
            txt = seg.text.strip()
            if txt:
                texts.append(txt)
            segments.append(
                {
                    "id": seg.id,
                    "start": round(float(seg.start), 2),
                    "end": round(float(seg.end), 2),
                    "text": txt,
                }
            )

        self.last_used = time.time()
        return STTResult(
            text=" ".join(texts).strip(),
            language=getattr(info, "language", lang_arg or "unknown"),
            duration_sec=float(getattr(info, "duration", 0.0)),
            segments=segments,
        )
