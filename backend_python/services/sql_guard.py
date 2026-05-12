"""SQL guard para queries ad-hoc generadas por el LLM (modo router/sql_generation).

Capas de defensa:
1. Pre-checks string-level: longitud, caracteres prohibidos, comentarios, ; final.
2. sqlparse AST: un único statement, tipo SELECT.
3. Whitelist semántica: tabla permitida = ventasgeneral2, requiere WHERE
   FechaContable BETWEEN, prohíbe LIMIT/OFFSET del LLM (los inyecta el backend),
   prohíbe UNION/INTO OUTFILE/INFORMATION_SCHEMA/etc.

Uso típico:
    from services.sql_guard import validate_select_sql, apply_pagination, SqlGuardError

    try:
        clean = validate_select_sql(raw_sql_from_llm)
    except SqlGuardError as e:
        return {'error': f'SQL rechazado: {e}'}

    final_sql = apply_pagination(clean, pagina, por_pagina)
"""
from __future__ import annotations

import re

import sqlparse
from sqlparse.tokens import DDL, DML, Keyword

ALLOWED_TABLES = {'ventasgeneral2'}
MAX_SQL_LEN = 5000

# Tokens prohibidos (case-insensitive). Mezcla operaciones destructivas, accesos
# a metadatos, funciones de timing-based blind SQLi, salidas a archivo, etc.
_FORBIDDEN_KEYWORDS = (
    r'\bINSERT\b', r'\bUPDATE\b', r'\bDELETE\b', r'\bREPLACE\b',
    r'\bDROP\b', r'\bALTER\b', r'\bCREATE\b', r'\bTRUNCATE\b', r'\bRENAME\b',
    r'\bGRANT\b', r'\bREVOKE\b', r'\bEXEC(UTE)?\b', r'\bCALL\b',
    r'\bHANDLER\b', r'\bLOCK\b', r'\bUNLOCK\b',
    r'\bUSE\b', r'\bSHOW\b', r'\bDESCRIBE\b', r'\bDESC\s+TABLE\b',
    r'\bEXPLAIN\b', r'\bLOAD_FILE\b', r'\bINTO\s+OUTFILE\b', r'\bINTO\s+DUMPFILE\b',
    r'\bSLEEP\s*\(', r'\bBENCHMARK\s*\(', r'\bGET_LOCK\s*\(',
    r'\bUNION\b', r'\bINFORMATION_SCHEMA\b', r'\bMYSQL\.\b', r'\bPERFORMANCE_SCHEMA\b',
    r'\bSYS\.\b', r'\bSET\s+@', r'\bDECLARE\b',
)
_FORBIDDEN_RE = re.compile('|'.join(_FORBIDDEN_KEYWORDS), re.IGNORECASE)

# LIMIT/OFFSET del LLM: prohibidos porque los inyecta el backend con paginación.
_LIMIT_OFFSET_RE = re.compile(r'\b(LIMIT|OFFSET)\b', re.IGNORECASE)

# Comentarios SQL (cualquier estilo).
_COMMENT_RE = re.compile(r'(--|#|/\*|\*/)')


class SqlGuardError(ValueError):
    """SQL rechazado por el guard."""


def _strip(sql: str) -> str:
    return (sql or '').strip().rstrip(';').strip()


def _statement_type(stmt) -> str:
    """Devuelve el tipo del statement (SELECT, INSERT, etc.) o '' si no se detecta."""
    for tok in stmt.tokens:
        if tok.ttype in (DML, DDL, Keyword):
            return tok.normalized.upper()
    return ''


def _referenced_tables(sql_lower: str) -> set[str]:
    """Heurística simple: extrae nombres que siguen a FROM o JOIN."""
    found = set()
    for m in re.finditer(r'\b(?:from|join)\s+([a-zA-Z_][\w]*)', sql_lower):
        found.add(m.group(1))
    return found


def validate_select_sql(raw_sql: str) -> str:
    """Valida un SELECT generado por el LLM y devuelve el SQL normalizado (sin ; final).

    Lanza SqlGuardError si el SQL no pasa alguna de las capas de validación.
    """
    if not raw_sql or not isinstance(raw_sql, str):
        raise SqlGuardError('SQL vacío.')

    sql = _strip(raw_sql)
    if not sql:
        raise SqlGuardError('SQL vacío después de normalizar.')
    if len(sql) > MAX_SQL_LEN:
        raise SqlGuardError(f'SQL excede longitud máxima ({MAX_SQL_LEN} caracteres).')

    if _COMMENT_RE.search(sql):
        raise SqlGuardError('Comentarios SQL (--, #, /* */) no permitidos.')
    if ';' in sql:
        raise SqlGuardError('Solo se permite un único statement (sin ";" intermedios).')

    forbidden = _FORBIDDEN_RE.search(sql)
    if forbidden:
        raise SqlGuardError(f'Token prohibido en SQL: {forbidden.group(0)}')

    if _LIMIT_OFFSET_RE.search(sql):
        raise SqlGuardError(
            'LIMIT/OFFSET no permitidos: el backend los inyecta vía pagina/por_pagina.'
        )

    parsed = sqlparse.parse(sql)
    if len(parsed) != 1:
        raise SqlGuardError('Solo se permite un único statement.')
    stmt = parsed[0]
    stmt_type = _statement_type(stmt)
    if stmt_type != 'SELECT':
        raise SqlGuardError(f'Solo se permite SELECT (recibido: {stmt_type or "desconocido"}).')

    sql_lower = sql.lower()
    tables = _referenced_tables(sql_lower)
    if not tables:
        raise SqlGuardError('No se detectó una tabla referenciada (falta FROM).')
    extra = tables - ALLOWED_TABLES
    if extra:
        raise SqlGuardError(
            f'Tabla(s) no permitida(s): {sorted(extra)}. Permitidas: {sorted(ALLOWED_TABLES)}.'
        )

    if not re.search(r'\bfechacontable\b\s+between\b', sql_lower):
        raise SqlGuardError(
            'Falta filtro de fechas: las queries ad-hoc deben incluir '
            '"WHERE FechaContable BETWEEN \'YYYY-MM-DD\' AND \'YYYY-MM-DD\'".'
        )

    return sql


def apply_pagination(clean_sql: str, pagina: int, por_pagina: int) -> str:
    """Agrega LIMIT/OFFSET al SQL ya validado. NO valida — usar tras validate_select_sql."""
    pp = max(1, int(por_pagina))
    pg = max(1, int(pagina))
    offset = (pg - 1) * pp
    return f'{clean_sql} LIMIT {pp} OFFSET {offset}'


def build_count_sql(clean_sql: str) -> str:
    """Envuelve un SELECT validado en COUNT(*) para obtener total_filas."""
    return f'SELECT COUNT(*) AS total FROM ({clean_sql}) AS _adhoc_count_'
