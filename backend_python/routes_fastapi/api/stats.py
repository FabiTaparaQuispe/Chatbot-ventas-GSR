from datetime import date

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.db import get_connection

router = APIRouter()


def _parse_ymd(s) -> str | None:
    if not s:
        return None
    try:
        d = date.fromisoformat(str(s).strip())
        return d.strftime('%Y-%m-%d') if d.strftime('%Y-%m-%d') == str(s).strip() else None
    except Exception:
        return None


@router.get('/api/stats')
@router.get('/api/stats.php')
async def stats(type: str = '', desde: str = '', hasta: str = '', limit: int = 12, campo: str = 'tfecfac'):
    d1 = _parse_ymd(desde)
    d2 = _parse_ymd(hasta)
    if not d1 or not d2:
        return JSONResponse({'ok': False, 'error': 'Parámetros desde y hasta requeridos (YYYY-MM-DD)'}, status_code=400)
    if d1 > d2:
        return JSONResponse({'ok': False, 'error': 'desde > hasta'}, status_code=400)
    from datetime import date as _date
    if (_date.fromisoformat(d2) - _date.fromisoformat(d1)).days > 366:
        return JSONResponse({'ok': False, 'error': 'Rango máximo 366 días'}, status_code=400)

    try:
        conn = get_connection()
        if type == 'vg_daily':
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT FechaContable AS dia, COUNT(*) AS filas, COALESCE(SUM(Valor),0) AS suma_valor'
                    ' FROM ventasgeneral2 WHERE FechaContable BETWEEN %(a)s AND %(b)s'
                    ' GROUP BY FechaContable ORDER BY FechaContable',
                    {'a': d1, 'b': d2}
                )
                series = [dict(r) for r in cur.fetchall()]
            return {'ok': True, 'series': series}

        elif type == 'vg_zonas':
            lim = max(1, min(25, limit))
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COALESCE(NULLIF(TRIM(ZonaComercial),''),'(sin zona)') AS zona,"
                    f" COUNT(*) AS filas, COALESCE(SUM(Valor),0) AS suma_valor"
                    f" FROM ventasgeneral2 WHERE FechaContable BETWEEN %(a)s AND %(b)s"
                    f" GROUP BY COALESCE(NULLIF(TRIM(ZonaComercial),''),'(sin zona)')"
                    f" ORDER BY suma_valor DESC LIMIT {lim}",
                    {'a': d1, 'b': d2}
                )
                series = [dict(r) for r in cur.fetchall()]
            return {'ok': True, 'series': series}

        elif type == 'sale_daily':
            if campo not in ('tfecfac', 'tfectra'):
                return JSONResponse({'ok': False, 'error': 'campo debe ser tfecfac o tfectra'}, status_code=400)
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT `{campo}` AS dia, COUNT(*) AS filas, COALESCE(SUM(timport),0) AS suma_importe'
                    f' FROM sale WHERE `{campo}` BETWEEN %(a)s AND %(b)s'
                    f' GROUP BY `{campo}` ORDER BY dia',
                    {'a': d1, 'b': d2}
                )
                series = [dict(r) for r in cur.fetchall()]
            return {'ok': True, 'campo': campo, 'series': series}

        return JSONResponse({'ok': False, 'error': 'type inválido (vg_daily|vg_zonas|sale_daily)'}, status_code=400)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=400)
