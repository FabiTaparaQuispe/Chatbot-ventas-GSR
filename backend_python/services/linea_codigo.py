"""
Mapeo `LineaComercial` (texto) → `CodigoLineaComercial`.

Permite que el WHERE de los reportes use el código corto (varchar(12)) en lugar
de la columna varchar(105) envuelta en LOWER(TRIM(...)). Eso habilita el uso
del índice compuesto `idx_vg2_fcont_linea (FechaContable, CodigoLineaComercial)`
y reduce el `EXPLAIN type` de `ALL` (full scan) a `range` con
`Using where; Using index` (covering).

El catálogo de líneas comerciales es pequeño y muy estable (~14 valores), así
que cacheamos en memoria con TTL para evitar consultas repetidas.
"""
from __future__ import annotations

import time
import threading
from typing import Optional

_TTL_S = 600.0  # 10 minutos
_LOCK = threading.Lock()
_CACHE: dict[str, str] = {}  # clave normalizada -> CodigoLineaComercial
_LAST_REFRESH: float = 0.0


def _norm(s: str) -> str:
    return (s or '').strip().lower()


def _refresh_cache(conn) -> None:
    """Carga todo el catálogo (línea → código) de una sola vez."""
    global _LAST_REFRESH
    sql = (
        "SELECT DISTINCT CodigoLineaComercial AS cod, LineaComercial AS nom "
        "FROM ventasgeneral2 "
        "WHERE COALESCE(NULLIF(TRIM(LineaComercial),''),'') <> '' "
        "  AND COALESCE(NULLIF(TRIM(CodigoLineaComercial),''),'') <> ''"
    )
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall() or []
    nuevo: dict[str, str] = {}
    for r in rows:
        cod = str(r.get('cod') or '').strip()
        nom = str(r.get('nom') or '').strip()
        if cod and nom:
            nuevo[_norm(nom)] = cod
    with _LOCK:
        _CACHE.clear()
        _CACHE.update(nuevo)
        _LAST_REFRESH = time.time()


def resolver_codigo_linea(conn, linea_texto: str) -> Optional[str]:
    """
    Devuelve el CodigoLineaComercial para un texto de LineaComercial dado.
    Retorna None si no se encuentra coincidencia (el caller debe usar el WHERE
    de texto como fallback).
    """
    if not linea_texto:
        return None
    key = _norm(linea_texto)
    now = time.time()
    with _LOCK:
        cached = _CACHE.get(key)
        fresh = (now - _LAST_REFRESH) < _TTL_S
    if cached and fresh:
        return cached
    # Cache miss o caducada: refrescar y reintentar
    try:
        _refresh_cache(conn)
    except Exception:
        return None
    with _LOCK:
        return _CACHE.get(key)


def linea_where_fragment(
    conn,
    linea_texto: str,
    style: str = 'colon',
) -> tuple[str, dict]:
    """
    Devuelve un fragmento SQL para AND-encadenar al WHERE y los binds adecuados.

    Si el código de la línea se resuelve usa `CodigoLineaComercial = :cod_linea`
    (sargable, usa índice compuesto). Si no, cae al WHERE de texto.

    style:
      'colon'    → emite `:cod_linea` / `:linea`        (usado en reports_modules)
      'pyformat' → emite `%(cod_linea)s` / `%(linea)s`  (usado en tool_executor)
    """
    cod = resolver_codigo_linea(conn, linea_texto)
    if style == 'pyformat':
        if cod:
            return ' AND CodigoLineaComercial = %(cod_linea)s', {'cod_linea': cod}
        return (
            " AND LOWER(TRIM(LineaComercial)) = LOWER(TRIM(%(linea)s))",
            {'linea': linea_texto},
        )
    # colon (default)
    if cod:
        return ' AND CodigoLineaComercial = :cod_linea', {'cod_linea': cod}
    return (
        ' AND LOWER(TRIM(LineaComercial)) = LOWER(TRIM(:linea))',
        {'linea': linea_texto},
    )


def index_hint_ventasgeneral2(
    conn,
    linea_texto: str,
    tipo_fecha: str = 'contable',
) -> str:
    """
    Devuelve un sufijo `FORCE INDEX (...)` para la cláusula
    `FROM ventasgeneral2 ...` cuando aplique, y string vacío en caso contrario.

    Motivación: el optimizador de MySQL, al haber `GROUP BY Provincia`, prefiere
    `idx_vg2_provincia` y termina escaneando toda la tabla. Forzar
    `idx_vg2_fcont_linea` (que filtra primero por fecha + código de línea) baja
    el tiempo entre 2× y 8× en el rango típico de un mes.

    Se aplica solo si:
      - tipo_fecha = 'contable' (índice compuesto incluye FechaContable), y
      - el código de línea se resolvió (de lo contrario el optimizador no podría
        usar el segundo nivel del índice).
    """
    tf = (tipo_fecha or 'contable').strip().lower()
    if tf == 'proceso':
        return ' FORCE INDEX (idx_vg2_fproc)'
    if tf != 'contable':
        return ''
    cod = resolver_codigo_linea(conn, linea_texto)
    if cod:
        return ' FORCE INDEX (idx_vg2_fcont_linea)'
    return ''
