from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi.concurrency import run_in_threadpool

from app.api.openai_compat import _download_audio_url, _format_srt
from app.config import get_settings
from app.core.audio_utils import encode_audio, save_audio_file
from app.core.manager import get_manager
from app.db import add_generation, get_job, log_api_call, update_job

_JOB_QUEUE: asyncio.Queue[dict[str, Any]] | None = None


def get_job_queue() -> asyncio.Queue[dict[str, Any]]:
    global _JOB_QUEUE
    if _JOB_QUEUE is None:
        _JOB_QUEUE = asyncio.Queue()
    return _JOB_QUEUE


async def _send_webhook(webhook_url: str, payload: dict[str, Any]) -> None:
    if not webhook_url:
        return
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(webhook_url, json=payload)
    except Exception:
        pass


async def _process_tts_job(task: dict[str, Any]) -> None:
    job_id = task["job_id"]
    t0 = time.perf_counter()
    mgr = get_manager()
    settings = get_settings()

    update_job(job_id, status="processing", progress=15, stage="loading_model")
    engine = mgr.get_tts(task["model"])
    if not engine.is_available():
        raise RuntimeError(f"Engine '{engine.name}' is not installed. {engine.install_hint}")

    update_job(job_id, progress=45, stage="synthesizing")

    def _run():
        res = engine.synthesize(
            text=task["input"],
            voice=task["voice"],
            language=task["language"],
            speed=task["speed"],
            instruct=task.get("instruct", ""),
        )
        return encode_audio(res.samples, res.sample_rate, task["response_format"])

    audio_bytes, actual_fmt, duration = await run_in_threadpool(_run)
    update_job(job_id, progress=85, stage="saving_audio")

    elapsed = time.perf_counter() - t0
    rtf = elapsed / duration if duration > 0 else 0.0
    filename = f"tts_{uuid.uuid4().hex[:12]}.{actual_fmt}"
    save_audio_file(audio_bytes, settings.outputs_path / filename)

    gen_id = add_generation(
        kind="tts",
        engine=engine.name,
        model=task["model"],
        voice=task["voice"],
        language=task["language"],
        input_text=task["input"],
        audio_filename=filename,
        fmt=actual_fmt,
        duration_sec=duration,
        process_sec=elapsed,
        rtf=rtf,
    )
    log_api_call("/v1/jobs/speech", "POST", 200, engine.name, elapsed)

    result_data = {
        "generation_id": gen_id,
        "format": actual_fmt,
        "duration_sec": round(duration, 3),
        "process_sec": round(elapsed, 3),
        "rtf": round(rtf, 3),
        "result_url": f"/v1/jobs/{job_id}/result",
    }
    update_job(
        job_id,
        status="completed",
        progress=100,
        stage="done",
        generation_id=gen_id,
        result_json=json.dumps(result_data),
    )


async def _process_stt_job(task: dict[str, Any]) -> None:
    job_id = task["job_id"]
    t0 = time.perf_counter()
    mgr = get_manager()
    settings = get_settings()
    max_bytes = settings.stt_max_file_mb * 1024 * 1024 if settings.stt_max_file_mb > 0 else 0

    update_job(job_id, status="processing", progress=15, stage="preparing_audio")
    engine = mgr.get_stt("whisper")
    if not engine.is_available():
        raise RuntimeError(f"Whisper engine is not installed. {engine.install_hint}")

    tmp_path = task.get("tmp_path")
    if not tmp_path and task.get("file_url"):
        raw_bytes, suffix = await run_in_threadpool(_download_audio_url, task["file_url"], max_bytes)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw_bytes)
            tmp_path = tmp.name

    assert tmp_path
    try:
        update_job(job_id, progress=45, stage="transcribing")
        res = await run_in_threadpool(engine.transcribe, tmp_path, task["model_size"], task.get("language"))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    update_job(job_id, progress=90, stage="finalizing")
    elapsed = time.perf_counter() - t0
    rtf = elapsed / res.duration_sec if res.duration_sec > 0 else 0.0

    gen_id = add_generation(
        kind="stt",
        engine="whisper",
        model=task["model_size"],
        language=res.language,
        input_text=task["source_label"],
        output_text=res.text,
        fmt=task["response_format"],
        duration_sec=res.duration_sec,
        process_sec=elapsed,
        rtf=rtf,
    )
    log_api_call("/v1/jobs/transcriptions", "POST", 200, "whisper", elapsed)

    fmt = task["response_format"].lower().strip()
    result_data: dict[str, Any] = {
        "generation_id": gen_id,
        "text": res.text,
        "language": res.language,
        "duration_sec": round(res.duration_sec, 3),
        "process_sec": round(elapsed, 3),
        "segments": res.segments,
        "result_url": f"/v1/jobs/{job_id}/result",
    }
    if fmt == "srt":
        result_data["srt"] = _format_srt(res.segments)

    update_job(
        job_id,
        status="completed",
        progress=100,
        stage="done",
        generation_id=gen_id,
        result_json=json.dumps(result_data),
    )


async def job_worker_loop(stop_event: asyncio.Event) -> None:
    q = get_job_queue()
    while not stop_event.is_set():
        try:
            task = await asyncio.wait_for(q.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue

        job_id = task["job_id"]
        webhook_url = task.get("webhook_url", "")
        try:
            if task["kind"] == "tts":
                await _process_tts_job(task)
            else:
                await _process_stt_job(task)
        except Exception as exc:
            update_job(job_id, status="failed", progress=100, stage="error", error=str(exc))
            if task.get("tmp_path") and os.path.exists(task["tmp_path"]):
                os.remove(task["tmp_path"])
        finally:
            q.task_done()
            job = get_job(job_id)
            if job and webhook_url:
                payload = {
                    "job_id": job["id"],
                    "kind": job["kind"],
                    "status": job["status"],
                    "progress": job["progress"],
                    "stage": job["stage"],
                    "result": json.loads(job["result_json"] or "{}"),
                    "error": job["error"],
                }
                await _send_webhook(webhook_url, payload)
