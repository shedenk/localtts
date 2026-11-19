from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import numpy as np


@dataclass
class VoiceInfo:
    id: str
    name: str
    language: str = "en"
    gender: str = "unknown"


@dataclass
class TTSResult:
    samples: np.ndarray
    sample_rate: int


@dataclass
class STTResult:
    text: str
    language: str
    duration_sec: float
    segments: list[dict[str, Any]] = field(default_factory=list)


class BaseEngine(ABC):
    name: str = ""
    display_name: str = ""
    kind: str = "tts"  # "tts" | "stt"
    description: str = ""
    supports_cloning: bool = False
    supports_voice_design: bool = False
    min_ram_gb: float = 1.0
    install_hint: str = ""
    source_url: str = ""
    license_name: str = ""

    def __init__(self) -> None:
        self._loaded: bool = False
        self.last_used: float = 0.0

    @abstractmethod
    def is_available(self) -> bool:
        """Whether required Python libraries for this engine are installed."""

    def is_loaded(self) -> bool:
        return self._loaded

    @abstractmethod
    def load(self) -> None:
        """Load model weights into memory."""

    @abstractmethod
    def unload(self) -> None:
        """Unload model weights and free memory."""

    def info(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "kind": self.kind,
            "description": self.description,
            "available": self.is_available(),
            "loaded": self.is_loaded(),
            "supports_cloning": self.supports_cloning,
            "supports_voice_design": self.supports_voice_design,
            "min_ram_gb": self.min_ram_gb,
            "install_hint": self.install_hint,
            "source_url": self.source_url,
            "license_name": self.license_name,
        }


class BaseTTSEngine(BaseEngine):
    kind: str = "tts"

    @abstractmethod
    def list_voices(self) -> list[VoiceInfo]:
        """List built-in voices."""

    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice: str = "",
        language: str = "en",
        speed: float = 1.0,
        ref_audio_path: str | None = None,
        ref_text: str = "",
        instruct: str = "",
    ) -> TTSResult:
        """Synthesize text into audio."""


class BaseSTTEngine(BaseEngine):
    kind: str = "stt"

    @abstractmethod
    def list_models(self) -> list[str]:
        """List supported STT model sizes."""

    @abstractmethod
    def transcribe(
        self,
        audio_path: str,
        model_size: str = "base",
        language: str | None = None,
    ) -> STTResult:
        """Transcribe audio file into text."""
