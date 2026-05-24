"""Formatea trazas SQL del chat para pegarlas y ejecutarlas en un cliente MySQL."""
import re

_RESUMEN_PROV_PATTERN = re.compile(
    r"SELECT\s+COUNT\(\*\)\s+AS\s+filas.*?FROM\s+ventasgeneral2\s+WHERE\s+FechaContable\s+BETWEEN\s+'([^']+)'\s+AND\s+'([^']+)'"
    r"(?:\s+AND\s+Provincia\s+LIKE\s+'[^']+')?",
    re.I | re.DOTALL,
)


def _ensure_semicolon(sql: str) -> str:
    s = sql.strip()
    if s and not s.endswith(';'):
        return s + ';'
    return s


def _group_by_provincia_sql(d1: str, d2: str, extra_where: str = '') -> str:
    return (
        "SELECT COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') AS provincia,\n"
        "       COUNT(*) AS lineas,\n"
        "       COALESCE(SUM(Cantidad),0) AS suma_cantidad,\n"
        "       COALESCE(SUM(Peso),0) AS suma_peso,\n"
        "       COALESCE(SUM(Valor),0) AS suma_valor\n"
        f"FROM ventasgeneral2\n"
        f"WHERE FechaContable BETWEEN '{d1}' AND '{d2}'{extra_where}\n"
        "GROUP BY provincia\n"
        "ORDER BY suma_valor DESC"
    )


def _extract_extra_where_after_dates(trace: str, d1: str, d2: str) -> str:
    """Filtros compartidos (línea, zona, etc.) sin Provincia LIKE."""
    upper = trace.upper()
    anchor = f"FECHACONTABLE BETWEEN '{d1}' AND '{d2}'".upper()
    pos = upper.find(anchor)
    if pos < 0:
        return ''
    rest = trace[pos + len(anchor):]
    parts = []
    for chunk in re.split(r'\s+AND\s+', rest, flags=re.I):
        chunk = chunk.strip()
        if not chunk:
            continue
        if re.match(r'^Provincia\s+LIKE\s+', chunk, re.I):
            continue
        parts.append(chunk.rstrip(';'))
    if not parts:
        return ''
    return ' AND ' + ' AND '.join(parts)


def format_sql_traces_for_display(traces: list[str]) -> str:
    if not traces:
        return ''
    cleaned = [t.strip() for t in traces if isinstance(t, str) and t.strip()]
    if not cleaned:
        return ''
    if len(cleaned) == 1:
        return _ensure_semicolon(cleaned[0])

    if all(_RESUMEN_PROV_PATTERN.search(t) for t in cleaned):
        date_sets = set()
        for t in cleaned:
            m = _RESUMEN_PROV_PATTERN.search(t)
            if m:
                date_sets.add((m.group(1), m.group(2)))
        if len(date_sets) == 1:
            d1, d2 = next(iter(date_sets))
            extra = _extract_extra_where_after_dates(cleaned[0], d1, d2)
            return _ensure_semicolon(_group_by_provincia_sql(d1, d2, extra))

    unique = list(dict.fromkeys(cleaned))
    if len(unique) == 1:
        return _ensure_semicolon(unique[0])

    return ';\n\n'.join(_ensure_semicolon(t) for t in unique)
