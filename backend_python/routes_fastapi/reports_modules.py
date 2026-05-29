"""Reportes /modules/... — FastAPI. Helpers puros importados del módulo Flask."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.exceptions import HTTPException

# Helpers sin dependencias Flask — se importan directamente
from routes.reports_modules import (
    _tdoc_label,
    _parse_date_string,
    _sql_fecha_dimension,
    _fecha_eje_leyenda,
    _fecha_columna_th,
    _colon_params_to_pymysql,
    _cascada_y_arbol,
    _buscar_ventasgeneral,
    REPORT_PLACEHOLDER_SLUGS,
)
from routes_fastapi.pages import APP_COMPANY, APP_NAME, ROLES_VENTAS_GENERAL
from routes_fastapi.templates import templates
from services.db import get_connection
from services.linea_codigo import index_hint_ventasgeneral2, linea_where_fragment
from services.urlmap import (
    REPORT_VENTASGENERAL_BUSCAR_TABLA,
    REPORT_VENTASGENERAL_RESUMEN_TABLA,
    REPORTS_PREFIX,
    REPORT_SLUG_VENTAS_RESUMEN_POR_PROVINCIA,
    REPORT_SLUG_VENTAS_CLIENTES_CORPORATIVO,
    chat_assistant_config_dict,
)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_login(request: Request):
    if not request.session.get('active'):
        return Response(status_code=302, headers={'Location': '/login'})
    return None


def _bad(msg: str, code: int = 400) -> Response:
    return Response(content=msg, status_code=code, media_type='text/plain; charset=utf-8')


def _q(request: Request, key: str, default: str = '') -> str:
    return (request.query_params.get(key) or default).strip()


def _ql(request: Request, key: str) -> list[str]:
    return [v.strip() for k, v in request.query_params.multi_items() if k == key and v.strip()]


def _report_ctx(request: Request, page_title: str) -> dict[str, Any]:
    usuario = str(request.session.get('usuario') or '')
    role = str(request.session.get('role') or 'lector').lower().strip()
    return {
        'page': 'reporte', 'page_title': page_title,
        'app_name': APP_NAME, 'app_company': APP_COMPANY,
        'load_ventas_assets': False, 'load_listado_skin': True,
        'skip_floating_chat': False, 'body_class': '',
        'role': role, 'usuario': usuario,
        'display_name': str(request.session.get('display_name') or ''),
        'nom_corto': '', 'roles_ventas_general': ROLES_VENTAS_GENERAL,
        'flash_ok': '', 'flash_err': '', 'csrf_token': '',
        'chat_assistant_config': chat_assistant_config_dict(usuario or 'anon', role),
    }


def _tipo_fecha(request: Request) -> str:
    t = _q(request, 'tipo_fecha').lower()
    return 'proceso' if t == 'proceso' else 'contable'


def _filtros_caption(request: Request) -> str:
    bits = []
    q = request.query_params
    for key, label in [('nombre_cliente', 'Cliente'), ('nombre_corporativo', 'Corporativo'),
                       ('linea_comercial', 'Línea'), ('zona_comercial', 'Zona comercial'),
                       ('cod_cliente', 'Cód. cliente'), ('prefijo_descri_zona_precio', 'Pref. zona precio'),
                       ('provincia', 'Provincia'), ('tipo_documento', 'Tipo documento')]:
        v = (q.get(key) or '').strip()
        if v:
            bits.append(f'{label}: {v}')
    cod_doc = (q.get('codigo_documento') or '').strip()
    if cod_doc:
        bits.append(f"Tipo documento: {'Nota de Crédito' if cod_doc == '07' else cod_doc}")
    return ' · '.join(bits)


def _tmpl(request: Request, name: str, ctx: dict) -> HTMLResponse:
    return templates.TemplateResponse(request, name, ctx)


# ── Rutas ─────────────────────────────────────────────────────────────────────

@router.get(REPORT_VENTASGENERAL_RESUMEN_TABLA)
@router.get('/modules/ventasgeneral_resumen_tabla.php')
def ventasgeneral_resumen_tabla(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'fecha_desde') or _q(request, 'desde'))
    d2 = _parse_date_string(_q(request, 'fecha_hasta') or _q(request, 'hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros: fecha_desde y fecha_hasta (YYYY-MM-DD).')

    sql = ("SELECT COUNT(*) AS filas, COALESCE(SUM(Valor),0) AS suma_valor,"
           " COALESCE(SUM(Cantidad),0) AS suma_cantidad, COALESCE(SUM(Peso),0) AS suma_peso"
           " FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2")
    bind: dict = {'d1': d1, 'd2': d2}
    for key, col in [('nombre_cliente', 'NombreCliente LIKE :nom_cli'),
                     ('nombre_corporativo', 'NombreCoorporativo LIKE :nom_corp'),
                     ('linea_comercial', 'LineaComercial = :linea'),
                     ('zona_comercial', 'ZonaComercial LIKE :zona'),
                     ('cod_cliente', 'CodigoCliente = :cod'),
                     ('provincia', 'Provincia LIKE :prov'),
                     ('tipo_documento', 'TipoDocumento LIKE :tdoc'),
                     ('codigo_documento', 'CodigoDocumento = :cod_doc')]:
        v = _q(request, key)
        if v:
            sql += f' AND {col}'
            bk = col.split(':')[1].split(')')[0]
            bind[bk] = f'%{v}%' if 'LIKE' in col else v
    pref_z = _q(request, 'prefijo_descri_zona_precio').upper()
    if pref_z:
        sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzp"
        bind['prefzp'] = pref_z + '%'

    where_suffix = sql[sql.index('WHERE'):]
    sql_daily = ("SELECT FechaContable AS fecha, COALESCE(SUM(Valor),0) AS suma_valor,"
                 " COUNT(*) AS lineas FROM ventasgeneral2 " + where_suffix
                 + " GROUP BY FechaContable ORDER BY FechaContable")

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        row = cur.fetchone() or {}
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_daily), bind)
        raw_daily = cur.fetchall() or []

    chart_fechas, chart_diario = [], []
    for r in raw_daily:
        f = r.get('fecha')
        chart_fechas.append(f.strftime('%Y-%m-%d') if hasattr(f, 'strftime') else str(f or ''))
        chart_diario.append(round(float(r.get('suma_valor') or 0), 2))

    ctx = _report_ctx(request, 'Resumen agregados')
    ctx.update({'d1': d1, 'd2': d2, 'filtros_texto': _filtros_caption(request),
                'r_filas': str(row.get('filas') or ''),
                'r_valor': f"{float(row.get('suma_valor') or 0):,.2f}",
                'r_cant': f"{float(row.get('suma_cantidad') or 0):,.2f}",
                'r_peso': f"{float(row.get('suma_peso') or 0):,.2f}",
                'pdf_filename': f'resumen_ventasgeneral_{d1}_{d2}.pdf',
                'chart_data': {'fechas': chart_fechas, 'diario': chart_diario}})
    return _tmpl(request, 'pages/reporte_resumen_tabla.html', ctx)


@router.get(REPORT_VENTASGENERAL_BUSCAR_TABLA)
@router.get('/modules/ventasgeneral_buscar_tabla.php')
def ventasgeneral_buscar_tabla(request: Request):
    if err := _require_login(request):
        return err
    q = request.query_params
    args: dict = {
        'fecha_desde': (_q(request, 'fecha_desde') or _q(request, 'desde')),
        'fecha_hasta': (_q(request, 'fecha_hasta') or _q(request, 'hasta')),
        'nombre_cliente': _q(request, 'nombre_cliente'),
        'nombre_corporativo': _q(request, 'nombre_corporativo'),
        'numero_doc': _q(request, 'numero_doc'),
        'cod_item': _q(request, 'cod_item'),
        'tdoc': _q(request, 'tdoc'),
        'prefijo_descri_zona_precio': _q(request, 'prefijo_descri_zona_precio'),
        'provincia': _q(request, 'provincia'),
        'tipo_documento': _q(request, 'tipo_documento'),
    }
    args = {k: v for k, v in args.items() if v}
    try:
        li = q.get('limit')
        off = q.get('offset')
        if li and li.strip():
            args['limit'] = int(li)
        if off and off.strip():
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
    headers = ['id', 'FechaContable', 'CodigoCliente', 'NombreCliente', 'NumeroFactura',
               'CodigoItem', 'GlosaDetalle', 'Cantidad', 'Peso', 'Valor', 'ZonaComercial']
    ctx = _report_ctx(request, 'Buscar ventasgeneral')
    ctx.update({'headers': headers, 'filas': filas, 'total_filas': len(raw_filas),
                'limit': out.get('limit'), 'offset': out.get('offset') or 0,
                'total_cantidad': f'{sum(float(r.get("Cantidad") or 0) for r in filas):,.2f}',
                'total_peso': f'{sum(float(r.get("Peso") or 0) for r in filas):,.2f}',
                'total_valor': f'{sum(float(r.get("Valor") or 0) for r in filas):,.2f}'})
    return _tmpl(request, 'pages/reporte_buscar_tabla.html', ctx)


@router.get('/modules/reports/ventas-top-clientes-nc')
def ventas_top_clientes_nc(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta (YYYY-MM-DD).')
    try:
        top = max(1, min(50, int(request.query_params.get('top') or 10)))
    except (TypeError, ValueError):
        top = 10

    cond = "COALESCE(NULLIF(TRIM(CodigoDocumento),''),'') = '07'"
    sql = (f"SELECT CodigoCliente AS cod_cliente,"
           f" MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,"
           f" COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor,"
           f" COALESCE(SUM(Peso),0) AS suma_peso"
           f" FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2 AND {cond}"
           f" GROUP BY CodigoCliente ORDER BY lineas DESC, suma_valor ASC LIMIT {top}")
    sql_tot = (f"SELECT COUNT(*) AS n, COALESCE(SUM(Valor),0) AS v, COALESCE(SUM(Peso),0) AS p"
               f" FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2 AND {cond}")
    bind = {'d1': d1, 'd2': d2}
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_tot), bind)
        tot = cur.fetchone() or {}

    total_lineas = int(tot.get('n') or 0)
    total_valor = float(tot.get('v') or 0)
    total_peso = float(tot.get('p') or 0)
    cum = 0.0
    filas, chart_labels, chart_lineas, chart_valores, chart_pesos, chart_pct_acum = [], [], [], [], [], []
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
        filas.append({'rank': i, 'cod_cliente': str(r.get('cod_cliente') or ''),
                      'nombre_cliente': nombre, 'lineas': ln,
                      'suma_valor': f'{sv:,.2f}', 'suma_peso': f'{sp:,.2f}',
                      'pct_lineas': f'{pct:.1f}', 'pct_acumulado': f'{cum:.1f}'})

    ctx = _report_ctx(request, 'Top clientes · Notas de crédito')
    ctx.update({'d1': d1, 'd2': d2, 'top': top, 'filas': filas,
                'total_lineas': total_lineas, 'total_valor': f'{total_valor:,.2f}',
                'total_peso': f'{total_peso:,.2f}',
                'pdf_filename': f'top_clientes_nc_{d1}_{d2}.pdf',
                'chart_data': {'labels': chart_labels, 'lineas': chart_lineas,
                               'valores': chart_valores, 'pesos': chart_pesos,
                               'pct_acum': chart_pct_acum}})
    return _tmpl(request, 'pages/reporte_top_clientes_nc.html', ctx)


@router.get('/modules/reports/ventas-linea-resumen-provincia')
def ventas_linea_resumen_provincia(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta (YYYY-MM-DD).')
    linea = _q(request, 'linea')
    if not linea:
        return _bad('Parámetro requerido: linea.')
    tipo_fecha = _tipo_fecha(request)
    fe = _sql_fecha_dimension(tipo_fecha)
    fecha_eje_leyenda = _fecha_eje_leyenda(tipo_fecha)
    fecha_columna_th = _fecha_columna_th(tipo_fecha)
    raw_top = request.query_params.get('top')
    top = None
    if raw_top and raw_top.strip() not in ('0', 'all', 'todos', ''):
        try:
            n = int(raw_top)
            if n > 0:
                top = max(1, min(100_000, n))
        except (TypeError, ValueError):
            pass
    cod_item = _q(request, 'cod_item')
    mercado = _q(request, 'mercado').upper()
    f_provincias = _ql(request, 'provincia')
    f_corporativos = _ql(request, 'corporativo')
    f_clientes = _ql(request, 'cliente')

    conn = get_connection()
    where_linea_sql, where_linea_bind = linea_where_fragment(conn, linea)
    _from_v2_suffix = index_hint_ventasgeneral2(conn, linea, tipo_fecha)
    base_where = (f" WHERE {fe} BETWEEN :d1 AND :d2" + where_linea_sql + " AND CodigoDocumento IN ('01','03')")
    base_bind: dict = {'d1': d1, 'd2': d2, **where_linea_bind}
    if cod_item:
        base_where += ' AND CodigoItem = :cod_item'
        base_bind['cod_item'] = cod_item
    if mercado:
        base_where += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo"
        base_bind['prefzo'] = mercado + '%'

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

    sql = ("SELECT COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') AS provincia,"
           " MAX(COALESCE(NULLIF(TRIM(NombreCoorporativo),''),'')) AS nombre_corporativo,"
           " CodigoCliente AS cod_cliente,"
           " MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,"
           " COUNT(*) AS lineas, COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
           " COALESCE(SUM(Peso),0) AS suma_peso, COALESCE(SUM(Valor),0) AS suma_valor,"
           " CASE WHEN COALESCE(SUM(Peso),0) > 0 THEN ROUND(COALESCE(SUM(Valor),0)/COALESCE(SUM(Peso),0),2) ELSE NULL END AS precio_kg"
           f" FROM ventasgeneral2{_from_v2_suffix}{ext_where}"
           " GROUP BY provincia, CodigoCliente ORDER BY suma_peso DESC")
    if top is not None:
        sql += f' LIMIT {top}'

    sql_precio_dia = (f"SELECT {fe} AS fecha, COALESCE(SUM(Peso),0) AS suma_peso,"
                      " CASE WHEN COALESCE(SUM(Peso),0) > 0 THEN ROUND(COALESCE(SUM(Valor),0)/COALESCE(SUM(Peso),0),4) ELSE NULL END AS precio_kg"
                      f" FROM ventasgeneral2{_from_v2_suffix}{ext_where} GROUP BY fecha ORDER BY fecha ASC")

    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_precio_dia), bind)
        raw_precio_dia = cur.fetchall() or []

    total_lineas = total_cantidad = total_peso = total_valor = 0.0
    filas, chart_labels, chart_pesos, chart_valores = [], [], [], []
    for i, r in enumerate(raw, 1):
        sp = float(r.get('suma_peso') or 0)
        sv = float(r.get('suma_valor') or 0)
        pk = r.get('precio_kg')
        nombre = str(r.get('nombre_cliente') or '')
        prov = str(r.get('provincia') or '')
        total_lineas += int(r.get('lineas') or 0)
        total_cantidad += float(r.get('suma_cantidad') or 0)
        total_peso += sp
        total_valor += sv
        chart_labels.append(f"{nombre[:20]} ({prov[:8]})")
        chart_pesos.append(round(sp, 2))
        chart_valores.append(round(sv, 2))
        filas.append({'rank': i, 'provincia': prov, 'nombre_corporativo': str(r.get('nombre_corporativo') or ''),
                      'cod_cliente': str(r.get('cod_cliente') or ''), 'nombre_cliente': nombre,
                      'lineas': f"{int(r.get('lineas') or 0):,}",
                      'suma_cantidad': f"{float(r.get('suma_cantidad') or 0):,.2f}",
                      'suma_peso': f'{sp:,.2f}', 'suma_valor': f'{sv:,.2f}',
                      'precio_kg': f'S/ {float(pk):.2f}' if pk is not None else '—'})

    chart_fechas, chart_precios_dia = [], []
    for r in raw_precio_dia:
        fecha = r.get('fecha')
        chart_fechas.append(fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha or ''))
        p = r.get('precio_kg')
        chart_precios_dia.append(round(float(p), 4) if p is not None else None)

    total_precio_kg = round(total_valor / total_peso, 2) if total_peso else None
    top_lead = 'Sin límite' if top is None else f'Top {top}'

    ctx = _report_ctx(request, f'Ventas {linea} · Resumen provincia/cliente')
    ctx.update({'d1': d1, 'd2': d2, 'linea': linea, 'top': top, 'top_lead': top_lead,
                'tipo_fecha': tipo_fecha, 'fecha_eje_leyenda': fecha_eje_leyenda,
                'fecha_columna_th': fecha_columna_th,
                'fechas_dim_label': 'fecha contable' if tipo_fecha == 'contable' else 'día de proceso',
                'filas': filas, 'total_lineas': f'{int(total_lineas):,}',
                'total_cantidad': f'{total_cantidad:,.2f}', 'total_peso': f'{total_peso:,.2f}',
                'total_valor': f'{total_valor:,.2f}',
                'total_precio_kg': f'S/ {total_precio_kg:.2f}' if total_precio_kg is not None else '—',
                'pdf_filename': f'linea_resumen_{d1}_{d2}.pdf',
                'chart_data': {'labels': chart_labels, 'pesos': chart_pesos, 'valores': chart_valores,
                               'fechas': chart_fechas, 'precios_dia': chart_precios_dia},
                'provincias_opts': provincias_opts, 'corporativos_opts': corporativos_opts,
                'clientes_opts': clientes_opts, 'f_provincias': f_provincias,
                'f_corporativos': f_corporativos, 'f_clientes': f_clientes, 'opts_tree': opts_tree,
                'body_class': 'app-page-reporte-wide'})
    return _tmpl(request, 'pages/reporte_linea_resumen_provincia.html', ctx)


@router.get('/modules/reports/ventas-linea-mix-productos')
def ventas_linea_mix_productos(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta (YYYY-MM-DD).')
    linea = _q(request, 'linea')
    if not linea:
        return _bad('Parámetro requerido: linea.')
    mercado = _q(request, 'mercado').upper()

    conn = get_connection()
    where_linea_sql, where_linea_bind = linea_where_fragment(conn, linea)
    _from_v2_suffix = index_hint_ventasgeneral2(conn, linea, 'contable')
    sql = ("SELECT CodigoItem AS cod_item,"
           " MAX(COALESCE(NULLIF(TRIM(GlosaDetalle),''),'(sin glosa)')) AS glosa,"
           " COUNT(*) AS lineas, COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
           " COALESCE(SUM(Peso),0) AS suma_peso, COALESCE(SUM(Valor),0) AS suma_valor,"
           " CASE WHEN COALESCE(SUM(Peso),0) > 0 THEN ROUND(COALESCE(SUM(Valor),0)/COALESCE(SUM(Peso),0),4) ELSE NULL END AS precio_kg"
           f" FROM ventasgeneral2{_from_v2_suffix} WHERE FechaContable BETWEEN :d1 AND :d2" + where_linea_sql)
    bind = {'d1': d1, 'd2': d2, **where_linea_bind}
    if mercado:
        sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo"
        bind['prefzo'] = mercado + '%'
    sql += ' GROUP BY CodigoItem ORDER BY suma_peso DESC'
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []

    total_peso = sum(float(r.get('suma_peso') or 0) for r in raw)
    total_valor = sum(float(r.get('suma_valor') or 0) for r in raw)
    filas, chart_labels, chart_pesos, chart_valores = [], [], [], []
    for i, r in enumerate(raw, 1):
        sp = float(r.get('suma_peso') or 0)
        sv = float(r.get('suma_valor') or 0)
        pk = r.get('precio_kg')
        glosa = str(r.get('glosa') or '')
        pct = round(sp / total_peso * 100, 2) if total_peso else 0.0
        chart_labels.append(glosa[:30] or str(r.get('cod_item') or ''))
        chart_pesos.append(round(sp, 2))
        chart_valores.append(round(sv, 2))
        filas.append({'rank': i, 'cod_item': str(r.get('cod_item') or ''), 'glosa': glosa,
                      'lineas': f"{int(r.get('lineas') or 0):,}",
                      'suma_cantidad': f"{float(r.get('suma_cantidad') or 0):,.2f}",
                      'suma_peso': f'{sp:,.2f}', 'suma_valor': f'{sv:,.2f}',
                      'precio_kg': f'S/ {float(pk):,.2f}' if pk is not None else '—',
                      'pct_peso': f'{pct:.2f}'})

    ctx = _report_ctx(request, f'Ventas {linea} · Mix de productos')
    ctx.update({'d1': d1, 'd2': d2, 'linea': linea, 'mercado': mercado or None,
                'filas': filas, 'total_peso': f'{total_peso:,.2f}', 'total_valor': f'{total_valor:,.2f}',
                'pdf_filename': f'linea_mix_productos_{d1}_{d2}.pdf',
                'chart_data': {'labels': chart_labels, 'pesos': chart_pesos, 'valores': chart_valores}})
    return _tmpl(request, 'pages/reporte_linea_mix_productos.html', ctx)


@router.get('/modules/reports/ventas-top-clientes-global')
def ventas_top_clientes_global(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta.')
    try:
        top = max(1, min(100, int(request.query_params.get('top') or 10)))
    except (TypeError, ValueError):
        top = 10

    sql = ("SELECT CodigoCliente AS cod_cliente,"
           " MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,"
           " COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor"
           f" FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2"
           f" GROUP BY CodigoCliente ORDER BY suma_valor DESC LIMIT {top}")
    sql_tot = "SELECT COALESCE(SUM(Valor),0) AS t FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2"
    bind = {'d1': d1, 'd2': d2}
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_tot), bind)
        tot = cur.fetchone() or {}

    total = float(tot.get('t') or 0)
    cum = 0.0
    filas, chart_labels, chart_valores, chart_pct_acum = [], [], [], []
    for i, r in enumerate(raw, 1):
        sv = float(r.get('suma_valor') or 0)
        pct = sv / total * 100 if total else 0.0
        cum += pct
        nombre = str(r.get('nombre_cliente') or '')
        chart_labels.append(nombre[:30])
        chart_valores.append(round(sv, 2))
        chart_pct_acum.append(round(cum, 1))
        filas.append({'rank': i, 'cod_cliente': str(r.get('cod_cliente') or ''),
                      'nombre_cliente': nombre, 'lineas': int(r.get('lineas') or 0),
                      'suma_valor': f'{sv:,.2f}', 'pct_del_total': f'{pct:.1f}',
                      'pct_acumulado': f'{cum:.1f}'})

    ctx = _report_ctx(request, f'Top {top} clientes · Global')
    ctx.update({'d1': d1, 'd2': d2, 'top': top, 'filas': filas,
                'total_valor': f'{total:,.2f}', 'pdf_filename': f'top_clientes_global_{d1}_{d2}.pdf',
                'chart_data': {'labels': chart_labels, 'valores': chart_valores, 'pct_acum': chart_pct_acum}})
    return _tmpl(request, 'pages/reporte_top_clientes_global.html', ctx)


@router.get('/modules/reports/ventas-top-productos')
def ventas_top_productos(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta.')
    try:
        top = max(1, min(100, int(request.query_params.get('top') or 15)))
    except (TypeError, ValueError):
        top = 15

    sql = ("SELECT CodigoItem AS cod_item,"
           " MAX(COALESCE(NULLIF(TRIM(GlosaDetalle),''),'(sin glosa)')) AS glosa,"
           " COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor, COALESCE(SUM(Cantidad),0) AS suma_cantidad"
           f" FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2"
           f" GROUP BY CodigoItem ORDER BY suma_valor DESC LIMIT {top}")
    sql_tot = "SELECT COALESCE(SUM(Valor),0) AS t FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2"
    bind = {'d1': d1, 'd2': d2}
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_tot), bind)
        tot = cur.fetchone() or {}

    total = float(tot.get('t') or 0)
    cum = 0.0
    filas, chart_labels, chart_valores, chart_pct_acum = [], [], [], []
    for i, r in enumerate(raw, 1):
        sv = float(r.get('suma_valor') or 0)
        pct = sv / total * 100 if total else 0.0
        cum += pct
        glosa = str(r.get('glosa') or r.get('cod_item') or '')
        chart_labels.append(glosa[:28])
        chart_valores.append(round(sv, 2))
        chart_pct_acum.append(round(cum, 1))
        filas.append({'rank': i, 'cod_item': str(r.get('cod_item') or ''), 'glosa': glosa,
                      'lineas': int(r.get('lineas') or 0),
                      'suma_cantidad': f"{float(r.get('suma_cantidad') or 0):,.2f}",
                      'suma_valor': f'{sv:,.2f}', 'pct_del_total': f'{pct:.1f}',
                      'pct_acumulado': f'{cum:.1f}'})

    ctx = _report_ctx(request, f'Top {top} productos')
    ctx.update({'d1': d1, 'd2': d2, 'top': top, 'filas': filas,
                'total_valor': f'{total:,.2f}', 'pdf_filename': f'top_productos_{d1}_{d2}.pdf',
                'chart_data': {'labels': chart_labels, 'valores': chart_valores, 'pct_acum': chart_pct_acum}})
    return _tmpl(request, 'pages/reporte_top_productos.html', ctx)


@router.get('/modules/reports/ventas-serie-mensual')
def ventas_serie_mensual(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta.')

    sql = ("SELECT DATE_FORMAT(FechaContable, '%%Y-%%m') AS mes,"
           " COALESCE(SUM(Valor),0) AS suma_valor, COUNT(*) AS lineas"
           " FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2"
           " GROUP BY DATE_FORMAT(FechaContable, '%%Y-%%m') ORDER BY mes")
    bind = {'d1': d1, 'd2': d2}
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []

    filas, chart_labels, chart_valores, chart_lineas = [], [], [], []
    total_valor = 0.0
    total_lineas = 0
    for r in raw:
        sv = float(r.get('suma_valor') or 0)
        ln = int(r.get('lineas') or 0)
        mes = str(r.get('mes') or '')
        total_valor += sv
        total_lineas += ln
        chart_labels.append(mes)
        chart_valores.append(round(sv, 2))
        chart_lineas.append(ln)
        filas.append({'mes': mes, 'lineas': ln, 'suma_valor': f'{sv:,.2f}'})

    ctx = _report_ctx(request, 'Serie mensual de ventas')
    ctx.update({'d1': d1, 'd2': d2, 'filas': filas,
                'total_valor': f'{total_valor:,.2f}', 'total_lineas': total_lineas,
                'pdf_filename': f'serie_mensual_{d1}_{d2}.pdf',
                'chart_data': {'labels': chart_labels, 'valores': chart_valores, 'lineas': chart_lineas}})
    return _tmpl(request, 'pages/reporte_serie_mensual.html', ctx)


@router.get('/modules/reports/ventas-mix-tdoc')
def ventas_mix_tdoc(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta.')

    sql = ("SELECT COALESCE(NULLIF(TRIM(CodigoDocumento),''),'(sin TDoc)') AS tdoc,"
           " COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor"
           " FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2"
           " GROUP BY COALESCE(NULLIF(TRIM(CodigoDocumento),''),'(sin TDoc)') ORDER BY suma_valor DESC")
    bind = {'d1': d1, 'd2': d2}
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []

    total = sum(float(r.get('suma_valor') or 0) for r in raw)
    filas, chart_labels, chart_valores = [], [], []
    for r in raw:
        sv = float(r.get('suma_valor') or 0)
        tdoc = str(r.get('tdoc') or '')
        label = _tdoc_label(tdoc)
        pct = sv / total * 100 if total else 0.0
        chart_labels.append(label)
        chart_valores.append(round(sv, 2))
        filas.append({'tdoc': tdoc, 'label': label, 'lineas': int(r.get('lineas') or 0),
                      'suma_valor': f'{sv:,.2f}', 'pct_del_total': f'{pct:.1f}'})

    ctx = _report_ctx(request, 'Mix por tipo de documento')
    ctx.update({'d1': d1, 'd2': d2, 'filas': filas, 'total_valor': f'{total:,.2f}',
                'pdf_filename': f'mix_tdoc_{d1}_{d2}.pdf',
                'chart_data': {'labels': chart_labels, 'valores': chart_valores}})
    return _tmpl(request, 'pages/reporte_mix_tdoc.html', ctx)


@router.get('/modules/reports/pareto-nc-zona')
def pareto_nc_zona(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta.')
    try:
        max_z = max(1, min(200, int(request.query_params.get('max') or 50)))
    except (TypeError, ValueError):
        max_z = 50

    sql = ("SELECT COALESCE(NULLIF(TRIM(DescripcionZonaPrecio),''),'(sin zona)') AS zona,"
           " COUNT(*) AS lineas_nc, COALESCE(SUM(ABS(Valor)),0) AS impacto_abs_valor"
           " FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2 AND CodigoDocumento = '07'"
           " GROUP BY COALESCE(NULLIF(TRIM(DescripcionZonaPrecio),''),'(sin zona)')"
           f" ORDER BY impacto_abs_valor DESC LIMIT {max_z}")
    bind = {'d1': d1, 'd2': d2}
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []

    total = sum(float(r.get('impacto_abs_valor') or 0) for r in raw)
    cum = 0.0
    filas, chart_labels, chart_valores, chart_pct_acum = [], [], [], []
    for i, r in enumerate(raw, 1):
        imp = float(r.get('impacto_abs_valor') or 0)
        pct = imp / total * 100 if total else 0.0
        cum += pct
        zona = str(r.get('zona') or '')
        chart_labels.append(zona[:25])
        chart_valores.append(round(imp, 2))
        chart_pct_acum.append(round(cum, 1))
        filas.append({'rank': i, 'zona': zona, 'lineas_nc': int(r.get('lineas_nc') or 0),
                      'impacto_abs_valor': f'{imp:,.2f}', 'pct_del_total': f'{pct:.1f}',
                      'pct_acumulado': f'{cum:.1f}'})

    ctx = _report_ctx(request, 'Pareto NC · Zona precio')
    ctx.update({'d1': d1, 'd2': d2, 'max_z': max_z, 'filas': filas,
                'total_impacto': f'{total:,.2f}', 'pdf_filename': f'pareto_nc_zona_{d1}_{d2}.pdf',
                'chart_data': {'labels': chart_labels, 'valores': chart_valores, 'pct_acum': chart_pct_acum}})
    return _tmpl(request, 'pages/reporte_pareto_nc_zona.html', ctx)


@router.get('/modules/reports/pareto-clientes-zona')
def pareto_clientes_zona(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta.')
    pref = (_q(request, 'prefijo') or _q(request, 'prefijo_descri_zona_precio')).upper()
    if not pref:
        return _bad('Parámetro requerido: prefijo (ej. TACNA).')
    try:
        top = max(1, min(100, int(request.query_params.get('top') or 10)))
    except (TypeError, ValueError):
        top = 10

    like = pref + '%'
    sql_tot = ("SELECT COALESCE(SUM(Valor),0) AS t FROM ventasgeneral2"
               " WHERE FechaContable BETWEEN :d1 AND :d2"
               " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :pref")
    sql = ("SELECT CodigoCliente AS cod_cliente,"
           " MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,"
           " COALESCE(SUM(Valor),0) AS suma_valor, COUNT(*) AS lineas_venta"
           " FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2"
           " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :pref"
           f" GROUP BY CodigoCliente ORDER BY suma_valor DESC LIMIT {top}")
    bind = {'d1': d1, 'd2': d2, 'pref': like}
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_tot), bind)
        tot = cur.fetchone() or {}
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []

    total_zona = float(tot.get('t') or 0)
    cum = 0.0
    filas, chart_labels, chart_valores, chart_pct_acum = [], [], [], []
    for i, r in enumerate(raw, 1):
        sv = float(r.get('suma_valor') or 0)
        pct = sv / total_zona * 100 if total_zona else 0.0
        cum += pct
        nombre = str(r.get('nombre_cliente') or '')
        chart_labels.append(nombre[:28])
        chart_valores.append(round(sv, 2))
        chart_pct_acum.append(round(cum, 1))
        filas.append({'rank': i, 'cod_cliente': str(r.get('cod_cliente') or ''),
                      'nombre_cliente': nombre, 'lineas_venta': int(r.get('lineas_venta') or 0),
                      'suma_valor': f'{sv:,.2f}', 'pct_del_total': f'{pct:.1f}',
                      'pct_acumulado': f'{cum:.1f}'})

    ctx = _report_ctx(request, f'Top {top} clientes · Zona {pref}')
    ctx.update({'d1': d1, 'd2': d2, 'top': top, 'prefijo': pref, 'filas': filas,
                'total_zona': f'{total_zona:,.2f}', 'pdf_filename': f'pareto_clientes_zona_{pref}_{d1}_{d2}.pdf',
                'chart_data': {'labels': chart_labels, 'valores': chart_valores, 'pct_acum': chart_pct_acum}})
    return _tmpl(request, 'pages/reporte_pareto_clientes_zona.html', ctx)


@router.get('/modules/reports/ventas-barras-dimension')
def ventas_barras_dimension(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta.')
    dim_raw = (_q(request, 'dim') or _q(request, 'dimension') or 'precio').lower()
    dim = dim_raw if dim_raw in ('precio', 'comercial') else 'precio'
    try:
        top = max(1, min(100, int(request.query_params.get('top') or 20)))
    except (TypeError, ValueError):
        top = 20

    expr = ("COALESCE(NULLIF(TRIM(DescripcionZonaPrecio),''),'(sin zona precio)')"
            if dim == 'precio' else "COALESCE(NULLIF(TRIM(ZonaComercial),''),'(sin zona comercial)')")
    sql = (f"SELECT {expr} AS etiqueta, COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor"
           f" FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2"
           f" GROUP BY {expr} ORDER BY suma_valor DESC LIMIT {top}")
    sql_tot = "SELECT COALESCE(SUM(Valor),0) AS t FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2"
    bind = {'d1': d1, 'd2': d2}
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_tot), bind)
        tot = cur.fetchone() or {}

    total = float(tot.get('t') or 0)
    filas, chart_labels, chart_valores = [], [], []
    for i, r in enumerate(raw, 1):
        sv = float(r.get('suma_valor') or 0)
        pct = sv / total * 100 if total else 0.0
        etq = str(r.get('etiqueta') or '')
        chart_labels.append(etq[:25])
        chart_valores.append(round(sv, 2))
        filas.append({'rank': i, 'etiqueta': etq, 'lineas': int(r.get('lineas') or 0),
                      'suma_valor': f'{sv:,.2f}', 'pct_del_total': f'{pct:.1f}'})

    dim_label = 'Zona de precio' if dim == 'precio' else 'Zona comercial'
    ctx = _report_ctx(request, f'Ventas por {dim_label}')
    ctx.update({'d1': d1, 'd2': d2, 'top': top, 'dim': dim, 'dim_label': dim_label,
                'filas': filas, 'total_valor': f'{total:,.2f}',
                'pdf_filename': f'barras_dimension_{dim}_{d1}_{d2}.pdf',
                'chart_data': {'labels': chart_labels, 'valores': chart_valores}})
    return _tmpl(request, 'pages/reporte_barras_dimension.html', ctx)


@router.get('/modules/reports/ventas-comparativo')
def ventas_comparativo(request: Request):
    if err := _require_login(request):
        return err
    a1 = _parse_date_string(_q(request, 'a_desde') or _q(request, 'fecha_desde_a'))
    a2 = _parse_date_string(_q(request, 'a_hasta') or _q(request, 'fecha_hasta_a'))
    b1 = _parse_date_string(_q(request, 'b_desde') or _q(request, 'fecha_desde_b'))
    b2 = _parse_date_string(_q(request, 'b_hasta') or _q(request, 'fecha_hasta_b'))
    if not a1 or not a2 or not b1 or not b2:
        return _bad('Parámetros requeridos: a_desde, a_hasta, b_desde, b_hasta.')
    if a1 > a2 or b1 > b2:
        return _bad('Rango de fechas inválido.')
    dim_raw = (_q(request, 'dim') or _q(request, 'dimension') or 'precio').lower()
    dim = dim_raw if dim_raw in ('precio', 'comercial') else 'precio'
    try:
        top = max(1, min(80, int(request.query_params.get('top') or 15)))
    except (TypeError, ValueError):
        top = 15

    expr = ("COALESCE(NULLIF(TRIM(DescripcionZonaPrecio),''),'(sin zona precio)')"
            if dim == 'precio' else "COALESCE(NULLIF(TRIM(ZonaComercial),''),'(sin zona comercial)')")
    sql = (f"SELECT etiqueta, SUM(va) AS valor_a, SUM(vb) AS valor_b FROM ("
           f"  SELECT {expr} AS etiqueta, COALESCE(SUM(Valor),0) AS va, 0 AS vb"
           f"  FROM ventasgeneral2 WHERE FechaContable BETWEEN :a1 AND :a2 GROUP BY {expr}"
           f"  UNION ALL"
           f"  SELECT {expr}, 0, COALESCE(SUM(Valor),0)"
           f"  FROM ventasgeneral2 WHERE FechaContable BETWEEN :b1 AND :b2 GROUP BY {expr}"
           f") u GROUP BY etiqueta HAVING ABS(SUM(va)) + ABS(SUM(vb)) > 0"
           f" ORDER BY GREATEST(ABS(SUM(va)), ABS(SUM(vb))) DESC LIMIT {top}")
    bind = {'a1': a1, 'a2': a2, 'b1': b1, 'b2': b2}
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []

    filas, chart_labels, chart_valores_a, chart_valores_b = [], [], [], []
    for i, r in enumerate(raw, 1):
        va = float(r.get('valor_a') or 0)
        vb = float(r.get('valor_b') or 0)
        delta = vb - va
        etq = str(r.get('etiqueta') or '')
        chart_labels.append(etq[:25])
        chart_valores_a.append(round(va, 2))
        chart_valores_b.append(round(vb, 2))
        filas.append({'rank': i, 'etiqueta': etq, 'valor_a': f'{va:,.2f}', 'valor_b': f'{vb:,.2f}',
                      'delta': f'{delta:,.2f}', 'delta_pct': f'{delta/va*100:.1f}' if va else '—'})

    dim_label = 'Zona de precio' if dim == 'precio' else 'Zona comercial'
    ctx = _report_ctx(request, f'Comparativo de períodos · {dim_label}')
    ctx.update({'a1': a1, 'a2': a2, 'b1': b1, 'b2': b2, 'top': top, 'dim': dim, 'dim_label': dim_label,
                'filas': filas, 'pdf_filename': f'comparativo_{a1}_{b2}.pdf',
                'chart_data': {'labels': chart_labels, 'valores_a': chart_valores_a,
                               'valores_b': chart_valores_b}})
    return _tmpl(request, 'pages/reporte_comparativo.html', ctx)


@router.get('/modules/reports/ventas-barras-ruta')
def ventas_barras_ruta(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta.')
    try:
        top = max(1, min(100, int(request.query_params.get('top') or 15)))
    except (TypeError, ValueError):
        top = 15

    expr = "COALESCE(NULLIF(TRIM(RutaComercial),''),'(sin ruta)')"
    sql = (f"SELECT {expr} AS ruta, COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor"
           f" FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2"
           f" GROUP BY {expr} ORDER BY suma_valor DESC LIMIT {top}")
    sql_tot = "SELECT COALESCE(SUM(Valor),0) AS t FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2"
    bind = {'d1': d1, 'd2': d2}
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_tot), bind)
        tot = cur.fetchone() or {}

    total = float(tot.get('t') or 0)
    filas, chart_labels, chart_valores = [], [], []
    for i, r in enumerate(raw, 1):
        sv = float(r.get('suma_valor') or 0)
        pct = sv / total * 100 if total else 0.0
        ruta = str(r.get('ruta') or '')
        chart_labels.append(ruta[:25])
        chart_valores.append(round(sv, 2))
        filas.append({'rank': i, 'ruta': ruta, 'lineas': int(r.get('lineas') or 0),
                      'suma_valor': f'{sv:,.2f}', 'pct_del_total': f'{pct:.1f}'})

    ctx = _report_ctx(request, f'Top {top} rutas comerciales')
    ctx.update({'d1': d1, 'd2': d2, 'top': top, 'filas': filas, 'total_valor': f'{total:,.2f}',
                'pdf_filename': f'barras_ruta_{d1}_{d2}.pdf',
                'chart_data': {'labels': chart_labels, 'valores': chart_valores}})
    return _tmpl(request, 'pages/reporte_barras_ruta.html', ctx)


@router.get('/modules/reports/ventas-barras-corporativo')
def ventas_barras_corporativo(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta.')
    try:
        top = max(1, min(100, int(request.query_params.get('top') or 15)))
    except (TypeError, ValueError):
        top = 15

    tipo_fecha = _tipo_fecha(request)
    fe = _sql_fecha_dimension(tipo_fecha)
    fecha_eje_leyenda = _fecha_eje_leyenda(tipo_fecha)
    f_provincias = _ql(request, 'provincia')
    f_corporativos = _ql(request, 'corporativo')
    f_clientes = _ql(request, 'cliente')
    nombre_cliente_q = _q(request, 'nombre_cliente')
    nombre_corporativo_q = _q(request, 'nombre_corporativo')

    conn = get_connection()
    base_where = f' WHERE {fe} BETWEEN :d1 AND :d2'
    base_bind: dict[str, Any] = {'d1': d1, 'd2': d2}
    if nombre_cliente_q:
        base_where += ' AND NombreCliente LIKE :nom_cli'
        base_bind['nom_cli'] = f'%{nombre_cliente_q}%'
    if nombre_corporativo_q and not f_corporativos:
        base_where += ' AND NombreCoorporativo LIKE :nom_corp'
        base_bind['nom_corp'] = f'%{nombre_corporativo_q}%'

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

    expr = "COALESCE(NULLIF(TRIM(NombreCoorporativo),''),'(sin corporativo)')"
    sql = (f"SELECT {expr} AS nombre_coorporativo,"
           f" MAX(COALESCE(NULLIF(TRIM(CodigoCoorporativo),''),'')) AS cod_coorporativo,"
           f" COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor"
           f" FROM ventasgeneral2{ext_where}"
           f" GROUP BY {expr} ORDER BY suma_valor DESC LIMIT {top}")
    sql_tot = f"SELECT COALESCE(SUM(Valor),0) AS t FROM ventasgeneral2{ext_where}"
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_tot), bind)
        tot = cur.fetchone() or {}

    total = float(tot.get('t') or 0)
    filas, chart_labels, chart_valores = [], [], []
    for i, r in enumerate(raw, 1):
        sv = float(r.get('suma_valor') or 0)
        pct = sv / total * 100 if total else 0.0
        corp = str(r.get('nombre_coorporativo') or '')
        chart_labels.append(corp[:25])
        chart_valores.append(round(sv, 2))
        filas.append({'rank': i, 'cod_coorporativo': str(r.get('cod_coorporativo') or ''),
                      'nombre_coorporativo': corp, 'lineas': f"{int(r.get('lineas') or 0):,}",
                      'suma_valor': f'{sv:,.2f}', 'pct_del_total': f'{pct:.1f}'})

    filtros_activos = []
    if nombre_cliente_q:
        filtros_activos.append(f'cliente «{nombre_cliente_q}»')
    if nombre_corporativo_q and not f_corporativos:
        filtros_activos.append(f'corporativo «{nombre_corporativo_q}»')
    if f_provincias:
        filtros_activos.append('provincia: ' + ', '.join(f_provincias))
    if f_corporativos:
        filtros_activos.append('corporativo: ' + ', '.join(f_corporativos))
    if f_clientes:
        filtros_activos.append(f'{len(f_clientes)} cliente(s)')

    ctx = _report_ctx(request, f'Top {top} corporativos')
    ctx.update({'d1': d1, 'd2': d2, 'top': top, 'tipo_fecha': tipo_fecha,
                'fecha_eje_leyenda': fecha_eje_leyenda, 'filas': filas,
                'total_valor': f'{total:,.2f}', 'pdf_filename': f'barras_corporativo_{d1}_{d2}.pdf',
                'chart_data': {'labels': chart_labels, 'valores': chart_valores},
                'provincias_opts': provincias_opts, 'corporativos_opts': corporativos_opts,
                'clientes_opts': clientes_opts, 'f_provincias': f_provincias,
                'f_corporativos': f_corporativos, 'f_clientes': f_clientes, 'opts_tree': opts_tree,
                'nombre_cliente_q': nombre_cliente_q, 'nombre_corporativo_q': nombre_corporativo_q,
                'filtros_activos': filtros_activos, 'body_class': 'app-page-reporte-wide'})
    return _tmpl(request, 'pages/reporte_barras_corporativo.html', ctx)


@router.get('/modules/reports/ventas-resumen-por-linea')
def ventas_resumen_por_linea(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta.')

    provincia = _q(request, 'provincia')
    prefijo = _q(request, 'prefijo').upper()
    lineas_raw = _q(request, 'lineas')
    lineas_list = [l.strip() for l in lineas_raw.split(',') if l.strip()] if lineas_raw else []

    where = ' WHERE FechaContable BETWEEN :d1 AND :d2'
    bind: dict = {'d1': d1, 'd2': d2}
    if provincia:
        where += ' AND Provincia LIKE :prov'
        bind['prov'] = f'%{provincia}%'
    if prefijo:
        where += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo"
        bind['prefzo'] = prefijo + '%'
    if lineas_list:
        keys = [f'lin{i}' for i in range(len(lineas_list))]
        where += ' AND LineaComercial IN (' + ','.join(f':{k}' for k in keys) + ')'
        bind.update(zip(keys, lineas_list))

    sql = ("SELECT COALESCE(NULLIF(TRIM(LineaComercial),''),'(sin línea)') AS linea_comercial,"
           " COUNT(*) AS lineas, COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
           " COALESCE(SUM(Peso),0) AS suma_peso, COALESCE(SUM(Valor),0) AS suma_valor"
           " FROM ventasgeneral2" + where +
           " GROUP BY COALESCE(NULLIF(TRIM(LineaComercial),''),'(sin línea)') ORDER BY suma_valor DESC")
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []

    total = sum(float(r.get('suma_valor') or 0) for r in raw)
    cum = 0.0
    filas, chart_labels, chart_valores, chart_pct_acum = [], [], [], []
    for i, r in enumerate(raw, 1):
        sv = float(r.get('suma_valor') or 0)
        sp = float(r.get('suma_peso') or 0)
        sc = float(r.get('suma_cantidad') or 0)
        pct = sv / total * 100 if total else 0.0
        cum += pct
        lbl = str(r.get('linea_comercial') or '')
        chart_labels.append(lbl[:30])
        chart_valores.append(round(sv, 2))
        chart_pct_acum.append(round(cum, 1))
        filas.append({'rank': i, 'linea_comercial': lbl, 'lineas': int(r.get('lineas') or 0),
                      'suma_cantidad': f'{sc:,.2f}', 'suma_peso': f'{sp:,.2f}',
                      'suma_valor': f'{sv:,.2f}', 'pct_del_total': f'{pct:.1f}',
                      'pct_acumulado': f'{cum:.1f}'})

    titulo = 'Ventas por línea comercial'
    if lineas_list:
        titulo += f' — {", ".join(lineas_list)}'
    if provincia:
        titulo += f' · {provincia}'

    ctx = _report_ctx(request, titulo)
    ctx.update({'d1': d1, 'd2': d2, 'titulo': titulo, 'provincia': provincia,
                'prefijo': prefijo, 'lineas_raw': lineas_raw, 'filas': filas,
                'total_valor': f'{total:,.2f}', 'pdf_filename': f'resumen_lineas_{d1}_{d2}.pdf',
                'chart_data': {'labels': chart_labels, 'valores': chart_valores,
                               'pct_acum': chart_pct_acum}})
    return _tmpl(request, 'pages/reporte_resumen_por_linea.html', ctx)


@router.get(REPORTS_PREFIX + REPORT_SLUG_VENTAS_RESUMEN_POR_PROVINCIA)
def ventas_resumen_por_provincia(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta.')

    linea = _q(request, 'linea_comercial')
    cod_doc = _q(request, 'codigo_documento')
    tdoc = _q(request, 'tipo_documento')
    prefijo = _q(request, 'prefijo_descri_zona_precio').upper()

    where = ' WHERE FechaContable BETWEEN :d1 AND :d2'
    bind: dict = {'d1': d1, 'd2': d2}
    if linea:
        where += ' AND LineaComercial = :linea'
        bind['linea'] = linea
    if cod_doc:
        where += ' AND CodigoDocumento = :cod_doc'
        bind['cod_doc'] = cod_doc
    if tdoc:
        where += ' AND TipoDocumento LIKE :tdoc'
        bind['tdoc'] = f'%{tdoc}%'
    if prefijo:
        where += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo"
        bind['prefzo'] = prefijo + '%'

    sql = ("SELECT COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') AS provincia,"
           " COUNT(*) AS lineas, COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
           " COALESCE(SUM(Peso),0) AS suma_peso, COALESCE(SUM(Valor),0) AS suma_valor"
           " FROM ventasgeneral2" + where +
           " GROUP BY COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') ORDER BY suma_valor DESC")
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []

    total = sum(float(r.get('suma_valor') or 0) for r in raw)
    cum = 0.0
    filas, chart_labels, chart_valores, chart_pct_acum = [], [], [], []
    for i, r in enumerate(raw, 1):
        sv = float(r.get('suma_valor') or 0)
        sp = float(r.get('suma_peso') or 0)
        sc = float(r.get('suma_cantidad') or 0)
        pct = sv / total * 100 if total else 0.0
        cum += pct
        lbl = str(r.get('provincia') or '')
        chart_labels.append(lbl[:30])
        chart_valores.append(round(sv, 2))
        chart_pct_acum.append(round(cum, 1))
        filas.append({'rank': i, 'provincia': lbl, 'lineas': int(r.get('lineas') or 0),
                      'suma_cantidad': f'{sc:,.2f}', 'suma_peso': f'{sp:,.2f}',
                      'suma_valor': f'{sv:,.2f}', 'pct_del_total': f'{pct:.1f}',
                      'pct_acumulado': f'{cum:.1f}'})

    titulo = 'Ventas por provincia'
    if linea:
        titulo += f' · {linea}'

    ctx = _report_ctx(request, titulo)
    ctx.update({'d1': d1, 'd2': d2, 'titulo': titulo, 'filas': filas,
                'total_valor': f'{total:,.2f}', 'pdf_filename': f'resumen_provincia_{d1}_{d2}.pdf',
                'chart_data': {'labels': chart_labels, 'valores': chart_valores,
                               'pct_acum': chart_pct_acum}})
    return _tmpl(request, 'pages/reporte_resumen_por_provincia.html', ctx)


@router.get(REPORTS_PREFIX + REPORT_SLUG_VENTAS_CLIENTES_CORPORATIVO)
def ventas_clientes_corporativo(request: Request):
    if err := _require_login(request):
        return err
    nom_corp = _q(request, 'corporativo')
    if not nom_corp:
        return _bad('Parámetro requerido: corporativo.')

    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))

    where = ' WHERE NombreCoorporativo LIKE :nom_corp'
    bind: dict = {'nom_corp': f'%{nom_corp}%'}
    if d1 and d2:
        where += ' AND FechaContable BETWEEN :d1 AND :d2'
        bind.update({'d1': d1, 'd2': d2})
    elif d1:
        where += ' AND FechaContable >= :d1'
        bind['d1'] = d1
    elif d2:
        where += ' AND FechaContable <= :d2'
        bind['d2'] = d2

    sql = ('SELECT CodigoCliente AS codigo_cliente, MAX(NombreCliente) AS nombre_cliente,'
           ' COUNT(*) AS lineas, COALESCE(SUM(Peso),0) AS suma_peso,'
           ' COALESCE(SUM(Valor),0) AS suma_valor,'
           ' MIN(FechaContable) AS primera_venta, MAX(FechaContable) AS ultima_venta'
           ' FROM ventasgeneral2' + where + ' GROUP BY CodigoCliente ORDER BY nombre_cliente')
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []

    total_lineas = sum(int(r.get('lineas') or 0) for r in raw)
    total_peso = sum(float(r.get('suma_peso') or 0) for r in raw)
    total_valor = sum(float(r.get('suma_valor') or 0) for r in raw)
    filas = [{'codigo_cliente': str(r.get('codigo_cliente') or ''),
              'nombre_cliente': str(r.get('nombre_cliente') or ''),
              'lineas': int(r.get('lineas') or 0),
              'suma_peso': f'{float(r.get("suma_peso") or 0):,.2f}',
              'suma_valor': f'{float(r.get("suma_valor") or 0):,.2f}',
              'primera_venta': str(r.get('primera_venta') or ''),
              'ultima_venta': str(r.get('ultima_venta') or '')} for r in raw]

    periodo_str = (f'{d1} al {d2}' if d1 and d2 else
                   f'desde {d1}' if d1 else f'hasta {d2}' if d2 else '')
    titulo = f'Clientes del corporativo: {nom_corp}'
    ctx = _report_ctx(request, titulo)
    ctx.update({'titulo': titulo, 'nom_corp': nom_corp, 'periodo_str': periodo_str,
                'filas': filas, 'total_lineas': f'{total_lineas:,}',
                'total_peso': f'{total_peso:,.2f}', 'total_valor': f'{total_valor:,.2f}',
                'pdf_filename': f'clientes_corporativo_{nom_corp[:30]}.pdf'})
    return _tmpl(request, 'pages/reporte_clientes_corporativo.html', ctx)


@router.get('/modules/reports/ventas-linea-precio-resumen-provincia')
def ventas_linea_precio_resumen_provincia(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta.')
    linea = _q(request, 'linea')
    if not linea:
        return _bad('Parámetro requerido: linea.')
    tipo_fecha = _tipo_fecha(request)
    fe = _sql_fecha_dimension(tipo_fecha)
    fecha_eje_leyenda = _fecha_eje_leyenda(tipo_fecha)
    cod_item = _q(request, 'cod_item')
    mercado = _q(request, 'mercado').upper()
    provincia_filtro = _q(request, 'provincia')

    conn = get_connection()
    where_linea_sql, where_linea_bind = linea_where_fragment(conn, linea)
    _from_v2_suffix = index_hint_ventasgeneral2(conn, linea, tipo_fecha)

    _bind_base: dict = {'d1': d1, 'd2': d2, **where_linea_bind}
    if cod_item:
        _bind_base['cod_item'] = cod_item
    if mercado:
        _bind_base['prefzo'] = mercado + '%'
    _sql_provs = (
        f"SELECT DISTINCT COALESCE(NULLIF(TRIM(Provincia),''),'') AS prov"
        f" FROM ventasgeneral2{_from_v2_suffix} WHERE {fe} BETWEEN :d1 AND :d2"
        + where_linea_sql
        + (' AND CodigoItem = :cod_item' if cod_item else '')
        + (" AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo" if mercado else '')
        + " AND TRIM(COALESCE(Provincia,'')) <> '' ORDER BY prov"
    )
    with conn.cursor() as _cur:
        _cur.execute(_colon_params_to_pymysql(_sql_provs), _bind_base)
        provincias_opts = [str(r.get('prov') or '').strip() for r in (_cur.fetchall() or []) if (r.get('prov') or '').strip()]

    sql = (f"SELECT COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') AS provincia,"
           " COUNT(*) AS lineas, COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
           " COALESCE(SUM(Peso),0) AS suma_peso, COALESCE(SUM(Valor),0) AS suma_valor,"
           " CASE WHEN COALESCE(SUM(Peso),0) > 0 THEN ROUND(COALESCE(SUM(Valor),0)/COALESCE(SUM(Peso),0),4) ELSE NULL END AS precio_kg"
           f" FROM ventasgeneral2{_from_v2_suffix} WHERE {fe} BETWEEN :d1 AND :d2"
           + where_linea_sql)
    bind: dict = {'d1': d1, 'd2': d2, **where_linea_bind}
    if cod_item:
        sql += ' AND CodigoItem = :cod_item'
        bind['cod_item'] = cod_item
    if mercado:
        sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo"
        bind['prefzo'] = mercado + '%'
    if provincia_filtro:
        sql += " AND COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') = :prov"
        bind['prov'] = provincia_filtro
    sql += ' GROUP BY provincia ORDER BY suma_peso DESC'

    sql_dia = (f"SELECT {fe} AS fecha, COALESCE(SUM(Peso),0) AS suma_peso,"
               " CASE WHEN COALESCE(SUM(Peso),0) > 0 THEN ROUND(COALESCE(SUM(Valor),0)/COALESCE(SUM(Peso),0),4) ELSE NULL END AS precio_kg"
               f" FROM ventasgeneral2{_from_v2_suffix} WHERE {fe} BETWEEN :d1 AND :d2"
               + where_linea_sql)
    if cod_item:
        sql_dia += ' AND CodigoItem = :cod_item'
    if mercado:
        sql_dia += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo"
    if provincia_filtro:
        sql_dia += " AND COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') = :prov"
    sql_dia += ' GROUP BY fecha ORDER BY fecha ASC'

    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_dia), bind)
        raw_dia = cur.fetchall() or []

    total_lineas = total_cantidad = total_peso = total_valor = 0.0
    filas, chart_labels, chart_precios, chart_pesos, chart_valores = [], [], [], [], []
    for i, r in enumerate(raw, 1):
        sp = float(r.get('suma_peso') or 0)
        sv = float(r.get('suma_valor') or 0)
        pk = r.get('precio_kg')
        prov = str(r.get('provincia') or '')
        total_lineas += int(r.get('lineas') or 0)
        total_cantidad += float(r.get('suma_cantidad') or 0)
        total_peso += sp
        total_valor += sv
        chart_labels.append(prov[:18])
        chart_precios.append(round(float(pk), 4) if pk is not None else None)
        chart_pesos.append(round(sp, 2))
        chart_valores.append(round(sv, 2))
        filas.append({'rank': i, 'provincia': prov, 'lineas': f"{int(r.get('lineas') or 0):,}",
                      'suma_cantidad': f"{float(r.get('suma_cantidad') or 0):,.2f}",
                      'suma_peso': f'{sp:,.2f}', 'suma_valor': f'S/ {sv:,.2f}',
                      'precio_kg': f'S/ {float(pk):,.2f}' if pk is not None else '—'})

    total_precio_kg = round(total_valor / total_peso, 4) if total_peso > 0 else None
    chart_fechas, chart_precios_dia = [], []
    for r in raw_dia:
        fecha = r.get('fecha')
        chart_fechas.append(fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha or ''))
        p = r.get('precio_kg')
        chart_precios_dia.append(round(float(p), 4) if p is not None else None)

    fmt = (_q(request, 'fmt') or '').lower()
    if fmt == 'json':
        return JSONResponse({'chart_data': {'labels': chart_labels, 'precios': chart_precios,
                                            'pesos': chart_pesos, 'valores': chart_valores,
                                            'fechas': chart_fechas, 'precios_dia': chart_precios_dia},
                             'total_precio_kg': total_precio_kg})

    ctx = _report_ctx(request, f'Ventas {linea} · Precio resumen por provincia')
    ctx.update({'d1': d1, 'd2': d2, 'linea': linea, 'tipo_fecha': tipo_fecha,
                'fecha_eje_leyenda': fecha_eje_leyenda, 'cod_item': cod_item or None,
                'mercado': mercado or None, 'filas': filas,
                'total_lineas': f'{int(total_lineas):,}', 'total_cantidad': f'{total_cantidad:,.2f}',
                'total_peso': f'{total_peso:,.2f}', 'total_valor': f'S/ {total_valor:,.2f}',
                'total_precio_kg': f'S/ {total_precio_kg:,.2f}' if total_precio_kg is not None else '—',
                'pdf_filename': f'linea_precio_resumen_provincia_{d1}_{d2}.pdf',
                'chart_data': {'labels': chart_labels, 'precios': chart_precios, 'pesos': chart_pesos,
                               'valores': chart_valores, 'fechas': chart_fechas,
                               'precios_dia': chart_precios_dia},
                'provincias_opts': provincias_opts, 'provincia_filtro': provincia_filtro,
                'body_class': 'app-page-reporte-wide'})
    return _tmpl(request, 'pages/reporte_linea_precio_resumen_provincia.html', ctx)


@router.get('/modules/reports/ventas-linea-precio-top-clientes')
def ventas_linea_precio_top_clientes(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta.')
    linea = _q(request, 'linea')
    if not linea:
        return _bad('Parámetro requerido: linea.')
    tipo_fecha = _tipo_fecha(request)
    fe = _sql_fecha_dimension(tipo_fecha)
    fecha_eje_leyenda = _fecha_eje_leyenda(tipo_fecha)
    try:
        top = max(1, min(500, int(request.query_params.get('top') or 50)))
    except (TypeError, ValueError):
        top = 50
    cod_item = _q(request, 'cod_item')
    mercado = _q(request, 'mercado').upper()
    provincia_filtro = _q(request, 'provincia')

    conn = get_connection()
    where_linea_sql, where_linea_bind = linea_where_fragment(conn, linea)
    _from_v2_suffix = index_hint_ventasgeneral2(conn, linea, tipo_fecha)
    sql = (f"SELECT CodigoCliente AS cod_cliente,"
           " MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,"
           " MAX(COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)')) AS provincia,"
           " COUNT(*) AS lineas, COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
           " COALESCE(SUM(Peso),0) AS suma_peso, COALESCE(SUM(Valor),0) AS suma_valor,"
           " CASE WHEN COALESCE(SUM(Peso),0) > 0"
           " THEN ROUND(COALESCE(SUM(Valor),0)/COALESCE(SUM(Peso),0),4) ELSE NULL END AS precio_kg"
           f" FROM ventasgeneral2{_from_v2_suffix} WHERE {fe} BETWEEN :d1 AND :d2"
           + where_linea_sql + " AND CodigoDocumento IN ('01','03')")
    bind: dict = {'d1': d1, 'd2': d2, **where_linea_bind}
    if cod_item:
        sql += ' AND CodigoItem = :cod_item'
        bind['cod_item'] = cod_item
    if mercado:
        sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo"
        bind['prefzo'] = mercado + '%'
    if provincia_filtro:
        sql += " AND COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') = :prov"
        bind['prov'] = provincia_filtro
    sql += " GROUP BY CodigoCliente HAVING COALESCE(SUM(Peso),0) > 0 ORDER BY precio_kg DESC"
    sql += f" LIMIT {top}"

    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []

    total_lineas = 0
    total_peso = 0.0
    total_valor = 0.0
    filas = []
    chart_labels: list = []
    chart_precios: list = []
    for i, r in enumerate(raw, 1):
        sp = float(r.get('suma_peso') or 0)
        sv = float(r.get('suma_valor') or 0)
        pk = r.get('precio_kg')
        total_lineas += int(r.get('lineas') or 0)
        total_peso += sp
        total_valor += sv
        nom = str(r.get('nombre_cliente') or '')
        chart_labels.append((nom[:22] + '…') if len(nom) > 23 else nom)
        chart_precios.append(round(float(pk), 4) if pk is not None else None)
        filas.append({
            'rank': i,
            'cod_cliente': str(r.get('cod_cliente') or ''),
            'nombre_cliente': nom,
            'provincia': str(r.get('provincia') or ''),
            'lineas': f"{int(r.get('lineas') or 0):,}",
            'suma_cantidad': f"{float(r.get('suma_cantidad') or 0):,.2f}",
            'suma_peso': f'{sp:,.2f}',
            'suma_valor': f'S/ {sv:,.2f}',
            'precio_kg': f'S/ {float(pk):,.2f}' if pk is not None else '—',
        })

    ctx = _report_ctx(request, f'Ventas {linea} · Top clientes por precio/kg')
    ctx.update({
        'd1': d1, 'd2': d2, 'linea': linea, 'top': top,
        'tipo_fecha': tipo_fecha, 'fecha_eje_leyenda': fecha_eje_leyenda,
        'cod_item': cod_item or None, 'mercado': mercado or None,
        'provincia_filtro': provincia_filtro, 'filas': filas,
        'total_lineas': f'{total_lineas:,}',
        'total_peso': f'{total_peso:,.2f}',
        'total_valor': f'S/ {total_valor:,.2f}',
        'pdf_filename': f'linea_precio_top_clientes_{d1}_{d2}.pdf',
        'chart_data': {'labels': chart_labels, 'precios': chart_precios},
        'body_class': 'app-page-reporte-wide',
    })
    return _tmpl(request, 'pages/reporte_linea_precio_top_clientes.html', ctx)


@router.get('/modules/reports/ventas-linea-diario-provincia')
def ventas_linea_diario_provincia(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta.')
    linea = _q(request, 'linea')
    if not linea:
        return _bad('Parámetro requerido: linea.')
    tipo_fecha = _tipo_fecha(request)
    fe = _sql_fecha_dimension(tipo_fecha)
    fecha_eje_leyenda = _fecha_eje_leyenda(tipo_fecha)
    fecha_columna_th = _fecha_columna_th(tipo_fecha)
    try:
        top = max(1, min(10_000, int(request.query_params.get('top') or 2000)))
    except (TypeError, ValueError):
        top = 2000
    cod_item = _q(request, 'cod_item')
    mercado = _q(request, 'mercado').upper()
    f_provincias = _ql(request, 'provincia')
    f_corporativos = _ql(request, 'corporativo')
    f_clientes = _ql(request, 'cliente')

    conn = get_connection()
    where_linea_sql, where_linea_bind = linea_where_fragment(conn, linea)
    _from_v2_suffix = index_hint_ventasgeneral2(conn, linea, tipo_fecha)
    base_where = (f" WHERE {fe} BETWEEN :d1 AND :d2" + where_linea_sql + " AND CodigoDocumento IN ('01','03')")
    base_bind: dict = {'d1': d1, 'd2': d2, **where_linea_bind}
    if cod_item:
        base_where += ' AND CodigoItem = :cod_item'
        base_bind['cod_item'] = cod_item
    if mercado:
        base_where += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo"
        base_bind['prefzo'] = mercado + '%'

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
           " COUNT(*) AS lineas, COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
           " COALESCE(SUM(Peso),0) AS suma_peso, COALESCE(SUM(Valor),0) AS suma_valor,"
           " CASE WHEN COALESCE(SUM(Peso),0) > 0 THEN ROUND(COALESCE(SUM(Valor),0)/COALESCE(SUM(Peso),0),2) ELSE NULL END AS precio_kg"
           f" FROM ventasgeneral2{_from_v2_suffix}{ext_where}"
           f" GROUP BY fecha, provincia, CodigoCliente ORDER BY fecha ASC, suma_peso DESC LIMIT {top}")
    sql_dia = (f"SELECT {fe} AS fecha, COALESCE(SUM(Peso),0) AS suma_peso, COALESCE(SUM(Valor),0) AS suma_valor"
               f" FROM ventasgeneral2{_from_v2_suffix}{ext_where} GROUP BY fecha ORDER BY fecha ASC")

    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_dia), bind)
        raw_dia = cur.fetchall() or []

    filas = []
    for i, r in enumerate(raw, 1):
        fecha = r.get('fecha')
        sp = float(r.get('suma_peso') or 0)
        sv = float(r.get('suma_valor') or 0)
        pk = r.get('precio_kg')
        filas.append({'rank': i, 'fecha': fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha or ''),
                      'provincia': str(r.get('provincia') or ''),
                      'nombre_corporativo': str(r.get('nombre_corporativo') or ''),
                      'cod_cliente': str(r.get('cod_cliente') or ''),
                      'nombre_cliente': str(r.get('nombre_cliente') or ''),
                      'lineas': f"{int(r.get('lineas') or 0):,}",
                      'suma_cantidad': f"{float(r.get('suma_cantidad') or 0):,.2f}",
                      'suma_peso': f'{sp:,.2f}', 'suma_valor': f'{sv:,.2f}',
                      'precio_kg': f'S/ {float(pk):.2f}' if pk is not None else '—'})

    chart_fechas, chart_pesos_dia, chart_valores_dia = [], [], []
    for r in raw_dia:
        fecha = r.get('fecha')
        chart_fechas.append(fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha or ''))
        chart_pesos_dia.append(round(float(r.get('suma_peso') or 0), 2))
        chart_valores_dia.append(round(float(r.get('suma_valor') or 0), 2))

    total_peso = sum(chart_pesos_dia)
    total_valor = sum(chart_valores_dia)

    ctx = _report_ctx(request, f'Ventas {linea} · Diario por provincia/cliente')
    ctx.update({'d1': d1, 'd2': d2, 'linea': linea, 'top': top,
                'tipo_fecha': tipo_fecha, 'fecha_eje_leyenda': fecha_eje_leyenda,
                'fecha_columna_th': fecha_columna_th, 'filas': filas,
                'total_peso': f'{total_peso:,.2f}', 'total_valor': f'{total_valor:,.2f}',
                'pdf_filename': f'linea_diario_{d1}_{d2}.pdf',
                'chart_data': {'fechas': chart_fechas, 'pesos': chart_pesos_dia,
                               'valores': chart_valores_dia, 'modo': 'total', 'series_clientes': []},
                'provincias_opts': provincias_opts, 'corporativos_opts': corporativos_opts,
                'clientes_opts': clientes_opts, 'f_provincias': f_provincias,
                'f_corporativos': f_corporativos, 'f_clientes': f_clientes, 'opts_tree': opts_tree,
                'body_class': 'app-page-reporte-wide'})
    return _tmpl(request, 'pages/reporte_linea_diario_provincia.html', ctx)


@router.get('/modules/reports/ventas-linea-precio-diario')
def ventas_linea_precio_diario(request: Request):
    if err := _require_login(request):
        return err
    d1 = _parse_date_string(_q(request, 'desde') or _q(request, 'fecha_desde'))
    d2 = _parse_date_string(_q(request, 'hasta') or _q(request, 'fecha_hasta'))
    if not d1 or not d2 or d1 > d2:
        return _bad('Parámetros requeridos: desde y hasta.')
    linea = _q(request, 'linea')
    if not linea:
        return _bad('Parámetro requerido: linea.')
    tipo_fecha = _tipo_fecha(request)
    fe = _sql_fecha_dimension(tipo_fecha)
    fecha_eje_leyenda = _fecha_eje_leyenda(tipo_fecha)
    fecha_columna_th = _fecha_columna_th(tipo_fecha)
    try:
        top = max(1, min(10_000, int(request.query_params.get('top') or 2000)))
    except (TypeError, ValueError):
        top = 2000
    cod_item = _q(request, 'cod_item')
    mercado = _q(request, 'mercado').upper()
    f_provincias = _ql(request, 'provincia')
    f_corporativos = _ql(request, 'corporativo')
    f_clientes = _ql(request, 'cliente')

    conn = get_connection()
    where_linea_sql, where_linea_bind = linea_where_fragment(conn, linea)
    _from_v2_suffix = index_hint_ventasgeneral2(conn, linea, tipo_fecha)
    base_where = (f" WHERE {fe} BETWEEN :d1 AND :d2" + where_linea_sql + " AND CodigoDocumento IN ('01','03')")
    base_bind: dict = {'d1': d1, 'd2': d2, **where_linea_bind}
    if cod_item:
        base_where += ' AND CodigoItem = :cod_item'
        base_bind['cod_item'] = cod_item
    if mercado:
        base_where += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo"
        base_bind['prefzo'] = mercado + '%'

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
           " COUNT(*) AS lineas, COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
           " COALESCE(SUM(Peso),0) AS suma_peso, COALESCE(SUM(Valor),0) AS suma_valor,"
           " CASE WHEN COALESCE(SUM(Peso),0) > 0 THEN ROUND(COALESCE(SUM(Valor),0)/COALESCE(SUM(Peso),0),4) ELSE NULL END AS precio_kg"
           f" FROM ventasgeneral2{_from_v2_suffix}{ext_where}"
           f" GROUP BY fecha, provincia, CodigoCliente ORDER BY fecha ASC, suma_peso DESC LIMIT {top}")
    sql_precio = (f"SELECT {fe} AS fecha, COALESCE(SUM(Peso),0) AS suma_peso, COALESCE(SUM(Valor),0) AS suma_valor,"
                  " CASE WHEN COALESCE(SUM(Peso),0) > 0 THEN ROUND(COALESCE(SUM(Valor),0)/COALESCE(SUM(Peso),0),4) ELSE NULL END AS precio_kg"
                  f" FROM ventasgeneral2{_from_v2_suffix}{ext_where} GROUP BY fecha ORDER BY fecha ASC")

    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql), bind)
        raw = cur.fetchall() or []
    with conn.cursor() as cur:
        cur.execute(_colon_params_to_pymysql(sql_precio), bind)
        raw_precio = cur.fetchall() or []

    filas = []
    rank = 0
    for r in raw:
        fecha = r.get('fecha')
        precio = r.get('precio_kg')
        rank += 1
        filas.append({'rank': rank,
                      'fecha': fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha or ''),
                      'provincia': str(r.get('provincia') or ''),
                      'nombre_corporativo': str(r.get('nombre_corporativo') or ''),
                      'cod_cliente': str(r.get('cod_cliente') or ''),
                      'nombre_cliente': str(r.get('nombre_cliente') or ''),
                      'lineas': f"{int(r.get('lineas') or 0):,}",
                      'suma_cantidad': f"{float(r.get('suma_cantidad') or 0):,.2f}",
                      'suma_peso': f"{float(r.get('suma_peso') or 0):,.2f}",
                      'suma_valor': f"{float(r.get('suma_valor') or 0):,.2f}",
                      'precio_kg': f"S/ {float(precio):,.2f}" if precio is not None else '—'})

    chart_fechas, chart_precios = [], []
    total_peso_periodo = total_valor_periodo = 0.0
    for r in raw_precio:
        fecha = r.get('fecha')
        chart_fechas.append(fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha or ''))
        p = r.get('precio_kg')
        chart_precios.append(round(float(p), 4) if p is not None else None)
        total_peso_periodo += float(r.get('suma_peso') or 0)
        total_valor_periodo += float(r.get('suma_valor') or 0)
    total_precio_kg_periodo = total_valor_periodo / total_peso_periodo if total_peso_periodo > 0 else None

    ctx = _report_ctx(request, f'Ventas {linea} · Precio por día provincia/cliente')
    ctx.update({'d1': d1, 'd2': d2, 'linea': linea, 'top': top,
                'tipo_fecha': tipo_fecha, 'fecha_eje_leyenda': fecha_eje_leyenda,
                'fecha_columna_th': fecha_columna_th, 'filas': filas,
                'total_peso': f'{total_peso_periodo:,.2f}', 'total_valor': f'{total_valor_periodo:,.2f}',
                'total_precio_kg_periodo': f'S/ {total_precio_kg_periodo:,.2f}' if total_precio_kg_periodo is not None else '—',
                'pdf_filename': f'linea_precio_diario_{d1}_{d2}.pdf',
                'chart_data': {'fechas': chart_fechas, 'precios': chart_precios,
                               'modo': 'total', 'series_clientes': []},
                'chart_data_tdoc': {'fechas': [], 'series': {}},
                'chart_data_tdoc_clientes': [],
                'provincias_opts': provincias_opts, 'corporativos_opts': corporativos_opts,
                'clientes_opts': clientes_opts, 'f_provincias': f_provincias,
                'f_corporativos': f_corporativos, 'f_clientes': f_clientes, 'opts_tree': opts_tree,
                'body_class': 'app-page-reporte-wide'})
    return _tmpl(request, 'pages/reporte_linea_precio_diario.html', ctx)


@router.get('/modules/reports/{slug}')
def report_placeholder(slug: str, request: Request):
    if err := _require_login(request):
        return err
    if slug not in REPORT_PLACEHOLDER_SLUGS:
        raise HTTPException(status_code=404)
    ctx = _report_ctx(request, 'Informe')
    ctx.update({'report_slug': slug,
                'report_query': str(request.query_string if hasattr(request, 'query_string')
                                    else request.url.query or '')})
    return _tmpl(request, 'pages/reporte_placeholder.html', ctx)
