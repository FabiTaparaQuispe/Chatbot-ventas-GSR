from __future__ import annotations

import secrets
from typing import Any

from fastapi import Request
from starlette.templating import Jinja2Templates

from app.auth_core import normalize_user_role


def templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


def session_get(request: Request, key: str, default: Any = None) -> Any:
    return request.session.get(key, default)


def session_user(request: Request) -> dict[str, Any] | None:
    if not request.session.get("active"):
        return None
    return {
        "username": str(request.session.get("usuario") or ""),
        "role": normalize_user_role(str(request.session.get("role") or "lector")),
        "display_name": str(request.session.get("display_name") or "").strip(),
    }


def ensure_csrf(request: Request) -> str:
    t = request.session.get("csrf_token")
    if isinstance(t, str) and t:
        return t
    tok = secrets.token_hex(32)
    request.session["csrf_token"] = tok
    return tok


def check_csrf_post(request: Request, form_token: str | None) -> bool:
    if request.method != "POST":
        return True
    real = str(request.session.get("csrf_token") or "")
    sent = str(form_token or "")
    return sent != "" and real != "" and secrets.compare_digest(real, sent)
