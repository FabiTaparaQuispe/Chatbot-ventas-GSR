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
        'load_listado_skin': True,
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


@bp.route('/modules/reports/ventas-top-clientes-nc')
@require_login
def ventas_top_clientes_nc():
    from services.db import get_connection

    d1 = _parse_date_string(request.args.get('desde') or request.args.get('fecha_desde'))
    d2 = _parse_date_string(request.args.get('hasta') or request.args.get('fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta (YYYY-MM-DD).')

    try:
        top = max(1, min(50, int(request.args.get('top') or 10)))
    except (TypeError, ValueError):
        top = 10

    tdoc_cond = "COALESCE(NULLIF(TRIM(CodigoDocumento),''),'') = '07'"
    sql = (f"SELECT CodigoCliente AS cod_cliente,"
           f" MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,"
           f" COUNT(*) AS lineas,"
           f" COALESCE(SUM(Valor),0) AS suma_valor,"
           f" COALESCE(SUM(Peso),0) AS suma_peso"
           f" FROM ventasgeneral2"
           f" WHERE FechaContable BETWEEN :d1 AND :d2 AND {tdoc_cond}"
           f" GROUP BY CodigoCliente ORDER BY lineas DESC, suma_valor ASC LIMIT {top}")
    sql_tot = (f"SELECT COUNT(*) AS n,"
               f" COALESCE(SUM(Valor),0) AS v,"
               f" COALESCE(SUM(Peso),0) AS p"
               f" FROM ventasgeneral2"
               f" WHERE FechaContable BETWEEN :d1 AND :d2 AND {tdoc_cond}")
    bind = {'d1': d1, 'd2': d2}

    conn = get_connection()
    sql_exec = _colon_params_to_pymysql(sql)
    sql_tot_exec = _colon_params_to_pymysql(sql_tot)
    with conn.cursor() as cur:
        cur.execute(sql_exec, bind)
        raw = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(sql_tot_exec, bind)
        tot = cur.fetchone() or {}

    total_lineas = int(tot.get('n') or 0)
    total_valor = float(tot.get('v') or 0)
    total_peso = float(tot.get('p') or 0)

    cum = 0.0
    filas = []
    chart_labels: list = []
    chart_lineas: list = []
    chart_valores: list = []
    chart_pesos: list = []
    chart_pct_acum: list = []
    for i, r in enumerate(raw, 1):
        ln = int(r.get('lineas') or 0)
        pct = ln / total_lineas * 100 if total_lineas else 0.0
        cum += pct
        sv = float(r.get('suma_valor') or 0)
        sp = float(r.get('suma_peso') or 0)
        nombre = str(r.get('nombre_cliente') or '')
        chart_labels.append(nombre[:28])
        chart_lineas.append(ln)
        chart_valores.append(round(abs(sv), 2))
        chart_pesos.append(round(abs(sp), 2))
        chart_pct_acum.append(round(cum, 1))
        filas.append({
            'rank': i,
            'cod_cliente': str(r.get('cod_cliente') or ''),
            'nombre_cliente': nombre,
            'lineas': ln,
            'suma_valor': f'{sv:,.2f}',
            'suma_peso': f'{sp:,.2f}',
            'pct_lineas': f'{pct:.1f}',
            'pct_acumulado': f'{cum:.1f}',
        })

    pdf_filename = f'top_clientes_nc_{d1}_{d2}.pdf'
    ctx = _report_shell_context('Top clientes · Notas de crédito')
    ctx.update({
        'd1': d1,
        'd2': d2,
        'top': top,
        'filas': filas,
        'total_lineas': total_lineas,
        'total_valor': f'{total_valor:,.2f}',
        'total_peso': f'{total_peso:,.2f}',
        'pdf_filename': pdf_filename,
        'chart_data': {
            'labels': chart_labels,
            'lineas': chart_lineas,
            'valores': chart_valores,
            'pesos': chart_pesos,
            'pct_acum': chart_pct_acum,
        },
    })
    return render_template('pages/reporte_top_clientes_nc.html', **ctx)


@bp.route('/modules/reports/ventas-linea-resumen-provincia')
@require_login
def ventas_linea_resumen_provincia():
    from services.db import get_connection

    d1 = _parse_date_string(request.args.get('desde') or request.args.get('fecha_desde'))
    d2 = _parse_date_string(request.args.get('hasta') or request.args.get('fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta (YYYY-MM-DD).')

    linea = (request.args.get('linea') or '').strip()
    if not linea:
        return _bad('Parámetro requerido: linea (ej. "Pollo Vivo").')

    raw_top = request.args.get('top')
    top = None
    if raw_top is not None and str(raw_top).strip() != '':
        s = str(raw_top).strip().lower()
        if s not in ('0', 'all', 'todos'):
            try:
                n = int(raw_top)
                if n > 0:
                    top = max(1, min(100_000, n))
            except (TypeError, ValueError):
                top = None

    cod_item = (request.args.get('cod_item') or '').strip()
    mercado = (request.args.get('mercado') or '').strip().upper()

    # Filtros multi-select (Fase 1)
    f_provincias   = [v.strip() for v in request.args.getlist('provincia')   if v.strip()]
    f_corporativos = [v.strip() for v in request.args.getlist('corporativo') if v.strip()]
    f_clientes     = [v.strip() for v in request.args.getlist('cliente')     if v.strip()]

    # WHERE base: fecha + linea + cod_item + mercado (se usa para opciones de dropdowns)
    base_where = (" WHERE FechaContable BETWEEN :d1 AND :d2"
                  " AND LOWER(TRIM(LineaComercial)) = LOWER(TRIM(:linea))"
                  " AND CodigoDocumento IN ('01','03')")
    base_bind: dict = {'d1': d1, 'd2': d2, 'linea': linea}
    if cod_item:
        base_where += " AND CodigoItem = :cod_item"
        base_bind['cod_item'] = cod_item
    if mercado:
        base_where += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo"
        base_bind['prefzo'] = mercado + '%'

    # WHERE extendido: agrega los filtros multi-select seleccionados
    ext_where = base_where
    bind = dict(base_bind)
    if f_provincias:
        keys = [f'prov_{i}' for i in range(len(f_provincias))]
        ext_where += ' AND Provincia IN (' + ','.join(f':{k}' for k in keys) + ')'
        bind.update(zip(keys, f_provincias))
    if f_corporativos:
        keys = [f'corp_{i}' for i in range(len(f_corporativos))]
        ext_where += ' AND NombreCoorporativo IN (' + ','.join(f':{k}' for k in keys) + ')'
        bind.update(zip(keys, f_corporativos))
    if f_clientes:
        keys = [f'cli_{i}' for i in range(len(f_clientes))]
        ext_where += ' AND CodigoCliente IN (' + ','.join(f':{k}' for k in keys) + ')'
        bind.update(zip(keys, f_clientes))

    # Query opciones (usa solo base_where para mostrar todos los valores disponibles)
    sql_opts = ("SELECT DISTINCT"
                " COALESCE(NULLIF(TRIM(NombreCoorporativo),''),'') AS nombre_corporativo,"
                " COALESCE(NULLIF(TRIM(CodigoCoorporativo),''),'') AS cod_corporativo,"
                " COALESCE(NULLIF(TRIM(NombreCliente),''),'') AS nombre_cliente,"
                " CodigoCliente AS cod_cliente,"
                " COALESCE(NULLIF(TRIM(Provincia),''),'') AS provincia"
                f" FROM ventasgeneral2{base_where}"
                " ORDER BY nombre_corporativo, nombre_cliente")

    # Query principal de agregación
    sql = ("SELECT"
           " COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') AS provincia,"
           " MAX(COALESCE(NULLIF(TRIM(NombreCoorporativo),''),'')) AS nombre_corporativo,"
           " CodigoCliente AS cod_cliente,"
           " MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,"
           " COUNT(*) AS lineas,"
           " COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
           " COALESCE(SUM(Peso),0) AS suma_peso,"
           " COALESCE(SUM(Valor),0) AS suma_valor,"
           " CASE WHEN COALESCE(SUM(Peso),0) > 0"
           "      THEN ROUND(COALESCE(SUM(Valor),0) / COALESCE(SUM(Peso),0), 2)"
           "      ELSE NULL END AS precio_kg"
           f" FROM ventasgeneral2{ext_where}"
           " GROUP BY provincia, CodigoCliente ORDER BY suma_peso DESC")
    if top is not None:
        sql += f" LIMIT {top}"

    # Query precio ponderado por día (para el 3er gráfico, mismos filtros)
    sql_precio_dia = ("SELECT FechaContable AS fecha,"
                      " COALESCE(SUM(Peso),0) AS suma_peso,"
                      " CASE WHEN COALESCE(SUM(Peso),0) > 0"
                      "      THEN ROUND(COALESCE(SUM(Valor),0) / COALESCE(SUM(Peso),0), 4)"
                      "      ELSE NULL END AS precio_kg"
                      f" FROM ventasgeneral2{ext_where}"
                      " GROUP BY fecha ORDER BY fecha ASC")

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_opts), base_bind)
        raw_opts = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_precio_dia), bind)
        raw_precio_dia = cur.fetchall() or []

    # Construir listas de opciones para los dropdowns
    provincias_opts: list[str] = []
    corporativos_opts: list[dict] = []
    clientes_opts: list[dict] = []
    seen_prov: set = set()
    seen_corp: set = set()
    seen_cli: set = set()
    for r in raw_opts:
        pv = str(r.get('provincia') or '')
        if pv and pv not in seen_prov:
            seen_prov.add(pv)
            provincias_opts.append(pv)
        corp = str(r.get('nombre_corporativo') or '')
        if corp and corp not in seen_corp:
            seen_corp.add(corp)
            corporativos_opts.append({'nombre': corp, 'cod': str(r.get('cod_corporativo') or '')})
        cli = str(r.get('cod_cliente') or '')
        if cli and cli not in seen_cli:
            seen_cli.add(cli)
            clientes_opts.append({
                'cod': cli,
                'nombre': str(r.get('nombre_cliente') or ''),
                'corporativo': str(r.get('nombre_corporativo') or ''),
            })

    # Construir filas y datos de gráficos
    total_lineas = 0
    total_cantidad = 0.0
    total_peso = 0.0
    total_valor = 0.0
    filas = []
    chart_labels: list = []
    chart_pesos: list = []
    chart_valores: list = []
    for i, r in enumerate(raw, 1):
        sp = float(r.get('suma_peso') or 0)
        sv = float(r.get('suma_valor') or 0)
        pk = r.get('precio_kg')
        nombre = str(r.get('nombre_cliente') or '')
        prov = str(r.get('provincia') or '')
        corp = str(r.get('nombre_corporativo') or '')
        total_lineas += int(r.get('lineas') or 0)
        total_cantidad += float(r.get('suma_cantidad') or 0)
        total_peso += sp
        total_valor += sv
        chart_labels.append(f"{nombre[:20]} ({prov[:8]})")
        chart_pesos.append(round(sp, 2))
        chart_valores.append(round(sv, 2))
        filas.append({
            'rank': i,
            'provincia': prov,
            'nombre_corporativo': corp,
            'cod_cliente': str(r.get('cod_cliente') or ''),
            'nombre_cliente': nombre,
            'lineas': f"{int(r.get('lineas') or 0):,}",
            'suma_cantidad': f"{float(r.get('suma_cantidad') or 0):,.2f}",
            'suma_peso': f'{sp:,.2f}',
            'suma_valor': f'{sv:,.2f}',
            'precio_kg': f'S/ {float(pk):.2f}' if pk is not None else '—',
        })

    # Datos gráfico precio diario
    chart_fechas: list = []
    chart_precios_dia: list = []
    for r in raw_precio_dia:
        fecha = r.get('fecha')
        chart_fechas.append(fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha or ''))
        p = r.get('precio_kg')
        chart_precios_dia.append(round(float(p), 4) if p is not None else None)

    total_precio_kg = round(total_valor / total_peso, 2) if total_peso else None

    top_lead = 'Sin límite (todas las filas)' if top is None else f'Top {top}'
    ctx = _report_shell_context(f'Ventas {linea} · Resumen provincia/cliente')
    ctx.update({
        'd1': d1, 'd2': d2, 'linea': linea, 'top': top, 'top_lead': top_lead,
        'filas': filas,
        'total_lineas': f'{total_lineas:,}',
        'total_cantidad': f'{total_cantidad:,.2f}',
        'total_peso': f'{total_peso:,.2f}',
        'total_valor': f'{total_valor:,.2f}',
        'total_precio_kg': f'S/ {total_precio_kg:.2f}' if total_precio_kg is not None else '—',
        'pdf_filename': f'linea_resumen_{d1}_{d2}.pdf',
        'chart_data': {
            'labels': chart_labels,
            'pesos': chart_pesos,
            'valores': chart_valores,
            'fechas': chart_fechas,
            'precios_dia': chart_precios_dia,
        },
        'provincias_opts': provincias_opts,
        'corporativos_opts': corporativos_opts,
        'clientes_opts': clientes_opts,
        'f_provincias': f_provincias,
        'f_corporativos': f_corporativos,
        'f_clientes': f_clientes,
    })
    return render_template('pages/reporte_linea_resumen_provincia.html', **ctx)


@bp.route('/modules/reports/ventas-linea-diario-provincia')
@require_login
def ventas_linea_diario_provincia():
    from services.db import get_connection

    d1 = _parse_date_string(request.args.get('desde') or request.args.get('fecha_desde'))
    d2 = _parse_date_string(request.args.get('hasta') or request.args.get('fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta (YYYY-MM-DD).')

    linea = (request.args.get('linea') or '').strip()
    if not linea:
        return _bad('Parámetro requerido: linea (ej. "Pollo Vivo").')

    try:
        top = max(1, min(10_000, int(request.args.get('top') or 2000)))
    except (TypeError, ValueError):
        top = 2000

    cod_item = (request.args.get('cod_item') or '').strip()
    mercado  = (request.args.get('mercado')   or '').strip().upper()

    # Filtros multi-select
    f_provincias   = [v.strip() for v in request.args.getlist('provincia')   if v.strip()]
    f_corporativos = [v.strip() for v in request.args.getlist('corporativo') if v.strip()]
    f_clientes     = [v.strip() for v in request.args.getlist('cliente')     if v.strip()]

    # WHERE base (para opciones de dropdowns)
    base_where = (" WHERE FechaContable BETWEEN :d1 AND :d2"
                  " AND LOWER(TRIM(LineaComercial)) = LOWER(TRIM(:linea))"
                  " AND CodigoDocumento IN ('01','03')")
    base_bind: dict = {'d1': d1, 'd2': d2, 'linea': linea}
    if cod_item:
        base_where += " AND CodigoItem = :cod_item"
        base_bind['cod_item'] = cod_item
    if mercado:
        base_where += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo"
        base_bind['prefzo'] = mercado + '%'

    # WHERE extendido (agrega multi-selects)
    ext_where = base_where
    bind = dict(base_bind)
    if f_provincias:
        keys = [f'prov_{i}' for i in range(len(f_provincias))]
        ext_where += ' AND Provincia IN (' + ','.join(f':{k}' for k in keys) + ')'
        bind.update(zip(keys, f_provincias))
    if f_corporativos:
        keys = [f'corp_{i}' for i in range(len(f_corporativos))]
        ext_where += ' AND NombreCoorporativo IN (' + ','.join(f':{k}' for k in keys) + ')'
        bind.update(zip(keys, f_corporativos))
    if f_clientes:
        keys = [f'cli_{i}' for i in range(len(f_clientes))]
        ext_where += ' AND CodigoCliente IN (' + ','.join(f':{k}' for k in keys) + ')'
        bind.update(zip(keys, f_clientes))

    # Opciones para dropdowns
    sql_opts = ("SELECT DISTINCT"
                " COALESCE(NULLIF(TRIM(NombreCoorporativo),''),'') AS nombre_corporativo,"
                " COALESCE(NULLIF(TRIM(CodigoCoorporativo),''),'') AS cod_corporativo,"
                " COALESCE(NULLIF(TRIM(NombreCliente),''),'') AS nombre_cliente,"
                " CodigoCliente AS cod_cliente,"
                " COALESCE(NULLIF(TRIM(Provincia),''),'') AS provincia"
                f" FROM ventasgeneral2{base_where}"
                " ORDER BY nombre_corporativo, nombre_cliente")

    # Query detalle diario (tabla)
    sql = ("SELECT FechaContable AS fecha,"
           " COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') AS provincia,"
           " MAX(COALESCE(NULLIF(TRIM(NombreCoorporativo),''),'')) AS nombre_corporativo,"
           " CodigoCliente AS cod_cliente,"
           " MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,"
           " COUNT(*) AS lineas,"
           " COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
           " COALESCE(SUM(Peso),0) AS suma_peso,"
           " COALESCE(SUM(Valor),0) AS suma_valor,"
           " CASE WHEN COALESCE(SUM(Peso),0) > 0"
           "      THEN ROUND(COALESCE(SUM(Valor),0) / COALESCE(SUM(Peso),0), 2)"
           "      ELSE NULL END AS precio_kg"
           f" FROM ventasgeneral2{ext_where}"
           f" GROUP BY fecha, provincia, CodigoCliente ORDER BY fecha ASC, suma_peso DESC LIMIT {top}")

    # Query agregado por día (gráficos — respeta los mismos filtros)
    sql_dia = ("SELECT FechaContable AS fecha,"
               " COALESCE(SUM(Peso),0) AS suma_peso,"
               " COALESCE(SUM(Valor),0) AS suma_valor"
               f" FROM ventasgeneral2{ext_where}"
               " GROUP BY fecha ORDER BY fecha ASC")

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_opts), base_bind)
        raw_opts = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_dia), bind)
        raw_dia = cur.fetchall() or []

    # Opciones dropdowns
    provincias_opts: list[str] = []
    corporativos_opts: list[dict] = []
    clientes_opts: list[dict] = []
    seen_prov: set = set()
    seen_corp: set = set()
    seen_cli: set = set()
    for r in raw_opts:
        pv = str(r.get('provincia') or '')
        if pv and pv not in seen_prov:
            seen_prov.add(pv)
            provincias_opts.append(pv)
        corp = str(r.get('nombre_corporativo') or '')
        if corp and corp not in seen_corp:
            seen_corp.add(corp)
            corporativos_opts.append({'nombre': corp, 'cod': str(r.get('cod_corporativo') or '')})
        cli = str(r.get('cod_cliente') or '')
        if cli and cli not in seen_cli:
            seen_cli.add(cli)
            clientes_opts.append({
                'cod': cli,
                'nombre': str(r.get('nombre_cliente') or ''),
                'corporativo': str(r.get('nombre_corporativo') or ''),
            })

    # Filas tabla
    filas = []
    for i, r in enumerate(raw, 1):
        fecha = r.get('fecha')
        sp  = float(r.get('suma_peso')  or 0)
        sv  = float(r.get('suma_valor') or 0)
        pk  = r.get('precio_kg')
        filas.append({
            'rank': i,
            'fecha': fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha or ''),
            'provincia': str(r.get('provincia') or ''),
            'nombre_corporativo': str(r.get('nombre_corporativo') or ''),
            'cod_cliente': str(r.get('cod_cliente') or ''),
            'nombre_cliente': str(r.get('nombre_cliente') or ''),
            'lineas': f"{int(r.get('lineas') or 0):,}",
            'suma_cantidad': f"{float(r.get('suma_cantidad') or 0):,.2f}",
            'suma_peso':  f'{sp:,.2f}',
            'suma_valor': f'{sv:,.2f}',
            'precio_kg': f'S/ {float(pk):.2f}' if pk is not None else '—',
        })

    # Datos gráficos (aggregado por día, con filtros aplicados)
    chart_fechas: list = []
    chart_pesos_dia: list = []
    chart_valores_dia: list = []
    for r in raw_dia:
        fecha = r.get('fecha')
        chart_fechas.append(fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha or ''))
        chart_pesos_dia.append(round(float(r.get('suma_peso')  or 0), 2))
        chart_valores_dia.append(round(float(r.get('suma_valor') or 0), 2))

    total_peso  = sum(chart_pesos_dia)
    total_valor = sum(chart_valores_dia)

    ctx = _report_shell_context(f'Ventas {linea} · Diario por provincia/cliente')
    ctx.update({
        'd1': d1, 'd2': d2, 'linea': linea, 'top': top,
        'filas': filas,
        'total_peso':  f'{total_peso:,.2f}',
        'total_valor': f'{total_valor:,.2f}',
        'pdf_filename': f'linea_diario_{d1}_{d2}.pdf',
        'chart_data': {'fechas': chart_fechas, 'pesos': chart_pesos_dia, 'valores': chart_valores_dia},
        'provincias_opts': provincias_opts,
        'corporativos_opts': corporativos_opts,
        'clientes_opts': clientes_opts,
        'f_provincias': f_provincias,
        'f_corporativos': f_corporativos,
        'f_clientes': f_clientes,
    })
    return render_template('pages/reporte_linea_diario_provincia.html', **ctx)


@bp.route('/modules/reports/ventas-linea-precio-diario')
@require_login
def ventas_linea_precio_diario():
    from services.db import get_connection

    d1 = _parse_date_string(request.args.get('desde') or request.args.get('fecha_desde'))
    d2 = _parse_date_string(request.args.get('hasta') or request.args.get('fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta (YYYY-MM-DD).')

    linea = (request.args.get('linea') or '').strip()
    if not linea:
        return _bad('Parámetro requerido: linea (ej. "Pollo Vivo").')

    try:
        top = max(1, min(10_000, int(request.args.get('top') or 2000)))
    except (TypeError, ValueError):
        top = 2000

    cod_item = (request.args.get('cod_item') or '').strip()
    mercado  = (request.args.get('mercado')   or '').strip().upper()

    # Filtros multi-select
    f_provincias   = [v.strip() for v in request.args.getlist('provincia')   if v.strip()]
    f_corporativos = [v.strip() for v in request.args.getlist('corporativo') if v.strip()]
    f_clientes     = [v.strip() for v in request.args.getlist('cliente')     if v.strip()]

    # WHERE base (para opciones de dropdowns)
    base_where = (" WHERE FechaContable BETWEEN :d1 AND :d2"
                  " AND LOWER(TRIM(LineaComercial)) = LOWER(TRIM(:linea))"
                  " AND CodigoDocumento IN ('01','03')")
    base_bind: dict = {'d1': d1, 'd2': d2, 'linea': linea}
    if cod_item:
        base_where += " AND CodigoItem = :cod_item"
        base_bind['cod_item'] = cod_item
    if mercado:
        base_where += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo"
        base_bind['prefzo'] = mercado + '%'

    # WHERE extendido (agrega multi-selects)
    ext_where = base_where
    bind = dict(base_bind)
    if f_provincias:
        keys = [f'prov_{i}' for i in range(len(f_provincias))]
        ext_where += ' AND Provincia IN (' + ','.join(f':{k}' for k in keys) + ')'
        bind.update(zip(keys, f_provincias))
    if f_corporativos:
        keys = [f'corp_{i}' for i in range(len(f_corporativos))]
        ext_where += ' AND NombreCoorporativo IN (' + ','.join(f':{k}' for k in keys) + ')'
        bind.update(zip(keys, f_corporativos))
    if f_clientes:
        keys = [f'cli_{i}' for i in range(len(f_clientes))]
        ext_where += ' AND CodigoCliente IN (' + ','.join(f':{k}' for k in keys) + ')'
        bind.update(zip(keys, f_clientes))

    # Opciones para dropdowns
    sql_opts = ("SELECT DISTINCT"
                " COALESCE(NULLIF(TRIM(NombreCoorporativo),''),'') AS nombre_corporativo,"
                " COALESCE(NULLIF(TRIM(CodigoCoorporativo),''),'') AS cod_corporativo,"
                " COALESCE(NULLIF(TRIM(NombreCliente),''),'') AS nombre_cliente,"
                " CodigoCliente AS cod_cliente,"
                " COALESCE(NULLIF(TRIM(Provincia),''),'') AS provincia"
                f" FROM ventasgeneral2{base_where}"
                " ORDER BY nombre_corporativo, nombre_cliente")

    sql = ("SELECT FechaContable AS fecha,"
           " COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') AS provincia,"
           " MAX(COALESCE(NULLIF(TRIM(NombreCoorporativo),''),'')) AS nombre_corporativo,"
           " CodigoCliente AS cod_cliente,"
           " MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,"
           " COUNT(*) AS lineas,"
           " COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
           " COALESCE(SUM(Peso),0) AS suma_peso,"
           " COALESCE(SUM(Valor),0) AS suma_valor,"
           " CASE WHEN COALESCE(SUM(Peso),0) > 0"
           "      THEN ROUND(COALESCE(SUM(Valor),0) / COALESCE(SUM(Peso),0), 4)"
           "      ELSE NULL END AS precio_kg"
           f" FROM ventasgeneral2{ext_where}"
           f" GROUP BY fecha, provincia, CodigoCliente ORDER BY suma_peso DESC, fecha ASC LIMIT {top}")

    sql_precio_dia = ("SELECT FechaContable AS fecha,"
                      " COALESCE(SUM(Peso),0) AS suma_peso,"
                      " CASE WHEN COALESCE(SUM(Peso),0) > 0"
                      "      THEN ROUND(COALESCE(SUM(Valor),0) / COALESCE(SUM(Peso),0), 4)"
                      "      ELSE NULL END AS precio_kg"
                      f" FROM ventasgeneral2{ext_where}"
                      " GROUP BY fecha ORDER BY fecha ASC")

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_opts), base_bind)
        raw_opts = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_precio_dia), bind)
        raw_precio = cur.fetchall() or []

    # Opciones dropdowns
    provincias_opts: list[str] = []
    corporativos_opts: list[dict] = []
    clientes_opts: list[dict] = []
    seen_prov: set = set()
    seen_corp: set = set()
    seen_cli: set = set()
    for r in raw_opts:
        pv = str(r.get('provincia') or '')
        if pv and pv not in seen_prov:
            seen_prov.add(pv)
            provincias_opts.append(pv)
        corp = str(r.get('nombre_corporativo') or '')
        if corp and corp not in seen_corp:
            seen_corp.add(corp)
            corporativos_opts.append({'nombre': corp, 'cod': str(r.get('cod_corporativo') or '')})
        cli = str(r.get('cod_cliente') or '')
        if cli and cli not in seen_cli:
            seen_cli.add(cli)
            clientes_opts.append({
                'cod': cli,
                'nombre': str(r.get('nombre_cliente') or ''),
                'corporativo': str(r.get('nombre_corporativo') or ''),
            })

    filas = []
    for i, r in enumerate(raw, 1):
        fecha = r.get('fecha')
        fecha_str = fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha or '')
        precio = r.get('precio_kg')
        filas.append({
            'rank': i,
            'fecha': fecha_str,
            'provincia': str(r.get('provincia') or ''),
            'nombre_corporativo': str(r.get('nombre_corporativo') or ''),
            'cod_cliente': str(r.get('cod_cliente') or ''),
            'nombre_cliente': str(r.get('nombre_cliente') or ''),
            'lineas': f"{int(r.get('lineas') or 0):,}",
            'suma_cantidad': f"{float(r.get('suma_cantidad') or 0):,.2f}",
            'suma_peso': f"{float(r.get('suma_peso') or 0):,.2f}",
            'suma_valor': f"{float(r.get('suma_valor') or 0):,.2f}",
            'precio_kg': f"{float(precio):,.4f}" if precio is not None else '—',
        })

    chart_fechas = []
    chart_precios = []
    for r in raw_precio:
        fecha = r.get('fecha')
        chart_fechas.append(fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha or ''))
        p = r.get('precio_kg')
        chart_precios.append(round(float(p), 4) if p is not None else None)

    ctx = _report_shell_context(f'Ventas {linea} · Precio por día provincia/cliente')
    ctx.update({
        'd1': d1, 'd2': d2, 'linea': linea, 'top': top,
        'filas': filas,
        'pdf_filename': f'linea_precio_diario_{d1}_{d2}.pdf',
        'chart_data': {'fechas': chart_fechas, 'precios': chart_precios},
        'provincias_opts': provincias_opts,
        'corporativos_opts': corporativos_opts,
        'clientes_opts': clientes_opts,
        'f_provincias': f_provincias,
        'f_corporativos': f_corporativos,
        'f_clientes': f_clientes,
        'body_class': 'app-page-reporte-wide',
    })
    return render_template('pages/reporte_linea_precio_diario.html', **ctx)


@bp.route('/modules/reports/ventas-linea-mix-productos')
@require_login
def ventas_linea_mix_productos():
    from services.db import get_connection

    d1 = _parse_date_string(request.args.get('desde') or request.args.get('fecha_desde'))
    d2 = _parse_date_string(request.args.get('hasta') or request.args.get('fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta (YYYY-MM-DD).')

    linea = (request.args.get('linea') or '').strip()
    if not linea:
        return _bad('Parámetro requerido: linea (ej. "Pollo Vivo").')

    mercado = (request.args.get('mercado') or '').strip().upper()

    sql = ("SELECT CodigoItem AS cod_item,"
           " MAX(COALESCE(NULLIF(TRIM(GlosaDetalle),''),'(sin glosa)')) AS glosa,"
           " COUNT(*) AS lineas,"
           " COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
           " COALESCE(SUM(Peso),0) AS suma_peso,"
           " COALESCE(SUM(Valor),0) AS suma_valor,"
           " CASE WHEN COALESCE(SUM(Peso),0) > 0"
           "      THEN ROUND(COALESCE(SUM(Valor),0) / COALESCE(SUM(Peso),0), 4)"
           "      ELSE NULL END AS precio_kg"
           " FROM ventasgeneral2"
           " WHERE FechaContable BETWEEN :d1 AND :d2"
           " AND LOWER(TRIM(LineaComercial)) = LOWER(TRIM(:linea))")
    bind = {'d1': d1, 'd2': d2, 'linea': linea}
    if mercado:
        sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo"
        bind['prefzo'] = mercado + '%'
    sql += " GROUP BY CodigoItem ORDER BY suma_peso DESC"

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []

    total_peso = sum(float(r.get('suma_peso') or 0) for r in raw)
    total_valor = sum(float(r.get('suma_valor') or 0) for r in raw)

    filas = []
    chart_labels: list = []
    chart_pesos: list = []
    chart_valores: list = []
    for i, r in enumerate(raw, 1):
        sp = float(r.get('suma_peso') or 0)
        sv = float(r.get('suma_valor') or 0)
        pk = r.get('precio_kg')
        glosa = str(r.get('glosa') or '')
        pct = round(sp / total_peso * 100, 2) if total_peso else 0.0
        chart_labels.append(glosa[:30] or str(r.get('cod_item') or ''))
        chart_pesos.append(round(sp, 2))
        chart_valores.append(round(sv, 2))
        filas.append({
            'rank': i,
            'cod_item': str(r.get('cod_item') or ''),
            'glosa': glosa,
            'lineas': f"{int(r.get('lineas') or 0):,}",
            'suma_cantidad': f"{float(r.get('suma_cantidad') or 0):,.2f}",
            'suma_peso': f'{sp:,.2f}',
            'suma_valor': f'{sv:,.2f}',
            'precio_kg': f'{float(pk):,.4f}' if pk is not None else '—',
            'pct_peso': f'{pct:.2f}',
        })

    ctx = _report_shell_context(f'Ventas {linea} · Mix de productos')
    ctx.update({
        'd1': d1, 'd2': d2, 'linea': linea,
        'mercado': mercado or None,
        'filas': filas,
        'total_peso': f'{total_peso:,.2f}',
        'total_valor': f'{total_valor:,.2f}',
        'pdf_filename': f'linea_mix_productos_{d1}_{d2}.pdf',
        'chart_data': {'labels': chart_labels, 'pesos': chart_pesos, 'valores': chart_valores},
    })
    return render_template('pages/reporte_linea_mix_productos.html', **ctx)


@bp.route('/modules/reports/<slug>')
@require_login
def report_placeholder(slug: str):
    if slug not in REPORT_PLACEHOLDER_SLUGS:
        abort(404)
    ctx = _report_shell_context('Informe')
    ctx['report_slug'] = slug
    ctx['report_query'] = (request.query_string or b'').decode('utf-8', errors='replace')
    return render_template('pages/reporte_placeholder.html', **ctx)
