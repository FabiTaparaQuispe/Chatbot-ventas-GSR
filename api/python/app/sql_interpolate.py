from __future__ import annotations

from typing import Any


def sql_literal_escape(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def interpolate_sql(sql: str, params: dict[str | int, Any]) -> str:
    """Sustituye placeholders :name en SQL por literales (solo depuración / enlaces)."""
    if not params:
        return sql
    keys = sorted(params.keys(), key=lambda k: len(str(k)), reverse=True)
    out = sql
    for k in keys:
        ph = k if isinstance(k, str) and k.startswith(":") else f":{k}"
        v = params[k]
        if v is None:
            lit = "NULL"
        elif isinstance(v, bool):
            lit = "1" if v else "0"
        elif isinstance(v, (int, float)):
            lit = str(v)
        else:
            lit = sql_literal_escape(str(v))
        out = out.replace(ph, lit)
    return out
