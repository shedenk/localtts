from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.auth import require_api_auth
from app.config import get_settings
from app.core.audio_utils import MIME_TYPES
from app.core.job_worker import get_job_queue
from app.core.manager import get_manager
from app.db import create_job, get_generation, get_job, list_jobs

router = APIRouter(prefix="/v1/jobs", tags=["async-jobs"], dependencies=[Depends(require_api_auth)])


class AsyncSpeechRequest(BaseModel):
    model: str = Field(default="kokoro")
    input: str = Field(..., min_length=1)
    voice: str = Field(default="af_heart")
    response_format: str = Field(default="mp3")
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    language: str = Field(default="en-us")
    instruct: str = Field(default="")
    webhook_url: Optional[str] = Field(default=None, description="Optional URL to POST when job finishes")


def _validate_webhook(url: str | None) -> str:
    if not url or not url.strip():
        return ""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid webhook_url. Must be http:// or https://.")
    return url.strip()


@router.post("/speech", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_speech_job(req: AsyncSpeechRequest):
    settings = get_settings()
    if settings.tts_max_chars > 0 and len(req.input) > settings.tts_max_chars:
        raise HTTPException(
            status_code=413,
            detail=f"Text exceeds TTS_MAX_CHARS limit ({len(req.input)} > {settings.tts_max_chars} chars).",
        )

    mgr = get_manager()
    try:
        engine = mgr.get_tts(req.model)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not engine.is_available():
        raise HTTPException(status_code=503, detail=f"Engine '{engine.name}' is not installed.")

    webhook = _validate_webhook(req.webhook_url)
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    create_job(job_id, "tts", webhook_url=webhook)

    await get_job_queue().put(
        {
            "job_id": job_id,
            "kind": "tts",
            "model": req.model,
            "input": req.input,
            "voice": req.voice,
            "language": req.language,
            "speed": req.speed,
            "response_format": req.response_format,
            "instruct": req.instruct,
            "webhook_url": webhook,
        }
    )
    job = get_job(job_id)
    return {
        "job_id": job_id,
        "kind": "tts",
        "status": "queued",
        "progress": 0,
        "queue_position": job["queue_position"] if job else 1,
        "status_url": f"/v1/jobs/{job_id}",
        "result_url": f"/v1/jobs/{job_id}/result",
    }


@router.post("/transcriptions", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_transcription_job(
    file: Optional[UploadFile] = File(default=None),
    file_url: Optional[str] = Form(default=None),
    model: str = Form(default="base"),
    language: Optional[str] = Form(default=None),
    response_format: str = Form(default="json"),
    webhook_url: Optional[str] = Form(default=None),
):
    settings = get_settings()
    mgr = get_manager()
    try:
        engine = mgr.get_stt("whisper")
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not engine.is_available():
        raise HTTPException(status_code=503, detail="Whisper engine is not installed.")

    if (file is None or not file.filename) and not (file_url and file_url.strip()):
        raise HTTPException(status_code=400, detail="Provide either 'file' upload or 'file_url'.")

    webhook = _validate_webhook(webhook_url)
    model_size = settings.whisper_default_model if model in ("whisper-1", "whisper", "") else model
    max_bytes = settings.stt_max_file_mb * 1024 * 1024 if settings.stt_max_file_mb > 0 else 0

    tmp_path: str | None = None
    source_label = ""
    if file is not None and file.filename:
        raw_bytes = await file.read()
        if max_bytes > 0 and len(raw_bytes) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Uploaded file exceeds STT_MAX_FILE_MB limit ({settings.stt_max_file_mb} MB).",
            )
        suffix = Path(file.filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw_bytes)
            tmp_path = tmp.name
        source_label = file.filename
    else:
        assert file_url is not None
        parsed = urlparse(file_url.strip())
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise HTTPException(status_code=400, detail="Invalid file_url. Must be http:// or https://.")
        source_label = file_url.strip()

    job_id = f"job_{uuid.uuid4().hex[:12]}"
    create_job(job_id, "stt", webhook_url=webhook)

    await get_job_queue().put(
        {
            "job_id": job_id,
            "kind": "stt",
            "tmp_path": tmp_path,
            "file_url": file_url.strip() if file_url else None,
            "source_label": source_label,
            "model_size": model_size,
            "language": language,
            "response_format": response_format,
            "webhook_url": webhook,
        }
    )
    job = get_job(job_id)
    return {
        "job_id": job_id,
        "kind": "stt",
        "status": "queued",
        "progress": 0,
        "queue_position": job["queue_position"] if job else 1,
        "status_url": f"/v1/jobs/{job_id}",
        "result_url": f"/v1/jobs/{job_id}/result",
    }


@router.get("")
def jobs_list(limit: int = 20):
    items = []
    for j in list_jobs(limit=limit):
        j["result"] = json.loads(j.pop("result_json", "{}") or "{}")
        items.append(j)
    return {"items": items}


@router.get("/{job_id}")
def job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    result = json.loads(job.pop("result_json", "{}") or "{}")
    return {
        "job_id": job["id"],
        "kind": job["kind"],
        "status": job["status"],
        "progress": job["progress"],
        "stage": job["stage"],
        "queue_position": job["queue_position"],
        "result": result,
        "error": job["error"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
    }


@router.get("/{job_id}/result")
def job_result(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job["status"] == "failed":
        raise HTTPException(status_code=500, detail=job["error"] or "Job failed.")
    if job["status"] != "completed":
        raise HTTPException(
            status_code=202,
            detail=f"Job still {job['status']} ({job['progress']}% - {job['stage']}).",
        )

    result = json.loads(job.get("result_json") or "{}")
    if job["kind"] == "tts":
        gen_id = job.get("generation_id")
        row = get_generation(gen_id) if gen_id else None
        if not row or not row.get("audio_filename"):
            raise HTTPException(status_code=404, detail="Audio result missing.")
        path = get_settings().outputs_path / row["audio_filename"]
        if not path.exists():
            raise HTTPException(status_code=404, detail="Audio file not found on disk.")
        media = MIME_TYPES.get(row.get("format", "mp3"), "audio/mpeg")
        return FileResponse(path, media_type=media, filename=row["audio_filename"])

    if "srt" in result:
        return Response(content=result["srt"], media_type="text/plain")
    return result
