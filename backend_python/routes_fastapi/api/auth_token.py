import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from routes_fastapi.auth import _check_login_db
from services.jwt_auth import create_token, _EXPIRE_MINUTES

router = APIRouter()


class LoginRequest(BaseModel):
    usuario: str
    clave: str


@router.post('/api/auth/token')
async def get_token(body: LoginRequest):
    u = body.usuario.strip()
    if not u or not body.clave:
        return JSONResponse({'ok': False, 'error': 'usuario y clave requeridos'}, status_code=400)

    ok, role, display_name = await asyncio.to_thread(_check_login_db, u, body.clave)
    if not ok:
        return JSONResponse({'ok': False, 'error': 'Credenciales incorrectas'}, status_code=401)

    token = create_token(u, role, display_name)
    return {
        'ok': True,
        'access_token': token,
        'token_type': 'bearer',
        'expires_in': _EXPIRE_MINUTES * 60,
        'role': role,
        'display_name': display_name,
    }
