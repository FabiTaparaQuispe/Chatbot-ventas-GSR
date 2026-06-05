from __future__ import annotations

import asyncio
import secrets
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from services.admin_actions import (
    process_gestion_post,
    process_gestion_self_post,
    process_usuarios_post,
)
from services.passwords import hash_password
from services.db import get_connection
from services.historial_data import (
    build_stats,
    clasificar_pregunta,
    estado_respuesta,
    fetch_efectividad_stats,
    fetch_efectividad_por_mes,
    fetch_historial_anios,
    fetch_historial_rows,
    fetch_historial_usernames,
    historial_preview,
    is_historial_filter_validation_error,
)
from services.roles import normalize_user_role
from services.urlmap import API_CHAT, chat_assistant_config_dict
from routes_fastapi.templates import templates

router = APIRouter()

APP_NAME = 'Ventas · cia2026'
APP_COMPANY = 'GRANJA RINCONADA DEL SUR S.A.'

ROLES_HOME_VENTAS = {'admin', 'gerencia', 'administrador', 'estrategico', 'tactico', 'operativo', 'analista'}
ROLES_VENTAS_GENERAL = ROLES_HOME_VENTAS | {'lector'}
ROLES_HISTORIAL = {'admin', 'estrategico', 'administrador'}
ROLES_GESTION_USUARIOS = {'admin', 'administrador'}


def _require_login(request: Request) -> RedirectResponse | None:
    if not request.session.get('active'):
        return RedirectResponse('/login', status_code=302)
    return None


def _user_role(request: Request) -> str:
    return str(request.session.get('role') or 'lector').lower().strip()


def _ensure_csrf(request: Request) -> str:
    tok = secrets.token_urlsafe(24)
    request.session['csrf_token'] = tok
    return tok


def _pop_flash(request: Request) -> tuple[str, str]:
    ok = str(request.session.pop('flash_ok', '') or '')
    err = str(request.session.pop('flash_err', '') or '')
    return ok, err


@router.get('/', response_class=HTMLResponse)
@router.get('/index.php', response_class=HTMLResponse)
async def index_get(request: Request, page: str = ''):
    redirect = _require_login(request)
    if redirect:
        return redirect
    return await _render_index(request, page)


@router.post('/', response_class=HTMLResponse)
@router.post('/index.php', response_class=HTMLResponse)
async def index_post(request: Request, page: str = ''):
    redirect = _require_login(request)
    if redirect:
        return redirect

    role = _user_role(request)
    form = dict(await request.form())
    flash: dict[str, str] = {}

    if page == 'usuarios' and role == 'admin':
        process_usuarios_post(request.session, form, flash)
    elif page == 'gestion_usuarios':
        usuario = str(request.session.get('usuario') or '')
        if role in ROLES_GESTION_USUARIOS:
            process_gestion_post(request.session, form, usuario, flash)
        else:
            process_gestion_self_post(request.session, form, usuario, flash)
    else:
        flash['err'] = 'POST no permitido en esta página.'

    if flash.get('ok'):
        request.session['flash_ok'] = flash['ok']
    if flash.get('err'):
        request.session['flash_err'] = flash['err']

    redirect_page = page or 'ventas'
    return RedirectResponse(f'/?page={redirect_page}', status_code=302)


async def _render_index(request: Request, page: str) -> HTMLResponse:
    role = _user_role(request)

    if not page:
        page = 'ventas' if role in ROLES_HOME_VENTAS else 'chatbot'
    if page == 'graficos':
        return RedirectResponse('/?page=chatbot', status_code=302)

    allowed = {'ventas', 'ventasgeneral2', 'chatbot', 'historial_preguntas', 'usuarios', 'gestion_usuarios'}
    if page not in allowed:
        page = 'ventas'
    if page == 'usuarios' and role != 'admin':
        return RedirectResponse('/', status_code=302)
    if page == 'historial_preguntas' and role not in ROLES_HISTORIAL:
        return RedirectResponse('/', status_code=302)
    if page in ('ventas', 'ventasgeneral2') and role not in ROLES_VENTAS_GENERAL:
        return RedirectResponse('/?page=chatbot', status_code=302)

    page_titles = {
        'chatbot': 'Chatbot',
        'historial_preguntas': 'Preguntas al chatbot',
        'usuarios': 'Usuarios',
        'gestion_usuarios': 'Administración de usuario',
        'ventasgeneral2': 'Ventas general 2',
    }

    usuario = str(request.session.get('usuario') or '')
    nom_corto = ''
    if usuario:
        part = usuario.split('@')[0].replace('.', ' ').replace('_', ' ').replace('-', ' ').strip()
        if part:
            nom_corto = ', ' + part.capitalize()

    flash_ok, flash_err = _pop_flash(request)
    csrf_token = _ensure_csrf(request)

    ctx: dict[str, Any] = {
        'page': page,
        'page_title': page_titles.get(page, 'Ventas general'),
        'app_name': APP_NAME,
        'app_company': APP_COMPANY,
        'load_ventas_assets': page in ('ventas', 'ventasgeneral2'),
        'load_listado_skin': page in ('usuarios', 'gestion_usuarios'),
        'skip_floating_chat': page == 'chatbot',
        'body_class': ('app-page-chatbot' if page == 'chatbot'
                       else ('app-page-historial-chat' if page == 'historial_preguntas' else '')),
        'role': role,
        'usuario': usuario,
        'display_name': request.session.get('display_name', ''),
        'nom_corto': nom_corto,
        'ventas_public_base': '/',
        'ventas_modules_web_base': '/modules/',
        'ventas_chat_api_url': API_CHAT.lstrip('/'),
        'ventas_chat_user_key': usuario or 'anon',
        'roles_ventas_general': ROLES_VENTAS_GENERAL,
        'roles_home_ventas': ROLES_HOME_VENTAS,
        'flash_ok': flash_ok,
        'flash_err': flash_err,
        'csrf_token': csrf_token,
        'chat_assistant_config': chat_assistant_config_dict(usuario or 'anon', role or ''),
    }

    if page == 'historial_preguntas':
        import datetime as _dt
        f_desde = request.query_params.get('fecha_desde', '').strip()
        f_hasta = request.query_params.get('fecha_hasta', '').strip()
        f_user = request.query_params.get('usuario', '').strip()
        f_feedback = request.query_params.get('feedback', '').strip().lower()
        if f_feedback not in ('buenos', 'malos', 'sin_voto', 'fallos'):
            f_feedback = ''
        # Filtro por año — por defecto el año actual. 'todos' = sin filtro de año.
        f_anio = request.query_params.get('anio', '').strip()
        if not f_anio:
            f_anio = str(_dt.date.today().year)
        # Rango efectivo: las fechas explícitas mandan; si no, el año seleccionado.
        if f_desde or f_hasta:
            ef_desde, ef_hasta = f_desde or None, f_hasta or None
        elif f_anio != 'todos':
            ef_desde, ef_hasta = f'{f_anio}-01-01', f'{f_anio}-12-31'
        else:
            ef_desde, ef_hasta = None, None
        filtros_activos = bool(f_desde or f_hasta or f_user or f_feedback or f_anio != 'todos')

        def _fetch_historial():
            conn = get_connection()
            usernames, _ = fetch_historial_usernames(conn)
            anios = fetch_historial_anios(conn)
            rows, db_err = fetch_historial_rows(conn, fecha_desde=ef_desde,
                                                fecha_hasta=ef_hasta, username=f_user or None,
                                                feedback=f_feedback or None)
            return usernames, anios, rows, db_err

        usernames, historial_anios, rows, db_err = await asyncio.to_thread(_fetch_historial)
        # asegurar que el año actual esté disponible para seleccionar
        _ya = str(_dt.date.today().year)
        if _ya not in historial_anios:
            historial_anios = [_ya] + historial_anios
        historial_filter_msg = ''
        if db_err and is_historial_filter_validation_error(db_err):
            historial_filter_msg = db_err
            db_err = ''
        stats = build_stats(rows) if rows and not db_err else {}
        top_categoria = (next((k for k, v in sorted(stats.items(), key=lambda x: -x[1]) if v > 0), '—') if stats else '—')

        def _fetch_ef():
            conn = get_connection()
            return (
                fetch_efectividad_stats(conn, fecha_desde=ef_desde, fecha_hasta=ef_hasta),
                fetch_efectividad_por_mes(conn, fecha_desde=ef_desde, fecha_hasta=ef_hasta),
            )

        ef, ef_por_mes = await asyncio.to_thread(_fetch_ef)

        ctx.update({
            'historial_rows': rows, 'db_error': db_err, 'stats': stats,
            'fb_buenos': ef['buenos'], 'fb_malos': ef['malos'], 'fb_sin_voto': ef['sin_voto'],
            'ef_total': ef['total'], 'ef_fallos': ef['fallos'], 'ef_fallo_auto': ef['fallo_auto'],
            'ef_aciertos': ef['aciertos'], 'ef_efectividad': ef['efectividad'],
            'ef_indice_exito': ef['indice_exito'], 'ef_respondidas': ef['respondidas'],
            'ef_por_mes': ef_por_mes,
            'total_preguntas': len(rows),
            'total_usuarios': len({str(r.get('usuario') or '') for r in rows if str(r.get('usuario') or '')}),
            'top_categoria': top_categoria,
            'colores': {'Ventas / resumen': '#2563eb', 'Clientes': '#7c3aed', 'Productos': '#059669',
                        'Por zona': '#d97706', 'Notas de crédito': '#dc2626', 'Comparativos': '#0891b2',
                        'Proyecciones': '#9333ea', 'Otras': '#6b7280'},
            'clasificar': clasificar_pregunta, 'preview': historial_preview,
            'estado_respuesta': estado_respuesta,
            'historial_usernames': usernames, 'filtro_fecha_desde': f_desde,
            'filtro_fecha_hasta': f_hasta, 'filtro_usuario': f_user,
            'filtro_feedback': f_feedback,
            'filtro_anio': f_anio, 'historial_anios': historial_anios,
            'filtros_activos': filtros_activos, 'historial_filter_msg': historial_filter_msg,
        })
    elif page == 'usuarios':
        def _fetch_users():
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute('SELECT id, username, display_name, role, is_active, last_login_at, created_at '
                            'FROM app_users ORDER BY created_at DESC, id DESC')
                return [dict(u) for u in (cur.fetchall() or [])]

        ctx['users'] = await asyncio.to_thread(_fetch_users)
        ctx['roles_disponibles'] = {'admin': 'Admin', 'gerencia': 'Gerencia', 'estrategico': 'Estratégico',
                                    'tactico': 'Táctico', 'analista': 'Analista', 'lector': 'Lector'}
        ctx['normalize_user_role'] = normalize_user_role
    elif page == 'gestion_usuarios':
        gestion_es_admin = role in ROLES_GESTION_USUARIOS

        def _fetch_gestion_users():
            conn = get_connection()
            with conn.cursor() as cur:
                if gestion_es_admin:
                    cur.execute("SELECT id, username, display_name, role, is_active, last_login_at, created_at "
                                "FROM app_users WHERE role IN ('administrador','estrategico','tactico','operativo') "
                                "ORDER BY created_at DESC, id DESC")
                else:
                    cur.execute('SELECT id, username, display_name, role, is_active, last_login_at, created_at '
                                'FROM app_users WHERE username = %s', (usuario,))
                return [dict(u) for u in (cur.fetchall() or [])]

        ctx['users'] = await asyncio.to_thread(_fetch_gestion_users)
        ctx['gestion_es_admin'] = gestion_es_admin
        if gestion_es_admin:
            ctx['roles_crear'] = {'estrategico': 'Estratégico', 'tactico': 'Táctico', 'operativo': 'Operativo'}
            ctx['roles_gestion'] = {'administrador': 'Administrador', 'estrategico': 'Estratégico',
                                    'tactico': 'Táctico', 'operativo': 'Operativo'}
        ctx['normalize_user_role'] = normalize_user_role

    return templates.TemplateResponse(request, f'pages/{page}.html', ctx)


@router.post('/api/change_password')
async def change_password(request: Request):
    if not request.session.get('active'):
        return JSONResponse({'ok': False, 'error': 'Sesión inválida.'}, status_code=401)
    data = await request.json()
    csrf = str(data.get('csrf_token') or '')
    if not csrf or csrf != request.session.get('csrf_token'):
        return JSONResponse({'ok': False, 'error': 'Solicitud inválida (CSRF).'}, status_code=403)
    new_pw = str(data.get('new_password') or '').strip()
    if len(new_pw) < 6:
        return JSONResponse({'ok': False, 'error': 'La contraseña debe tener al menos 6 caracteres.'}, status_code=400)
    username = str(request.session.get('usuario') or '')
    if not username:
        return JSONResponse({'ok': False, 'error': 'Sesión inválida.'}, status_code=401)
    def _update_pw():
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute('UPDATE app_users SET password_hash = %s WHERE username = %s',
                        (hash_password(new_pw), username))
        conn.commit()

    try:
        await asyncio.to_thread(_update_pw)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)
    return JSONResponse({'ok': True})
