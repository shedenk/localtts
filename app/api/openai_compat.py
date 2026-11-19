from __future__ import annotations

import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.auth import require_api_auth
from app.config import get_settings
from app.core.audio_utils import MIME_TYPES, encode_audio, save_audio_file
from app.core.manager import get_manager
from app.db import add_generation, log_api_call

router = APIRouter(prefix="/v1", tags=["openai-compatible"], dependencies=[Depends(require_api_auth)])


class SpeechRequest(BaseModel):
    model: str = Field(default="kokoro", description="kokoro | omnivoice | qwen3 | tts-1")
    input: str = Field(..., min_length=1, description="Text to synthesize")
    voice: str = Field(default="af_heart")
    response_format: str = Field(default="mp3", description="mp3 | wav | opus | flac")
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    language: str = Field(default="en-us")
    instruct: str = Field(default="")


@router.get("/models")
def list_models():
    mgr = get_manager()
    data = []
    for eng in mgr.list_all():
        if eng["available"]:
            data.append({"id": eng["name"], "object": "model", "owned_by": "local"})
    return {"object": "list", "data": data}


@router.post("/audio/speech")
async def create_speech(req: SpeechRequest):
    mgr = get_manager()
    settings = get_settings()
    t0 = time.perf_counter()

    try:
        engine = mgr.get_tts(req.model)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not engine.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"Engine '{engine.name}' is not installed. {engine.install_hint}",
        )

    def _run():
        res = engine.synthesize(
            text=req.input,
            voice=req.voice,
            language=req.language,
            speed=req.speed,
            instruct=req.instruct,
        )
        return encode_audio(res.samples, res.sample_rate, req.response_format)

    try:
        audio_bytes, actual_fmt, duration = await run_in_threadpool(_run)
    except Exception as exc:
        log_api_call("/v1/audio/speech", "POST", 500, engine.name, time.perf_counter() - t0)
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {exc}") from exc

    elapsed = time.perf_counter() - t0
    rtf = elapsed / duration if duration > 0 else 0.0

    filename = f"tts_{uuid.uuid4().hex[:12]}.{actual_fmt}"
    save_audio_file(audio_bytes, settings.outputs_path / filename)

    add_generation(
        kind="tts",
        engine=engine.name,
        model=req.model,
        voice=req.voice,
        language=req.language,
        input_text=req.input,
        audio_filename=filename,
        fmt=actual_fmt,
        duration_sec=duration,
        process_sec=elapsed,
        rtf=rtf,
    )
    log_api_call("/v1/audio/speech", "POST", 200, engine.name, elapsed)

    return Response(
        content=audio_bytes,
        media_type=MIME_TYPES.get(actual_fmt, "audio/wav"),
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "X-Process-Seconds": f"{elapsed:.3f}",
            "X-Audio-Duration": f"{duration:.3f}",
        },
    )


def _format_srt(segments: list[dict]) -> str:
    def _ts(sec: float) -> str:
        ms = int((sec % 1) * 1000)
        total_s = int(sec)
        h = total_s // 3600
        m = (total_s % 3600) // 60
        s = total_s % 60
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    for idx, seg in enumerate(segments, start=1):
        lines.append(f"{idx}")
        lines.append(f"{_ts(seg['start'])} --> {_ts(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


@router.post("/audio/transcriptions")
async def create_transcription(
    file: UploadFile = File(...),
    model: str = Form(default="base"),
    language: Optional[str] = Form(default=None),
    response_format: str = Form(default="json"),
):
    mgr = get_manager()
    t0 = time.perf_counter()

    try:
        engine = mgr.get_stt("whisper")
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not engine.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"Whisper engine is not installed. {engine.install_hint}",
        )

    model_size = get_settings().whisper_default_model if model in ("whisper-1", "whisper", "") else model
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        res = await run_in_threadpool(engine.transcribe, tmp_path, model_size, language)
    except Exception as exc:
        log_api_call("/v1/audio/transcriptions", "POST", 500, "whisper", time.perf_counter() - t0)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    elapsed = time.perf_counter() - t0
    rtf = elapsed / res.duration_sec if res.duration_sec > 0 else 0.0

    add_generation(
        kind="stt",
        engine="whisper",
        model=model_size,
        language=res.language,
        input_text=file.filename or "upload",
        output_text=res.text,
        fmt=response_format,
        duration_sec=res.duration_sec,
        process_sec=elapsed,
        rtf=rtf,
    )
    log_api_call("/v1/audio/transcriptions", "POST", 200, "whisper", elapsed)

    fmt = response_format.lower().strip()
    if fmt == "text":
        return Response(content=res.text, media_type="text/plain")
    if fmt == "srt":
        return Response(content=_format_srt(res.segments), media_type="text/plain")
    if fmt == "verbose_json":
        return {
            "text": res.text,
            "language": res.language,
            "duration": res.duration_sec,
            "segments": res.segments,
            "process_sec": round(elapsed, 3),
        }
    return {"text": res.text}
