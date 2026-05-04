from __future__ import annotations

import secrets
from typing import Any

from flask import Blueprint, redirect, render_template, request, session, url_for

from services.admin_actions import process_gestion_post, process_usuarios_post
from services.db import get_connection
from services.historial_data import (
    build_stats,
    clasificar_pregunta,
    fetch_historial_rows,
    historial_preview,
)
from services.roles import normalize_user_role
from services.urlmap import API_CHAT, chat_assistant_config_dict

bp = Blueprint("pages", __name__)

APP_NAME = "Ventas · cia2026"
APP_COMPANY = "GRANJA RINCONADA DEL SUR S.A."

ROLES_HOME_VENTAS = {
    "admin",
    "gerencia",
    "administrador",
    "estrategico",
    "tactico",
    "operativo",
    "analista",
}
ROLES_VENTAS_GENERAL = ROLES_HOME_VENTAS | {"lector"}

# Quién ve el menú / páginas administrativas
ROLES_HISTORIAL = {"admin", "estrategico", "administrador"}
ROLES_GESTION_USUARIOS = {"admin", "administrador"}


def require_login(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("active"):
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated


def user_role() -> str:
    return str(session.get("role") or "lector").lower().strip()


def _ensure_csrf() -> str:
    tok = secrets.token_urlsafe(24)
    session["csrf_token"] = tok
    return tok


def _pop_flash() -> tuple[str, str]:
    ok = str(session.pop("flash_ok", "") or "")
    err = str(session.pop("flash_err", "") or "")
    return ok, err


@bp.route("/", methods=["GET", "POST"])
@bp.route("/index.php", methods=["GET", "POST"])
@require_login
def index():
    role = user_role()
    page = request.args.get("page", "").strip()

    if request.method == "POST":
        flash: dict[str, str] = {}
        if page == "usuarios" and role == "admin":
            process_usuarios_post(session, dict(request.form), flash)
        elif page == "gestion_usuarios" and role in ROLES_GESTION_USUARIOS:
            process_gestion_post(session, dict(request.form), str(session.get("usuario") or ""), flash)
        else:
            flash["err"] = "POST no permitido en esta página."
        if flash.get("ok"):
            session["flash_ok"] = flash["ok"]
        if flash.get("err"):
            session["flash_err"] = flash["err"]
        return redirect(url_for("pages.index", page=page or "ventas"))

    if not page:
        page = "ventas" if role in ROLES_HOME_VENTAS else "chatbot"

    if page == "graficos":
        return redirect(url_for("pages.index", page="chatbot"))

    allowed = {
        "ventas",
        "ventasgeneral2",
        "chatbot",
        "historial_preguntas",
        "usuarios",
        "gestion_usuarios",
    }
    if page not in allowed:
        page = "ventas"

    if page == "usuarios" and role != "admin":
        return redirect(url_for("pages.index"))
    if page == "gestion_usuarios" and role not in ROLES_GESTION_USUARIOS:
        return redirect(url_for("pages.index"))
    if page == "historial_preguntas" and role not in ROLES_HISTORIAL:
        return redirect(url_for("pages.index"))
    if page in ("ventas", "ventasgeneral2") and role not in ROLES_VENTAS_GENERAL:
        return redirect(url_for("pages.index", page="chatbot"))

    page_titles = {
        "chatbot": "Chatbot",
        "historial_preguntas": "Preguntas al chatbot",
        "usuarios": "Usuarios",
        "gestion_usuarios": "Creación de usuarios",
        "ventasgeneral2": "Ventas general 2",
    }
    page_title = page_titles.get(page, "Ventas general")

    load_ventas_assets = page in ("ventas", "ventasgeneral2")
    load_listado_skin = page in ("usuarios", "gestion_usuarios")
    skip_floating_chat = page == "chatbot"
    body_class = (
        "app-page-chatbot"
        if page == "chatbot"
        else ("app-page-historial-chat" if page == "historial_preguntas" else "")
    )

    usuario = session.get("usuario", "")
    nom_corto = ""
    if usuario:
        part = usuario.split("@")[0]
        part = part.replace(".", " ").replace("_", " ").replace("-", " ").strip()
        if part:
            nom_corto = ", " + part.capitalize()

    flash_ok, flash_err = _pop_flash()
    csrf_token = _ensure_csrf()

    ctx: dict[str, Any] = {
        "page": page,
        "page_title": page_title,
        "app_name": APP_NAME,
        "app_company": APP_COMPANY,
        "load_ventas_assets": load_ventas_assets,
        "load_listado_skin": load_listado_skin,
        "skip_floating_chat": skip_floating_chat,
        "body_class": body_class,
        "role": role,
        "usuario": usuario,
        "display_name": session.get("display_name", ""),
        "nom_corto": nom_corto,
        "ventas_public_base": "/",
        "ventas_modules_web_base": "/modules/",
        "ventas_chat_api_url": API_CHAT.lstrip("/"),
        "ventas_chat_user_key": usuario or "anon",
        "roles_ventas_general": ROLES_VENTAS_GENERAL,
        "roles_home_ventas": ROLES_HOME_VENTAS,
        "flash_ok": flash_ok,
        "flash_err": flash_err,
        "csrf_token": csrf_token,
        "chat_assistant_config": chat_assistant_config_dict(usuario or "anon"),
    }

    tpl = f"pages/{page}.html"

    if page == "historial_preguntas":
        conn = get_connection()
        rows, db_err = fetch_historial_rows(conn)
        stats = build_stats(rows) if rows and not db_err else {}
        total_p = len(rows)
        total_u = len({str(r.get("usuario") or "") for r in rows if str(r.get("usuario") or "")})
        top_categoria = (
            next((k for k, v in sorted(stats.items(), key=lambda x: -x[1]) if v > 0), "—") if stats else "—"
        )
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
            }
        )
    elif page == "usuarios":
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, display_name, role, is_active, last_login_at, created_at "
                "FROM app_users ORDER BY created_at DESC, id DESC"
            )
            users = cur.fetchall() or []
        ctx["users"] = [dict(u) for u in users]
        ctx["roles_disponibles"] = {
            "admin": "Admin",
            "gerencia": "Gerencia",
            "estrategico": "Estratégico",
            "tactico": "Táctico",
            "analista": "Analista",
            "lector": "Lector",
        }
        ctx["normalize_user_role"] = normalize_user_role
    elif page == "gestion_usuarios":
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, display_name, role, is_active, last_login_at, created_at "
                "FROM app_users WHERE role IN ('administrador','estrategico','tactico','operativo') "
                "ORDER BY created_at DESC, id DESC"
            )
            users = cur.fetchall() or []
        ctx["users"] = [dict(u) for u in users]
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
        ctx["normalize_user_role"] = normalize_user_role

    return render_template(tpl, **ctx)
