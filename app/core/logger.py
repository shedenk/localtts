from __future__ import annotations

import os
import threading
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Optional

from app.config import get_settings

_LOG_LOCK = threading.Lock()
_MAX_MEMORY_LOGS = 500
_MEMORY_LOGS: deque[dict[str, Any]] = deque(maxlen=_MAX_MEMORY_LOGS)


def log(level: str, category: str, message: str) -> None:
    """Record a log entry into memory and persistent log file."""
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "timestamp": now_str,
        "level": level.upper(),
        "category": category.upper(),
        "source": category.upper(),
        "message": message,
    }

    # Print to stdout/console
    print(f"[{now_str}] [{level.upper()}] [{category.upper()}] {message}")

    settings = get_settings()
    log_file = settings.log_path

    with _LOG_LOCK:
        _MEMORY_LOGS.append(entry)
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{now_str}] [{level.upper()}] [{category.upper()}] {message}\n")
        except Exception:
            pass


def log_info(category: str, message: str) -> None:
    log("INFO", category, message)


def log_warning(category: str, message: str) -> None:
    log("WARNING", category, message)


def log_error(category: str, message: str) -> None:
    log("ERROR", category, message)


def get_recent_logs(limit: int = 150, level: Optional[str] = None) -> list[dict[str, Any]]:
    """Retrieve recent log entries from memory/file."""
    with _LOG_LOCK:
        items = list(_MEMORY_LOGS)

    if level and level.upper() != "ALL":
        items = [x for x in items if x["level"] == level.upper()]

    return items[-limit:][::-1]  # Newest first


def clean_log_file(retention_days: int = 3, max_mb: int = 10) -> dict[str, Any]:
    """Rotates log file if larger than max_mb or prunes lines older than retention_days."""
    settings = get_settings()
    log_file = settings.log_path

    if not log_file.exists():
        return {"rotated": False, "pruned_lines": 0, "size_mb": 0.0}

    cutoff = datetime.now() - timedelta(days=max(1, retention_days))
    pruned_count = 0
    rotated = False

    with _LOG_LOCK:
        try:
            size_mb = log_file.stat().st_size / (1024 * 1024)
            lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()

            # Filter lines by retention date
            valid_lines: list[str] = []
            for line in lines:
                if line.startswith("["):
                    # Extract timestamp: [YYYY-MM-DD HH:MM:SS]
                    ts_part = line[1:20]
                    try:
                        line_dt = datetime.strptime(ts_part, "%Y-%m-%d %H:%M:%S")
                        if line_dt < cutoff:
                            pruned_count += 1
                            continue
                    except ValueError:
                        pass
                valid_lines.append(line)

            # If still larger than max_mb, keep last 2000 lines
            if (len(valid_lines) * 100) > (max_mb * 1024 * 1024) or len(valid_lines) > 5000:
                valid_lines = valid_lines[-2000:]
                rotated = True

            log_file.write_text("\n".join(valid_lines) + ("\n" if valid_lines else ""), encoding="utf-8")
            final_size = log_file.stat().st_size / (1024 * 1024)

            return {
                "rotated": rotated,
                "pruned_lines": pruned_count,
                "size_mb": round(final_size, 2),
            }
        except Exception as e:
            return {"error": str(e), "rotated": False, "pruned_lines": 0}


def clear_logs() -> bool:
    """Clear memory logs and truncate log file."""
    settings = get_settings()
    with _LOG_LOCK:
        _MEMORY_LOGS.clear()
        try:
            settings.log_path.write_text("", encoding="utf-8")
            return True
        except Exception:
            return False
