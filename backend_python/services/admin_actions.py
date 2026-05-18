from __future__ import annotations

import re
import secrets
from typing import Any

from services.db import get_connection
from services.passwords import hash_password
from services.roles import normalize_user_role


def _username_ok(u: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9._@-]{3,120}$", u))


def check_csrf(session: dict[str, Any], token: str | None) -> bool:
    return secrets.compare_digest(str(session.get("csrf_token") or ""), str(token or ""))


def process_usuarios_post(session: dict[str, Any], form: dict[str, str], flash: dict[str, str]) -> None:
    if not check_csrf(session, form.get("csrf_token")):
        flash["err"] = "Solicitud inválida (CSRF)."
        return
    accion = str(form.get("accion") or "")
    try:
        conn = get_connection()
        with conn.cursor() as cur:
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
                cur.execute(
                    "INSERT INTO app_users (username, password_hash, display_name, role, is_active) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (username, h, display_name or None, role, is_active),
                )
                flash["ok"] = "Usuario creado correctamente."
            elif accion == "toggle_active":
                uid = int(form.get("id") or 0)
                new_a = 1 if str(form.get("new_active") or "0") == "1" else 0
                if uid <= 0:
                    raise RuntimeError("Usuario inválido.")
                cur.execute("UPDATE app_users SET is_active = %s WHERE id = %s", (new_a, uid))
                flash["ok"] = "Estado actualizado."
            elif accion == "cambiar_rol":
                uid = int(form.get("id") or 0)
                role = normalize_user_role(str(form.get("role") or "").lower().strip())
                if uid <= 0:
                    raise RuntimeError("Usuario inválido.")
                if role not in ["admin", "gerencia", "estrategico", "tactico", "analista", "lector"]:
                    raise RuntimeError("Rol inválido.")
                cur.execute("UPDATE app_users SET role = %s WHERE id = %s", (role, uid))
                flash["ok"] = "Rol actualizado."
            elif accion == "reset_password":
                uid = int(form.get("id") or 0)
                password = str(form.get("new_password") or "")
                if uid <= 0:
                    raise RuntimeError("Usuario inválido.")
                if len(password) < 6:
                    raise RuntimeError("La contraseña debe tener al menos 6 caracteres.")
                cur.execute(
                    "UPDATE app_users SET password_hash = %s WHERE id = %s",
                    (hash_password(password), uid),
                )
                flash["ok"] = "Contraseña actualizada."
            else:
                raise RuntimeError("Acción no reconocida.")
    except Exception as e:
        flash["err"] = str(e)


def process_gestion_post(
    session: dict[str, Any],
    form: dict[str, str],
    my_username: str,
    flash: dict[str, str],
) -> None:
    if not check_csrf(session, form.get("csrf_token")):
        flash["err"] = "Solicitud inválida (CSRF)."
        return
    accion = str(form.get("accion") or "")
    roles_gestion = ("administrador", "estrategico", "tactico", "operativo")
    roles_crear = ("estrategico", "tactico", "operativo")
    roles_sql = "'administrador','estrategico','tactico','operativo'"
    try:
        conn = get_connection()
        with conn.cursor() as cur:
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
                cur.execute(
                    "INSERT INTO app_users (username, password_hash, display_name, role, is_active) "
                    "VALUES (%s, %s, %s, %s, 1)",
                    (username, h, display_name or None, role),
                )
                flash["ok"] = "Usuario creado correctamente."
            elif accion == "toggle_active":
                uid = int(form.get("id") or 0)
                new_a = 1 if str(form.get("new_active") or "0") == "1" else 0
                if uid <= 0:
                    raise RuntimeError("Usuario inválido.")
                cur.execute(
                    f"UPDATE app_users SET is_active = %s WHERE id = %s AND role IN ({roles_sql})",
                    (new_a, uid),
                )
                flash["ok"] = "Estado actualizado."
            elif accion == "cambiar_rol":
                uid = int(form.get("id") or 0)
                role = str(form.get("role") or "").lower().strip()
                if uid <= 0:
                    raise RuntimeError("Usuario inválido.")
                if role not in roles_gestion:
                    raise RuntimeError("Rol inválido.")
                cur.execute("SELECT username FROM app_users WHERE id = %s LIMIT 1", (uid,))
                row = cur.fetchone()
                target = str((row or {}).get("username") or "")
                if target and target == my_username:
                    raise RuntimeError("No puede cambiar su propio rol desde esta pantalla.")
                cur.execute(
                    f"UPDATE app_users SET role = %s WHERE id = %s AND role IN ({roles_sql})",
                    (role, uid),
                )
                flash["ok"] = "Rol actualizado."
            elif accion == "reset_password":
                uid = int(form.get("id") or 0)
                password = str(form.get("new_password") or "")
                if uid <= 0:
                    raise RuntimeError("Usuario inválido.")
                if len(password) < 6:
                    raise RuntimeError("La contraseña debe tener al menos 6 caracteres.")
                cur.execute(
                    f"UPDATE app_users SET password_hash = %s WHERE id = %s AND role IN ({roles_sql})",
                    (hash_password(password), uid),
                )
                flash["ok"] = "Contraseña actualizada."
            elif accion == "eliminar":
                uid = int(form.get("id") or 0)
                if uid <= 0:
                    raise RuntimeError("Usuario inválido.")
                cur.execute("SELECT username FROM app_users WHERE id = %s LIMIT 1", (uid,))
                row = cur.fetchone()
                target = str((row or {}).get("username") or "")
                if target == my_username:
                    raise RuntimeError("No puede eliminarse a sí mismo.")
                cur.execute(f"DELETE FROM app_users WHERE id = %s AND role IN ({roles_sql})", (uid,))
                flash["ok"] = "Usuario eliminado."
            else:
                raise RuntimeError("Acción no reconocida.")
    except Exception as e:
        flash["err"] = str(e)


def process_gestion_self_post(
    session: dict[str, Any],
    form: dict[str, str],
    my_username: str,
    flash: dict[str, str],
) -> None:
    """Usuario no admin: solo puede cambiar su propia contraseña en gestión."""
    if not check_csrf(session, form.get("csrf_token")):
        flash["err"] = "Solicitud inválida (CSRF)."
        return
    accion = str(form.get("accion") or "")
    if accion != "reset_password":
        flash["err"] = "Acción no permitida."
        return
    password = str(form.get("new_password") or "")
    if len(password) < 6:
        flash["err"] = "La contraseña debe tener al menos 6 caracteres."
        return
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE app_users SET password_hash = %s WHERE username = %s",
                (hash_password(password), my_username),
            )
        flash["ok"] = "Contraseña actualizada correctamente."
    except Exception as e:
        flash["err"] = str(e)
