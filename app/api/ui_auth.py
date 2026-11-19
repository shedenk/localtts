from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.auth import (
    COOKIE_NAME,
    SESSION_MAX_AGE,
    create_session_token,
    is_ui_authenticated,
    verify_ui_credentials,
)
from app.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.get("/status")
def auth_status(request: Request):
    settings = get_settings()
    return {
        "ui_auth_enabled": settings.ui_auth_enabled,
        "api_auth_enabled": settings.api_auth_enabled,
        "authenticated": is_ui_authenticated(request),
        "username": settings.auth_username if is_ui_authenticated(request) else None,
    }


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    settings = get_settings()
    if not settings.ui_auth_enabled:
        return {"ok": True, "message": "UI auth disabled in .env"}

    if not verify_ui_credentials(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_session_token(payload.username)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return {"ok": True, "username": payload.username}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}
