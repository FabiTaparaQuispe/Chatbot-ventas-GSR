"""Persistencia de propuestas de nuevas tools sugeridas por el router agent.

La tabla se crea on-demand (CREATE TABLE IF NOT EXISTS) en la primera llamada,
para no requerir migration runner. Una propuesta se identifica por `name`
(snake_case), de modo que múltiples ocurrencias del mismo patrón solo incrementan
`votes_count` en lugar de crear filas duplicadas.

Estados:
    pending     → recién propuesta, pendiente de revisión.
    approved    → aprobada por admin, lista para ser implementada.
    rejected    → rechazada.
    implemented → ya existe como tool real en `tools_definitions.py`.
"""
from __future__ import annotations

import json
from typing import Any

_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS tool_proposals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    parameters_json LONGTEXT NOT NULL,
    example_sql_logic LONGTEXT NULL,
    trigger_pattern VARCHAR(255) NULL,
    reason VARCHAR(255) NULL,
    source_user_msg TEXT NULL,
    status ENUM('pending','approved','rejected','implemented') NOT NULL DEFAULT 'pending',
    votes_count INT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_votes (votes_count DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def ensure_schema(conn) -> None:
    """Crea la tabla si no existe. Idempotente, llamar antes de cualquier operación."""
    with conn.cursor() as cur:
        cur.execute(_TABLE_DDL)


def record_proposal(conn, proposal: dict[str, Any], *,
                   reason: str | None = None,
                   source_user_msg: str | None = None) -> dict[str, Any]:
    """Inserta una propuesta nueva o incrementa `votes_count` si ya existe.

    Devuelve `{id, name, status, votes_count, created: bool}`.
    """
    ensure_schema(conn)

    name = str(proposal.get('name') or '').strip()
    if not name:
        raise ValueError('Propuesta sin name.')
    description = str(proposal.get('description') or '').strip()
    if not description:
        raise ValueError('Propuesta sin description.')
    params = proposal.get('parameters') or {}
    if not isinstance(params, dict):
        raise ValueError('Propuesta: parameters debe ser objeto.')

    params_json = json.dumps(params, ensure_ascii=False)
    example_sql = proposal.get('example_sql_logic')
    trigger = proposal.get('trigger_pattern')

    with conn.cursor() as cur:
        cur.execute('SELECT id, status, votes_count FROM tool_proposals WHERE name = %s', (name,))
        row = cur.fetchone()
        if row:
            cur.execute(
                'UPDATE tool_proposals SET votes_count = votes_count + 1,'
                ' description = %s, parameters_json = %s,'
                ' example_sql_logic = %s, trigger_pattern = %s,'
                ' reason = COALESCE(%s, reason),'
                ' source_user_msg = COALESCE(%s, source_user_msg)'
                ' WHERE id = %s',
                (description, params_json, example_sql, trigger,
                 reason, source_user_msg, row['id']),
            )
            return {
                'id': int(row['id']),
                'name': name,
                'status': row['status'],
                'votes_count': int(row['votes_count']) + 1,
                'created': False,
            }
        cur.execute(
            'INSERT INTO tool_proposals'
            ' (name, description, parameters_json, example_sql_logic, trigger_pattern,'
            '  reason, source_user_msg)'
            ' VALUES (%s, %s, %s, %s, %s, %s, %s)',
            (name, description, params_json, example_sql, trigger, reason, source_user_msg),
        )
        new_id = cur.lastrowid
        return {
            'id': int(new_id),
            'name': name,
            'status': 'pending',
            'votes_count': 1,
            'created': True,
        }


def list_proposals(conn, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Lista propuestas, opcionalmente filtradas por status."""
    ensure_schema(conn)
    limit = max(1, min(500, int(limit or 50)))
    sql = ('SELECT id, name, description, parameters_json, example_sql_logic,'
           ' trigger_pattern, reason, source_user_msg, status, votes_count,'
           ' created_at, updated_at'
           ' FROM tool_proposals')
    params: tuple = ()
    if status:
        sql += ' WHERE status = %s'
        params = (status,)
    sql += f' ORDER BY votes_count DESC, created_at DESC LIMIT {limit}'
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall() or []
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            params_obj = json.loads(r.get('parameters_json') or '{}')
        except (ValueError, TypeError):
            params_obj = {}
        out.append({
            'id': int(r['id']),
            'name': r['name'],
            'description': r['description'],
            'parameters': params_obj,
            'example_sql_logic': r.get('example_sql_logic'),
            'trigger_pattern': r.get('trigger_pattern'),
            'reason': r.get('reason'),
            'source_user_msg': r.get('source_user_msg'),
            'status': r['status'],
            'votes_count': int(r['votes_count'] or 0),
            'created_at': str(r['created_at']) if r.get('created_at') else None,
            'updated_at': str(r['updated_at']) if r.get('updated_at') else None,
        })
    return out


def set_proposal_status(conn, proposal_id: int, status: str) -> bool:
    """Actualiza el estado de una propuesta."""
    if status not in ('pending', 'approved', 'rejected', 'implemented'):
        raise ValueError(f'status inválido: {status}')
    ensure_schema(conn)
    with conn.cursor() as cur:
        cur.execute('UPDATE tool_proposals SET status = %s WHERE id = %s',
                    (status, int(proposal_id)))
        return cur.rowcount > 0
