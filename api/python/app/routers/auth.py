from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text

from app.auth_core import normalize_user_role, verify_password
from app.db import get_engine
from app.deps import check_csrf_post, ensure_csrf, templates
from app.settings import get_settings

router = APIRouter(tags=["auth"])


@router.get("/login.php", response_class=HTMLResponse)
def login_get(request: Request) -> Any:
    if request.session.get("active"):
        return RedirectResponse("/index.php", status_code=302)
    s = get_settings()
    csrf = ensure_csrf(request)
    return templates(request).TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": "",
            "csrf_token": csrf,
            "app_name": s.app_name,
            "app_company": s.app_company,
        },
    )


@router.post("/login.php")
def login_post(
    request: Request,
    usuario: str = Form(""),
    clave: str = Form(""),
    csrf_token: str = Form(""),
) -> Any:
    if request.session.get("active"):
        return RedirectResponse("/index.php", status_code=302)
    s = get_settings()
    if not check_csrf_post(request, csrf_token):
        csrf = ensure_csrf(request)
        return templates(request).TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Solicitud inválida (CSRF).",
                "csrf_token": csrf,
                "app_name": s.app_name,
                "app_company": s.app_company,
            },
            status_code=400,
        )
    u = usuario.strip()
    err = ""
    if not u or not clave:
        err = "Usuario y contraseña requeridos."
    else:
        try:
            engine = get_engine()
            with engine.begin() as conn:
                row = (
                    conn.execute(
                        text(
                            "SELECT password_hash, is_active, role, display_name FROM app_users WHERE username = :u LIMIT 1"
                        ),
                        {"u": u},
                    )
                    .mappings()
                    .first()
                )
                ok = False
                role = ""
                display_name = ""
                if row and int(row.get("is_active") or 0) == 1:
                    h = str(row.get("password_hash") or "")
                    ok = bool(h) and verify_password(clave, h)
                    if ok:
                        conn.execute(
                            text("UPDATE app_users SET last_login_at = NOW() WHERE username = :u"),
                            {"u": u},
                        )
                        role = normalize_user_role(str(row.get("role") or "").lower().strip())
                        if not role:
                            role = "lector"
                        display_name = str(row.get("display_name") or "").strip()
                if ok:
                    request.session["active"] = True
                    request.session["usuario"] = u
                    request.session["role"] = role
                    request.session["display_name"] = display_name
                    return RedirectResponse("/index.php", status_code=302)
                err = "Usuario o contraseña incorrectos."
        except Exception:
            err = (
                "No se pudo validar el acceso (tablas de usuarios no configuradas). "
                "Ejecute `docs/schema_auth_chat.sql` en la BD."
            )
    csrf = ensure_csrf(request)
    return templates(request).TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": err,
            "csrf_token": csrf,
            "app_name": s.app_name,
            "app_company": s.app_company,
        },
        status_code=401 if err else 200,
    )


@router.get("/logout.php")
def logout(request: Request) -> Any:
    request.session.clear()
    return RedirectResponse("/login.php", status_code=302)
