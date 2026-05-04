from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.paths import public_assets_dir, templates_dir
from app.routers import auth, chat, chat_config, dt_api, reports, sql_texto_route, stats_api, threads, web
from app.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="session",
        same_site="lax",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    tpl = web.init_templates(Path(templates_dir()))
    app.state.templates = tpl
    app.state.settings = settings

    assets = public_assets_dir()
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    app.include_router(chat.router)
    app.include_router(threads.router)
    app.include_router(stats_api.router)
    app.include_router(dt_api.router)
    app.include_router(sql_texto_route.router)
    app.include_router(chat_config.router)
    app.include_router(auth.router)
    app.include_router(web.router)
    app.include_router(reports.router)
    return app


app = create_app()
