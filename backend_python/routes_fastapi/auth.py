import os

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from services.db import get_connection
from services.passwords import verify_password
from services.roles import normalize_user_role

router = APIRouter()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), '..', 'templates')
)

APP_NAME = 'Ventas · cia2026'
APP_COMPANY = 'GRANJA RINCONADA DEL SUR S.A.'


@router.get('/login', response_class=HTMLResponse)
@router.get('/login.php', response_class=HTMLResponse)
async def login_get(request: Request):
    if request.session.get('active'):
        return RedirectResponse('/', status_code=302)
    return templates.TemplateResponse('login.html', {
        'request': request,
        'error': '',
        'app_name': APP_NAME,
        'app_company': APP_COMPANY,
    })


@router.post('/login', response_class=HTMLResponse)
@router.post('/login.php', response_class=HTMLResponse)
async def login_post(
    request: Request,
    usuario: str = Form(default=''),
    clave: str = Form(default=''),
):
    if request.session.get('active'):
        return RedirectResponse('/', status_code=302)

    error = ''
    u = usuario.strip()
    if not u or not clave:
        error = 'Usuario y contraseña requeridos.'
    else:
        try:
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT password_hash, is_active, role, display_name '
                    'FROM app_users WHERE username = %s LIMIT 1',
                    (u,),
                )
                row = cur.fetchone()
            ok = False
            role = ''
            display_name = ''
            if row and int(row.get('is_active') or 0) == 1:
                h = str(row.get('password_hash') or '')
                if h and verify_password(clave, h):
                    ok = True
                    with conn.cursor() as cur:
                        cur.execute('UPDATE app_users SET last_login_at = NOW() WHERE username = %s', (u,))
                    role = normalize_user_role(str(row.get('role') or ''))
                    if not role:
                        role = 'lector'
                    display_name = str(row.get('display_name') or '').strip()
            if ok:
                request.session.clear()
                request.session['active'] = True
                request.session['usuario'] = u
                request.session['role'] = role
                request.session['display_name'] = display_name
                return RedirectResponse('/', status_code=302)
            error = 'Usuario o contraseña incorrectos.'
        except Exception as e:
            error = f'No se pudo validar el acceso. Detalle: {e}'

    return templates.TemplateResponse('login.html', {
        'request': request,
        'error': error,
        'app_name': APP_NAME,
        'app_company': APP_COMPANY,
    })


@router.get('/logout')
@router.get('/logout.php')
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse('/login', status_code=302)
