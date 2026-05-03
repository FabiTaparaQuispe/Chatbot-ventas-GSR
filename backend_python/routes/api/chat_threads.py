from flask import Blueprint, request, session, jsonify
from services.db import get_connection

bp = Blueprint('api_chat_threads', __name__)


def _require_login():
    if not session.get('active'):
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    username = str(session.get('usuario') or '').strip()
    if not username:
        return jsonify({'ok': False, 'error': 'Sesión inválida'}), 401
    return None, username


@bp.route('/api/chat_threads.php', methods=['GET', 'POST', 'DELETE'])
def chat_threads():
    err_resp = _require_login()
    if err_resp[0] is not None:
        return err_resp
    _, username = err_resp

    conn = get_connection()
    method = request.method

    if method == 'GET':
        return _get(conn, username)
    if method == 'POST':
        return _post(conn, username)
    if method == 'DELETE':
        return _delete(conn, username)

    return jsonify({'ok': False, 'error': 'Método no permitido'}), 405


def _get(conn, username):
    client_id = request.args.get('thread', '').strip()
    q = request.args.get('q', '').strip()

    if client_id:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id, client_thread_id, title, created_at, updated_at FROM app_chat_threads WHERE username = %s AND client_thread_id = %s LIMIT 1',
                (username, client_id)
            )
            t = cur.fetchone()
        if not t:
            return jsonify({'ok': True, 'thread': None})

        with conn.cursor() as cur:
            cur.execute(
                'SELECT role, content, created_at FROM app_chat_messages WHERE thread_id = %s ORDER BY id ASC',
                (int(t['id']),)
            )
            msgs = [{'role': str(r['role'] or ''), 'content': str(r['content'] or ''), 'createdAt': str(r['created_at'] or '')}
                    for r in cur.fetchall()]

        return jsonify({'ok': True, 'thread': {
            'id': str(t['client_thread_id'] or ''),
            'title': str(t['title'] or ''),
            'createdAt': str(t['created_at'] or ''),
            'updatedAt': str(t['updated_at'] or ''),
            'messages': msgs,
        }})

    sql = ('SELECT t.client_thread_id, t.title, t.updated_at,'
           ' (SELECT COUNT(*) FROM app_chat_messages m WHERE m.thread_id = t.id) AS n'
           ' FROM app_chat_threads t WHERE t.username = %s')
    params = [username]
    if q:
        sql += (' AND (t.title LIKE %s OR EXISTS ('
                ' SELECT 1 FROM app_chat_messages m2 WHERE m2.thread_id = t.id AND m2.content LIKE %s'
                '))')
        params += [f'%{q}%', f'%{q}%']
    sql += ' ORDER BY t.updated_at DESC LIMIT 60'

    with conn.cursor() as cur:
        cur.execute(sql, params)
        threads = [{'id': str(r['client_thread_id'] or ''), 'title': str(r['title'] or ''),
                    'updatedAt': str(r['updated_at'] or ''), 'n': int(r['n'] or 0)}
                   for r in cur.fetchall()]

    return jsonify({'ok': True, 'threads': threads})


def _post(conn, username):
    body = request.get_json(silent=True) or {}
    client_id = str(body.get('id') or '').strip()
    title = str(body.get('title') or '').strip() or 'Nuevo chat'
    messages = body.get('messages') if isinstance(body.get('messages'), list) else []

    if not client_id:
        return jsonify({'ok': False, 'error': 'Falta id'}), 400
    if len(title) > 220:
        title = title[:220]

    conn.begin()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id FROM app_chat_threads WHERE username = %s AND client_thread_id = %s LIMIT 1',
                (username, client_id)
            )
            row = cur.fetchone()

        if row:
            thread_id = int(row['id'])
            with conn.cursor() as cur:
                cur.execute('UPDATE app_chat_threads SET title = %s, updated_at = NOW() WHERE id = %s', (title, thread_id))
                cur.execute('DELETE FROM app_chat_messages WHERE thread_id = %s', (thread_id,))
        else:
            with conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO app_chat_threads (username, client_thread_id, title) VALUES (%s, %s, %s)',
                    (username, client_id, title)
                )
                thread_id = cur.lastrowid

        n = 0
        with conn.cursor() as cur:
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
                cur.execute(
                    'INSERT INTO app_chat_messages (thread_id, role, content) VALUES (%s, %s, %s)',
                    (thread_id, role, content)
                )
                n += 1
                if n >= 500:
                    break

        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500


def _delete(conn, username):
    body = request.get_json(silent=True) or {}
    purge_all = bool(body.get('purge_all'))

    if purge_all:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM app_chat_threads WHERE username = %s', (username,))
        return jsonify({'ok': True, 'purge_all': True})

    client_id = str(body.get('id') or '').strip()
    if not client_id:
        return jsonify({'ok': False, 'error': 'Falta id'}), 400

    with conn.cursor() as cur:
        cur.execute('DELETE FROM app_chat_threads WHERE username = %s AND client_thread_id = %s', (username, client_id))
    return jsonify({'ok': True})
