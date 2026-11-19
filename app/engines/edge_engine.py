from __future__ import annotations

import asyncio
import io
import shutil
import subprocess
import time
from typing import Any

import soundfile as sf

from app.engines.base import BaseTTSEngine, TTSResult, VoiceInfo

EDGE_VOICES: list[VoiceInfo] = [
    VoiceInfo(id="id-ID-GadisNeural", name="Gadis (Indonesia)", language="id", gender="female"),
    VoiceInfo(id="id-ID-ArdiNeural", name="Ardi (Indonesia)", language="id", gender="male"),
    VoiceInfo(id="en-US-AriaNeural", name="Aria (US)", language="en-us", gender="female"),
    VoiceInfo(id="en-US-JennyNeural", name="Jenny (US)", language="en-us", gender="female"),
    VoiceInfo(id="en-US-AndrewNeural", name="Andrew (US)", language="en-us", gender="male"),
    VoiceInfo(id="en-US-GuyNeural", name="Guy (US)", language="en-us", gender="male"),
    VoiceInfo(id="en-GB-SoniaNeural", name="Sonia (UK)", language="en-gb", gender="female"),
    VoiceInfo(id="en-GB-RyanNeural", name="Ryan (UK)", language="en-gb", gender="male"),
]


class EdgeTTSEngine(BaseTTSEngine):
    name = "edge"
    display_name = "Edge-TTS (Free Online)"
    description = "Free Microsoft Edge neural voices (EN & ID) with near-zero CPU/RAM usage."
    supports_cloning = False
    supports_voice_design = False
    install_hint = "pip install edge-tts"
    source_url = "https://github.com/rany2/edge-tts"
    license_name = "LGPL-3.0 (Online Service)"

    def is_available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    def load(self) -> None:
        self._loaded = True
        self.last_used = time.time()

    def unload(self) -> None:
        self._loaded = False

    def list_voices(self) -> list[VoiceInfo]:
        return EDGE_VOICES

    def synthesize(
        self,
        text: str,
        voice: str = "id-ID-GadisNeural",
        language: str = "id",
        speed: float = 1.0,
        ref_audio_path: str | None = None,
        ref_text: str = "",
        instruct: str = "",
    ) -> TTSResult:
        import edge_tts  # type: ignore

        self.load()
        self.last_used = time.time()

        valid_ids = {v.id for v in EDGE_VOICES}
        chosen_voice = voice if voice in valid_ids else (
            "id-ID-GadisNeural" if language.lower().startswith("id") else "en-US-AriaNeural"
        )

        pct = int(round((float(speed) - 1.0) * 100))
        pct = max(-50, min(100, pct))
        rate_str = f"{pct:+d}%"

        async def _fetch_mp3() -> bytes:
            comm = edge_tts.Communicate(text, chosen_voice, rate=rate_str)
            buf = io.BytesIO()
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            return buf.getvalue()

        mp3_bytes = asyncio.run(_fetch_mp3())
        if not mp3_bytes:
            raise RuntimeError("Edge-TTS returned empty audio.")

        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            raise RuntimeError("ffmpeg is required to decode Edge-TTS audio.")

        proc = subprocess.run(
            [ffmpeg_bin, "-y", "-i", "pipe:0", "-f", "wav", "-acodec", "pcm_s16le", "pipe:1"],
            input=mp3_bytes,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout:
            raise RuntimeError(f"ffmpeg decode failed: {proc.stderr.decode(errors='ignore')}")

        samples, sample_rate = sf.read(io.BytesIO(proc.stdout), dtype="float32")
        self.last_used = time.time()
        return TTSResult(samples=samples, sample_rate=int(sample_rate))
