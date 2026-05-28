from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from services.db import get_connection

router = APIRouter()


def _require_login(request: Request):
    if not request.session.get('active'):
        return JSONResponse({'ok': False, 'error': 'No autenticado'}, status_code=401), None
    username = str(request.session.get('usuario') or '').strip()
    if not username:
        return JSONResponse({'ok': False, 'error': 'Sesión inválida'}, status_code=401), None
    return None, username


@router.get('/api/chat_threads')
@router.get('/api/chat_threads.php')
async def chat_threads_get(request: Request, thread: str = '', q: str = ''):
    err, username = _require_login(request)
    if err:
        return err
    conn = get_connection()
    return _get(conn, username, thread.strip(), q.strip())


@router.post('/api/chat_threads')
@router.post('/api/chat_threads.php')
async def chat_threads_post(request: Request):
    err, username = _require_login(request)
    if err:
        return err
    conn = get_connection()
    body = await request.json()
    return _post(conn, username, body)


@router.delete('/api/chat_threads')
@router.delete('/api/chat_threads.php')
async def chat_threads_delete(request: Request):
    err, username = _require_login(request)
    if err:
        return err
    conn = get_connection()
    body = await request.json()
    return _delete(conn, username, body)


def _get(conn, username, client_id, q):
    if client_id:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id, client_thread_id, title, created_at, updated_at '
                'FROM app_chat_threads WHERE username = %s AND client_thread_id = %s LIMIT 1',
                (username, client_id)
            )
            t = cur.fetchone()
        if not t:
            return {'ok': True, 'thread': None}
        with conn.cursor() as cur:
            cur.execute(
                'SELECT role, content, created_at FROM app_chat_messages WHERE thread_id = %s ORDER BY id ASC',
                (int(t['id']),)
            )
            msgs = [{'role': str(r['role'] or ''), 'content': str(r['content'] or ''), 'createdAt': str(r['created_at'] or '')}
                    for r in cur.fetchall()]
        return {'ok': True, 'thread': {
            'id': str(t['client_thread_id'] or ''), 'title': str(t['title'] or ''),
            'createdAt': str(t['created_at'] or ''), 'updatedAt': str(t['updated_at'] or ''),
            'messages': msgs,
        }}

    sql = ('SELECT t.client_thread_id, t.title, t.updated_at,'
           ' (SELECT COUNT(*) FROM app_chat_messages m WHERE m.thread_id = t.id) AS n'
           ' FROM app_chat_threads t WHERE t.username = %s')
    params = [username]
    if q:
        sql += (' AND (t.title LIKE %s OR EXISTS ('
                ' SELECT 1 FROM app_chat_messages m2 WHERE m2.thread_id = t.id AND m2.content LIKE %s))')
        params += [f'%{q}%', f'%{q}%']
    sql += ' ORDER BY t.updated_at DESC LIMIT 60'

    with conn.cursor() as cur:
        cur.execute(sql, params)
        threads = [{'id': str(r['client_thread_id'] or ''), 'title': str(r['title'] or ''),
                    'updatedAt': str(r['updated_at'] or ''), 'n': int(r['n'] or 0)}
                   for r in cur.fetchall()]
    return {'ok': True, 'threads': threads}


def _post(conn, username, body):
    client_id = str(body.get('id') or '').strip()
    title = str(body.get('title') or '').strip() or 'Nuevo chat'
    messages = body.get('messages') if isinstance(body.get('messages'), list) else []
    if not client_id:
        return JSONResponse({'ok': False, 'error': 'Falta id'}, status_code=400)
    if len(title) > 220:
        title = title[:220]

    conn.begin()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM app_chat_threads WHERE username = %s AND client_thread_id = %s LIMIT 1',
                        (username, client_id))
            row = cur.fetchone()
        if row:
            thread_id = int(row['id'])
            with conn.cursor() as cur:
                cur.execute('UPDATE app_chat_threads SET title = %s, updated_at = NOW() WHERE id = %s', (title, thread_id))
                cur.execute('DELETE FROM app_chat_messages WHERE thread_id = %s', (thread_id,))
        else:
            with conn.cursor() as cur:
                cur.execute('INSERT INTO app_chat_threads (username, client_thread_id, title) VALUES (%s, %s, %s)',
                            (username, client_id, title))
                thread_id = cur.lastrowid

        with conn.cursor() as cur:
            n = 0
            for m in messages:
                if not isinstance(m, dict):
                    continue
                role = str(m.get('role') or '')
                if role not in ('user', 'assistant'):
                    continue
                content = str(m.get('content') or '')
                if not content:
                    continue
                if len(content) > 524288:
                    content = content[:524288]
                cur.execute('INSERT INTO app_chat_messages (thread_id, role, content) VALUES (%s, %s, %s)',
                            (thread_id, role, content))
                n += 1
                if n >= 500:
                    break
        conn.commit()
        return {'ok': True}
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)


def _delete(conn, username, body):
    if bool(body.get('purge_all')):
        with conn.cursor() as cur:
            cur.execute('DELETE FROM app_chat_threads WHERE username = %s', (username,))
        return {'ok': True, 'purge_all': True}
    client_id = str(body.get('id') or '').strip()
    if not client_id:
        return JSONResponse({'ok': False, 'error': 'Falta id'}, status_code=400)
    with conn.cursor() as cur:
        cur.execute('DELETE FROM app_chat_threads WHERE username = %s AND client_thread_id = %s', (username, client_id))
    return {'ok': True}
