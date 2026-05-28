import logging
from datetime import date

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.db import get_connection

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_ymd(s: str) -> str | None:
    s = str(s).strip() if s else ''
    if not s:
        return None
    try:
        d = date.fromisoformat(s)
        if d.strftime('%Y-%m-%d') == s:
            return s
    except Exception:
        pass
    return None


@router.get('/api/ventas_kpi')
async def ventas_kpi(
    desde: str = '', hasta: str = '', nombre: str = '',
    numero_doc: str = '', tipo_documento: str = '',
    codigo_documento: str = '', provincia: str = '',
):
    d1 = _parse_ymd(desde)
    d2 = _parse_ymd(hasta)
    where = ' WHERE 1=1'
    params = []
    if d1:
        where += ' AND FechaContable >= %s'
        params.append(d1)
    if d2:
        where += ' AND FechaContable <= %s'
        params.append(d2)
    if nombre.strip():
        where += ' AND NombreCliente LIKE %s'
        params.append(f'%{nombre.strip()}%')
    if numero_doc.strip():
        where += ' AND NumeroFactura LIKE %s'
        params.append(f'%{numero_doc.strip()}%')
    if tipo_documento.strip():
        where += ' AND TipoDocumento LIKE %s'
        params.append(f'%{tipo_documento.strip()}%')
    if codigo_documento.strip():
        where += ' AND CodigoDocumento = %s'
        params.append(codigo_documento.strip())
    if provincia.strip():
        where += ' AND Provincia LIKE %s'
        params.append(f'%{provincia.strip()}%')

    try:
        conn = get_connection()
        sql = (
            'SELECT COUNT(*) AS filas,'
            ' COALESCE(SUM(Valor), 0) AS suma_valor,'
            ' COUNT(DISTINCT CodigoCliente) AS clientes,'
            " COUNT(DISTINCT NULLIF(TRIM(ZonaComercial), '')) AS zonas"
            ' FROM ventasgeneral2' + where
        )
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone() or {}
        return {
            'ok': True,
            'filas': int(row.get('filas') or 0),
            'suma_valor': float(row.get('suma_valor') or 0),
            'clientes': int(row.get('clientes') or 0),
            'zonas': int(row.get('zonas') or 0),
        }
    except Exception as e:
        logger.exception('ventas_kpi')
        return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)
