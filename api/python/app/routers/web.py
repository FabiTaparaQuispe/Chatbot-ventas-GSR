from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text
from starlette.templating import Jinja2Templates

from app.auth_core import normalize_user_role, roles_home_ventas, roles_ventas_general
from app.db import get_engine
from app.deps import ensure_csrf, session_user, templates
from app.historial_logic import (
    build_stats,
    clasificar_pregunta,
    fetch_historial_rows,
    fetch_historial_usernames,
    historial_preview,
    is_historial_filter_validation_error,
)
from app.settings import get_settings
from app.web_admin import process_gestion_post, process_usuarios_post

router = APIRouter(tags=["web"])


def init_templates(directory: Path) -> Jinja2Templates:
    t = Jinja2Templates(directory=str(directory))
    t.env.globals["roles_ventas_general"] = roles_ventas_general()
    t.env.globals["normalize_user_role"] = normalize_user_role
    return t


def _nom_corto(username: str) -> str:
    if not username:
        return ""
    p = username.split("@", 1)[0].replace(".", " ").replace("_", " ").replace("-", " ").strip()
    if not p:
        return ""
    return ", " + (p[0].upper() + p[1:] if len(p) > 1 else p.upper())


def _pop_flash(request: Request) -> tuple[str, str]:
    ok = str(request.session.pop("flash_ok", "") or "")
    err = str(request.session.pop("flash_err", "") or "")
    return ok, err


def _resolve_page(request: Request, role: str) -> str:
    raw = request.query_params.get("page")
    page = str(raw or "").strip()
    if not page:
        page = "ventas" if role in roles_home_ventas() else "chatbot"
    if page == "graficos":
        return "chatbot"
    allowed = [
        "ventas",
        "ventasgeneral2",
        "chatbot",
        "historial_preguntas",
        "usuarios",
        "gestion_usuarios",
    ]
    if page not in allowed:
        page = "ventas"
    return page


def _require_roles(role: str, page: str) -> str | None:
    if page == "usuarios":
        return None if role == "admin" else "ventas"
    if page == "gestion_usuarios":
        return None if role == "administrador" else "ventas"
    if page == "historial_preguntas":
        return None if role in ("estrategico", "administrador") else "ventas"
    if page in ("ventas", "ventasgeneral2"):
        return None if role in roles_ventas_general() else "chatbot"
    return None


def _page_title(page: str) -> str:
    return {
        "chatbot": "Chatbot",
        "historial_preguntas": "Preguntas al chatbot",
        "usuarios": "Usuarios",
        "gestion_usuarios": "Creación de usuarios",
        "ventasgeneral2": "Ventas general 2",
    }.get(page, "Ventas general")


@router.get("/", response_class=HTMLResponse)
def root_redirect() -> Any:
    return RedirectResponse("/index.php", status_code=302)


@router.post("/index.php")
async def index_post(request: Request) -> Any:
    user = session_user(request)
    if not user:
        return RedirectResponse("/login.php", status_code=302)
    page = str(request.query_params.get("page") or "").strip()
    form = {k: v for k, v in (await request.form()).multi_items()}
    flash: dict[str, str] = {}
    if page == "usuarios":
        process_usuarios_post(request, form, flash)
    elif page == "gestion_usuarios":
        process_gestion_post(request, form, user["username"], flash)
    else:
        flash["err"] = "POST no permitido en esta página."
    if flash.get("ok"):
        request.session["flash_ok"] = flash["ok"]
    if flash.get("err"):
        request.session["flash_err"] = flash["err"]
    return RedirectResponse(f"/index.php?page={page}", status_code=303)


@router.get("/index.php", response_class=HTMLResponse)
def index_get(request: Request) -> Any:
    if not request.session.get("active"):
        return RedirectResponse("/login.php", status_code=302)
    u = session_user(request)
    assert u is not None
    role = u["role"]
    page = _resolve_page(request, role)
    redirect_default = _require_roles(role, page)
    if redirect_default is not None:
        return RedirectResponse(f"/index.php?page={redirect_default}", status_code=302)

    s = get_settings()
    page_title = _page_title(page)
    load_ventas = page in ("ventas", "ventasgeneral2", "usuarios", "gestion_usuarios")
    skip_float = page == "chatbot"
    chat_script = True
    chat_cfg = {
        "chatApi": "/api/chat",
        "publicBase": "/",
        "modulesBase": "/modules/",
        "userKey": u["username"],
        "threadsApi": "/api/chat_threads.php",
    }

    ctx: dict[str, Any] = {
        "request": request,
        "page_title": page_title,
        "body_class": (
            "app-shell app-page-chatbot"
            if page == "chatbot"
            else ("app-shell app-page-historial-chat" if page == "historial_preguntas" else "app-shell")
        ),
        "load_ventas_assets": load_ventas,
        "skip_floating_chat": skip_float,
        "chat_script": chat_script,
        "chat_config": chat_cfg,
        "app_name": s.app_name,
        "usuario": u["username"],
        "role": role,
        "current_page": page,
        "csrf_token": ensure_csrf(request),
    }

    flash_ok, flash_err = _pop_flash(request)
    ctx["flash_ok"] = flash_ok
    ctx["flash_err"] = flash_err

    if page in ("ventas", "ventasgeneral2"):
        tpl = "pages/ventasgeneral.html"
    elif page == "chatbot":
        tpl = "pages/chatbot.html"
        ctx["nom_corto"] = _nom_corto(u["username"])
    elif page == "historial_preguntas":
        tpl = "pages/historial_preguntas.html"
        f_desde = str(request.query_params.get("fecha_desde") or "").strip()
        f_hasta = str(request.query_params.get("fecha_hasta") or "").strip()
        f_user = str(request.query_params.get("usuario") or "").strip()
        filtros_activos = bool(f_desde or f_hasta or f_user)
        engine = get_engine()
        with engine.connect() as conn:
            usernames, _ = fetch_historial_usernames(conn)
            rows, db_err = fetch_historial_rows(
                conn,
                fecha_desde=f_desde or None,
                fecha_hasta=f_hasta or None,
                username=f_user or None,
            )
        historial_filter_msg = ""
        if db_err and is_historial_filter_validation_error(db_err):
            historial_filter_msg = db_err
            db_err = ""
        stats = build_stats(rows) if rows and not db_err else {}
        total_p = len(rows)
        total_u = len({str(r.get("usuario") or "") for r in rows if str(r.get("usuario") or "")})
        top_categoria = next((k for k, v in sorted(stats.items(), key=lambda x: -x[1]) if v > 0), "—") if stats else "—"
        colores = {
            "Ventas / resumen": "#2563eb",
            "Clientes": "#7c3aed",
            "Productos": "#059669",
            "Por zona": "#d97706",
            "Notas de crédito": "#dc2626",
            "Comparativos": "#0891b2",
            "Proyecciones": "#9333ea",
            "Otras": "#6b7280",
        }
        ctx.update(
            {
                "historial_rows": rows,
                "db_error": db_err,
                "stats": stats,
                "total_preguntas": total_p,
                "total_usuarios": total_u,
                "top_categoria": top_categoria,
                "colores": colores,
                "clasificar": clasificar_pregunta,
                "preview": historial_preview,
                "historial_usernames": usernames,
                "filtro_fecha_desde": f_desde,
                "filtro_fecha_hasta": f_hasta,
                "filtro_usuario": f_user,
                "filtros_activos": filtros_activos,
                "historial_filter_msg": historial_filter_msg,
            }
        )
    elif page == "usuarios":
        tpl = "pages/usuarios.html"
        engine = get_engine()
        with engine.connect() as conn:
            users = [dict(r._mapping) for r in conn.execute(text("SELECT id, username, display_name, role, is_active, last_login_at, created_at FROM app_users ORDER BY created_at DESC, id DESC")).mappings().all()]
        ctx["users"] = users
        ctx["roles_disponibles"] = {
            "admin": "Admin",
            "gerencia": "Gerencia",
            "estrategico": "Estratégico",
            "tactico": "Táctico",
            "analista": "Analista",
            "lector": "Lector",
        }
    elif page == "gestion_usuarios":
        tpl = "pages/gestion_usuarios.html"
        engine = get_engine()
        with engine.connect() as conn:
            users = [
                dict(r._mapping)
                for r in conn.execute(
                    text(
                        "SELECT id, username, display_name, role, is_active, last_login_at, created_at FROM app_users "
                        "WHERE role IN ('administrador','estrategico','tactico','operativo') "
                        "ORDER BY created_at DESC, id DESC"
                    )
                ).mappings().all()
            ]
        ctx["users"] = users
        ctx["roles_crear"] = {
            "estrategico": "Estratégico",
            "tactico": "Táctico",
            "operativo": "Operativo",
        }
        ctx["roles_gestion"] = {
            "administrador": "Administrador",
            "estrategico": "Estratégico",
            "tactico": "Táctico",
            "operativo": "Operativo",
        }
    else:
        tpl = "pages/ventasgeneral.html"

    return templates(request).TemplateResponse(tpl, ctx)
