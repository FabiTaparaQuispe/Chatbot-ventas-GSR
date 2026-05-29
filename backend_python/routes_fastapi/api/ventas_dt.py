import asyncio
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from services.db import get_connection

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_ymd(s: str | None) -> str | None:
    s = s.strip() if s else ''
    if not s:
        return None
    try:
        d = date.fromisoformat(s)
        if d.strftime('%Y-%m-%d') == s:
            return s
    except Exception:
        pass
    return None


def _text_cell(v) -> str:
    if v is None:
        return ''
    s = str(v)
    if not s:
        return ''
    if 'Ã' not in s and 'Â' not in s:
        return s
    try:
        fixed = s.encode('latin-1').decode('utf-8')
        return fixed if fixed else s
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


def _query_lineas(q: str, page: int) -> dict:
    page_size = 30
    offset = (max(1, page) - 1) * page_size
    like = f'%{q.strip()}%' if q.strip() else '%'
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT TRIM(LineaComercial) AS linea FROM ventasgeneral2"
            " WHERE LineaComercial IS NOT NULL AND TRIM(LineaComercial) != ''"
            " AND TRIM(LineaComercial) LIKE %s ORDER BY linea LIMIT %s OFFSET %s",
            (like, page_size + 1, offset),
        )
        rows = cur.fetchall()
    has_more = len(rows) > page_size
    lineas = [r['linea'] for r in rows[:page_size]]
    return {'results': [{'id': l, 'text': l} for l in lineas], 'pagination': {'more': has_more}}


def _query_tipos_documento() -> list:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT TRIM(TipoDocumento) AS tdoc FROM ventasgeneral2"
            " WHERE TipoDocumento IS NOT NULL AND TRIM(TipoDocumento) != '' ORDER BY tdoc"
        )
        return [r['tdoc'] for r in cur.fetchall()]


def _query_provincias() -> list:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT TRIM(Provincia) AS prov FROM ventasgeneral2"
            " WHERE Provincia IS NOT NULL AND TRIM(Provincia) != '' ORDER BY prov"
        )
        return [r['prov'] for r in cur.fetchall()]


def _query_ventas_dt(draw, start, length, search, desde, hasta,
                     nombre, numero_doc, tipo_documento, codigo_documento, provincia) -> dict:
    conn = get_connection()
    base_where = ' WHERE 1=1'
    params = []

    if desde:
        base_where += ' AND FechaContable >= %s'
        params.append(desde)
    if hasta:
        base_where += ' AND FechaContable <= %s'
        params.append(hasta)
    if nombre:
        base_where += ' AND NombreCliente LIKE %s'
        params.append(f'%{nombre}%')
    if numero_doc:
        base_where += ' AND NumeroFactura LIKE %s'
        params.append(f'%{numero_doc}%')
    if tipo_documento:
        base_where += ' AND TipoDocumento LIKE %s'
        params.append(f'%{tipo_documento}%')
    if codigo_documento:
        base_where += ' AND CodigoDocumento = %s'
        params.append(codigo_documento)
    if provincia:
        base_where += ' AND Provincia LIKE %s'
        params.append(f'%{provincia}%')

    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) AS n FROM ventasgeneral2')
        records_total = int((cur.fetchone() or {}).get('n') or 0)

    where = base_where
    search_params = list(params)
    if search:
        where += (' AND (NombreCliente LIKE %s OR NumeroFactura LIKE %s OR CodigoItem LIKE %s'
                  ' OR GlosaDetalle LIKE %s OR ZonaComercial LIKE %s OR TipoDocumento LIKE %s'
                  ' OR Provincia LIKE %s OR LineaComercial LIKE %s)')
        search_params += [f'%{search}%'] * 8

    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) AS n FROM ventasgeneral2' + where, search_params)
        records_filtered = int((cur.fetchone() or {}).get('n') or 0)

    sql = (
        'SELECT FechaContable, CodigoCliente, NombreCliente, NumeroFactura, CodigoItem,'
        ' GlosaDetalle, Cantidad, Valor, ZonaComercial, TipoDocumento, Provincia, LineaComercial'
        ' FROM ventasgeneral2' + where
        + f' ORDER BY FechaContable DESC, NumeroFactura DESC, CodigoItem DESC LIMIT {length} OFFSET {start}'
    )
    with conn.cursor() as cur:
        cur.execute(sql, search_params)
        rows = cur.fetchall()

    data = [
        [str(start + i + 1), _text_cell(r.get('FechaContable')), _text_cell(r.get('CodigoCliente')),
         _text_cell(r.get('NombreCliente')), _text_cell(r.get('NumeroFactura')), _text_cell(r.get('CodigoItem')),
         _text_cell(r.get('GlosaDetalle')), _text_cell(r.get('Cantidad')), _text_cell(r.get('Valor')),
         _text_cell(r.get('ZonaComercial')), _text_cell(r.get('TipoDocumento')), _text_cell(r.get('Provincia')),
         _text_cell(r.get('LineaComercial'))]
        for i, r in enumerate(rows)
    ]
    return {'draw': draw, 'recordsTotal': records_total, 'recordsFiltered': records_filtered, 'data': data}


@router.get('/api/lineas')
async def api_lineas(q: str = '', page: int = 1):
    try:
        return await asyncio.to_thread(_query_lineas, q, page)
    except Exception as e:
        logger.exception('api_lineas')
        return JSONResponse({'results': [], 'pagination': {'more': False}, 'error': str(e)}, status_code=500)


@router.get('/api/tipos_documento_vg')
async def api_tipos_documento_vg():
    try:
        return await asyncio.to_thread(_query_tipos_documento)
    except Exception as e:
        logger.exception('api_tipos_documento_vg')
        return JSONResponse([], status_code=500)


@router.get('/api/provincias_vg')
async def api_provincias_vg():
    try:
        return await asyncio.to_thread(_query_provincias)
    except Exception as e:
        logger.exception('api_provincias_vg')
        return JSONResponse([], status_code=500)


@router.get('/api/ventasgeneral')
@router.get('/ventasgeneral')
@router.get('/api/ventasgeneral_dt.php')
async def ventas_dt(
    request: Request,
    draw: int = 0,
    start: int = 0,
    length: int = 20,
    search: str = '',
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    nombre: str = '',
    numero_doc: str = '',
    tipo_documento: str = '',
    codigo_documento: str = '',
    provincia: str = '',
):
    draw = max(0, draw)
    start = max(0, start)
    length = max(1, min(200, length))

    try:
        return await asyncio.to_thread(
            _query_ventas_dt,
            draw, start, length, search.strip(),
            _parse_ymd(desde), _parse_ymd(hasta),
            nombre.strip(), numero_doc.strip(),
            tipo_documento.strip(), codigo_documento.strip(), provincia.strip(),
        )
    except Exception as e:
        logger.exception('ventasgeneral_dt')
        return JSONResponse(
            {'draw': draw, 'recordsTotal': 0, 'recordsFiltered': 0, 'data': [], 'error': str(e)},
            status_code=500,
        )
