from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from app.config import get_settings

_DB_LOCK = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    settings = get_settings()
    conn = sqlite3.connect(str(settings.db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


@contextmanager
def db_session() -> Iterator[sqlite3.Connection]:
    with _DB_LOCK:
        conn = _get_conn()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init_db() -> None:
    with db_session() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS generations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,           -- 'tts' or 'stt'
                engine TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT '',
                voice TEXT NOT NULL DEFAULT '',
                language TEXT NOT NULL DEFAULT '',
                input_text TEXT NOT NULL DEFAULT '',
                output_text TEXT NOT NULL DEFAULT '',
                audio_filename TEXT NOT NULL DEFAULT '',
                format TEXT NOT NULL DEFAULT 'wav',
                duration_sec REAL NOT NULL DEFAULT 0.0,
                process_sec REAL NOT NULL DEFAULT 0.0,
                rtf REAL NOT NULL DEFAULT 0.0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS voice_clones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                engine TEXT NOT NULL DEFAULT 'omnivoice',
                ref_audio_filename TEXT NOT NULL,
                ref_text TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS api_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                engine TEXT NOT NULL DEFAULT '',
                process_sec REAL NOT NULL DEFAULT 0.0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,           -- 'tts' or 'stt'
                status TEXT NOT NULL DEFAULT 'queued', -- queued | processing | completed | failed
                progress INTEGER NOT NULL DEFAULT 0,
                stage TEXT NOT NULL DEFAULT 'queued',
                webhook_url TEXT NOT NULL DEFAULT '',
                generation_id INTEGER,
                result_json TEXT NOT NULL DEFAULT '{}',
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            """
        )


def add_generation(
    *,
    kind: str,
    engine: str,
    model: str = "",
    voice: str = "",
    language: str = "",
    input_text: str = "",
    output_text: str = "",
    audio_filename: str = "",
    fmt: str = "wav",
    duration_sec: float = 0.0,
    process_sec: float = 0.0,
    rtf: float = 0.0,
) -> int:
    with db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO generations (
                kind, engine, model, voice, language,
                input_text, output_text, audio_filename, format,
                duration_sec, process_sec, rtf
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                kind,
                engine,
                model,
                voice,
                language,
                input_text,
                output_text,
                audio_filename,
                fmt,
                round(duration_sec, 3),
                round(process_sec, 3),
                round(rtf, 3),
            ),
        )
        return int(cur.lastrowid)


def list_generations(limit: int = 10, offset: int = 0, kind: str | None = None) -> list[dict[str, Any]]:
    with db_session() as conn:
        if kind:
            rows = conn.execute(
                "SELECT * FROM generations WHERE kind = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                (kind, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM generations ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]


def count_generations(kind: str | None = None) -> int:
    with db_session() as conn:
        if kind:
            return int(conn.execute("SELECT COUNT(*) FROM generations WHERE kind = ?", (kind,)).fetchone()[0])
        return int(conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0])


def delete_generations_bulk(ids: list[int] | None = None, kind: str | None = None, delete_all: bool = False) -> list[dict[str, Any]]:
    with db_session() as conn:
        if delete_all and kind:
            rows = conn.execute("SELECT * FROM generations WHERE kind = ?", (kind,)).fetchall()
            conn.execute("DELETE FROM generations WHERE kind = ?", (kind,))
            return [dict(r) for r in rows]
        if delete_all:
            rows = conn.execute("SELECT * FROM generations").fetchall()
            conn.execute("DELETE FROM generations")
            return [dict(r) for r in rows]
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(f"SELECT * FROM generations WHERE id IN ({placeholders})", ids).fetchall()
        conn.execute(f"DELETE FROM generations WHERE id IN ({placeholders})", ids)
        return [dict(r) for r in rows]


def get_generation(gen_id: int) -> dict[str, Any] | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM generations WHERE id = ?", (gen_id,)).fetchone()
        return dict(row) if row else None


def delete_generation(gen_id: int) -> dict[str, Any] | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM generations WHERE id = ?", (gen_id,)).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM generations WHERE id = ?", (gen_id,))
        return dict(row)


def add_voice_clone(name: str, engine: str, ref_audio_filename: str, ref_text: str = "") -> int:
    with db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO voice_clones (name, engine, ref_audio_filename, ref_text)
            VALUES (?, ?, ?, ?)
            """,
            (name, engine, ref_audio_filename, ref_text),
        )
        return int(cur.lastrowid)


def list_voice_clones() -> list[dict[str, Any]]:
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM voice_clones ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


def get_voice_clone(clone_id: int) -> dict[str, Any] | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM voice_clones WHERE id = ?", (clone_id,)).fetchone()
        return dict(row) if row else None


def delete_voice_clone(clone_id: int) -> dict[str, Any] | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM voice_clones WHERE id = ?", (clone_id,)).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM voice_clones WHERE id = ?", (clone_id,))
        return dict(row)


def log_api_call(endpoint: str, method: str, status_code: int, engine: str = "", process_sec: float = 0.0) -> None:
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO api_logs (endpoint, method, status_code, engine, process_sec)
            VALUES (?, ?, ?, ?, ?)
            """,
            (endpoint, method, status_code, engine, round(process_sec, 3)),
        )


def get_stats() -> dict[str, Any]:
    with db_session() as conn:
        total_tts = conn.execute("SELECT COUNT(*) FROM generations WHERE kind='tts'").fetchone()[0]
        total_stt = conn.execute("SELECT COUNT(*) FROM generations WHERE kind='stt'").fetchone()[0]
        total_clones = conn.execute("SELECT COUNT(*) FROM voice_clones").fetchone()[0]
        total_api = conn.execute("SELECT COUNT(*) FROM api_logs").fetchone()[0]
        return {
            "total_tts": total_tts,
            "total_stt": total_stt,
            "total_clones": total_clones,
            "total_api_calls": total_api,
        }


def create_job(job_id: str, kind: str, webhook_url: str = "") -> None:
    with db_session() as conn:
        conn.execute(
            "INSERT INTO jobs (id, kind, status, progress, stage, webhook_url) VALUES (?, ?, 'queued', 0, 'queued', ?)",
            (job_id, kind, webhook_url),
        )


def update_job(
    job_id: str,
    *,
    status: str | None = None,
    progress: int | None = None,
    stage: str | None = None,
    generation_id: int | None = None,
    result_json: str | None = None,
    error: str | None = None,
) -> None:
    fields: list[str] = ["updated_at = datetime('now', 'localtime')"]
    vals: list[Any] = []
    if status is not None:
        fields.append("status = ?")
        vals.append(status)
    if progress is not None:
        fields.append("progress = ?")
        vals.append(progress)
    if stage is not None:
        fields.append("stage = ?")
        vals.append(stage)
    if generation_id is not None:
        fields.append("generation_id = ?")
        vals.append(generation_id)
    if result_json is not None:
        fields.append("result_json = ?")
        vals.append(result_json)
    if error is not None:
        fields.append("error = ?")
        vals.append(error)
    vals.append(job_id)
    with db_session() as conn:
        conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?", vals)


def get_job(job_id: str) -> dict[str, Any] | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        if d["status"] in ("queued", "processing"):
            pos = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status IN ('queued', 'processing') AND rowid <= (SELECT rowid FROM jobs WHERE id = ?)",
                (job_id,),
            ).fetchone()[0]
            d["queue_position"] = int(pos)
        else:
            d["queue_position"] = 0
        return d


def list_jobs(limit: int = 30) -> list[dict[str, Any]]:
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
