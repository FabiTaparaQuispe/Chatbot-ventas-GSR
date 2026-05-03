from flask import Blueprint, request, jsonify
from services.db import get_connection
from datetime import date

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


def _utf8_str(v) -> str:
    if v is None:
        return ''
    try:
        s = str(v)
        s.encode('utf-8')
        return s
    except Exception:
        return str(v).encode('utf-8', errors='replace').decode('utf-8')


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

        sql = ('SELECT FechaContable, CodigoCliente, NombreCliente, NumeroFactura, CodigoItem,'
               ' GlosaDetalle, Cantidad, Valor, ZonaComercial, TipoDocumento, Provincia, LineaComercial'
               ' FROM ventasgeneral2' + where +
               f' ORDER BY FechaContable DESC, id DESC LIMIT {length} OFFSET {start}')

        with conn.cursor() as cur:
            cur.execute(sql, search_params)
            rows = cur.fetchall()

        data = []
        for i, r in enumerate(rows):
            data.append([
                str(start + i + 1),
                _utf8_str(r.get('FechaContable')),
                _utf8_str(r.get('CodigoCliente')),
                _utf8_str(r.get('NombreCliente')),
                _utf8_str(r.get('NumeroFactura')),
                _utf8_str(r.get('CodigoItem')),
                _utf8_str(r.get('GlosaDetalle')),
                _utf8_str(r.get('Cantidad')),
                _utf8_str(r.get('Valor')),
                _utf8_str(r.get('ZonaComercial')),
                _utf8_str(r.get('TipoDocumento')),
                _utf8_str(r.get('Provincia')),
                _utf8_str(r.get('LineaComercial')),
            ])

        return jsonify({
            'draw': draw,
            'recordsTotal': records_total,
            'recordsFiltered': records_filtered,
            'data': data,
        })
    except Exception as e:
        return jsonify({
            'draw': draw,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': [],
            'error': str(e),
        }), 500
