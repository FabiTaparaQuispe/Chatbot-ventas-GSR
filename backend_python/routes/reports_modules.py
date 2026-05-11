"""
Informes bajo /modules/… (el chat enlaza rutas canónicas; legacy *.php en paralelo).
Deben registrarse antes del catch-all serve_modules_static en app.py.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from flask import Blueprint, Response, abort, jsonify, render_template, request

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


def _tipo_fecha_param() -> str:
    """`contable` (FechaContable) o `proceso` (columna fechaProceso, con respaldo a contable)."""
    t = (request.args.get('tipo_fecha') or '').strip().lower()
    return 'proceso' if t == 'proceso' else 'contable'


def _sql_fecha_dimension(tipo_fecha: str) -> str:
    if tipo_fecha == 'proceso':
        return 'COALESCE(fechaProceso, FechaContable)'
    return 'FechaContable'


def _fecha_eje_leyenda(tipo_fecha: str) -> str:
    if tipo_fecha == 'proceso':
        return 'Día de proceso (fechaProceso)'
    return 'Fecha contable'


def _fecha_columna_th(tipo_fecha: str) -> str:
    """Encabezado de columna única de fecha en tablas (el eje activo del período)."""
    return 'Día de proceso' if tipo_fecha == 'proceso' else 'Fecha contable'


def _fmt_min_max_date(mn: Any, mx: Any) -> str:
    """Rango min–max de fechas en filas agregadas (resumen por cliente)."""
    def _s(d: Any) -> str:
        if d is None:
            return ''
        if hasattr(d, 'strftime'):
            return d.strftime('%Y-%m-%d')
        return str(d).strip()[:10]

    a, b = _s(mn), _s(mx)
    if not a and not b:
        return '—'
    if a == b:
        return a or b or '—'
    if not a:
        return b
    if not b:
        return a
    return f'{a} — {b}'


def _colon_params_to_pymysql(sql: str) -> str:
    return re.sub(r':([a-zA-Z_][a-zA-Z0-9_]*)', r'%(\1)s', sql)


def _linea_where_cascada(
    base_where: str,
    base_bind: dict[str, Any],
    f_provincias: list[str],
    f_corporativos: list[str],
    f_clientes: list[str],
    *,
    omit_provincia: bool,
    omit_corporativo: bool,
    omit_cliente: bool,
) -> tuple[str, dict[str, Any]]:
    """Extiende WHERE base con filtros multi-select omitiendo la propia dimensión (para opciones cascada)."""
    w = base_where
    b: dict[str, Any] = dict(base_bind)
    if not omit_provincia and f_provincias:
        keys = [f'_pvc_{i}' for i in range(len(f_provincias))]
        w += ' AND Provincia IN (' + ','.join(f':{k}' for k in keys) + ')'
        b.update(zip(keys, f_provincias))
    if not omit_corporativo and f_corporativos:
        keys = [f'_corp_{i}' for i in range(len(f_corporativos))]
        w += ' AND NombreCoorporativo IN (' + ','.join(f':{k}' for k in keys) + ')'
        b.update(zip(keys, f_corporativos))
    if not omit_cliente and f_clientes:
        keys = [f'_cli_{i}' for i in range(len(f_clientes))]
        w += ' AND CodigoCliente IN (' + ','.join(f':{k}' for k in keys) + ')'
        b.update(zip(keys, f_clientes))
    return w, b


def _linea_dropdowns_opciones_validas(
    conn,
    base_where: str,
    base_bind: dict[str, Any],
    f_provincias: list[str],
    f_corporativos: list[str],
    f_clientes: list[str],
) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Cascada: cada lista solo muestra valores que coexisten en ventasgeneral2 con los otros filtros
    (fecha, línea, mercado/cod_item, y las selecciones en las dimensiones aplicables).
    """
    # Provincias: respeta corporativo + cliente (no provincial)
    wp, bp = _linea_where_cascada(
        base_where, base_bind, f_provincias, f_corporativos, f_clientes,
        omit_provincia=True, omit_corporativo=False, omit_cliente=False,
    )
    sql_prov = (
        'SELECT DISTINCT COALESCE(NULLIF(TRIM(Provincia),\'\'),\'\') AS provincia'
        f' FROM ventasgeneral2{wp}'
        " AND COALESCE(NULLIF(TRIM(Provincia),''),'') <> '' ORDER BY provincia"
    )

    wc, bc = _linea_where_cascada(
        base_where, base_bind, f_provincias, f_corporativos, f_clientes,
        omit_provincia=False, omit_corporativo=True, omit_cliente=False,
    )
    sql_corp = (
        'SELECT DISTINCT'
        ' COALESCE(NULLIF(TRIM(NombreCoorporativo),\'\'),\'\') AS nombre_corporativo,'
        ' COALESCE(NULLIF(TRIM(CodigoCoorporativo),\'\'),\'\') AS cod_corporativo'
        f' FROM ventasgeneral2{wc}'
        " AND COALESCE(NULLIF(TRIM(NombreCoorporativo),''),'') <> ''"
        ' ORDER BY nombre_corporativo'
    )

    wk, bk = _linea_where_cascada(
        base_where, base_bind, f_provincias, f_corporativos, f_clientes,
        omit_provincia=False, omit_corporativo=False, omit_cliente=True,
    )
    sql_cli = (
        'SELECT DISTINCT'
        ' COALESCE(NULLIF(TRIM(NombreCliente),\'\'),\'\') AS nombre_cliente,'
        ' CodigoCliente AS cod_cliente,'
        ' COALESCE(NULLIF(TRIM(NombreCoorporativo),\'\'),\'\') AS nombre_corporativo'
        f' FROM ventasgeneral2{wk}'
        " AND COALESCE(NULLIF(TRIM(CodigoCliente),''),'') <> '' ORDER BY nombre_corporativo, nombre_cliente"
    )

    provincias_opts: list[str] = []
    corporativos_opts: list[dict[str, Any]] = []
    clientes_opts: list[dict[str, Any]] = []

    exec_sql = _colon_params_to_pymysql(sql_prov)
    with conn.cursor() as cur:
        cur.execute(exec_sql, bp)
        for r in cur.fetchall() or []:
            d = dict(r) if not isinstance(r, dict) else r
            pv = str(d.get('provincia') or '').strip()
            if pv:
                provincias_opts.append(pv)

    exec_sql = _colon_params_to_pymysql(sql_corp)
    seen_corp: set[str] = set()
    with conn.cursor() as cur:
        cur.execute(exec_sql, bc)
        for r in cur.fetchall() or []:
            d = dict(r) if not isinstance(r, dict) else r
            corp = str(d.get('nombre_corporativo') or '').strip()
            if corp and corp not in seen_corp:
                seen_corp.add(corp)
                corporativos_opts.append({
                    'nombre': corp,
                    'cod': str(d.get('cod_corporativo') or ''),
                })

    seen_cli: set[str] = set()
    exec_sql = _colon_params_to_pymysql(sql_cli)
    with conn.cursor() as cur:
        cur.execute(exec_sql, bk)
        for r in cur.fetchall() or []:
            d = dict(r) if not isinstance(r, dict) else r
            cli = str(d.get('cod_cliente') or '').strip()
            if cli and cli not in seen_cli:
                seen_cli.add(cli)
                clientes_opts.append({
                    'cod': cli,
                    'nombre': str(d.get('nombre_cliente') or ''),
                    'corporativo': str(d.get('nombre_corporativo') or ''),
                })

    return provincias_opts, corporativos_opts, clientes_opts


def _sanear_filtros_linea(
    provincias_opts: list[str],
    corporativos_opts: list[dict[str, Any]],
    clientes_opts: list[dict[str, Any]],
    f_provincias: list[str],
    f_corporativos: list[str],
    f_clientes: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """Quita valores imposibles (no coexisten según cascada actual)."""
    p_ok = set(provincias_opts)
    c_ok = {str(d.get('nombre') or '').strip() for d in corporativos_opts if (d.get('nombre') or '').strip()}
    k_ok = {str(d.get('cod') or '').strip() for d in clientes_opts if (d.get('cod') or '').strip()}
    return (
        [x for x in f_provincias if x.strip() and x.strip() in p_ok],
        [x for x in f_corporativos if x.strip() and x.strip() in c_ok],
        [x for x in f_clientes if x.strip() and x.strip() in k_ok],
    )


_ARBOL_CACHE: dict[tuple, tuple[float, list[dict[str, str]]]] = {}
_ARBOL_CACHE_TTL_S = 120.0
_ARBOL_CACHE_MAX = 32


def _linea_arbol_distinct(
    conn,
    base_where: str,
    base_bind: dict[str, Any],
) -> list[dict[str, str]]:
    """
    Trae UNA sola vez las tripletas (provincia, corporativo, cliente) válidas según el WHERE base.
    Reemplaza a 3 consultas DISTINCT independientes y evita los full-scans repetidos.
    Devuelve filas con: provincia, nombre_corporativo, cod_corporativo, cod_cliente, nombre_cliente.
    Cachea el resultado por (base_where, parámetros) durante _ARBOL_CACHE_TTL_S segundos.
    """
    import time as _t
    cache_key = (base_where, tuple(sorted((k, str(v)) for k, v in base_bind.items())))
    now = _t.time()
    cached = _ARBOL_CACHE.get(cache_key)
    if cached and (now - cached[0]) < _ARBOL_CACHE_TTL_S:
        return cached[1]

    sql = (
        'SELECT DISTINCT'
        " COALESCE(NULLIF(TRIM(Provincia),''),'') AS provincia,"
        " COALESCE(NULLIF(TRIM(NombreCoorporativo),''),'') AS nombre_corporativo,"
        " COALESCE(NULLIF(TRIM(CodigoCoorporativo),''),'') AS cod_corporativo,"
        ' CodigoCliente AS cod_cliente,'
        " COALESCE(NULLIF(TRIM(NombreCliente),''),'') AS nombre_cliente"
        f' FROM ventasgeneral2{base_where}'
        " AND COALESCE(NULLIF(TRIM(Provincia),''),'') <> ''"
        " AND COALESCE(NULLIF(TRIM(CodigoCliente),''),'') <> ''"
    )
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), base_bind)
        rows = cur.fetchall() or []
    out: list[dict[str, str]] = []
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else r
        out.append({
            'provincia':          str(d.get('provincia')          or '').strip(),
            'nombre_corporativo': str(d.get('nombre_corporativo') or '').strip(),
            'cod_corporativo':    str(d.get('cod_corporativo')    or '').strip(),
            'cod_cliente':        str(d.get('cod_cliente')        or '').strip(),
            'nombre_cliente':     str(d.get('nombre_cliente')     or '').strip(),
        })

    if len(_ARBOL_CACHE) >= _ARBOL_CACHE_MAX:
        oldest = min(_ARBOL_CACHE.items(), key=lambda kv: kv[1][0])[0]
        _ARBOL_CACHE.pop(oldest, None)
    _ARBOL_CACHE[cache_key] = (now, out)
    return out


def _opciones_desde_arbol(
    arbol: list[dict[str, str]],
    f_provincias: list[str],
    f_corporativos: list[str],
    f_clientes: list[str],
) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Replica la lógica de _linea_dropdowns_opciones_validas SIN tocar la base.
    Cada lista de opciones omite su propia dimensión al cruzar con los filtros activos.
    """
    sP = set(f_provincias)
    sC = set(f_corporativos)
    sK = set(f_clientes)

    prov_set: set[str] = set()
    corp_map: dict[str, str] = {}  # nombre -> cod (se usa el primero visto)
    cli_map: dict[str, dict[str, str]] = {}

    for r in arbol:
        pv   = r['provincia']
        corp = r['nombre_corporativo']
        ccod = r['cod_corporativo']
        ki   = r['cod_cliente']
        knom = r['nombre_cliente']
        if not pv or not ki:
            continue

        # provincias_opts: filtra por corporativo+cliente, NO por provincia
        if (not sC or corp in sC) and (not sK or ki in sK):
            prov_set.add(pv)

        # corporativos_opts: filtra por provincia+cliente, NO por corporativo
        if corp and (not sP or pv in sP) and (not sK or ki in sK):
            corp_map.setdefault(corp, ccod)

        # clientes_opts: filtra por provincia+corporativo, NO por cliente
        if (not sP or pv in sP) and (not sC or corp in sC):
            if ki not in cli_map:
                cli_map[ki] = {
                    'cod': ki,
                    'nombre': knom or '(sin nombre)',
                    'corporativo': corp,
                }

    provincias_opts = sorted(prov_set)
    corporativos_opts = sorted(
        ({'nombre': k, 'cod': v} for k, v in corp_map.items()),
        key=lambda d: d['nombre'].lower(),
    )
    clientes_opts = sorted(
        cli_map.values(),
        key=lambda d: ((d.get('corporativo') or '').lower(), (d.get('nombre') or '').lower()),
    )
    return provincias_opts, corporativos_opts, clientes_opts


def _construir_opts_tree(arbol: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    """Construye el árbol Provincia → Corporativos → Clientes a partir del DISTINCT en memoria."""
    tree: dict[str, dict[str, Any]] = {}
    for r in arbol:
        pv      = r['provincia']
        corp    = r['nombre_corporativo']
        cli_cod = r['cod_cliente']
        cli_nom = r['nombre_cliente']
        if not pv:
            continue
        node = tree.setdefault(pv, {'corps': [], 'clients': {}})
        if corp and corp not in node['corps']:
            node['corps'].append(corp)
        if cli_cod and corp:
            bucket = node['clients'].setdefault(corp, [])
            if not any(c['cod'] == cli_cod for c in bucket):
                bucket.append({'cod': cli_cod, 'nombre': cli_nom or '(sin nombre)'})
    for pv, node in tree.items():
        node['corps'].sort(key=lambda s: s.lower())
        for corp, items in node['clients'].items():
            items.sort(key=lambda d: (d.get('nombre') or '').lower())
    return tree


def _cascada_y_arbol(
    conn,
    base_where: str,
    base_bind: dict[str, Any],
    f_provincias: list[str],
    f_corporativos: list[str],
    f_clientes: list[str],
) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]],
           list[str], list[str], list[str], dict[str, dict[str, Any]]]:
    """
    Una sola consulta a DB (DISTINCT del árbol) y todas las opciones + saneo en memoria.
    Reemplaza a `for _ in range(2): _linea_dropdowns_opciones_validas + _sanear_filtros_linea`
    seguido de una llamada final y la query `tree_sql`. Pasa de ~10 consultas a 1.
    """
    arbol = _linea_arbol_distinct(conn, base_where, base_bind)
    fP, fC, fK = list(f_provincias), list(f_corporativos), list(f_clientes)

    # Iterar hasta converger (en memoria); típicamente 1-2 vueltas, sin tocar DB.
    for _ in range(4):
        prov_opts, corp_opts, cli_opts = _opciones_desde_arbol(arbol, fP, fC, fK)
        nP, nC, nK = _sanear_filtros_linea(prov_opts, corp_opts, cli_opts, fP, fC, fK)
        if (nP, nC, nK) == (fP, fC, fK):
            break
        fP, fC, fK = nP, nC, nK
    prov_opts, corp_opts, cli_opts = _opciones_desde_arbol(arbol, fP, fC, fK)
    opts_tree = _construir_opts_tree(arbol)
    return prov_opts, corp_opts, cli_opts, fP, fC, fK, opts_tree


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

    tipo_fecha = _tipo_fecha_param()
    fe = _sql_fecha_dimension(tipo_fecha)
    fecha_eje_leyenda = _fecha_eje_leyenda(tipo_fecha)
    fecha_columna_th = _fecha_columna_th(tipo_fecha)

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
    base_where = (f" WHERE {fe} BETWEEN :d1 AND :d2"
                  " AND LOWER(TRIM(LineaComercial)) = LOWER(TRIM(:linea))"
                  " AND CodigoDocumento IN ('01','03')")
    base_bind: dict = {'d1': d1, 'd2': d2, 'linea': linea}
    if cod_item:
        base_where += " AND CodigoItem = :cod_item"
        base_bind['cod_item'] = cod_item
    if mercado:
        base_where += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo"
        base_bind['prefzo'] = mercado + '%'

    conn = get_connection()
    (provincias_opts, corporativos_opts, clientes_opts,
     f_provincias, f_corporativos, f_clientes, opts_tree) = _cascada_y_arbol(
        conn, base_where, base_bind, f_provincias, f_corporativos, f_clientes)

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
    sql_precio_dia = (f"SELECT {fe} AS fecha,"
                      " COALESCE(SUM(Peso),0) AS suma_peso,"
                      " CASE WHEN COALESCE(SUM(Peso),0) > 0"
                      "      THEN ROUND(COALESCE(SUM(Valor),0) / COALESCE(SUM(Peso),0), 4)"
                      "      ELSE NULL END AS precio_kg"
                      f" FROM ventasgeneral2{ext_where}"
                      " GROUP BY fecha ORDER BY fecha ASC")

    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_precio_dia), bind)
        raw_precio_dia = cur.fetchall() or []

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
        'tipo_fecha': tipo_fecha,
        'fecha_eje_leyenda': fecha_eje_leyenda,
        'fecha_columna_th': fecha_columna_th,
        'fechas_dim_label': 'fecha contable' if tipo_fecha == 'contable' else 'día de proceso',
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
        'opts_tree': opts_tree,
        'body_class': 'app-page-reporte-wide',
    })

    if (request.args.get('fmt') or '').strip().lower() == 'json':
        return jsonify({
            'chart_data': {
                'labels': chart_labels,
                'pesos': chart_pesos,
                'valores': chart_valores,
                'fechas': chart_fechas,
                'precios_dia': chart_precios_dia,
            }
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

    tipo_fecha = _tipo_fecha_param()
    fe = _sql_fecha_dimension(tipo_fecha)
    fecha_eje_leyenda = _fecha_eje_leyenda(tipo_fecha)
    fecha_columna_th = _fecha_columna_th(tipo_fecha)

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
    base_where = (f" WHERE {fe} BETWEEN :d1 AND :d2"
                  " AND LOWER(TRIM(LineaComercial)) = LOWER(TRIM(:linea))"
                  " AND CodigoDocumento IN ('01','03')")
    base_bind: dict = {'d1': d1, 'd2': d2, 'linea': linea}
    if cod_item:
        base_where += " AND CodigoItem = :cod_item"
        base_bind['cod_item'] = cod_item
    if mercado:
        base_where += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo"
        base_bind['prefzo'] = mercado + '%'

    conn = get_connection()
    (provincias_opts, corporativos_opts, clientes_opts,
     f_provincias, f_corporativos, f_clientes, opts_tree) = _cascada_y_arbol(
        conn, base_where, base_bind, f_provincias, f_corporativos, f_clientes)

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

    # Query detalle diario (tabla)
    sql = (f"SELECT {fe} AS fecha,"
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
    sql_dia = (f"SELECT {fe} AS fecha,"
               " COALESCE(SUM(Peso),0) AS suma_peso,"
               " COALESCE(SUM(Valor),0) AS suma_valor"
               f" FROM ventasgeneral2{ext_where}"
               " GROUP BY fecha ORDER BY fecha ASC")

    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_dia), bind)
        raw_dia = cur.fetchall() or []

    # Gráficos comparativos por cliente (2+ seleccionados en el filtro)
    chart_modo = 'total'
    series_clientes: list[dict[str, Any]] = []
    if len(f_clientes) >= 2:
        sql_dia_cli = (
            f"SELECT {fe} AS fecha, CodigoCliente AS cod_cliente,"
            " MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,"
            " COALESCE(SUM(Peso),0) AS suma_peso,"
            " COALESCE(SUM(Valor),0) AS suma_valor"
            f" FROM ventasgeneral2{ext_where}"
            " GROUP BY fecha, CodigoCliente ORDER BY fecha ASC, cod_cliente"
        )
        with conn.cursor() as cur:
            cur.execute(_colon_params_to_pymysql(sql_dia_cli), bind)
            raw_cli = cur.fetchall() or []
        cod_to_name: dict[str, str] = {}
        per_p: dict[str, dict[str, float]] = {}
        per_v: dict[str, dict[str, float]] = {}
        for r in raw_cli:
            cod = str(r.get('cod_cliente') or '').strip()
            if not cod:
                continue
            fecha = r.get('fecha')
            fd = fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha or '')
            if not fd:
                continue
            per_p.setdefault(cod, {})[fd] = float(r.get('suma_peso') or 0)
            per_v.setdefault(cod, {})[fd] = float(r.get('suma_valor') or 0)
            cod_to_name[cod] = str(r.get('nombre_cliente') or '').strip() or cod
        chart_fechas_pre: list[str] = []
        for r in raw_dia:
            fecha = r.get('fecha')
            chart_fechas_pre.append(
                fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha or '')
            )
        for cod in f_clientes:
            c = str(cod).strip()
            if not c:
                continue
            nm = cod_to_name.get(c, c)
            label = (f'{c} — {nm}')[:80]
            series_clientes.append({
                'cod': c,
                'label': label,
                'pesos': [round(per_p.get(c, {}).get(f, 0.0), 2) for f in chart_fechas_pre],
                'valores': [round(per_v.get(c, {}).get(f, 0.0), 2) for f in chart_fechas_pre],
            })
        if len(series_clientes) >= 2:
            chart_modo = 'clientes'

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
        'tipo_fecha': tipo_fecha,
        'fecha_eje_leyenda': fecha_eje_leyenda,
        'fecha_columna_th': fecha_columna_th,
        'filas': filas,
        'total_peso':  f'{total_peso:,.2f}',
        'total_valor': f'{total_valor:,.2f}',
        'pdf_filename': f'linea_diario_{d1}_{d2}.pdf',
        'chart_data': {
            'fechas': chart_fechas,
            'pesos': chart_pesos_dia,
            'valores': chart_valores_dia,
            'modo': chart_modo,
            'series_clientes': series_clientes,
        },
        'provincias_opts': provincias_opts,
        'corporativos_opts': corporativos_opts,
        'clientes_opts': clientes_opts,
        'f_provincias': f_provincias,
        'f_corporativos': f_corporativos,
        'f_clientes': f_clientes,
        'opts_tree': opts_tree,
        'body_class': 'app-page-reporte-wide',
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

    tipo_fecha = _tipo_fecha_param()
    fe = _sql_fecha_dimension(tipo_fecha)
    fecha_eje_leyenda = _fecha_eje_leyenda(tipo_fecha)
    fecha_columna_th = _fecha_columna_th(tipo_fecha)

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
    base_where = (f" WHERE {fe} BETWEEN :d1 AND :d2"
                  " AND LOWER(TRIM(LineaComercial)) = LOWER(TRIM(:linea))"
                  " AND CodigoDocumento IN ('01','03')")
    base_bind: dict = {'d1': d1, 'd2': d2, 'linea': linea}
    if cod_item:
        base_where += " AND CodigoItem = :cod_item"
        base_bind['cod_item'] = cod_item
    if mercado:
        base_where += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo"
        base_bind['prefzo'] = mercado + '%'

    conn = get_connection()
    (provincias_opts, corporativos_opts, clientes_opts,
     f_provincias, f_corporativos, f_clientes, opts_tree) = _cascada_y_arbol(
        conn, base_where, base_bind, f_provincias, f_corporativos, f_clientes)

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

    sql = (f"SELECT {fe} AS fecha,"
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
           f" GROUP BY fecha, provincia, CodigoCliente ORDER BY fecha ASC, suma_peso DESC LIMIT {top}")

    sql_precio_dia = (f"SELECT {fe} AS fecha,"
                      " COALESCE(SUM(Peso),0) AS suma_peso,"
                      " COALESCE(SUM(Valor),0) AS suma_valor,"
                      " CASE WHEN COALESCE(SUM(Peso),0) > 0"
                      "      THEN ROUND(COALESCE(SUM(Valor),0) / COALESCE(SUM(Peso),0), 4)"
                      "      ELSE NULL END AS precio_kg"
                      f" FROM ventasgeneral2{ext_where}"
                      " GROUP BY fecha ORDER BY fecha ASC")

    # WHERE para gráfico por tipo-doc: incluye 07 además de 01 y 03
    tdoc_where = ext_where.replace(
        "AND CodigoDocumento IN ('01','03')",
        "AND CodigoDocumento IN ('01','03','07')"
    )
    sql_precio_tdoc = (
        f"SELECT {fe} AS fecha, CodigoDocumento AS tipo_doc,"
        " CASE WHEN COALESCE(SUM(Peso),0) <> 0"
        "      THEN ROUND(ABS(COALESCE(SUM(Valor),0) / COALESCE(SUM(Peso),0)), 4)"
        "      ELSE NULL END AS precio_kg"
        f" FROM ventasgeneral2{tdoc_where}"
        f" GROUP BY {fe}, CodigoDocumento ORDER BY {fe} ASC, CodigoDocumento ASC"
    )

    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_precio_dia), bind)
        raw_precio = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_precio_tdoc), bind)
        raw_precio_tdoc = cur.fetchall() or []

    # Eje X común (fechas del período) — debe calcularse antes del bloque multi-cliente,
    # que mapea precios diarios por cliente sobre estas mismas fechas.
    chart_fechas: list = []
    chart_precios: list = []
    total_peso_periodo = 0.0
    total_valor_periodo = 0.0
    for r in raw_precio:
        fecha = r.get('fecha')
        chart_fechas.append(fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha or ''))
        p = r.get('precio_kg')
        chart_precios.append(round(float(p), 4) if p is not None else None)
        total_peso_periodo += float(r.get('suma_peso') or 0)
        total_valor_periodo += float(r.get('suma_valor') or 0)
    total_precio_kg_periodo = (total_valor_periodo / total_peso_periodo) if total_peso_periodo > 0 else None

    # Comparativa por cliente (2+ seleccionados): precio promedio ponderado y por tipo-doc por cliente
    chart_modo = 'total'
    series_clientes_precio: list[dict[str, Any]] = []
    tdoc_por_cliente: list[dict[str, Any]] = []
    if len(f_clientes) >= 2:
        sql_precio_cli = (
            f"SELECT {fe} AS fecha, CodigoCliente AS cod_cliente,"
            " MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,"
            " CASE WHEN COALESCE(SUM(Peso),0) > 0"
            "      THEN ROUND(COALESCE(SUM(Valor),0) / COALESCE(SUM(Peso),0), 4)"
            "      ELSE NULL END AS precio_kg"
            f" FROM ventasgeneral2{ext_where}"
            f" GROUP BY {fe}, CodigoCliente ORDER BY fecha ASC, cod_cliente"
        )
        sql_tdoc_cli = (
            f"SELECT {fe} AS fecha, CodigoCliente AS cod_cliente,"
            " CodigoDocumento AS tipo_doc,"
            " CASE WHEN COALESCE(SUM(Peso),0) <> 0"
            "      THEN ROUND(ABS(COALESCE(SUM(Valor),0) / COALESCE(SUM(Peso),0)), 4)"
            "      ELSE NULL END AS precio_kg"
            f" FROM ventasgeneral2{tdoc_where}"
            f" GROUP BY {fe}, CodigoCliente, CodigoDocumento"
            f" ORDER BY {fe} ASC, CodigoCliente, CodigoDocumento"
        )
        with conn.cursor() as cur:
            cur.execute(_colon_params_to_pymysql(sql_precio_cli), bind)
            raw_precio_cli = cur.fetchall() or []
        with conn.cursor() as cur:
            cur.execute(_colon_params_to_pymysql(sql_tdoc_cli), bind)
            raw_tdoc_cli = cur.fetchall() or []

        cod_to_name: dict[str, str] = {}
        per_precio: dict[str, dict[str, float]] = {}
        for r in raw_precio_cli:
            cod = str(r.get('cod_cliente') or '').strip()
            if not cod:
                continue
            fecha = r.get('fecha')
            fd = fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha or '')
            if not fd:
                continue
            p = r.get('precio_kg')
            per_precio.setdefault(cod, {})[fd] = round(float(p), 4) if p is not None else None
            cod_to_name[cod] = str(r.get('nombre_cliente') or '').strip() or cod

        for cod in f_clientes:
            c = str(cod).strip()
            if not c:
                continue
            nm = cod_to_name.get(c, c)
            label = (f'{c} — {nm}')[:80]
            series_clientes_precio.append({
                'cod': c,
                'label': label,
                'precios': [per_precio.get(c, {}).get(f) for f in chart_fechas],
            })

        # Por cliente: fechas únicas y series por tipo-doc
        per_cli_tdoc: dict[str, dict[str, dict[str, float | None]]] = {}
        per_cli_dates: dict[str, set[str]] = {}
        per_cli_tipos: dict[str, set[str]] = {}
        for r in raw_tdoc_cli:
            cod = str(r.get('cod_cliente') or '').strip()
            if not cod:
                continue
            fecha = r.get('fecha')
            fd = fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha or '')
            tdoc = str(r.get('tipo_doc') or '').strip()
            if not fd or not tdoc:
                continue
            p = r.get('precio_kg')
            per_cli_tdoc.setdefault(cod, {}).setdefault(fd, {})[tdoc] = (
                round(float(p), 4) if p is not None else None
            )
            per_cli_dates.setdefault(cod, set()).add(fd)
            per_cli_tipos.setdefault(cod, set()).add(tdoc)

        for cod in f_clientes:
            c = str(cod).strip()
            if not c:
                continue
            nm = cod_to_name.get(c, c)
            label = (f'{c} — {nm}')[:80]
            fechas_cli = sorted(per_cli_dates.get(c, set()))
            tipos_cli = sorted(per_cli_tipos.get(c, set()))
            series_t = {
                t: [
                    per_cli_tdoc.get(c, {}).get(f, {}).get(t)
                    for f in fechas_cli
                ]
                for t in tipos_cli
            }
            tdoc_por_cliente.append({
                'cod': c,
                'label': label,
                'fechas': fechas_cli,
                'series': series_t,
            })

        if len(series_clientes_precio) >= 2:
            chart_modo = 'clientes'

    filas = []
    rank = 0
    for r in raw:
        fecha = r.get('fecha')
        fecha_str = fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha or '')
        precio = r.get('precio_kg')
        rank += 1
        row = {
            'rank': rank,
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
        }
        filas.append(row)

    # Precio por tipo de documento (01 Factura, 03 Boleta, 07 Nota de Crédito)
    _tdoc_by_date: dict = {}
    _tdoc_tipos: list = []
    for r in raw_precio_tdoc:
        fecha = r.get('fecha')
        f_str = fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha or '')
        tdoc = str(r.get('tipo_doc') or '').strip()
        p = r.get('precio_kg')
        if tdoc and tdoc not in _tdoc_tipos:
            _tdoc_tipos.append(tdoc)
        if f_str not in _tdoc_by_date:
            _tdoc_by_date[f_str] = {}
        _tdoc_by_date[f_str][tdoc] = round(float(p), 4) if p is not None else None
    _tdoc_tipos.sort()
    _tdoc_fechas = sorted(_tdoc_by_date)
    chart_data_tdoc = {
        'fechas': _tdoc_fechas,
        'series': {t: [_tdoc_by_date[f].get(t) for f in _tdoc_fechas] for t in _tdoc_tipos},
    }

    ctx = _report_shell_context(f'Ventas {linea} · Precio por día provincia/cliente')
    ctx.update({
        'd1': d1, 'd2': d2, 'linea': linea, 'top': top,
        'tipo_fecha': tipo_fecha,
        'fecha_eje_leyenda': fecha_eje_leyenda,
        'fecha_columna_th': fecha_columna_th,
        'filas': filas,
        'total_peso': f'{total_peso_periodo:,.2f}',
        'total_valor': f'{total_valor_periodo:,.2f}',
        'total_precio_kg_periodo': f'{total_precio_kg_periodo:,.4f}' if total_precio_kg_periodo is not None else '—',
        'pdf_filename': f'linea_precio_diario_{d1}_{d2}.pdf',
        'chart_data': {
            'fechas': chart_fechas,
            'precios': chart_precios,
            'modo': chart_modo,
            'series_clientes': series_clientes_precio,
        },
        'chart_data_tdoc': chart_data_tdoc,
        'chart_data_tdoc_clientes': tdoc_por_cliente,
        'provincias_opts': provincias_opts,
        'corporativos_opts': corporativos_opts,
        'clientes_opts': clientes_opts,
        'f_provincias': f_provincias,
        'f_corporativos': f_corporativos,
        'f_clientes': f_clientes,
        'opts_tree': opts_tree,
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
