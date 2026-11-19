from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import os
from pathlib import Path
from typing import Any

import psutil

from app.config import get_settings
from app.core.logger import clean_log_file, log_info, log_warning
from app.db import db_session


def run_storage_cleanup() -> dict[str, Any]:
    """
    Performs storage maintenance:
    1. Removes audio files older than AUTO_CLEAN_RETENTION_DAYS (default 30 days).
    2. If disk space >= AUTO_CLEAN_DISK_PERCENT (default 75%), removes oldest audio files.
    3. Cleans log file if > LOG_MAX_MB or older than LOG_RETENTION_DAYS (default 3 days).
    4. Purges SQLite api_logs older than LOG_RETENTION_DAYS.
    """
    settings = get_settings()
    out_dir = settings.outputs_path
    disk_before = psutil.disk_usage(str(settings.data_path))
    percent_before = disk_before.percent

    cleaned_by_age = 0
    cleaned_by_threshold = 0
    freed_bytes = 0

    cutoff_date = datetime.now() - timedelta(days=max(1, settings.auto_clean_retention_days))

    # 1. Clean files older than retention days
    deleted_filenames: list[str] = []
    if out_dir.exists():
        files_info: list[tuple[Path, float, int]] = []  # (path, mtime, size)
        for p in out_dir.iterdir():
            if p.is_file() and not p.name.startswith("."):
                try:
                    stat = p.stat()
                    files_info.append((p, stat.st_mtime, stat.st_size))
                except Exception:
                    pass

        # Sort by mtime ascending (oldest first)
        files_info.sort(key=lambda x: x[1])

        # Step 1A: Remove by age (> retention days)
        cutoff_ts = cutoff_date.timestamp()
        remaining_files = []
        for p, mtime, size in files_info:
            if mtime < cutoff_ts:
                try:
                    p.unlink()
                    cleaned_by_age += 1
                    freed_bytes += size
                    deleted_filenames.append(p.name)
                except Exception:
                    remaining_files.append((p, mtime, size))
            else:
                remaining_files.append((p, mtime, size))

        # Step 1B: If disk usage is still >= threshold (default 75%), delete oldest remaining files
        current_disk = psutil.disk_usage(str(settings.data_path))
        if current_disk.percent >= settings.auto_clean_disk_percent:
            log_warning(
                "STORAGE",
                f"Disk space {current_disk.percent}% exceeds threshold {settings.auto_clean_disk_percent}%. Cleaning oldest outputs...",
            )
            for p, mtime, size in remaining_files:
                try:
                    p.unlink()
                    cleaned_by_threshold += 1
                    freed_bytes += size
                    deleted_filenames.append(p.name)
                    # Check disk again
                    if psutil.disk_usage(str(settings.data_path)).percent < settings.auto_clean_disk_percent:
                        break
                except Exception:
                    pass

    # 2. Update SQLite generations for deleted files
    if deleted_filenames:
        with db_session() as conn:
            for name in deleted_filenames:
                conn.execute("UPDATE generations SET audio_filename = '' WHERE audio_filename = ?", (name,))

    # 3. Prune SQLite api_logs older than LOG_RETENTION_DAYS (default 3 days)
    logs_cutoff = (datetime.now() - timedelta(days=max(1, settings.log_retention_days))).strftime("%Y-%m-%d %H:%M:%S")
    pruned_db_logs = 0
    try:
        with db_session() as conn:
            cur = conn.execute("DELETE FROM api_logs WHERE created_at < ?", (logs_cutoff,))
            pruned_db_logs = cur.rowcount
    except Exception:
        pass

    # 4. Clean system log file
    log_clean_result = clean_log_file(settings.log_retention_days, settings.log_max_mb)

    disk_after = psutil.disk_usage(str(settings.data_path))
    freed_mb = round(freed_bytes / (1024 * 1024), 2)

    total_cleaned = cleaned_by_age + cleaned_by_threshold
    log_info(
        "STORAGE",
        f"Cleanup finished: {total_cleaned} files removed ({freed_mb} MB freed). Disk: {percent_before}% -> {disk_after.percent}%. DB logs pruned: {pruned_db_logs}.",
    )

    return {
        "ok": True,
        "cleaned_files": total_cleaned,
        "cleaned_by_age": cleaned_by_age,
        "cleaned_by_threshold": cleaned_by_threshold,
        "freed_mb": freed_mb,
        "disk_percent_before": percent_before,
        "disk_percent_after": disk_after.percent,
        "disk_free_gb": round(disk_after.free / (1024**3), 2),
        "pruned_db_logs": pruned_db_logs,
        "log_file_status": log_clean_result,
    }


async def storage_cleaner_loop(stop_event: asyncio.Event) -> None:
    """Runs periodic storage maintenance every 1 hour."""
    # Run once shortly after startup
    await asyncio.sleep(5)
    try:
        run_storage_cleanup()
    except Exception as exc:
        log_warning("STORAGE", f"Initial storage cleanup failed: {exc}")

    while not stop_event.is_set():
        try:
            # Wait 1 hour (3600s) or until stopped
            await asyncio.wait_for(stop_event.wait(), timeout=3600.0)
        except asyncio.TimeoutError:
            try:
                run_storage_cleanup()
            except Exception as exc:
                log_warning("STORAGE", f"Periodic storage cleanup error: {exc}")
        except asyncio.CancelledError:
            break
