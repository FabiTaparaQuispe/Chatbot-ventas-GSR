from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import get_engine

router = APIRouter(prefix="/api", tags=["stats"])


def _parse_ymd(s: str) -> str | None:
    s = s.strip()
    try:
        d = datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None
    if d.strftime("%Y-%m-%d") != s:
        return None
    return s


def _assert_range(d1: str, d2: str) -> None:
    if d1 > d2:
        raise ValueError("desde > hasta")
    a = datetime.strptime(d1, "%Y-%m-%d")
    b = datetime.strptime(d2, "%Y-%m-%d")
    if (b - a).days > 366:
        raise ValueError("Rango máximo 366 días")


@router.get("/stats.php")
def stats_api(
    type: str = Query("", alias="type"),
    desde: str = Query(""),
    hasta: str = Query(""),
    limit: int = Query(12),
    campo: str = Query("tfecfac"),
) -> Any:
    try:
        d1 = _parse_ymd(desde)
        d2 = _parse_ymd(hasta)
        if d1 is None or d2 is None:
            raise ValueError("Parámetros desde y hasta requeridos (YYYY-MM-DD)")
        _assert_range(d1, d2)
        engine = get_engine()
        with engine.connect() as conn:
            if type == "vg_daily":
                st = conn.execute(
                    text(
                        "SELECT FechaContable AS dia, COUNT(*) AS filas, COALESCE(SUM(Valor),0) AS suma_valor "
                        "FROM ventasgeneral2 WHERE FechaContable BETWEEN :a AND :b "
                        "GROUP BY FechaContable ORDER BY FechaContable"
                    ),
                    {"a": d1, "b": d2},
                )
                series = [dict(r._mapping) for r in st]
                return {"ok": True, "series": series}
            if type == "vg_zonas":
                lim = max(1, min(25, int(limit)))
                st = conn.execute(
                    text(
                        f"SELECT COALESCE(NULLIF(TRIM(ZonaComercial),''),'(sin zona)') AS zona, "
                        f"COUNT(*) AS filas, COALESCE(SUM(Valor),0) AS suma_valor "
                        f"FROM ventasgeneral2 WHERE FechaContable BETWEEN :a AND :b "
                        f"GROUP BY COALESCE(NULLIF(TRIM(ZonaComercial),''),'(sin zona)') "
                        f"ORDER BY suma_valor DESC LIMIT {lim}"
                    ),
                    {"a": d1, "b": d2},
                )
                return {"ok": True, "series": [dict(r._mapping) for r in st]}
            if type == "sale_daily":
                if campo not in ("tfecfac", "tfectra"):
                    raise ValueError("campo debe ser tfecfac o tfectra")
                sql = text(
                    f"SELECT `{campo}` AS dia, COUNT(*) AS filas, COALESCE(SUM(timport),0) AS suma_importe "
                    f"FROM sale WHERE `{campo}` BETWEEN :a AND :b GROUP BY `{campo}` ORDER BY dia"
                )
                st = conn.execute(sql, {"a": d1, "b": d2})
                return {"ok": True, "campo": campo, "series": [dict(r._mapping) for r in st]}
            raise ValueError("type inválido (vg_daily|vg_zonas|sale_daily)")
    except ValueError as e:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(e)})
