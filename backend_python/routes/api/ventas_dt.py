import logging
from datetime import date

from flask import Blueprint, jsonify, request

from services.db import get_connection

logger = logging.getLogger(__name__)

bp = Blueprint('api_ventas_dt', __name__)


def _parse_ymd(s: str):
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
    """Convierte celda a texto JSON; corrige mojibake UTF-8 leído como Latin-1 (ej. CAMPIÃ'A → CAMPIÑA)."""
    if v is None:
        return ''
    s = str(v)
    if not s:
        return ''
    # Solo intentar si hay secuencias típicas de UTF-8 mal interpretado como latin1
    if 'Ã' not in s and 'Â' not in s:
        return s
    try:
        fixed = s.encode('latin-1').decode('utf-8')
        return fixed if fixed else s
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


@bp.route('/api/lineas')
def api_lineas():
    q = (request.args.get('q') or '').strip()
    page = max(1, int(request.args.get('page') or 1))
    page_size = 30
    offset = (page - 1) * page_size
    like = f'%{q}%' if q else '%'

    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT TRIM(LineaComercial) AS linea FROM ventasgeneral2"
                " WHERE LineaComercial IS NOT NULL AND TRIM(LineaComercial) != ''"
                " AND TRIM(LineaComercial) LIKE %s"
                " ORDER BY linea LIMIT %s OFFSET %s",
                (like, page_size + 1, offset),
            )
            rows = cur.fetchall()
        has_more = len(rows) > page_size
        lineas = [r['linea'] for r in rows[:page_size]]
        return jsonify({
            'results': [{'id': l, 'text': l} for l in lineas],
            'pagination': {'more': has_more},
        })
    except Exception as e:
        logger.exception('api_lineas')
        return jsonify({'results': [], 'pagination': {'more': False}, 'error': str(e)}), 500


@bp.route('/api/ventasgeneral', methods=['GET'])
@bp.route('/api/ventasgeneral_dt.php', methods=['GET'])
def ventas_dt():
    draw = int(request.args.get('draw') or 0)
    start = max(0, int(request.args.get('start') or 0))
    length = max(1, min(200, int(request.args.get('length') or 20)))

    search_val = request.args.get('search') or ''
    if isinstance(search_val, dict):
        search_val = search_val.get('value') or ''
    search = str(search_val).strip()

    desde = _parse_ymd(request.args.get('desde') or '')
    hasta = _parse_ymd(request.args.get('hasta') or '')
    nombre = str(request.args.get('nombre') or '').strip()
    numero_doc = str(request.args.get('numero_doc') or '').strip()
    tipo_documento = str(request.args.get('tipo_documento') or '').strip()
    codigo_documento = str(request.args.get('codigo_documento') or '').strip()
    provincia = str(request.args.get('provincia') or '').strip()

    try:
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

        # Orden estable sin depender de columna `id` (en algunas BD la tabla no tiene PK `id`).
        sql = (
            'SELECT FechaContable, CodigoCliente, NombreCliente, NumeroFactura, CodigoItem,'
            ' GlosaDetalle, Cantidad, Valor, ZonaComercial, TipoDocumento, Provincia, LineaComercial'
            ' FROM ventasgeneral2' + where
            + f' ORDER BY FechaContable DESC, NumeroFactura DESC, CodigoItem DESC LIMIT {length} OFFSET {start}'
        )

        with conn.cursor() as cur:
            cur.execute(sql, search_params)
            rows = cur.fetchall()

        data = []
        for i, r in enumerate(rows):
            data.append([
                str(start + i + 1),
                _text_cell(r.get('FechaContable')),
                _text_cell(r.get('CodigoCliente')),
                _text_cell(r.get('NombreCliente')),
                _text_cell(r.get('NumeroFactura')),
                _text_cell(r.get('CodigoItem')),
                _text_cell(r.get('GlosaDetalle')),
                _text_cell(r.get('Cantidad')),
                _text_cell(r.get('Valor')),
                _text_cell(r.get('ZonaComercial')),
                _text_cell(r.get('TipoDocumento')),
                _text_cell(r.get('Provincia')),
                _text_cell(r.get('LineaComercial')),
            ])

        return jsonify({
            'draw': draw,
            'recordsTotal': records_total,
            'recordsFiltered': records_filtered,
            'data': data,
        })
    except Exception as e:
        logger.exception('ventasgeneral_dt')
        return jsonify({
            'draw': draw,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': [],
            'error': str(e),
        }), 500
