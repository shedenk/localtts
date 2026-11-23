from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.core.logger import log_warning

BYPASS_PATHS = {"/health"}


def get_client_ip(request: Request) -> str:
    """Extract real client IP, supporting Cloudflare, Coolify/Traefik, and Nginx proxies."""
    raw_ip = ""
    cf_ip = request.headers.get("CF-Connecting-IP", "").strip()
    if cf_ip:
        raw_ip = cf_ip
    else:
        xff = request.headers.get("X-Forwarded-For", "").strip()
        if xff:
            raw_ip = xff.split(",")[0].strip()
        else:
            x_real = request.headers.get("X-Real-IP", "").strip()
            if x_real:
                raw_ip = x_real
            elif request.client and request.client.host:
                raw_ip = request.client.host.strip()

    # Normalize IPv6-mapped IPv4 addresses like ::ffff:127.0.0.1
    if raw_ip.lower().startswith("::ffff:"):
        raw_ip = raw_ip[7:]
    return raw_ip


def is_ip_allowed(client_ip: str, allowed_ips: list[str]) -> bool:
    """Check whether client_ip matches any IP or CIDR entry in allowed_ips."""
    if not allowed_ips:
        return True
    if "*" in allowed_ips:
        return True
    if not client_ip:
        return False

    try:
        ip_obj = ipaddress.ip_address(client_ip)
    except ValueError:
        return False

    for entry in allowed_ips:
        item = entry.strip().lower()
        if not item:
            continue
        if item == "localhost":
            if ip_obj.is_loopback:
                return True
            continue
        try:
            if "/" in item:
                net = ipaddress.ip_network(item, strict=False)
                if ip_obj in net:
                    return True
            else:
                target = ipaddress.ip_address(item)
                if ip_obj == target:
                    return True
        except ValueError:
            continue
    return False


def extract_hostname(value: str) -> str:
    """Extract lowercase hostname without scheme or port from Host/Origin/Referer."""
    val = (value or "").strip()
    if not val:
        return ""
    if "://" in val:
        parsed = urlparse(val)
        return (parsed.hostname or "").lower()
    # Handle bracketed IPv6 [::1]:8000
    if val.startswith("["):
        end = val.find("]")
        return val[1:end].lower() if end != -1 else val.lower()
    # Strip :port if single colon
    if ":" in val:
        return val.split(":", 1)[0].strip().lower()
    return val.lower()


def _normalize_domain_pattern(pattern: str) -> str:
    p = (pattern or "").strip().lower()
    if "://" in p:
        p = extract_hostname(p)
    elif "/" in p:
        p = p.split("/", 1)[0]
    if ":" in p and not p.startswith("["):
        p = p.split(":", 1)[0]
    return p


def is_domain_match(hostname: str, pattern: str) -> bool:
    if not hostname:
        return False
    p = _normalize_domain_pattern(pattern)
    if not p:
        return False
    if p == "*":
        return True
    if p.startswith("*."):
        base = p[2:]
        return hostname == base or hostname.endswith("." + base)
    return hostname == p


def get_request_host(request: Request) -> str:
    fwd_host = request.headers.get("X-Forwarded-Host", "").strip()
    if fwd_host:
        return extract_hostname(fwd_host.split(",")[0])
    return extract_hostname(request.headers.get("Host", ""))


def check_domain_allowed(request: Request, allowed_domains: list[str]) -> tuple[bool, str]:
    """Validate Origin/Referer (if present) or Host against ALLOWED_DOMAINS."""
    if not allowed_domains:
        return True, ""

    origin = request.headers.get("Origin", "").strip()
    referer = request.headers.get("Referer", "").strip()
    origin_host = extract_hostname(origin) if origin else extract_hostname(referer)
    req_host = get_request_host(request)

    target_host = origin_host or req_host
    for pattern in allowed_domains:
        if is_domain_match(target_host, pattern):
            return True, target_host
    return False, target_host or "unknown"


class AccessControlMiddleware(BaseHTTPMiddleware):
    """Enforce ALLOWED_IPS and ALLOWED_DOMAINS whitelist from .env."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in BYPASS_PATHS:
            return await call_next(request)

        settings = get_settings()
        allowed_ips = settings.allowed_ip_list
        allowed_domains = settings.allowed_domain_list

        if allowed_ips:
            client_ip = get_client_ip(request)
            if not is_ip_allowed(client_ip, allowed_ips):
                log_warning("SECURITY", f"Blocked IP {client_ip} accessing {request.url.path}")
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": f"Access denied: IP '{client_ip}' is not in ALLOWED_IPS.",
                    },
                )

        if allowed_domains:
            ok, target_host = check_domain_allowed(request, allowed_domains)
            if not ok:
                log_warning("SECURITY", f"Blocked domain '{target_host}' accessing {request.url.path}")
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": f"Access denied: Domain '{target_host}' is not in ALLOWED_DOMAINS.",
                    },
                )

        return await call_next(request)
