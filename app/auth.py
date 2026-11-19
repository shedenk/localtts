from __future__ import annotations

import secrets
from fastapi import Request, HTTPException, status
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.config import get_settings

COOKIE_NAME = "tts_local_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def _get_serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    return URLSafeTimedSerializer(settings.session_secret, salt="tts-local-auth")


def create_session_token(username: str) -> str:
    return _get_serializer().dumps({"u": username})


def verify_session_token(token: str | None) -> str | None:
    if not token:
        return None
    try:
        data = _get_serializer().loads(token, max_age=SESSION_MAX_AGE)
        return data.get("u")
    except (BadSignature, SignatureExpired):
        return None


def verify_ui_credentials(username: str, password: str) -> bool:
    settings = get_settings()
    if not settings.ui_auth_enabled:
        return True
    u_ok = secrets.compare_digest(username, settings.auth_username)
    p_ok = secrets.compare_digest(password, settings.auth_password)
    return u_ok and p_ok


def is_ui_authenticated(request: Request) -> bool:
    settings = get_settings()
    if not settings.ui_auth_enabled:
        return True
    token = request.cookies.get(COOKIE_NAME)
    user = verify_session_token(token)
    return user is not None and secrets.compare_digest(user, settings.auth_username)


def _extract_api_key(request: Request) -> str | None:
    settings = get_settings()
    # 1. Check Authorization: Bearer <key>
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    # 2. Check custom header (default X-API-Key)
    custom_key = request.headers.get(settings.api_key_header, "")
    if custom_key:
        return custom_key.strip()
    # 3. Also accept X-API-Key fallback if custom header was changed
    fallback_key = request.headers.get("X-API-Key", "")
    if fallback_key:
        return fallback_key.strip()
    return None


def require_ui_auth(request: Request) -> None:
    """Protect Studio UI & internal /api/* endpoints."""
    if not is_ui_authenticated(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized. Please login first.",
        )


def require_api_auth(request: Request) -> None:
    """
    Protect /v1/* OpenAI-compatible API endpoints.
    - If API_KEY in .env is empty: open access (no header needed).
    - If API_KEY is set: require Bearer <API_KEY> or <API_KEY_HEADER>: <API_KEY>,
      OR a valid logged-in UI session cookie.
    """
    settings = get_settings()
    if not settings.api_auth_enabled:
        return
    if is_ui_authenticated(request):
        return
    provided = _extract_api_key(request)
    if provided and secrets.compare_digest(provided, settings.api_key):
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Invalid or missing API key. Send Authorization: Bearer <API_KEY> or {settings.api_key_header}: <API_KEY>.",
    )
