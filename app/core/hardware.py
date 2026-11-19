from __future__ import annotations

import platform
import shutil
import subprocess
from functools import lru_cache
from typing import Any

import psutil

from app.config import get_settings


def _has_nvidia_smi() -> str | None:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        ).strip()
        return out.splitlines()[0] if out else None
    except Exception:
        return None


@lru_cache
def detect_device() -> str:
    settings = get_settings()
    req = settings.device.strip().lower()
    if req in ("cuda", "mps", "cpu"):
        return req

    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass

    if _has_nvidia_smi():
        return "cuda"
    return "cpu"


def get_hardware_info() -> dict[str, Any]:
    vm = psutil.virtual_memory()
    device = detect_device()
    gpu_name = None

    if device == "cuda":
        gpu_name = _has_nvidia_smi()
        if not gpu_name:
            try:
                import torch  # type: ignore

                if torch.cuda.is_available():
                    gpu_name = torch.cuda.get_device_name(0)
            except ImportError:
                pass
    elif device == "mps":
        gpu_name = f"Apple Silicon ({platform.machine()})"

    settings = get_settings()
    try:
        disk = psutil.disk_usage(str(settings.data_path))
        disk_total_gb = round(disk.total / (1024**3), 2)
        disk_used_gb = round(disk.used / (1024**3), 2)
        disk_free_gb = round(disk.free / (1024**3), 2)
        disk_percent = disk.percent
    except Exception:
        disk_total_gb = disk_used_gb = disk_free_gb = disk_percent = 0.0

    def _dir_size_mb(path) -> float:
        if not path.exists():
            return 0.0
        tot = 0
        try:
            for p in path.rglob("*"):
                if p.is_file():
                    tot += p.stat().st_size
        except Exception:
            pass
        return round(tot / (1024 * 1024), 2)

    return {
        "os": platform.system(),
        "arch": platform.machine(),
        "python": platform.python_version(),
        "device": device,
        "gpu_name": gpu_name,
        "cpu_cores": psutil.cpu_count(logical=True) or 1,
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_total_gb": round(vm.total / (1024**3), 2),
        "ram_used_gb": round(vm.used / (1024**3), 2),
        "ram_available_gb": round(vm.available / (1024**3), 2),
        "ram_percent": vm.percent,
        "ffmpeg_available": shutil.which("ffmpeg") is not None,
        # Storage & Disk Usage
        "disk_total_gb": disk_total_gb,
        "disk_used_gb": disk_used_gb,
        "disk_free_gb": disk_free_gb,
        "disk_percent": disk_percent,
        "outputs_size_mb": _dir_size_mb(settings.outputs_path),
        "models_size_mb": _dir_size_mb(settings.models_path),
        # Retention Settings from .env
        "auto_clean_disk_percent": settings.auto_clean_disk_percent,
        "auto_clean_retention_days": settings.auto_clean_retention_days,
        "log_retention_days": settings.log_retention_days,
        "log_max_mb": settings.log_max_mb,
    }
