from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.openai_compat import router as openai_router
from app.api.studio import router as studio_router
from app.api.ui_auth import router as auth_router
from app.auth import is_ui_authenticated
from app.config import get_settings
from app.core.manager import get_manager, idle_cleanup_loop
from app.db import init_db

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings().ensure_dirs()
    init_db()
    get_manager()

    stop_event = asyncio.Event()
    cleanup_task = asyncio.create_task(idle_cleanup_loop(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        get_manager().unload_all()


app = FastAPI(
    title=get_settings().app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(openai_router)
app.include_router(studio_router)

if (WEB_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(WEB_DIR / "assets")), name="assets")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/login")
def login_page(request: Request):
    if is_ui_authenticated(request):
        return RedirectResponse(url="/", status_code=302)
    return FileResponse(WEB_DIR / "login.html")


@app.get("/")
def index_page(request: Request):
    if not is_ui_authenticated(request):
        return RedirectResponse(url="/login", status_code=302)
    return FileResponse(WEB_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port)
