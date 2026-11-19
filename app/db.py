from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
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


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


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
                source TEXT NOT NULL DEFAULT 'ui',
                status TEXT NOT NULL DEFAULT 'completed',
                progress INTEGER NOT NULL DEFAULT 100,
                started_at TEXT NOT NULL DEFAULT '',
                completed_at TEXT NOT NULL DEFAULT '',
                estimated_finish_at TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
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
                source TEXT NOT NULL DEFAULT 'api',
                engine TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                voice TEXT NOT NULL DEFAULT '',
                language TEXT NOT NULL DEFAULT '',
                input_text TEXT NOT NULL DEFAULT '',
                output_text TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL DEFAULT '',
                completed_at TEXT NOT NULL DEFAULT '',
                estimated_finish_at TEXT NOT NULL DEFAULT '',
                generation_id INTEGER,
                result_json TEXT NOT NULL DEFAULT '{}',
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            """
        )

        # Migrations for existing databases
        _add_column_if_missing(conn, "generations", "source", "TEXT NOT NULL DEFAULT 'ui'")
        _add_column_if_missing(conn, "generations", "status", "TEXT NOT NULL DEFAULT 'completed'")
        _add_column_if_missing(conn, "generations", "progress", "INTEGER NOT NULL DEFAULT 100")
        _add_column_if_missing(conn, "generations", "started_at", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "generations", "completed_at", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "generations", "estimated_finish_at", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "generations", "error", "TEXT NOT NULL DEFAULT ''")

        _add_column_if_missing(conn, "jobs", "source", "TEXT NOT NULL DEFAULT 'api'")
        _add_column_if_missing(conn, "jobs", "engine", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "jobs", "model", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "jobs", "voice", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "jobs", "language", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "jobs", "input_text", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "jobs", "output_text", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "jobs", "started_at", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "jobs", "completed_at", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "jobs", "estimated_finish_at", "TEXT NOT NULL DEFAULT ''")

        # Backfill timestamps for existing generations
        conn.execute("UPDATE generations SET started_at = created_at WHERE started_at = ''")
        conn.execute("UPDATE generations SET completed_at = created_at WHERE completed_at = ''")
        conn.execute("UPDATE generations SET estimated_finish_at = created_at WHERE estimated_finish_at = ''")


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
    source: str = "ui",
    status: str = "completed",
    progress: int = 100,
    started_at: str = "",
    completed_at: str = "",
    estimated_finish_at: str = "",
    error: str = "",
) -> int:
    with db_session() as conn:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not started_at:
            started_at = now_str
        if not completed_at:
            completed_at = now_str
        if not estimated_finish_at:
            estimated_finish_at = completed_at

        cur = conn.execute(
            """
            INSERT INTO generations (
                kind, engine, model, voice, language,
                input_text, output_text, audio_filename, format,
                duration_sec, process_sec, rtf,
                source, status, progress, started_at, completed_at, estimated_finish_at, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                source,
                status,
                progress,
                started_at,
                completed_at,
                estimated_finish_at,
                error,
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


def delete_generations_bulk(ids: list[Any] | None = None, kind: str | None = None, delete_all: bool = False) -> list[dict[str, Any]]:
    with db_session() as conn:
        deleted_rows: list[dict[str, Any]] = []
        if delete_all:
            if kind:
                gen_rows = conn.execute("SELECT * FROM generations WHERE kind = ?", (kind,)).fetchall()
                conn.execute("DELETE FROM generations WHERE kind = ?", (kind,))
                job_rows = conn.execute("SELECT * FROM jobs WHERE kind = ?", (kind,)).fetchall()
                conn.execute("DELETE FROM jobs WHERE kind = ?", (kind,))
            else:
                gen_rows = conn.execute("SELECT * FROM generations").fetchall()
                conn.execute("DELETE FROM generations")
                job_rows = conn.execute("SELECT * FROM jobs").fetchall()
                conn.execute("DELETE FROM jobs")
            return [dict(r) for r in gen_rows] + [dict(r) for r in job_rows]

        if not ids:
            return []

        gen_ids = []
        job_ids = []
        for x in ids:
            if isinstance(x, str) and x.startswith("job_"):
                job_ids.append(x)
            else:
                try:
                    gen_ids.append(int(x))
                except (ValueError, TypeError):
                    job_ids.append(str(x))

        if gen_ids:
            placeholders = ",".join("?" for _ in gen_ids)
            rows = conn.execute(f"SELECT * FROM generations WHERE id IN ({placeholders})", gen_ids).fetchall()
            conn.execute(f"DELETE FROM generations WHERE id IN ({placeholders})", gen_ids)
            deleted_rows.extend([dict(r) for r in rows])

        if job_ids:
            placeholders = ",".join("?" for _ in job_ids)
            rows = conn.execute(f"SELECT * FROM jobs WHERE id IN ({placeholders})", job_ids).fetchall()
            conn.execute(f"DELETE FROM jobs WHERE id IN ({placeholders})", job_ids)
            deleted_rows.extend([dict(r) for r in rows])

        return deleted_rows


def get_generation(gen_id: int) -> dict[str, Any] | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM generations WHERE id = ?", (gen_id,)).fetchone()
        return dict(row) if row else None


def delete_generation(gen_id: Any) -> dict[str, Any] | None:
    with db_session() as conn:
        str_id = str(gen_id)
        if str_id.startswith("job_"):
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (str_id,)).fetchone()
            if row:
                conn.execute("DELETE FROM jobs WHERE id = ?", (str_id,))
                return dict(row)
            return None
        try:
            gid = int(gen_id)
            row = conn.execute("SELECT * FROM generations WHERE id = ?", (gid,)).fetchone()
            if not row:
                return None
            conn.execute("DELETE FROM generations WHERE id = ?", (gid,))
            return dict(row)
        except (ValueError, TypeError):
            return None


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


def cleanup_stale_jobs_on_startup() -> int:
    """Marks any leftover processing or queued jobs from previous crashed runs as failed."""
    with db_session() as conn:
        cur = conn.execute(
            """
            UPDATE jobs
            SET status = 'failed',
                error = 'Server restarted before job completed',
                updated_at = datetime('now', 'localtime'),
                completed_at = datetime('now', 'localtime')
            WHERE status IN ('queued', 'processing')
            """
        )
        return cur.rowcount


def create_job(
    job_id: str,
    kind: str,
    webhook_url: str = "",
    source: str = "api",
    engine: str = "",
    model: str = "",
    voice: str = "",
    language: str = "",
    input_text: str = "",
    output_text: str = "",
    estimated_seconds: float = 3.0,
) -> None:
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    est_str = (now + timedelta(seconds=max(1.0, estimated_seconds))).strftime("%Y-%m-%d %H:%M:%S")
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                id, kind, status, progress, stage, webhook_url,
                source, engine, model, voice, language, input_text, output_text,
                started_at, completed_at, estimated_finish_at, created_at, updated_at
            ) VALUES (?, ?, 'queued', 0, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, '', '', ?, ?, ?)
            """,
            (
                job_id,
                kind,
                webhook_url,
                source,
                engine,
                model,
                voice,
                language,
                input_text,
                output_text,
                est_str,
                now_str,
                now_str,
            ),
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
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fields: list[str] = ["updated_at = datetime('now', 'localtime')"]
    vals: list[Any] = []
    if status is not None:
        fields.append("status = ?")
        vals.append(status)
        if status == "processing":
            fields.append("started_at = CASE WHEN started_at = '' THEN ? ELSE started_at END")
            vals.append(now_str)
        elif status in ("completed", "failed"):
            fields.append("completed_at = ?")
            vals.append(now_str)
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


def get_history_stats(kind: str | None = None) -> dict[str, int]:
    with db_session() as conn:
        if kind:
            proc = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE kind = ? AND status IN ('queued', 'processing')",
                (kind,),
            ).fetchone()[0]
            failed = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE kind = ? AND status = 'failed'",
                (kind,),
            ).fetchone()[0]
            succ = conn.execute(
                "SELECT COUNT(*) FROM generations WHERE kind = ?",
                (kind,),
            ).fetchone()[0]
        else:
            proc = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status IN ('queued', 'processing')"
            ).fetchone()[0]
            failed = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = 'failed'"
            ).fetchone()[0]
            succ = conn.execute(
                "SELECT COUNT(*) FROM generations"
            ).fetchone()[0]
        total = proc + succ + failed
        return {
            "total": int(total),
            "processing": int(proc),
            "success": int(succ),
            "failed": int(failed),
        }


def list_unified_history(limit: int = 10, offset: int = 0, kind: str | None = None) -> list[dict[str, Any]]:
    with db_session() as conn:
        job_query = """
            SELECT id, kind, status, progress, stage, source, engine, model, voice, language,
                   input_text, output_text, '' as audio_filename, 'mp3' as format,
                   0.0 as duration_sec, 0.0 as process_sec, 0.0 as rtf,
                   created_at, started_at, completed_at, estimated_finish_at, error,
                   rowid as sort_key, 1 as is_job
            FROM jobs
            WHERE status IN ('queued', 'processing', 'failed')
        """
        if kind:
            job_query += " AND kind = ?"
            job_rows = [dict(r) for r in conn.execute(job_query, (kind,)).fetchall()]
        else:
            job_rows = [dict(r) for r in conn.execute(job_query).fetchall()]

        gen_query = """
            SELECT id, kind, status, progress, 'done' as stage, source, engine, model, voice, language,
                   input_text, output_text, audio_filename, format,
                   duration_sec, process_sec, rtf,
                   created_at, started_at, completed_at, estimated_finish_at, error,
                   id as sort_key, 0 as is_job
            FROM generations
        """
        if kind:
            gen_query += " WHERE kind = ? ORDER BY id DESC"
            gen_rows = [dict(r) for r in conn.execute(gen_query, (kind,)).fetchall()]
        else:
            gen_query += " ORDER BY id DESC"
            gen_rows = [dict(r) for r in conn.execute(gen_query).fetchall()]

        # Active jobs at the top, followed by latest completed and failed
        active_jobs = [j for j in job_rows if j["status"] in ("queued", "processing")]
        other_jobs = [j for j in job_rows if j["status"] not in ("queued", "processing")]

        combined = active_jobs + sorted(other_jobs + gen_rows, key=lambda x: str(x.get("created_at", "")), reverse=True)
        return combined[offset : offset + limit]
