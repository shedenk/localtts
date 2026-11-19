from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path
from typing import Tuple

import numpy as np
import soundfile as sf


MIME_TYPES = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "opus": "audio/ogg",
    "ogg": "audio/ogg",
    "flac": "audio/flac",
}


def encode_audio(
    samples: np.ndarray,
    sample_rate: int,
    fmt: str = "wav",
) -> Tuple[bytes, str, float]:
    """
    Encode float32/int16 numpy audio array into target format bytes.
    Returns (audio_bytes, actual_format, duration_seconds).
    """
    fmt = fmt.lower().strip()
    if fmt not in MIME_TYPES:
        fmt = "wav"

    arr = np.asarray(samples, dtype=np.float32)
    if arr.ndim > 1:
        arr = arr.squeeze()
    duration = float(len(arr) / sample_rate) if sample_rate > 0 else 0.0

    wav_buf = io.BytesIO()
    sf.write(wav_buf, arr, sample_rate, format="WAV", subtype="PCM_16")
    wav_bytes = wav_buf.getvalue()

    if fmt == "wav":
        return wav_bytes, "wav", duration

    if fmt == "flac":
        flac_buf = io.BytesIO()
        sf.write(flac_buf, arr, sample_rate, format="FLAC")
        return flac_buf.getvalue(), "flac", duration

    # mp3 / opus / ogg via ffmpeg
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        return wav_bytes, "wav", duration

    codec_args = {
        "mp3": ["-f", "mp3", "-acodec", "libmp3lame", "-b:a", "192k"],
        "opus": ["-f", "ogg", "-acodec", "libopus", "-b:a", "96k"],
        "ogg": ["-f", "ogg", "-acodec", "libopus", "-b:a", "96k"],
    }.get(fmt, ["-f", "mp3", "-acodec", "libmp3lame", "-b:a", "192k"])

    proc = subprocess.run(
        [ffmpeg_bin, "-y", "-i", "pipe:0", *codec_args, "pipe:1"],
        input=wav_bytes,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        return wav_bytes, "wav", duration

    return proc.stdout, fmt, duration


def save_audio_file(audio_bytes: bytes, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(audio_bytes)
