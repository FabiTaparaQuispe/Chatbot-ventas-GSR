from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text

from app.auth_core import hash_password, normalize_user_role
from app.db import get_engine
from app.deps import check_csrf_post


def _username_ok(u: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9._@-]{3,120}$", u))


def process_usuarios_post(
    request: Any,
    form: dict[str, Any],
    flash: dict[str, str],
) -> None:
    if not check_csrf_post(request, str(form.get("csrf_token") or "")):
        flash["err"] = "Solicitud inválida (CSRF)."
        return
    accion = str(form.get("accion") or "")
    try:
        engine = get_engine()
        with engine.begin() as conn:
            if accion == "crear":
                username = str(form.get("username") or "").strip()
                display_name = str(form.get("display_name") or "").strip()
                role = normalize_user_role(str(form.get("role") or "").lower().strip())
                password = str(form.get("password") or "")
                is_active = 1 if str(form.get("is_active") or "1") == "1" else 0
                roles_ok = ["admin", "gerencia", "estrategico", "tactico", "analista", "lector"]
                if not username or not password:
                    raise RuntimeError("Usuario y contraseña son obligatorios.")
                if not _username_ok(username):
                    raise RuntimeError(
                        "El usuario debe tener 3–120 caracteres (letras, números, punto, guion, @ o _)."
                    )
                if role not in roles_ok:
                    role = "lector"
                if len(password) < 6:
                    raise RuntimeError("La contraseña debe tener al menos 6 caracteres.")
                h = hash_password(password)
                conn.execute(
                    text(
                        "INSERT INTO app_users (username, password_hash, display_name, role, is_active) "
                        "VALUES (:u, :h, :d, :r, :a)"
                    ),
                    {"u": username, "h": h, "d": display_name or None, "r": role, "a": is_active},
                )
                flash["ok"] = "Usuario creado correctamente."
            elif accion == "toggle_active":
                uid = int(form.get("id") or 0)
                new_a = 1 if str(form.get("new_active") or "0") == "1" else 0
                if uid <= 0:
                    raise RuntimeError("Usuario inválido.")
                conn.execute(text("UPDATE app_users SET is_active = :a WHERE id = :id"), {"a": new_a, "id": uid})
                flash["ok"] = "Estado actualizado."
            elif accion == "cambiar_rol":
                uid = int(form.get("id") or 0)
                role = normalize_user_role(str(form.get("role") or "").lower().strip())
                if uid <= 0:
                    raise RuntimeError("Usuario inválido.")
                if role not in ["admin", "gerencia", "estrategico", "tactico", "analista", "lector"]:
                    raise RuntimeError("Rol inválido.")
                conn.execute(text("UPDATE app_users SET role = :r WHERE id = :id"), {"r": role, "id": uid})
                flash["ok"] = "Rol actualizado."
            elif accion == "reset_password":
                uid = int(form.get("id") or 0)
                password = str(form.get("new_password") or "")
                if uid <= 0:
                    raise RuntimeError("Usuario inválido.")
                if len(password) < 6:
                    raise RuntimeError("La contraseña debe tener al menos 6 caracteres.")
                conn.execute(
                    text("UPDATE app_users SET password_hash = :h WHERE id = :id"),
                    {"h": hash_password(password), "id": uid},
                )
                flash["ok"] = "Contraseña actualizada."
            else:
                raise RuntimeError("Acción no reconocida.")
    except Exception as e:
        flash["err"] = str(e)


def process_gestion_post(
    request: Any,
    form: dict[str, Any],
    my_username: str,
    flash: dict[str, str],
) -> None:
    if not check_csrf_post(request, str(form.get("csrf_token") or "")):
        flash["err"] = "Solicitud inválida (CSRF)."
        return
    accion = str(form.get("accion") or "")
    roles_gestion = ("administrador", "estrategico", "tactico", "operativo")
    roles_crear = ("estrategico", "tactico", "operativo")
    roles_sql = "'administrador','estrategico','tactico','operativo'"
    try:
        engine = get_engine()
        with engine.begin() as conn:
            if accion == "crear":
                username = str(form.get("username") or "").strip()
                display_name = str(form.get("display_name") or "").strip()
                role = str(form.get("role") or "").lower().strip()
                password = str(form.get("password") or "")
                if not username or not password:
                    raise RuntimeError("Usuario y contraseña son obligatorios.")
                if not _username_ok(username):
                    raise RuntimeError(
                        "El usuario debe tener 3–120 caracteres (letras, números, punto, guion, @ o _)."
                    )
                if role not in roles_crear:
                    raise RuntimeError("Rol inválido.")
                if len(password) < 6:
                    raise RuntimeError("La contraseña debe tener al menos 6 caracteres.")
                h = hash_password(password)
                conn.execute(
                    text(
                        "INSERT INTO app_users (username, password_hash, display_name, role, is_active) "
                        "VALUES (:u, :h, :d, :r, 1)"
                    ),
                    {"u": username, "h": h, "d": display_name or None, "r": role},
                )
                flash["ok"] = "Usuario creado correctamente."
            elif accion == "toggle_active":
                uid = int(form.get("id") or 0)
                new_a = 1 if str(form.get("new_active") or "0") == "1" else 0
                if uid <= 0:
                    raise RuntimeError("Usuario inválido.")
                conn.execute(
                    text(f"UPDATE app_users SET is_active = :a WHERE id = :id AND role IN ({roles_sql})"),
                    {"a": new_a, "id": uid},
                )
                flash["ok"] = "Estado actualizado."
            elif accion == "cambiar_rol":
                uid = int(form.get("id") or 0)
                role = str(form.get("role") or "").lower().strip()
                if uid <= 0:
                    raise RuntimeError("Usuario inválido.")
                if role not in roles_gestion:
                    raise RuntimeError("Rol inválido.")
                row = conn.execute(
                    text("SELECT username FROM app_users WHERE id = :id LIMIT 1"), {"id": uid}
                ).scalar()
                target = str(row or "")
                if target and target == my_username:
                    raise RuntimeError("No puede cambiar su propio rol desde esta pantalla.")
                conn.execute(
                    text(f"UPDATE app_users SET role = :r WHERE id = :id AND role IN ({roles_sql})"),
                    {"r": role, "id": uid},
                )
                flash["ok"] = "Rol actualizado."
            elif accion == "reset_password":
                uid = int(form.get("id") or 0)
                password = str(form.get("new_password") or "")
                if uid <= 0:
                    raise RuntimeError("Usuario inválido.")
                if len(password) < 6:
                    raise RuntimeError("La contraseña debe tener al menos 6 caracteres.")
                conn.execute(
                    text(f"UPDATE app_users SET password_hash = :h WHERE id = :id AND role IN ({roles_sql})"),
                    {"h": hash_password(password), "id": uid},
                )
                flash["ok"] = "Contraseña actualizada."
            elif accion == "eliminar":
                uid = int(form.get("id") or 0)
                if uid <= 0:
                    raise RuntimeError("Usuario inválido.")
                row = conn.execute(
                    text("SELECT username FROM app_users WHERE id = :id LIMIT 1"), {"id": uid}
                ).scalar()
                target = str(row or "")
                if target == my_username:
                    raise RuntimeError("No puede eliminarse a sí mismo.")
                conn.execute(
                    text(f"DELETE FROM app_users WHERE id = :id AND role IN ({roles_sql})"), {"id": uid}
                )
                flash["ok"] = "Usuario eliminado."
            else:
                raise RuntimeError("Acción no reconocida.")
    except Exception as e:
        flash["err"] = str(e)
