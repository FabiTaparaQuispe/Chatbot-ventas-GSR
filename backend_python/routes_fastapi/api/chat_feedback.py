import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from services.db import get_connection
from routes_fastapi.pages import _require_login, _user_role

router = APIRouter()
_log = logging.getLogger(__name__)


@router.post('/api/chat/feedback')
async def save_feedback(request: Request):
    if _require_login(request):
        return JSONResponse({'ok': False, 'error': 'No autenticado'}, status_code=401)
    data = await request.json()
    message_id = data.get('message_id')
    value = data.get('value')
    if not message_id or value not in (1, -1, 0):
        return JSONResponse({'ok': False, 'error': 'Parámetros inválidos'}, status_code=400)
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                'UPDATE app_chat_messages SET feedback = %s WHERE id = %s AND role = %s',
                (value if value != 0 else None, message_id, 'assistant')
            )
        conn.commit()
        return {'ok': True}
    except Exception as e:
        _log.error('feedback error: %s', e)
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)


@router.get('/api/chat/last_msg_id')
async def last_msg_id(request: Request, cid: str = ''):
    if _require_login(request):
        return JSONResponse({'ok': False, 'error': 'No autenticado'}, status_code=401)
    username = str(request.session.get('usuario') or '')
    if not cid or not username:
        return JSONResponse({'ok': False, 'error': 'Parámetros inválidos'}, status_code=400)
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                '''SELECT m.id, m.feedback FROM app_chat_messages m
                   JOIN app_chat_threads t ON t.id = m.thread_id
                   WHERE t.username = %s AND t.client_thread_id = %s AND m.role = %s
                   ORDER BY m.id DESC LIMIT 1''',
                (username, cid, 'assistant')
            )
            row = cur.fetchone()
        if not row:
            return {'ok': False, 'id': None}
        return {'ok': True, 'id': row[0], 'feedback': row[1]}
    except Exception as e:
        _log.error('last_msg_id error: %s', e)
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)


@router.get('/api/chat/feedback/stats')
async def feedback_stats(request: Request):
    if _require_login(request):
        return JSONResponse({'ok': False, 'error': 'No autenticado'}, status_code=401)
    role = _user_role(request)
    if role not in ('admin', 'administrador'):
        return JSONResponse({'ok': False, 'error': 'Sin permiso'}, status_code=403)
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                '''SELECT
                     COUNT(*) AS total,
                     SUM(feedback = 1) AS buenos,
                     SUM(feedback = -1) AS malos,
                     SUM(feedback IS NULL) AS sin_voto
                   FROM app_chat_messages WHERE role = %s''',
                ('assistant',)
            )
            row = cur.fetchone()
        return {
            'ok': True,
            'total_respuestas': row[0],
            'buenos': int(row[1] or 0),
            'malos': int(row[2] or 0),
            'sin_voto': int(row[3] or 0),
        }
    except Exception as e:
        _log.error('feedback stats error: %s', e)
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)
