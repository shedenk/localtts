from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from app.auth import require_ui_auth
from app.config import get_settings
from app.core.audio_utils import MIME_TYPES, encode_audio, save_audio_file
from app.core.hardware import get_hardware_info
from app.core.manager import get_manager
from app.db import (
    add_generation,
    add_voice_clone,
    count_generations,
    delete_generation,
    delete_generations_bulk,
    delete_voice_clone,
    get_generation,
    get_stats,
    get_voice_clone,
    list_generations,
    list_voice_clones,
)

router = APIRouter(prefix="/api", tags=["studio"], dependencies=[Depends(require_ui_auth)])


@router.get("/system")
def system_status():
    settings = get_settings()
    mgr = get_manager()
    return {
        "app_name": settings.app_name,
        "hardware": get_hardware_info(),
        "stats": get_stats(),
        "ui_auth_enabled": settings.ui_auth_enabled,
        "api_auth_enabled": settings.api_auth_enabled,
        "api_key": settings.api_key,
        "api_key_header": settings.api_key_header,
        "idle_unload_seconds": settings.idle_unload_seconds,
        "tts_max_chars": settings.tts_max_chars,
        "stt_max_file_mb": settings.stt_max_file_mb,
        "engines": mgr.list_all(),
    }


@router.get("/engines")
def list_engines():
    return {"engines": get_manager().list_all()}


@router.get("/readme")
def get_readme():
    readme_path = Path(__file__).resolve().parent.parent.parent / "README.md"
    if not readme_path.exists():
        return {"content": "# LocalTTS\n\nREADME.md not found."}
    return {"content": readme_path.read_text(encoding="utf-8")}


@router.get("/voices/sample")
async def voice_sample(engine: str, voice: str, language: str = "en"):
    mgr = get_manager()
    settings = get_settings()

    try:
        tts = mgr.get_tts(engine)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not tts.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"Engine '{tts.display_name}' is not installed. Run: {tts.install_hint}",
        )

    safe_eng = "".join(c for c in tts.name if c.isalnum() or c in ("-", "_"))
    safe_voice = "".join(c for c in voice if c.isalnum() or c in ("-", "_"))
    bundled_file = Path(__file__).resolve().parent.parent.parent / "web" / "samples" / f"{safe_eng}_{safe_voice}.mp3"
    if bundled_file.exists():
        return FileResponse(bundled_file, media_type="audio/mpeg", filename=bundled_file.name)

    sample_file = settings.samples_path / f"{safe_eng}_{safe_voice}.mp3"
    if sample_file.exists():
        return FileResponse(sample_file, media_type="audio/mpeg", filename=sample_file.name)

    # Determine short sample text based on voice/language (Indonesian vs English)
    is_id = language.lower().startswith("id") or voice.startswith("id_") or voice.startswith("id-")
    sample_text = (
        "Halo, ini contoh suara saya."
        if is_id
        else "Hello, this is a voice sample."
    )
    lang_arg = "id" if is_id else ("en-gb" if voice.startswith("b") else "en-us")

    def _gen():
        res = tts.synthesize(text=sample_text, voice=voice, language=lang_arg, speed=1.0)
        return encode_audio(res.samples, res.sample_rate, "mp3")

    try:
        audio_bytes, actual_fmt, _ = await run_in_threadpool(_gen)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sample generation failed: {exc}") from exc

    target = settings.samples_path / f"{safe_eng}_{safe_voice}.{actual_fmt}"
    save_audio_file(audio_bytes, target)
    return FileResponse(target, media_type=MIME_TYPES.get(actual_fmt, "audio/mpeg"), filename=target.name)


@router.post("/engines/{name}/load")
async def load_engine(name: str):
    mgr = get_manager()
    try:
        info = await run_in_threadpool(mgr.load_engine, name)
        return {"ok": True, "engine": info}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load {name}: {exc}") from exc


@router.post("/engines/{name}/unload")
async def unload_engine(name: str):
    mgr = get_manager()
    try:
        info = await run_in_threadpool(mgr.unload_engine, name)
        return {"ok": True, "engine": info}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


_INSTALL_LOCK = threading.Lock()
_INSTALL_STATE: dict[str, object] = {
    "status": "idle",  # idle | installing | success | error
    "engine": "",
    "message": "",
}


def _run_install_bg(engine_name: str, omnivoice_present: bool) -> None:
    global _INSTALL_STATE
    try:
        uv_bin = shutil.which("uv")
        root_dir = Path(__file__).resolve().parent.parent.parent

        if engine_name == "qwen3" and omnivoice_present:
            # OmniVoice uses transformers>=5.3 while qwen-tts requires transformers==4.57.3.
            # Install qwen-tts into an isolated .venv-qwen3 so both engines coexist cleanly.
            iso_venv = root_dir / ".venv-qwen3"
            iso_py = iso_venv / "bin" / "python"
            if not iso_py.exists():
                iso_py = iso_venv / "Scripts" / "python.exe"
            if uv_bin:
                p0 = subprocess.run(
                    [uv_bin, "venv", str(iso_venv), "--python", "3.12", "--allow-existing"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if p0.returncode != 0:
                    raise RuntimeError(p0.stderr[-500:] or p0.stdout[-500:])
                cmd = [uv_bin, "pip", "install", "--python", str(iso_py), "torch", "torchaudio", "qwen-tts"]
            else:
                p0 = subprocess.run([sys.executable, "-m", "venv", str(iso_venv)], capture_output=True, text=True, check=False)
                if p0.returncode != 0:
                    raise RuntimeError(p0.stderr[-500:])
                cmd = [str(iso_py), "-m", "pip", "install", "torch", "torchaudio", "qwen-tts"]
        else:
            if engine_name == "omnivoice":
                pkgs = ["torch", "torchaudio", "omnivoice"]
            elif engine_name == "qwen3":
                pkgs = ["torch", "torchaudio", "qwen-tts"]
            else:
                pkgs = [engine_name]

            if uv_bin:
                cmd = [uv_bin, "pip", "install", "--python", sys.executable, *pkgs]
            else:
                cmd = [sys.executable, "-m", "pip", "install", *pkgs]

        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "Install failed").strip()
            _INSTALL_STATE = {"status": "error", "engine": engine_name, "message": err[-400:]}
            return

        _INSTALL_STATE = {
            "status": "success",
            "engine": engine_name,
            "message": f"{engine_name} installed successfully!",
        }
    except Exception as exc:
        _INSTALL_STATE = {"status": "error", "engine": engine_name, "message": str(exc)[-400:]}


@router.get("/engines/install-status")
def engine_install_status():
    return _INSTALL_STATE


@router.post("/engines/{name}/install")
def install_engine(name: str, force: bool = False):
    global _INSTALL_STATE
    mgr = get_manager()
    try:
        eng = mgr.get(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if eng.is_available():
        return {"ok": True, "already_installed": True, "engine": eng.info()}

    hw = get_hardware_info()
    if not force and hw["ram_total_gb"] < eng.min_ram_gb:
        raise HTTPException(
            status_code=409,
            detail=f"RAM server ({hw['ram_total_gb']} GB) di bawah minimum ({eng.min_ram_gb} GB) untuk {eng.display_name}.",
        )

    with _INSTALL_LOCK:
        if _INSTALL_STATE.get("status") == "installing":
            raise HTTPException(
                status_code=409,
                detail=f"Sedang menginstall {_INSTALL_STATE.get('engine')}, harap tunggu.",
            )
        _INSTALL_STATE = {
            "status": "installing",
            "engine": eng.name,
            "message": f"Installing {eng.display_name}...",
        }
        omnivoice_present = mgr.get("omnivoice").is_available() if "omnivoice" in [e["name"] for e in mgr.list_all()] else False
        threading.Thread(target=_run_install_bg, args=(eng.name, omnivoice_present), daemon=True).start()

    return {"ok": True, "status": "installing", "engine": eng.name}


@router.post("/tts/generate")
async def studio_tts_generate(
    engine: str = Form(default="kokoro"),
    text: str = Form(...),
    voice: str = Form(default="af_heart"),
    language: str = Form(default="en-us"),
    speed: float = Form(default=1.0),
    response_format: str = Form(default="mp3"),
    instruct: str = Form(default=""),
    clone_id: Optional[int] = Form(default=None),
    ref_text: str = Form(default=""),
    ref_audio: Optional[UploadFile] = File(default=None),
):
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    mgr = get_manager()
    settings = get_settings()
    if settings.tts_max_chars > 0 and len(text) > settings.tts_max_chars:
        raise HTTPException(
            status_code=413,
            detail=f"Teks melebihi batas TTS_MAX_CHARS ({len(text)} > {settings.tts_max_chars} karakter).",
        )
    t0 = time.perf_counter()

    try:
        tts = mgr.get_tts(engine)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not tts.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"Engine '{tts.display_name}' is not installed. Run: {tts.install_hint}",
        )

    temp_ref_path: str | None = None
    ref_audio_path: str | None = None
    actual_ref_text = ref_text

    if clone_id:
        clone = get_voice_clone(clone_id)
        if not clone:
            raise HTTPException(status_code=404, detail="Saved voice clone not found.")
        ref_audio_path = str(settings.voices_path / clone["ref_audio_filename"])
        if not actual_ref_text:
            actual_ref_text = clone.get("ref_text", "")
    elif ref_audio is not None and ref_audio.filename:
        suffix = Path(ref_audio.filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await ref_audio.read())
            temp_ref_path = tmp.name
        ref_audio_path = temp_ref_path

    def _run():
        res = tts.synthesize(
            text=text,
            voice=voice,
            language=language,
            speed=speed,
            ref_audio_path=ref_audio_path,
            ref_text=actual_ref_text,
            instruct=instruct,
        )
        return encode_audio(res.samples, res.sample_rate, response_format)

    try:
        audio_bytes, actual_fmt, duration = await run_in_threadpool(_run)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {exc}") from exc
    finally:
        if temp_ref_path and os.path.exists(temp_ref_path):
            os.remove(temp_ref_path)

    elapsed = time.perf_counter() - t0
    rtf = elapsed / duration if duration > 0 else 0.0

    filename = f"tts_{uuid.uuid4().hex[:12]}.{actual_fmt}"
    save_audio_file(audio_bytes, settings.outputs_path / filename)

    gen_id = add_generation(
        kind="tts",
        engine=tts.name,
        model=tts.display_name,
        voice=f"clone:{clone_id}" if clone_id else voice,
        language=language,
        input_text=text,
        audio_filename=filename,
        fmt=actual_fmt,
        duration_sec=duration,
        process_sec=elapsed,
        rtf=rtf,
    )

    return {
        "id": gen_id,
        "engine": tts.name,
        "format": actual_fmt,
        "audio_url": f"/api/history/{gen_id}/audio",
        "duration_sec": round(duration, 2),
        "process_sec": round(elapsed, 2),
        "rtf": round(rtf, 3),
    }


@router.post("/stt/transcribe")
async def studio_stt_transcribe(
    file: Optional[UploadFile] = File(default=None),
    file_url: Optional[str] = Form(default=None),
    model_size: str = Form(default="base"),
    language: str = Form(default="auto"),
):
    from app.api.openai_compat import _download_audio_url

    mgr = get_manager()
    t0 = time.perf_counter()

    try:
        stt = mgr.get_stt("whisper")
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not stt.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"Whisper engine is not installed. Run: {stt.install_hint}",
        )

    if (file is None or not file.filename) and not (file_url and file_url.strip()):
        raise HTTPException(status_code=400, detail="Provide either a file upload or file_url.")

    settings = get_settings()
    max_bytes = settings.stt_max_file_mb * 1024 * 1024 if settings.stt_max_file_mb > 0 else 0

    if file is not None and file.filename:
        raw_bytes = await file.read()
        if max_bytes > 0 and len(raw_bytes) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Ukuran file melebihi batas STT_MAX_FILE_MB ({settings.stt_max_file_mb} MB).",
            )
        suffix = Path(file.filename).suffix or ".wav"
        source_label = file.filename
    else:
        assert file_url is not None
        try:
            raw_bytes, suffix = await run_in_threadpool(_download_audio_url, file_url, max_bytes)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to download file_url: {exc}") from exc
        source_label = file_url.strip()

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(raw_bytes)
        tmp_path = tmp.name

    try:
        res = await run_in_threadpool(stt.transcribe, tmp_path, model_size, language)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    elapsed = time.perf_counter() - t0
    rtf = elapsed / res.duration_sec if res.duration_sec > 0 else 0.0

    gen_id = add_generation(
        kind="stt",
        engine="whisper",
        model=model_size,
        language=res.language,
        input_text=source_label,
        output_text=res.text,
        fmt="json",
        duration_sec=res.duration_sec,
        process_sec=elapsed,
        rtf=rtf,
    )

    return {
        "id": gen_id,
        "text": res.text,
        "language": res.language,
        "duration_sec": round(res.duration_sec, 2),
        "process_sec": round(elapsed, 2),
        "rtf": round(rtf, 3),
        "segments": res.segments,
    }


@router.get("/history")
def history_list(limit: int = 10, page: int = 1, kind: Optional[str] = None):
    page = max(1, page)
    limit = max(1, min(100, limit))
    offset = (page - 1) * limit
    total = count_generations(kind=kind)
    return {
        "items": list_generations(limit=limit, offset=offset, kind=kind),
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": max(1, (total + limit - 1) // limit),
    }


@router.post("/history/bulk-delete")
def history_bulk_delete(payload: dict):
    raw_ids = payload.get("ids") or []
    try:
        ids = [int(x) for x in raw_ids]
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid ids list.") from exc
    kind = payload.get("kind")
    if kind is not None and kind not in ("tts", "stt"):
        raise HTTPException(status_code=400, detail="Invalid kind.")
    delete_all = bool(payload.get("all", False))
    rows = delete_generations_bulk(ids=ids, kind=kind, delete_all=delete_all)
    out_dir = get_settings().outputs_path
    for row in rows:
        if row.get("audio_filename"):
            p = out_dir / row["audio_filename"]
            if p.exists():
                p.unlink()
    return {"ok": True, "deleted": len(rows)}


@router.get("/history/{gen_id}/audio")
def history_audio(gen_id: int):
    row = get_generation(gen_id)
    if not row or not row.get("audio_filename"):
        raise HTTPException(status_code=404, detail="Audio not found.")
    path = get_settings().outputs_path / row["audio_filename"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file missing from disk.")
    media = MIME_TYPES.get(row.get("format", "wav"), "audio/wav")
    return FileResponse(path, media_type=media, filename=row["audio_filename"])


@router.delete("/history/{gen_id}")
def history_delete(gen_id: int):
    row = delete_generation(gen_id)
    if not row:
        raise HTTPException(status_code=404, detail="History item not found.")
    if row.get("audio_filename"):
        p = get_settings().outputs_path / row["audio_filename"]
        if p.exists():
            p.unlink()
    return {"ok": True}


@router.get("/clones")
def clones_list():
    return {"items": list_voice_clones()}


@router.post("/clones")
async def clones_create(
    name: str = Form(...),
    engine: str = Form(default="omnivoice"),
    ref_text: str = Form(default=""),
    file: UploadFile = File(...),
):
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Clone name is required.")

    settings = get_settings()
    suffix = Path(file.filename or "ref.wav").suffix or ".wav"
    filename = f"clone_{uuid.uuid4().hex[:10]}{suffix}"
    dest = settings.voices_path / filename
    dest.write_bytes(await file.read())

    try:
        cid = add_voice_clone(clean_name, engine, filename, ref_text.strip())
    except Exception as exc:
        if dest.exists():
            dest.unlink()
        raise HTTPException(status_code=400, detail=f"Could not save clone (name may already exist): {exc}") from exc

    return {"ok": True, "id": cid, "name": clean_name}


@router.delete("/clones/{clone_id}")
def clones_delete(clone_id: int):
    row = delete_voice_clone(clone_id)
    if not row:
        raise HTTPException(status_code=404, detail="Voice clone not found.")
    p = get_settings().voices_path / row["ref_audio_filename"]
    if p.exists():
        p.unlink()
    return {"ok": True}
