"""
Informes bajo /modules/… (el chat enlaza rutas canónicas; legacy *.php en paralelo).
Deben registrarse antes del catch-all serve_modules_static en app.py.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from flask import Blueprint, Response, abort, render_template, request

from routes.pages import APP_COMPANY, APP_NAME, ROLES_VENTAS_GENERAL, require_login
from services.urlmap import (
    REPORT_VENTASGENERAL_BUSCAR_TABLA,
    REPORT_VENTASGENERAL_RESUMEN_TABLA,
    chat_assistant_config_dict,
)

bp = Blueprint('reports_modules', __name__)

# Slugs alineados con services.urlmap + tool_executor (informes pendientes de portar)
REPORT_PLACEHOLDER_SLUGS = frozenset(
    {
        'pareto-nc-zona',
        'pareto-clientes-zona',
        'ventas-barras-dimension',
        'ventas-comparativo',
        'ventas-top-productos',
        'ventas-top-clientes-global',
        'ventas-top-clientes-nc',
        'ventas-mix-tdoc',
        'ventas-barras-ruta',
        'ventas-barras-corporativo',
        'ventas-serie-mensual',
    }
)


def _report_shell_context(page_title: str) -> dict[str, Any]:
    from flask import session

    usuario = session.get('usuario', '')
    role = str(session.get('role') or 'lector').lower().strip()
    return {
        'page': 'reporte',
        'page_title': page_title,
        'app_name': APP_NAME,
        'app_company': APP_COMPANY,
        'load_ventas_assets': False,
        'load_listado_skin': False,
        'skip_floating_chat': False,
        'body_class': '',
        'role': role,
        'usuario': usuario,
        'display_name': session.get('display_name', ''),
        'nom_corto': '',
        'roles_ventas_general': ROLES_VENTAS_GENERAL,
        'flash_ok': '',
        'flash_err': '',
        'csrf_token': '',
        'chat_assistant_config': chat_assistant_config_dict(usuario or 'anon'),
    }


def _filtros_resumen_caption() -> str:
    bits: list[str] = []
    z = (request.args.get('zona_comercial') or '').strip()
    if z:
        bits.append(f'Zona comercial: {z}')
    cod = (request.args.get('cod_cliente') or '').strip()
    if cod:
        bits.append(f'Cliente: {cod}')
    pref = (request.args.get('prefijo_descri_zona_precio') or '').strip()
    if pref:
        bits.append(f'Pref. zona precio: {pref}')
    prov = (request.args.get('provincia') or '').strip()
    if prov:
        bits.append(f'Provincia: {prov}')
    tdoc = (request.args.get('tipo_documento') or '').strip()
    if tdoc:
        bits.append(f'Tipo documento: {tdoc}')
    return ' · '.join(bits)


def _parse_date_string(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().strip(" \t\n\r\0\x0b\"'()[]<>")
    if not s:
        return None
    try:
        d = datetime.strptime(s, '%Y-%m-%d')
    except ValueError:
        return None
    return d.strftime('%Y-%m-%d')


def _colon_params_to_pymysql(sql: str) -> str:
    return re.sub(r':([a-zA-Z_][a-zA-Z0-9_]*)', r'%(\1)s', sql)


def _bad(msg: str, code: int = 400) -> Response:
    return Response(msg, status=code, mimetype='text/plain; charset=utf-8')


def _buscar_ventasgeneral(conn, args: dict) -> dict:
    """Misma lógica que api/python/app/ventas_queries.buscar, con PyMySQL."""
    max_limit = 100
    default_limit = 50

    def clamp_limit(n: int | None) -> int:
        if n is None:
            return default_limit
        return max(1, min(max_limit, n))

    try:
        li = int(args['limit']) if args.get('limit') not in (None, '') else None
    except (TypeError, ValueError):
        li = None
    limit = clamp_limit(li)

    try:
        off = max(0, int(args.get('offset') or 0))
    except (TypeError, ValueError):
        off = 0

    def parse_date_optional(key: str) -> str | None:
        v = args.get(key)
        if v is None or str(v).strip() == '':
            return None
        s = str(v).strip()
        try:
            datetime.strptime(s, '%Y-%m-%d')
        except ValueError as e:
            raise ValueError('Fecha inválida (YYYY-MM-DD)') from e
        return s

    sql = """SELECT id, FechaContable, CodigoCoorporativo, NombreCoorporativo, CodigoCliente, NombreCliente, CodigoDocumento, TipoDocumento, SerieDocumento, NumeroDocumento, NumeroFactura, CodigoItem, GlosaDetalle, Cantidad, Peso, Valor, ZonaComercial, DescripcionZonaPrecio, RutaComercial, Provincia, LineaComercial
        FROM ventasgeneral2 WHERE 1=1"""
    params: dict = {}

    fd = parse_date_optional('fecha_desde')
    fh = parse_date_optional('fecha_hasta')

    if fd is not None and fh is not None:
        if fd > fh:
            raise ValueError('fecha_desde no puede ser mayor que fecha_hasta')
        sql += ' AND FechaContable BETWEEN :fd AND :fh'
        params['fd'] = fd
        params['fh'] = fh
    elif fd is not None:
        sql += ' AND FechaContable >= :fd'
        params['fd'] = fd
    elif fh is not None:
        sql += ' AND FechaContable <= :fh'
        params['fh'] = fh

    nom = str(args.get('nombre_cliente') or '').strip()
    if nom:
        sql += ' AND NombreCliente LIKE :nom'
        params['nom'] = f'%{nom}%'

    ndoc = str(args.get('numero_doc') or '').strip()
    if ndoc:
        sql += ' AND NumeroFactura LIKE :ndoc'
        params['ndoc'] = f'%{ndoc}%'

    item = str(args.get('cod_item') or '').strip()
    if item:
        sql += ' AND CodigoItem = :item'
        params['item'] = item

    tdoc = str(args.get('tdoc') or '').strip()
    if tdoc:
        if len(tdoc) > 4:
            raise ValueError('tdoc demasiado largo')
        sql += ' AND CodigoDocumento = :tdoc'
        params['tdoc'] = tdoc

    pref_z = str(args.get('prefijo_descri_zona_precio') or '').strip().upper()
    if pref_z:
        sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzp"
        params['prefzp'] = pref_z + '%'

    prov = str(args.get('provincia') or '').strip()
    if prov:
        sql += ' AND Provincia LIKE :prov'
        params['prov'] = f'%{prov}%'

    tdoctipo = str(args.get('tipo_documento') or '').strip()
    if tdoctipo:
        sql += ' AND TipoDocumento LIKE :tdoctipo'
        params['tdoctipo'] = f'%{tdoctipo}%'

    sql += f' ORDER BY FechaContable DESC, id DESC LIMIT {int(limit)} OFFSET {int(off)}'

    sql_exec = _colon_params_to_pymysql(sql)
    with conn.cursor() as cur:
        cur.execute(sql_exec, params)
        rows = cur.fetchall() or []

    return {'filas': rows, 'limit': limit, 'offset': off}


@bp.route(REPORT_VENTASGENERAL_RESUMEN_TABLA)
@bp.route('/modules/ventasgeneral_resumen_tabla.php')
@require_login
def ventasgeneral_resumen_tabla():
    from services.db import get_connection

    d1 = _parse_date_string(request.args.get('fecha_desde')) or _parse_date_string(request.args.get('desde'))
    d2 = _parse_date_string(request.args.get('fecha_hasta')) or _parse_date_string(request.args.get('hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros: fecha_desde y fecha_hasta (YYYY-MM-DD); alias desde y hasta.')

    sql = """SELECT COUNT(*) AS filas, COALESCE(SUM(Valor),0) AS suma_valor,
        COALESCE(SUM(Cantidad),0) AS suma_cantidad, COALESCE(SUM(Peso),0) AS suma_peso
        FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2"""
    bind: dict = {'d1': d1, 'd2': d2}
    zona = (request.args.get('zona_comercial') or '').strip()
    if zona:
        sql += ' AND ZonaComercial LIKE :zona'
        bind['zona'] = f'%{zona}%'
    cod = (request.args.get('cod_cliente') or '').strip()
    if cod:
        sql += ' AND CodigoCliente = :cod'
        bind['cod'] = cod
    pref_z = (request.args.get('prefijo_descri_zona_precio') or '').strip().upper()
    if pref_z:
        sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzp"
        bind['prefzp'] = pref_z + '%'
    prov = (request.args.get('provincia') or '').strip()
    if prov:
        sql += ' AND Provincia LIKE :prov'
        bind['prov'] = f'%{prov}%'
    tdoctipo = (request.args.get('tipo_documento') or '').strip()
    if tdoctipo:
        sql += ' AND TipoDocumento LIKE :tdoctipo'
        bind['tdoctipo'] = f'%{tdoctipo}%'

    conn = get_connection()
    sql_exec = _colon_params_to_pymysql(sql)
    with conn.cursor() as cur:
        cur.execute(sql_exec, bind)
        row = cur.fetchone() or {}

    pdf_filename = f'resumen_ventasgeneral_{d1}_{d2}.pdf'
    ctx = _report_shell_context('Resumen agregados')
    filtros_texto = _filtros_resumen_caption()
    ctx.update(
        {
            'd1': d1,
            'd2': d2,
            'filtros_texto': filtros_texto,
            'r_filas': str(row.get('filas') or ''),
            'r_valor': f"{float(row.get('suma_valor') or 0):,.2f}",
            'r_cant': f"{float(row.get('suma_cantidad') or 0):,.2f}",
            'r_peso': f"{float(row.get('suma_peso') or 0):,.2f}",
            'pdf_filename': pdf_filename,
        }
    )
    return render_template('pages/reporte_resumen_tabla.html', **ctx)


@bp.route(REPORT_VENTASGENERAL_BUSCAR_TABLA)
@bp.route('/modules/ventasgeneral_buscar_tabla.php')
@require_login
def ventasgeneral_buscar_tabla():
    from services.db import get_connection

    fd = (request.args.get('fecha_desde') or request.args.get('desde') or '').strip()
    fh = (request.args.get('fecha_hasta') or request.args.get('hasta') or '').strip()
    args: dict = {
        'fecha_desde': fd,
        'fecha_hasta': fh,
        'nombre_cliente': (request.args.get('nombre_cliente') or '').strip(),
        'numero_doc': (request.args.get('numero_doc') or '').strip(),
        'cod_item': (request.args.get('cod_item') or '').strip(),
        'tdoc': (request.args.get('tdoc') or '').strip(),
        'prefijo_descri_zona_precio': (request.args.get('prefijo_descri_zona_precio') or '').strip(),
        'provincia': (request.args.get('provincia') or '').strip(),
        'tipo_documento': (request.args.get('tipo_documento') or '').strip(),
    }
    for k in list(args.keys()):
        if args[k] == '':
            del args[k]
    try:
        li = request.args.get('limit')
        off = request.args.get('offset')
        if li is not None and str(li).strip() != '':
            args['limit'] = int(li)
        if off is not None and str(off).strip() != '':
            args['offset'] = int(off)
    except ValueError:
        return _bad('limit/offset inválidos')

    try:
        conn = get_connection()
        out = _buscar_ventasgeneral(conn, args)
    except ValueError as e:
        return _bad(str(e))

    raw_filas = out.get('filas') or []
    filas = [dict(r) if not isinstance(r, dict) else r for r in raw_filas[:100]]
    headers = [
        'id',
        'FechaContable',
        'CodigoCliente',
        'NombreCliente',
        'NumeroFactura',
        'CodigoItem',
        'GlosaDetalle',
        'Cantidad',
        'Valor',
        'ZonaComercial',
    ]
    ctx = _report_shell_context('Buscar ventasgeneral')
    ctx.update(
        {
            'headers': headers,
            'filas': filas,
            'total_filas': len(raw_filas),
            'limit': out.get('limit'),
            'offset': out.get('offset') or 0,
        }
    )
    return render_template('pages/reporte_buscar_tabla.html', **ctx)


@bp.route('/modules/reports/<slug>')
@require_login
def report_placeholder(slug: str):
    if slug not in REPORT_PLACEHOLDER_SLUGS:
        abort(404)
    ctx = _report_shell_context('Informe')
    ctx['report_slug'] = slug
    ctx['report_query'] = (request.query_string or b'').decode('utf-8', errors='replace')
    return render_template('pages/reporte_placeholder.html', **ctx)
