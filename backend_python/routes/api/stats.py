from flask import Blueprint, request, jsonify
from datetime import date
from services.db import get_connection

bp = Blueprint('stats', __name__)


def _parse_ymd(s):
    if not s:
        return None
    try:
        d = date.fromisoformat(str(s).strip())
        return d.strftime('%Y-%m-%d') if d.strftime('%Y-%m-%d') == str(s).strip() else None
    except Exception:
        return None


@bp.route('/api/stats.php')
def stats():
    type_ = request.args.get('type', '')
    desde = request.args.get('desde', '')
    hasta = request.args.get('hasta', '')

    d1 = _parse_ymd(desde)
    d2 = _parse_ymd(hasta)

    if not d1 or not d2:
        return jsonify({'ok': False, 'error': 'Parámetros desde y hasta requeridos (YYYY-MM-DD)'}), 400
    if d1 > d2:
        return jsonify({'ok': False, 'error': 'desde > hasta'}), 400

    from datetime import date as _date
    dt1 = _date.fromisoformat(d1)
    dt2 = _date.fromisoformat(d2)
    if (dt2 - dt1).days > 366:
        return jsonify({'ok': False, 'error': 'Rango máximo 366 días'}), 400

    try:
        conn = get_connection()
        if type_ == 'vg_daily':
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT FechaContable AS dia, COUNT(*) AS filas, COALESCE(SUM(Valor),0) AS suma_valor'
                    ' FROM ventasgeneral2 WHERE FechaContable BETWEEN %(a)s AND %(b)s'
                    ' GROUP BY FechaContable ORDER BY FechaContable',
                    {'a': d1, 'b': d2}
                )
                series = [dict(r) for r in cur.fetchall()]
            return jsonify({'ok': True, 'series': series})

        elif type_ == 'vg_zonas':
            limit = max(1, min(25, int(request.args.get('limit', 12) or 12)))
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COALESCE(NULLIF(TRIM(ZonaComercial),''),'(sin zona)') AS zona,"
                    f" COUNT(*) AS filas, COALESCE(SUM(Valor),0) AS suma_valor"
                    f" FROM ventasgeneral2 WHERE FechaContable BETWEEN %(a)s AND %(b)s"
                    f" GROUP BY COALESCE(NULLIF(TRIM(ZonaComercial),''),'(sin zona)')"
                    f" ORDER BY suma_valor DESC LIMIT {limit}",
                    {'a': d1, 'b': d2}
                )
                series = [dict(r) for r in cur.fetchall()]
            return jsonify({'ok': True, 'series': series})

        elif type_ == 'sale_daily':
            campo = request.args.get('campo', 'tfecfac')
            if campo not in ('tfecfac', 'tfectra'):
                return jsonify({'ok': False, 'error': 'campo debe ser tfecfac o tfectra'}), 400
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT `{campo}` AS dia, COUNT(*) AS filas, COALESCE(SUM(timport),0) AS suma_importe'
                    f' FROM sale WHERE `{campo}` BETWEEN %(a)s AND %(b)s'
                    f' GROUP BY `{campo}` ORDER BY dia',
                    {'a': d1, 'b': d2}
                )
                series = [dict(r) for r in cur.fetchall()]
            return jsonify({'ok': True, 'campo': campo, 'series': series})

        else:
            return jsonify({'ok': False, 'error': 'type inválido (vg_daily|vg_zonas|sale_daily)'}), 400

    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
