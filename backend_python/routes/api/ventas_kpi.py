import logging
from datetime import date

from flask import Blueprint, jsonify, request

from services.db import get_connection

logger = logging.getLogger(__name__)
bp = Blueprint('api_ventas_kpi', __name__)


def _parse_ymd(s: str):
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


@bp.route('/api/ventas_kpi')
def ventas_kpi():
    desde = _parse_ymd(request.args.get('desde') or '')
    hasta = _parse_ymd(request.args.get('hasta') or '')
    nombre = str(request.args.get('nombre') or '').strip()
    numero_doc = str(request.args.get('numero_doc') or '').strip()
    tipo_documento = str(request.args.get('tipo_documento') or '').strip()
    provincia = str(request.args.get('provincia') or '').strip()

    where = ' WHERE 1=1'
    params = []
    if desde:
        where += ' AND FechaContable >= %s'
        params.append(desde)
    if hasta:
        where += ' AND FechaContable <= %s'
        params.append(hasta)
    if nombre:
        where += ' AND NombreCliente LIKE %s'
        params.append(f'%{nombre}%')
    if numero_doc:
        where += ' AND NumeroFactura LIKE %s'
        params.append(f'%{numero_doc}%')
    if tipo_documento:
        where += ' AND TipoDocumento LIKE %s'
        params.append(f'%{tipo_documento}%')
    if provincia:
        where += ' AND Provincia LIKE %s'
        params.append(f'%{provincia}%')

    try:
        conn = get_connection()
        sql = (
            'SELECT COUNT(*) AS filas,'
            ' COALESCE(SUM(Valor), 0) AS suma_valor,'
            ' COUNT(DISTINCT CodigoCliente) AS clientes,'
            ' COUNT(DISTINCT NULLIF(TRIM(ZonaComercial), \'\')) AS zonas'
            ' FROM ventasgeneral2' + where
        )
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone() or {}
        return jsonify({
            'ok': True,
            'filas': int(row.get('filas') or 0),
            'suma_valor': float(row.get('suma_valor') or 0),
            'clientes': int(row.get('clientes') or 0),
            'zonas': int(row.get('zonas') or 0),
        })
    except Exception as e:
        logger.exception('ventas_kpi')
        return jsonify({'ok': False, 'error': str(e)}), 500
