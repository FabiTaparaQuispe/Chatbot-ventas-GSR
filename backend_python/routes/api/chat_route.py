"""Endpoint /api/chat/route: enrutamiento explícito basado en router_agent.

A diferencia de /api/chat (function-calling tradicional), este endpoint pide al
LLM una decisión estructurada en JSON, valida la decisión y ejecuta:

- tool_call          → ToolExecutor.execute(name, args)
- sql_generation     → sql_guard.validate_select_sql → COUNT(*) + paged SELECT
- ask_user           → devuelve reason y reply
- propose_new_tool   → persiste en tabla tool_proposals

Endpoints admin asociados:
- GET  /api/admin/tool_proposals
- POST /api/admin/tool_proposals/<id>/status  body: {"status": "approved|..."}
"""
from __future__ import annotations

import json
import re
from functools import wraps

from flask import Blueprint, jsonify, request, session

from services.db import get_connection
from services.router_agent import route_user_query, RouterError
from services.sql_guard import (
    SqlGuardError,
    apply_pagination,
    build_count_sql,
    validate_select_sql,
)
from services.tool_executor import (
    ToolExecutor,
    _count_query,
    _pagination_meta,
    _parse_pagina,
    _parse_por_pagina,
)
from services.tool_proposals import list_proposals, record_proposal, set_proposal_status

bp = Blueprint('api_chat_route', __name__)

ADMIN_ROLES = frozenset({'admin', 'administrador'})


def require_admin(fn):
    """Decorator: sesión activa + role admin/administrador, o 401/403 JSON."""
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get('active'):
            return jsonify({'ok': False, 'error': 'No autenticado'}), 401
        role = str(session.get('role') or '').lower().strip()
        if role not in ADMIN_ROLES:
            return jsonify({'ok': False, 'error': 'Permiso insuficiente'}), 403
        return fn(*args, **kwargs)
    return wrapped


def require_login_api(fn):
    """Decorator: sesión activa o 401 JSON (no redirige como require_login pages)."""
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get('active'):
            return jsonify({'ok': False, 'error': 'No autenticado'}), 401
        return fn(*args, **kwargs)
    return wrapped


def _sanitize_messages(messages_in: list) -> list[dict[str, str]]:
    """Filtra y recorta mensajes de entrada (user/assistant) — mismo criterio que /api/chat."""
    sanitized: list[dict[str, str]] = []
    for m in messages_in or []:
        if not isinstance(m, dict):
            continue
        role = m.get('role', '')
        if role not in ('user', 'assistant'):
            continue
        content = m.get('content', '')
        if not isinstance(content, str) or not content:
            continue
        if len(content) > 4000:
            content = content[:4000]
        sanitized.append({'role': role, 'content': content})
    if len(sanitized) > 6:
        sanitized = sanitized[-6:]
    return sanitized


def _handle_tool_call(executor: ToolExecutor, payload: dict) -> dict:
    name = payload.get('tool_name')
    args = payload.get('tool_args') or {}
    json_result = executor.execute(name, args)
    try:
        result = json.loads(json_result)
    except (ValueError, TypeError):
        result = {'raw': json_result}
    return {'tool_name': name, 'tool_args': args, 'result': result}


def _handle_sql_generation(conn, payload: dict) -> dict:
    raw_sql = str(payload.get('sql') or '')
    clean = validate_select_sql(raw_sql)
    pagina = _parse_pagina(payload)
    por_pagina = _parse_por_pagina(payload)

    count_sql = build_count_sql(clean)
    total_rows = _count_query(conn, count_sql, ())

    paged_sql = apply_pagination(clean, pagina, por_pagina)
    with conn.cursor() as cur:
        cur.execute(paged_sql)
        rows = cur.fetchall() or []

    return {
        'sql_validado': clean,
        'sql_ejecutado': paged_sql,
        'filas': [dict(r) for r in rows],
        'paginacion': _pagination_meta(total_rows, pagina, por_pagina),
    }


def _handle_propose(conn, proposal: dict, reason: str, user_msg: str) -> dict:
    rec = record_proposal(conn, proposal, reason=reason, source_user_msg=user_msg)
    if rec['created']:
        reply = (f'Registré tu pregunta como una propuesta de nueva herramienta '
                 f'("{rec["name"]}"). Un administrador la revisará.')
    else:
        reply = (f'Tu pregunta coincide con una propuesta existente ("{rec["name"]}") '
                 f'que ya tiene {rec["votes_count"]} votos. Estado actual: {rec["status"]}.')
    return {
        'proposal_id': rec['id'],
        'proposal_name': rec['name'],
        'votes_count': rec['votes_count'],
        'status': rec['status'],
        'created': rec['created'],
        'reply': reply,
    }


@bp.route('/api/chat/route', methods=['POST'])
@require_login_api
def chat_route():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'ok': False, 'error': 'JSON inválido'}), 400

    messages_in = data.get('messages')
    if not isinstance(messages_in, list):
        return jsonify({'ok': False, 'error': 'Falta messages (array)'}), 400

    user_context = ''
    if isinstance(data.get('user_context'), str):
        user_context = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', data['user_context'])[:800]

    sanitized = _sanitize_messages(messages_in)
    if not sanitized:
        return jsonify({'ok': False, 'error': 'No hay mensajes válidos'}), 400

    user_msg = next((m['content'] for m in reversed(sanitized) if m['role'] == 'user'), '')
    if not user_msg.strip():
        return jsonify({'ok': False, 'error': 'Falta mensaje del usuario'}), 400
    history = [m for m in sanitized if m['content'] != user_msg]

    try:
        decision = route_user_query(user_msg, history)
    except RouterError as e:
        return jsonify({'ok': False, 'error': f'Router falló: {e}'}), 502
    except RuntimeError as e:
        return jsonify({'ok': False, 'error': str(e)}), 503

    route = decision['route']
    reason = decision.get('reason', '')

    decision_echo: dict = {'route': route, 'reason': reason}
    if route == 'tool_call' and isinstance(decision.get('payload'), dict):
        decision_echo['tool_name'] = decision['payload'].get('tool_name')
        decision_echo['tool_args'] = decision['payload'].get('tool_args')
    elif route == 'sql_generation' and isinstance(decision.get('payload'), dict):
        decision_echo['sql_propuesto'] = decision['payload'].get('sql')
    elif route == 'propose_new_tool':
        decision_echo['new_tool_proposal'] = decision.get('new_tool_proposal')

    try:
        conn = get_connection()
        if route == 'tool_call':
            data_out = _handle_tool_call(ToolExecutor(conn), decision['payload'])
        elif route == 'sql_generation':
            data_out = _handle_sql_generation(conn, decision['payload'])
        elif route == 'ask_user':
            data_out = {'reply': reason}
        elif route == 'propose_new_tool':
            data_out = _handle_propose(conn, decision['new_tool_proposal'], reason, user_msg)
        else:
            return jsonify({'ok': False, **decision_echo,
                            'error': f'route desconocida: {route}'}), 500
    except SqlGuardError as e:
        return jsonify({'ok': False, **decision_echo,
                        'error': f'SQL rechazado: {e}'}), 422
    except ValueError as e:
        return jsonify({'ok': False, **decision_echo, 'error': str(e)}), 422
    except Exception as e:  # noqa: BLE001
        return jsonify({'ok': False, **decision_echo, 'error': str(e)}), 500

    return jsonify({
        'ok': True,
        **decision_echo,
        **data_out,
        'user_context': user_context or None,
    })


@bp.route('/api/admin/tool_proposals', methods=['GET'])
@require_admin
def admin_list_proposals():
    status = request.args.get('status')
    limit = request.args.get('limit', 50, type=int)
    try:
        conn = get_connection()
        items = list_proposals(conn, status=status, limit=limit)
    except Exception as e:  # noqa: BLE001
        return jsonify({'ok': False, 'error': str(e)}), 500
    return jsonify({'ok': True, 'items': items, 'count': len(items)})


@bp.route('/api/admin/tool_proposals/<int:proposal_id>/status', methods=['POST'])
@require_admin
def admin_set_status(proposal_id: int):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'ok': False, 'error': 'JSON inválido'}), 400
    status = str(data.get('status') or '').strip()
    try:
        conn = get_connection()
        ok = set_proposal_status(conn, proposal_id, status)
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 422
    except Exception as e:  # noqa: BLE001
        return jsonify({'ok': False, 'error': str(e)}), 500
    if not ok:
        return jsonify({'ok': False, 'error': 'Propuesta no encontrada'}), 404
    return jsonify({'ok': True, 'id': proposal_id, 'status': status})
