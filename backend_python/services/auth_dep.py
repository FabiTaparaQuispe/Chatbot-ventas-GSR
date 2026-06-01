from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from services.jwt_auth import decode_token
from services.roles import normalize_user_role


def get_api_user(request: Request) -> dict[str, Any] | None:
    """Valida Bearer JWT o sesión web. Devuelve dict con sub/role/display_name o None."""
    auth = request.headers.get('Authorization', '')
    if auth.lower().startswith('bearer '):
        token = auth[7:].strip()
        payload = decode_token(token)
        if payload:
            return {
                'username': str(payload.get('sub') or ''),
                'role': normalize_user_role(str(payload.get('role') or 'lector')),
                'display_name': str(payload.get('display_name') or ''),
                'via': 'jwt',
            }
        return None

    if request.session.get('active'):
        return {
            'username': str(request.session.get('usuario') or ''),
            'role': normalize_user_role(str(request.session.get('role') or 'lector')),
            'display_name': str(request.session.get('display_name') or ''),
            'via': 'session',
        }

    return None


def require_api_user(request: Request) -> JSONResponse | None:
    """Retorna JSONResponse 401 si no hay usuario válido, None si está autenticado."""
    if get_api_user(request) is None:
        return JSONResponse(
            {'ok': False, 'error': 'No autenticado. Usa Bearer token o inicia sesión.'},
            status_code=401,
        )
    return None
