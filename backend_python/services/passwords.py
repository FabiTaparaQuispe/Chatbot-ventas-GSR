"""Verificación alineada con api/python (passlib bcrypt) y hashes legacy Werkzeug."""

from __future__ import annotations

from passlib.context import CryptContext
from werkzeug.security import check_password_hash as werkzeug_check

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, stored_hash: str) -> bool:
    if not plain or not stored_hash:
        return False
    h = str(stored_hash).strip()
    if not h:
        return False
    if h.startswith(("pbkdf2:", "scrypt:")):
        try:
            return bool(werkzeug_check(h, plain))
        except (ValueError, TypeError):
            return False
    try:
        return bool(_pwd.verify(plain, h))
    except ValueError:
        return False
