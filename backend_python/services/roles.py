"""Normalización de roles (alineado con api/python/app/auth_core.py)."""


def normalize_user_role(r: str) -> str:
    r = str(r or "").strip().lower()
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
