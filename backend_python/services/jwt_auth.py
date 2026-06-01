import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

_SECRET = os.getenv('JWT_SECRET', '')
_EXPIRE_MINUTES = int(os.getenv('JWT_EXPIRE_MINUTES', '1440'))
_ALGORITHM = 'HS256'


def create_token(username: str, role: str, display_name: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=_EXPIRE_MINUTES)
    payload = {
        'sub': username,
        'role': role,
        'display_name': display_name,
        'exp': exp,
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _secret() -> str:
    s = _SECRET or os.getenv('JWT_SECRET', '')
    if not s:
        raise RuntimeError('JWT_SECRET no configurado en .env')
    return s
