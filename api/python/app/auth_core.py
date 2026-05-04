from __future__ import annotations

from passlib.context import CryptContext

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def normalize_user_role(r: str) -> str:
    r = r.strip().lower()
    if r == "gerente":
        return "gerencia"
    if r == "administrador":
        return "administrador"
    if r in ("estrategico", "estratégico"):
        return "estrategico"
    if r in ("tactico", "táctico"):
        return "tactico"
    if r == "usuario2":
        return "tactico"
    return r


def roles_home_ventas() -> list[str]:
    return ["admin", "gerencia", "administrador", "estrategico", "tactico", "operativo", "analista"]


def roles_ventas_general() -> list[str]:
    return list(dict.fromkeys([*roles_home_ventas(), "lector"]))


def verify_password(plain: str, password_hash: str) -> bool:
    if not password_hash or not plain:
        return False
    try:
        return _pwd.verify(plain, password_hash)
    except ValueError:
        return False


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)
