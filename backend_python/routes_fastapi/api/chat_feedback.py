import asyncio
import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from services.db import get_connection
from routes_fastapi.pages import _require_login, _user_role, ROLES_HISTORIAL

router = APIRouter()
_log = logging.getLogger(__name__)


@router.get('/api/historial/conversacion')
async def historial_conversacion(request: Request, aid: str = ''):
    """Devuelve la conversación completa (pregunta + respuesta) por id del mensaje
    del asistente, sin importar de qué usuario sea. Para revisar/evaluar desde la
    página global 'Preguntas al chatbot'. Protegido por rol de historial."""
    if _require_login(request):
        return JSONResponse({'ok': False, 'error': 'No autenticado'}, status_code=401)
    if _user_role(request) not in ROLES_HISTORIAL:
        return JSONResponse({'ok': False, 'error': 'Sin permiso'}, status_code=403)
    try:
        aid_i = int(aid)
    except (TypeError, ValueError):
        return JSONResponse({'ok': False, 'error': 'aid inválido'}, status_code=400)

    def _fetch():
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                '''SELECT m.id, m.content, m.feedback, m.thread_id, m.created_at,
                          t.username, t.title
                   FROM app_chat_messages m
                   JOIN app_chat_threads t ON t.id = m.thread_id
                   WHERE m.id = %s AND m.role = 'assistant' LIMIT 1''',
                (aid_i,)
            )
            a = cur.fetchone()
            if not a:
                return None
            cur.execute(
                '''SELECT content FROM app_chat_messages
                   WHERE thread_id = %s AND role = 'user' AND id < %s
                   ORDER BY id DESC LIMIT 1''',
                (a['thread_id'], aid_i)
            )
            q = cur.fetchone()
        return a, q

    try:
        res = await asyncio.to_thread(_fetch)
    except Exception as e:
        _log.error('historial_conversacion error: %s', e)
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)
    if not res:
        return JSONResponse({'ok': False, 'error': 'No encontrado'}, status_code=404)
    a, q = res
    return {
        'ok': True,
        'aid': a['id'],
        'usuario': str(a['username'] or ''),
        'titulo': str(a['title'] or ''),
        'fecha': str(a['created_at'] or ''),
        'pregunta': str((q or {}).get('content') or ''),
        'respuesta': str(a['content'] or ''),
        'feedback': a['feedback'],
    }


def _save_feedback_db(message_id, value):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            'UPDATE app_chat_messages SET feedback = %s WHERE id = %s AND role = %s',
            (value if value != 0 else None, message_id, 'assistant')
        )
    conn.commit()


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
        await asyncio.to_thread(_save_feedback_db, message_id, value)
        return {'ok': True}
    except Exception as e:
        _log.error('feedback error: %s', e)
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)


def _last_msg_id_db(username, cid):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            '''SELECT m.id, m.feedback FROM app_chat_messages m
               JOIN app_chat_threads t ON t.id = m.thread_id
               WHERE t.username = %s AND t.client_thread_id = %s AND m.role = %s
               ORDER BY m.id DESC LIMIT 1''',
            (username, cid, 'assistant')
        )
        return cur.fetchone()


@router.get('/api/chat/last_msg_id')
async def last_msg_id(request: Request, cid: str = ''):
    if _require_login(request):
        return JSONResponse({'ok': False, 'error': 'No autenticado'}, status_code=401)
    username = str(request.session.get('usuario') or '')
    _log.info('[feedback] last_msg_id llamado | user=%s cid=%s', username, cid[:12] if cid else '')
    if not cid or not username:
        return JSONResponse({'ok': False, 'error': 'Parámetros inválidos'}, status_code=400)
    try:
        row = await asyncio.to_thread(_last_msg_id_db, username, cid)
        if not row:
            return {'ok': False, 'id': None}
        return {'ok': True, 'id': row['id'], 'feedback': row['feedback']}
    except Exception as e:
        _log.error('last_msg_id error: %s | tipo: %s', e, type(e).__name__, exc_info=True)
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)


def _feedback_stats_db():
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
        return cur.fetchone()


@router.get('/api/chat/feedback/stats')
async def feedback_stats(request: Request):
    if _require_login(request):
        return JSONResponse({'ok': False, 'error': 'No autenticado'}, status_code=401)
    role = _user_role(request)
    if role not in ('admin', 'administrador'):
        return JSONResponse({'ok': False, 'error': 'Sin permiso'}, status_code=403)
    try:
        row = await asyncio.to_thread(_feedback_stats_db)
        return {
            'ok': True,
            'total_respuestas': row['total'],
            'buenos': int(row['buenos'] or 0),
            'malos': int(row['malos'] or 0),
            'sin_voto': int(row['sin_voto'] or 0),
        }
    except Exception as e:
        _log.error('feedback stats error: %s', e)
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)
