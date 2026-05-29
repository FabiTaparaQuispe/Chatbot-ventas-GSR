import json
import logging
import traceback
from datetime import date
from urllib.parse import urlencode

_log = logging.getLogger(__name__)

from services.linea_codigo import index_hint_ventasgeneral2, linea_where_fragment
from services.sql_guard import validate_select_sql, apply_pagination, build_count_sql, SqlGuardError
from services.urlmap import (
    REPORT_SLUG_PARETO_CLIENTES_ZONA,
    REPORT_SLUG_PARETO_NC_ZONA,
    REPORT_SLUG_VENTAS_BARRAS_CORPORATIVO,
    REPORT_SLUG_VENTAS_BARRAS_DIMENSION,
    REPORT_SLUG_VENTAS_BARRAS_RUTA,
    REPORT_SLUG_VENTAS_COMPARATIVO,
    REPORT_SLUG_VENTAS_LINEA_DIARIO_PROVINCIA,
    REPORT_SLUG_VENTAS_LINEA_MIX_PRODUCTOS,
    REPORT_SLUG_VENTAS_LINEA_PRECIO_DIARIO,
    REPORT_SLUG_VENTAS_LINEA_PRECIO_RESUMEN_PROV,
    REPORT_SLUG_VENTAS_LINEA_RESUMEN_PROVINCIA,
    REPORT_SLUG_VENTAS_MIX_TDOC,
    REPORT_SLUG_VENTAS_RESUMEN_POR_LINEA,
    REPORT_SLUG_VENTAS_RESUMEN_POR_PROVINCIA,
    REPORT_SLUG_VENTAS_CLIENTES_CORPORATIVO,
    REPORT_SLUG_VENTAS_SERIE_MENSUAL,
    REPORT_SLUG_VENTAS_TOP_CLIENTES_GLOBAL,
    REPORT_SLUG_VENTAS_TOP_CLIENTES_NC,
    REPORT_SLUG_VENTAS_TOP_PRODUCTOS,
    REPORT_VENTASGENERAL_BUSCAR_TABLA,
    REPORT_VENTASGENERAL_RESUMEN_TABLA,
    report_slug_url,
)

MAX_LIMIT = 100
DEFAULT_LIMIT = 50

DEFAULT_POR_PAGINA = 50
MIN_POR_PAGINA = 10
MAX_POR_PAGINA = 100

_TOOL_REGISTRY: dict[str, str] = {}


def tool(name: str):
    """Registra un método de ToolExecutor como handler del tool dado."""
    def decorator(fn):
        _TOOL_REGISTRY[name] = fn.__name__
        return fn
    return decorator


def _parse_date(val, key='fecha', required=True):
    if val is None or val == '':
        if required:
            raise ValueError(f'Falta parámetro de fecha: {key}')
        return None
    s = str(val).strip()
    try:
        d = date.fromisoformat(s)
        if d.strftime('%Y-%m-%d') != s:
            raise ValueError()
    except Exception:
        raise ValueError(f'Fecha inválida (use YYYY-MM-DD): {key}')
    return s


def _parse_date_range(args, from_key='fecha_desde', to_key='fecha_hasta'):
    d1 = _parse_date(args.get(from_key), from_key)
    d2 = _parse_date(args.get(to_key), to_key)
    if d1 > d2:
        raise ValueError(f'{from_key} no puede ser mayor que {to_key}')
    return d1, d2


def _int_arg(v, default, min_val, max_val):
    if v is None or v == '':
        return default
    try:
        n = int(v)
    except (ValueError, TypeError):
        return default
    return max(min_val, min(max_val, n))


def _clamp_limit(n, default=DEFAULT_LIMIT):
    if n is None:
        return default
    return max(1, min(MAX_LIMIT, int(n)))


def _parse_pagina(args, default=1):
    """Página solicitada por el LLM. 1-indexada, mínimo 1."""
    v = args.get('pagina') if isinstance(args, dict) else None
    if v is None or v == '':
        return default
    try:
        n = int(v)
    except (ValueError, TypeError):
        return default
    return max(1, n)


def _parse_por_pagina(args, default=DEFAULT_POR_PAGINA,
                     min_v=MIN_POR_PAGINA, max_v=MAX_POR_PAGINA):
    """Tamaño de página solicitado por el LLM, acotado a [min_v, max_v]."""
    v = args.get('por_pagina') if isinstance(args, dict) else None
    if v is None or v == '':
        return default
    try:
        n = int(v)
    except (ValueError, TypeError):
        return default
    return max(min_v, min(max_v, n))


def _pagination_offset(pagina, por_pagina):
    return max(0, (max(1, int(pagina)) - 1) * max(1, int(por_pagina)))


def _pagination_meta(total_rows, pagina, por_pagina):
    """Construye el bloque 'paginacion' que se devuelve al LLM/frontend."""
    pp = max(1, int(por_pagina))
    pg = max(1, int(pagina))
    total = max(0, int(total_rows or 0))
    total_paginas = (total + pp - 1) // pp if total > 0 else 0
    return {
        'pagina': pg,
        'por_pagina': pp,
        'total_filas': total,
        'total_paginas': total_paginas,
        'hay_siguiente': pg < total_paginas,
        'hay_anterior': pg > 1 and total_paginas > 0,
    }


def _paginate_list(rows, pagina, por_pagina):
    """Slicing en memoria (para tools que post-procesan en Python, ej. pareto)."""
    pp = max(1, int(por_pagina))
    pg = max(1, int(pagina))
    start = (pg - 1) * pp
    return rows[start:start + pp]


def _count_query(conn, sql_count, params):
    """Ejecuta un COUNT(*) y devuelve un entero seguro."""
    row = _q1(conn, sql_count, params) or {}
    val = row.get('total') if 'total' in row else (next(iter(row.values())) if row else 0)
    try:
        return int(val or 0)
    except (ValueError, TypeError):
        return 0


def _dimension(v):
    d = str(v or 'precio').lower().strip()
    if d not in ('precio', 'comercial'):
        raise ValueError('dimension debe ser precio o comercial')
    return d


def _col_etiqueta(dimension):
    if dimension == 'precio':
        return "COALESCE(NULLIF(TRIM(DescripcionZonaPrecio),''),'(sin zona precio)')"
    if dimension == 'comercial':
        return "COALESCE(NULLIF(TRIM(ZonaComercial),''),'(sin zona comercial)')"
    if dimension == 'ruta':
        return "COALESCE(NULLIF(TRIM(RutaComercial),''),'(sin ruta)')"
    if dimension == 'corporativo':
        return "COALESCE(NULLIF(TRIM(NombreCoorporativo),''),'(sin corporativo)')"
    raise ValueError('dimension inválida')


def _qs(params):
    return urlencode({k: v for k, v in params.items() if v is not None and v != ''})


def _report_canonical(path: str, params: dict) -> str:
    q = _qs(params)
    return path + ('?' + q if q else '')


def _q(conn, sql, params):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def _q1(conn, sql, params):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def sql_interpolate(sql, params):
    out = sql
    for k, v in sorted(params.items(), key=lambda x: -len(str(x[0]))):
        literal = _literal(v)
        out = out.replace(f'%({k})s', literal, 1)
    return out


def _literal(v):
    if v is None:
        return 'NULL'
    if isinstance(v, bool):
        return '1' if v else '0'
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace('\\', '\\\\').replace("'", "\\'")
    return f"'{s}'"


class SqlInterpolator:
    def __init__(self):
        self._traces = []

    def record(self, sql, params):
        interp = sql
        for k, v in sorted(params.items(), key=lambda x: -len(str(x[0]))):
            interp = interp.replace(k, _literal(v))
        self._traces.append(interp)

    def pull(self):
        t = self._traces[:]
        self._traces.clear()
        return t


class ToolExecutor:
    def __init__(self, conn, prev_result=None):
        self._conn = conn
        self._sql_traces = []
        self._last_tool_json: str | None = None
        self._prev_result = prev_result  # dict or None

    def pull_sql_traces(self):
        t = self._sql_traces[:]
        self._sql_traces.clear()
        return t

    def pull_last_tool_json(self) -> str | None:
        j = self._last_tool_json
        self._last_tool_json = None
        return j

    async def execute_async(self, name: str, args: dict) -> str:
        """Versión async de execute(): corre el trabajo síncrono en el thread pool."""
        import asyncio
        return await asyncio.to_thread(self.execute, name, args)

    def execute(self, name, args):
        try:
            method_name = _TOOL_REGISTRY.get(name)
            if method_name is None:
                result = {'error': f'Función no reconocida: {name}'}
            else:
                result = getattr(self, method_name)(args)
        except ValueError as e:
            result = {
                'error': str(e),
                'accion_para_el_asistente': (
                    'Pregunta al usuario en español, de forma concreta, por el dato que falta o el formato correcto '
                    '(fechas YYYY-MM-DD). No inventes valores. Cuando el usuario responda, vuelve a llamar esta '
                    'herramienta con todos los parámetros requeridos.'
                ),
            }
        except Exception as e:
            _log.error('tool_executor error [%s]: %s\n%s', name, e, traceback.format_exc())
            result = {'error': str(e)}

        traces = result.pop('_sql_traces', [])
        for t in (traces or []):
            if isinstance(t, dict) and 'sql' in t and 'params' in t:
                interp = t['sql']
                for k, v in sorted(t['params'].items(), key=lambda x: -len(str(x[0]))):
                    interp = interp.replace(f'%({k})s', _literal(v))
                self._sql_traces.append(interp)
            elif isinstance(t, str):
                self._sql_traces.append(t)

        result_json = json.dumps(result, ensure_ascii=False, default=str)
        if not result.get('error'):
            self._last_tool_json = result_json
        return result_json

    @tool('ventasgeneral_resumen')
    def _resumen(self, args):
        d1, d2 = _parse_date_range(args)
        sql = ('SELECT COUNT(*) AS filas, COALESCE(SUM(Valor),0) AS suma_valor,'
               ' COALESCE(SUM(Cantidad),0) AS suma_cantidad, COALESCE(SUM(Peso),0) AS suma_peso'
               ' FROM ventasgeneral2 WHERE FechaContable BETWEEN %(d1)s AND %(d2)s')
        params = {'d1': d1, 'd2': d2}

        linea = str(args.get('linea_comercial') or '').strip()
        if linea:
            _linea_where, _linea_bind = linea_where_fragment(self._conn, linea, style='pyformat')
            sql += _linea_where
            params.update(_linea_bind)

        zona = str(args.get('zona_comercial') or '').strip()
        if zona:
            sql += ' AND ZonaComercial LIKE %(zona)s'
            params['zona'] = f'%{zona}%'
        cod = str(args.get('cod_cliente') or '').strip()
        if cod:
            sql += ' AND CodigoCliente = %(cod)s'
            params['cod'] = cod
        nom_cli = str(args.get('nombre_cliente') or '').strip()
        if nom_cli:
            sql += ' AND NombreCliente LIKE %(nom_cli)s'
            params['nom_cli'] = f'%{nom_cli}%'
        nom_corp = str(args.get('nombre_corporativo') or '').strip()
        if nom_corp:
            sql += ' AND NombreCoorporativo LIKE %(nom_corp)s'
            params['nom_corp'] = f'%{nom_corp}%'
        pref_z = str(args.get('prefijo_descri_zona_precio') or '').strip().upper()
        if pref_z:
            sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE %(prefzp)s"
            params['prefzp'] = pref_z + '%'
        prov = str(args.get('provincia') or '').strip()
        if prov:
            sql += ' AND Provincia LIKE %(prov)s'
            params['prov'] = f'%{prov}%'
        tdoc = str(args.get('tipo_documento') or '').strip()
        if tdoc:
            sql += ' AND TipoDocumento LIKE %(tdoc)s'
            params['tdoc'] = f'%{tdoc}%'
        cod_doc = str(args.get('codigo_documento') or '').strip()
        if cod_doc:
            sql += ' AND CodigoDocumento = %(cod_doc)s'
            params['cod_doc'] = cod_doc
        excluir_nc = str(args.get('excluir_nc') or '').strip().lower() in ('true', '1', 'yes', 'si', 'sí')
        if excluir_nc:
            sql += " AND CodigoDocumento != '07'"

        row = _q1(self._conn, sql, params) or {}
        q = {'fecha_desde': d1, 'fecha_hasta': d2}
        if linea:
            q['linea_comercial'] = linea
        if zona:
            q['zona_comercial'] = zona
        if cod:
            q['cod_cliente'] = cod
        if nom_cli:
            q['nombre_cliente'] = nom_cli
        if nom_corp:
            q['nombre_corporativo'] = nom_corp
        if pref_z:
            q['prefijo_descri_zona_precio'] = pref_z
        if prov:
            q['provincia'] = prov
        if tdoc:
            q['tipo_documento'] = tdoc
        if cod_doc:
            q['codigo_documento'] = cod_doc

        return {
            'tabla': 'ventasgeneral2',
            'periodo': {'desde': d1, 'hasta': d2},
            'agregados': {k: (float(v) if v is not None else 0) if k != 'filas' else int(v or 0) for k, v in row.items()},
            'reporte_url': _report_canonical(REPORT_VENTASGENERAL_RESUMEN_TABLA, q),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('ventasgeneral_buscar')
    def _buscar(self, args):
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)
        offset = _pagination_offset(pagina, por_pagina)

        where_sql = ' FROM ventasgeneral2 WHERE 1=1'
        params = {}

        fd = _parse_date(args.get('fecha_desde'), 'fecha_desde', required=False)
        fh = _parse_date(args.get('fecha_hasta'), 'fecha_hasta', required=False)
        if fd and fh:
            if fd > fh:
                raise ValueError('fecha_desde no puede ser mayor que fecha_hasta')
            where_sql += ' AND FechaContable BETWEEN %(fd)s AND %(fh)s'
            params['fd'] = fd
            params['fh'] = fh
        elif fd:
            where_sql += ' AND FechaContable >= %(fd)s'
            params['fd'] = fd
        elif fh:
            where_sql += ' AND FechaContable <= %(fh)s'
            params['fh'] = fh

        nom = str(args.get('nombre_cliente') or '').strip()
        if nom:
            where_sql += ' AND NombreCliente LIKE %(nom)s'
            params['nom'] = f'%{nom}%'
        nom_corp = str(args.get('nombre_corporativo') or '').strip()
        if nom_corp:
            where_sql += ' AND NombreCoorporativo LIKE %(nom_corp)s'
            params['nom_corp'] = f'%{nom_corp}%'
        ndoc = str(args.get('numero_doc') or '').strip()
        if ndoc:
            where_sql += ' AND NumeroFactura LIKE %(ndoc)s'
            params['ndoc'] = f'%{ndoc}%'
        item = str(args.get('cod_item') or '').strip()
        if item:
            where_sql += ' AND CodigoItem = %(item)s'
            params['item'] = item
        tdoc = str(args.get('tdoc') or '').strip()
        if tdoc:
            if len(tdoc) > 4:
                raise ValueError('tdoc demasiado largo')
            where_sql += ' AND CodigoDocumento = %(tdoc)s'
            params['tdoc'] = tdoc
        pref_z = str(args.get('prefijo_descri_zona_precio') or '').strip().upper()
        if pref_z:
            where_sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE %(prefzp)s"
            params['prefzp'] = pref_z + '%'
        prov = str(args.get('provincia') or '').strip()
        if prov:
            where_sql += ' AND Provincia LIKE %(prov)s'
            params['prov'] = f'%{prov}%'
        tdoctipo = str(args.get('tipo_documento') or '').strip()
        if tdoctipo:
            where_sql += ' AND TipoDocumento LIKE %(tdoctipo)s'
            params['tdoctipo'] = f'%{tdoctipo}%'

        sql_count = 'SELECT COUNT(*) AS total' + where_sql
        total_rows = _count_query(self._conn, sql_count, params)

        sql_select = (
            'SELECT id, FechaContable, CodigoCoorporativo, NombreCoorporativo, CodigoCliente,'
            ' NombreCliente, CodigoDocumento, TipoDocumento, SerieDocumento, NumeroDocumento,'
            ' NumeroFactura, CodigoItem, GlosaDetalle, Cantidad, Peso, Valor,'
            ' ZonaComercial, DescripcionZonaPrecio, RutaComercial, Provincia, LineaComercial'
            + where_sql
            + f' ORDER BY FechaContable DESC, id DESC LIMIT {por_pagina} OFFSET {offset}'
        )
        rows = _q(self._conn, sql_select, params)

        tab_args = {k: str(v) for k, v in {
            'fecha_desde': fd, 'fecha_hasta': fh, 'nombre_cliente': nom,
            'nombre_corporativo': nom_corp,
            'numero_doc': ndoc, 'cod_item': item, 'tdoc': tdoc,
            'prefijo_descri_zona_precio': pref_z, 'provincia': prov,
            'tipo_documento': tdoctipo,
            'pagina': pagina, 'por_pagina': por_pagina,
        }.items() if v is not None and str(v) != ''}

        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'buscar',
            'count_devuelto': len(rows),
            'paginacion': _pagination_meta(total_rows, pagina, por_pagina),
            'filas': [dict(r) for r in rows],
            'reporte_url': _report_canonical(REPORT_VENTASGENERAL_BUSCAR_TABLA, tab_args),
            '_sql_traces': [
                {'sql': sql_count, 'params': params},
                {'sql': sql_select, 'params': params},
            ],
        }

    @tool('ventasgeneral_pareto_nc_zonaprecio')
    def _pareto_nc(self, args):
        d1, d2 = _parse_date_range(args)
        max_z = _int_arg(args.get('max_zonas'), 100, 1, 200)
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)
        sql = ("SELECT COALESCE(NULLIF(TRIM(DescripcionZonaPrecio),''),'(sin zona)') AS zona,"
               " COUNT(*) AS lineas_nc,"
               " COALESCE(SUM(ABS(Valor)),0) AS impacto_abs_valor"
               " FROM ventasgeneral2"
               " WHERE FechaContable BETWEEN %(d1)s AND %(d2)s AND CodigoDocumento = '07'"
               " GROUP BY COALESCE(NULLIF(TRIM(DescripcionZonaPrecio),''),'(sin zona)')"
               f" ORDER BY impacto_abs_valor DESC LIMIT {max_z}")
        params = {'d1': d1, 'd2': d2}
        raw = _q(self._conn, sql, params)
        total = sum(float(r.get('impacto_abs_valor') or 0) for r in raw)
        cum = 0.0
        filas_all = []
        hasta80 = 0
        for i, r in enumerate(raw):
            imp = float(r.get('impacto_abs_valor') or 0)
            pct = (imp / total * 100) if total else 0.0
            cum += pct
            filas_all.append({
                'zona': str(r.get('zona') or ''),
                'lineas_nc': int(r.get('lineas_nc') or 0),
                'impacto_abs_valor': imp,
                'pct_del_total': round(pct, 2),
                'pct_acumulado': round(cum, 2),
            })
            if hasta80 == 0 and cum >= 80.0:
                hasta80 = i + 1
        if hasta80 == 0 and filas_all:
            hasta80 = len(filas_all)
        filas = _paginate_list(filas_all, pagina, por_pagina)
        q = _qs({'desde': d1, 'hasta': d2, 'max': max_z})
        return {
            'tabla': 'ventasgeneral2',
            'criterio_nc': "TDoc = '07' (notas de crédito en ETL ventasgeneral)",
            'agrupacion': 'DescripcionZonaPrecio',
            'periodo': {'desde': d1, 'hasta': d2},
            'total_impacto_nc_valor_abs': total,
            'filas_pareto': filas,
            'paginacion': _pagination_meta(len(filas_all), pagina, por_pagina),
            'zonas_hasta_80pct_aprox': hasta80,
            'reporte_url': report_slug_url(REPORT_SLUG_PARETO_NC_ZONA, q),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('ventasgeneral_top_clientes_zona_precio')
    def _top_clientes_zona(self, args):
        d1, d2 = _parse_date_range(args)
        pref = str(args.get('prefijo_descri_zona_precio') or '').strip().upper()
        if not pref:
            raise ValueError('Falta prefijo_descri_zona_precio (ej. LAJOYA)')
        top = _int_arg(args.get('top_n'), 10, 1, 100)
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)
        like = pref + '%'

        sql_total = ("SELECT COALESCE(SUM(Valor), 0) AS total_valor FROM ventasgeneral2"
                     " WHERE FechaContable BETWEEN %(d1)s AND %(d2)s"
                     " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio, ''))) LIKE %(pref)s")
        p_total = {'d1': d1, 'd2': d2, 'pref': like}
        total_row = _q1(self._conn, sql_total, p_total) or {}
        total_zona = float(total_row.get('total_valor') or 0)

        sql = ("SELECT CodigoCliente,"
               " MAX(COALESCE(NULLIF(TRIM(NombreCliente), ''), '(sin nombre)')) AS nombre_cliente,"
               " COALESCE(SUM(Valor), 0) AS suma_valor, COUNT(*) AS lineas_venta"
               " FROM ventasgeneral2"
               " WHERE FechaContable BETWEEN %(d1)s AND %(d2)s"
               " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio, ''))) LIKE %(pref)s"
               " GROUP BY CodigoCliente"
               f" ORDER BY suma_valor DESC LIMIT {top}")
        params = {'d1': d1, 'd2': d2, 'pref': like}
        raw = _q(self._conn, sql, params)

        cum = 0.0
        filas_all = []
        hasta80 = 0
        for i, r in enumerate(raw):
            sv = float(r.get('suma_valor') or 0)
            pct = (sv / total_zona * 100) if total_zona else 0.0
            cum += pct
            filas_all.append({
                'cod_cliente': str(r.get('CodigoCliente') or ''),
                'nombre_cliente': str(r.get('nombre_cliente') or ''),
                'suma_valor': sv,
                'lineas_venta': int(r.get('lineas_venta') or 0),
                'pct_del_total_zona': round(pct, 2),
                'pct_acumulado': round(cum, 2),
            })
            if hasta80 == 0 and cum >= 80.0:
                hasta80 = i + 1
        if hasta80 == 0 and filas_all:
            hasta80 = len(filas_all)
        filas = _paginate_list(filas_all, pagina, por_pagina)

        q = _qs({'desde': d1, 'hasta': d2, 'prefijo': pref, 'top': top})
        return {
            'tabla': 'ventasgeneral2',
            'criterio': 'SUM(Valor) por CodigoCliente; solo líneas con DescripcionZonaPrecio LIKE prefijo%',
            'agrupacion': 'CodigoCliente (NombreCliente)',
            'periodo': {'desde': d1, 'hasta': d2},
            'prefijo_descri_zona_precio': pref,
            'total_valor_zona': total_zona,
            'filas_ranking': filas,
            'paginacion': _pagination_meta(len(filas_all), pagina, por_pagina),
            'clientes_hasta_80pct_aprox': hasta80,
            'reporte_url': report_slug_url(REPORT_SLUG_PARETO_CLIENTES_ZONA, q),
            '_sql_traces': [
                {'sql': sql_total, 'params': p_total},
                {'sql': sql, 'params': params},
            ],
        }

    @tool('ventasgeneral_barras_ventas_dimension')
    def _barras_dimension(self, args):
        d1, d2 = _parse_date_range(args)
        dim = _dimension(args.get('dimension', 'precio'))
        top = _int_arg(args.get('top_n'), 20, 1, 100)
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)
        expr = _col_etiqueta(dim)
        sql = (f"SELECT {expr} AS etiqueta, COUNT(*) AS lineas,"
               " COALESCE(SUM(Valor),0) AS suma_valor,"
               " COALESCE(SUM(Cantidad),0) AS suma_quantidade, COALESCE(SUM(Peso),0) AS suma_peso"
               " FROM ventasgeneral2 WHERE FechaContable BETWEEN %(d1)s AND %(d2)s"
               f" GROUP BY {expr} ORDER BY suma_valor DESC LIMIT {top}")
        params = {'d1': d1, 'd2': d2}
        raw = _q(self._conn, sql, params)
        total_row = _q1(self._conn,
            'SELECT COALESCE(SUM(Valor),0) AS t FROM ventasgeneral2 WHERE FechaContable BETWEEN %(d1)s AND %(d2)s',
            params)
        total = float((total_row or {}).get('t') or 0)
        filas_all = []
        for r in raw:
            sv = float(r.get('suma_valor') or 0)
            filas_all.append({
                'etiqueta': str(r.get('etiqueta') or ''),
                'lineas': int(r.get('lineas') or 0),
                'suma_valor': sv,
                'suma_cantidad': float(r.get('suma_quantidade') or 0),
                'suma_peso': float(r.get('suma_peso') or 0),
                'pct_del_total': round(sv / total * 100, 2) if total else 0.0,
            })
        filas = _paginate_list(filas_all, pagina, por_pagina)
        q = _qs({'desde': d1, 'hasta': d2, 'dim': dim, 'top': top})
        return {
            'tabla': 'ventasgeneral2',
            'tipo': f'barras_por_{dim}',
            'periodo': {'desde': d1, 'hasta': d2},
            'total_valor_periodo': total,
            'filas': filas,
            'paginacion': _pagination_meta(len(filas_all), pagina, por_pagina),
            'reporte_url': report_slug_url(REPORT_SLUG_VENTAS_BARRAS_DIMENSION, q),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('ventasgeneral_comparativo_periodos')
    def _comparativo(self, args):
        a1, a2 = _parse_date_range(args, 'fecha_desde_a', 'fecha_hasta_a')
        b1, b2 = _parse_date_range(args, 'fecha_desde_b', 'fecha_hasta_b')
        dim = _dimension(args.get('dimension', 'precio'))
        top = _int_arg(args.get('top_n'), 15, 1, 80)
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)
        expr = _col_etiqueta(dim)
        sql = (f"SELECT etiqueta, SUM(va) AS valor_a, SUM(vb) AS valor_b FROM ("
               f"  SELECT {expr} AS etiqueta, COALESCE(SUM(Valor),0) AS va, 0 AS vb"
               f"  FROM ventasgeneral2 WHERE FechaContable BETWEEN %(a1)s AND %(a2)s GROUP BY {expr}"
               f"  UNION ALL"
               f"  SELECT {expr}, 0, COALESCE(SUM(Valor),0)"
               f"  FROM ventasgeneral2 WHERE FechaContable BETWEEN %(b1)s AND %(b2)s GROUP BY {expr}"
               f") u GROUP BY etiqueta HAVING ABS(SUM(va)) + ABS(SUM(vb)) > 0"
               f" ORDER BY GREATEST(ABS(SUM(va)), ABS(SUM(vb))) DESC LIMIT {top}")
        params = {'a1': a1, 'a2': a2, 'b1': b1, 'b2': b2}
        raw = _q(self._conn, sql, params)
        filas_all = []
        for r in raw:
            va = float(r.get('valor_a') or 0)
            vb = float(r.get('valor_b') or 0)
            filas_all.append({
                'etiqueta': str(r.get('etiqueta') or ''),
                'valor_periodo_a': va,
                'valor_periodo_b': vb,
                'delta': round(vb - va, 2),
            })
        filas = _paginate_list(filas_all, pagina, por_pagina)
        q = _qs({'a_desde': a1, 'a_hasta': a2, 'b_desde': b1, 'b_hasta': b2, 'dim': dim, 'top': top})
        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'comparativo_periodos',
            'periodo_a': {'desde': a1, 'hasta': a2},
            'periodo_b': {'desde': b1, 'hasta': b2},
            'dimension': dim,
            'filas': filas,
            'paginacion': _pagination_meta(len(filas_all), pagina, por_pagina),
            'reporte_url': report_slug_url(REPORT_SLUG_VENTAS_COMPARATIVO, q),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('ventasgeneral_top_productos')
    def _top_productos(self, args):
        d1, d2 = _parse_date_range(args)
        top = _int_arg(args.get('top_n'), 15, 1, 100)
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)
        sql = ("SELECT CodigoItem AS cod_item,"
               " MAX(COALESCE(NULLIF(TRIM(GlosaDetalle),''),'(sin glosa)')) AS glosa,"
               " COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor,"
               " COALESCE(SUM(Cantidad),0) AS suma_cantidad"
               " FROM ventasgeneral2 WHERE FechaContable BETWEEN %(d1)s AND %(d2)s"
               f" GROUP BY CodigoItem ORDER BY suma_valor DESC LIMIT {top}")
        params = {'d1': d1, 'd2': d2}
        rows = _q(self._conn, sql, params)
        filas_all = [dict(r) for r in rows]
        filas = _paginate_list(filas_all, pagina, por_pagina)
        q = _qs({'desde': d1, 'hasta': d2, 'top': top})
        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'top_productos',
            'periodo': {'desde': d1, 'hasta': d2},
            'filas': filas,
            'paginacion': _pagination_meta(len(filas_all), pagina, por_pagina),
            'reporte_url': report_slug_url(REPORT_SLUG_VENTAS_TOP_PRODUCTOS, q),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('ventasgeneral_top_clientes_globales')
    def _top_clientes_global(self, args):
        d1, d2 = _parse_date_range(args)
        top = _int_arg(args.get('top_n'), 10, 1, 100)
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)
        prov = str(args.get('provincia') or '').strip()
        linea = str(args.get('linea_comercial') or '').strip()
        orden = str(args.get('orden') or 'valor').strip().lower()
        order_col = 'suma_peso' if orden == 'peso' else 'suma_valor'

        where_extra = ''
        params = {'d1': d1, 'd2': d2}
        if prov:
            where_extra += ' AND Provincia LIKE %(prov)s'
            params['prov'] = f'%{prov}%'
        if linea:
            _linea_where, _linea_bind = linea_where_fragment(self._conn, linea, style='pyformat')
            where_extra += _linea_where
            params.update(_linea_bind)

        sql = ("SELECT CodigoCliente AS cod_cliente,"
               " MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,"
               " COUNT(*) AS lineas,"
               " COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
               " COALESCE(SUM(Peso),0) AS suma_peso,"
               " COALESCE(SUM(Valor),0) AS suma_valor"
               " FROM ventasgeneral2 WHERE FechaContable BETWEEN %(d1)s AND %(d2)s"
               + where_extra +
               f" GROUP BY CodigoCliente ORDER BY {order_col} DESC LIMIT {top}")
        raw = _q(self._conn, sql, params)
        total_row = _q1(self._conn,
            'SELECT COALESCE(SUM(Valor),0) AS t FROM ventasgeneral2 WHERE FechaContable BETWEEN %(d1)s AND %(d2)s' + where_extra,
            params)
        total = float((total_row or {}).get('t') or 0)
        cum = 0.0
        filas_all = []
        for r in raw:
            sv = float(r.get('suma_valor') or 0)
            pct = sv / total * 100 if total else 0.0
            cum += pct
            filas_all.append({
                'cod_cliente': str(r.get('cod_cliente') or ''),
                'nombre_cliente': str(r.get('nombre_cliente') or ''),
                'lineas': int(r.get('lineas') or 0),
                'suma_cantidad': float(r.get('suma_cantidad') or 0),
                'suma_peso': float(r.get('suma_peso') or 0),
                'suma_valor': sv,
                'pct_del_total': round(pct, 2),
                'pct_acumulado': round(cum, 2),
            })
        filas = _paginate_list(filas_all, pagina, por_pagina)
        q = _qs({'desde': d1, 'hasta': d2, 'top': top})
        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'top_clientes_global',
            'periodo': {'desde': d1, 'hasta': d2},
            'total_valor': total,
            'filas': filas,
            'paginacion': _pagination_meta(len(filas_all), pagina, por_pagina),
            'reporte_url': report_slug_url(REPORT_SLUG_VENTAS_TOP_CLIENTES_GLOBAL, q),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('ventasgeneral_top_clientes_nota_credito')
    def _top_clientes_nc(self, args):
        d1, d2 = _parse_date_range(args)
        top = _int_arg(args.get('top_n'), 10, 1, 100)
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)
        tdoc_cond = "COALESCE(NULLIF(TRIM(CodigoDocumento),''),'') = '07'"
        sql = (f"SELECT CodigoCliente AS cod_cliente,"
               f" MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,"
               f" COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor,"
               f" COALESCE(SUM(Peso),0) AS suma_peso"
               f" FROM ventasgeneral2"
               f" WHERE FechaContable BETWEEN %(d1)s AND %(d2)s AND {tdoc_cond}"
               f" GROUP BY CodigoCliente ORDER BY lineas DESC, suma_valor ASC LIMIT {top}")
        params = {'d1': d1, 'd2': d2}
        raw = _q(self._conn, sql, params)
        sql_tot = (f"SELECT COUNT(*) AS n, COALESCE(SUM(Valor),0) AS v, COALESCE(SUM(Peso),0) AS p"
                   f" FROM ventasgeneral2 WHERE FechaContable BETWEEN %(d1)s AND %(d2)s AND {tdoc_cond}")
        tot_row = _q1(self._conn, sql_tot, params) or {}
        total_lineas = int(tot_row.get('n') or 0)
        total_valor_nc = float(tot_row.get('v') or 0)
        total_peso_nc = float(tot_row.get('p') or 0)
        cum = 0.0
        filas_all = []
        for r in raw:
            ln = int(r.get('lineas') or 0)
            pct = ln / total_lineas * 100 if total_lineas else 0.0
            cum += pct
            filas_all.append({
                'cod_cliente': str(r.get('cod_cliente') or ''),
                'nombre_cliente': str(r.get('nombre_cliente') or ''),
                'lineas': ln,
                'suma_valor': float(r.get('suma_valor') or 0),
                'suma_peso': float(r.get('suma_peso') or 0),
                'pct_lineas_del_total': round(pct, 2),
                'pct_lineas_acumulado': round(cum, 2),
            })
        filas = _paginate_list(filas_all, pagina, por_pagina)
        q = _qs({'desde': d1, 'hasta': d2, 'top': top})
        return {
            'tabla': 'ventasgeneral2',
            'criterio': 'CodigoDocumento = 07; ranking por COUNT(*) por CodigoCliente (notas de crédito)',
            'periodo': {'desde': d1, 'hasta': d2},
            'total_lineas_nc': total_lineas,
            'total_valor_nc': total_valor_nc,
            'total_peso_nc': total_peso_nc,
            'filas': filas,
            'paginacion': _pagination_meta(len(filas_all), pagina, por_pagina),
            'reporte_url': report_slug_url(REPORT_SLUG_VENTAS_TOP_CLIENTES_NC, q),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('ventasgeneral_nc_por_corporativo')
    def _nc_por_corporativo(self, args):
        d1, d2 = _parse_date_range(args)
        top = _int_arg(args.get('top_n'), 50, 1, 200)
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)
        tdoc_cond = "COALESCE(NULLIF(TRIM(CodigoDocumento),''),'') = '07'"
        sql = (f"SELECT CodigoCoorporativo AS cod_corporativo,"
               f" MAX(COALESCE(NULLIF(TRIM(NombreCoorporativo),''),'(sin corporativo)')) AS nombre_corporativo,"
               f" COUNT(*) AS lineas_nc,"
               f" COALESCE(SUM(Valor),0) AS suma_valor,"
               f" COALESCE(SUM(Peso),0) AS suma_peso"
               f" FROM ventasgeneral2"
               f" WHERE FechaContable BETWEEN %(d1)s AND %(d2)s AND {tdoc_cond}"
               f" GROUP BY CodigoCoorporativo"
               f" ORDER BY lineas_nc DESC, suma_valor ASC LIMIT {top}")
        params = {'d1': d1, 'd2': d2}
        raw = _q(self._conn, sql, params)
        sql_tot = (f"SELECT COUNT(*) AS n, COALESCE(SUM(Valor),0) AS v"
                   f" FROM ventasgeneral2 WHERE FechaContable BETWEEN %(d1)s AND %(d2)s AND {tdoc_cond}")
        tot_row = _q1(self._conn, sql_tot, params) or {}
        total_lineas = int(tot_row.get('n') or 0)
        total_valor_nc = float(tot_row.get('v') or 0)
        cum = 0.0
        filas_all = []
        for r in raw:
            ln = int(r.get('lineas_nc') or 0)
            pct = ln / total_lineas * 100 if total_lineas else 0.0
            cum += pct
            filas_all.append({
                'cod_corporativo': str(r.get('cod_corporativo') or ''),
                'nombre_corporativo': str(r.get('nombre_corporativo') or ''),
                'lineas_nc': ln,
                'suma_valor': float(r.get('suma_valor') or 0),
                'suma_peso': float(r.get('suma_peso') or 0),
                'pct_lineas_del_total': round(pct, 2),
                'pct_lineas_acumulado': round(cum, 2),
            })
        filas = _paginate_list(filas_all, pagina, por_pagina)
        q = _qs({'desde': d1, 'hasta': d2, 'top': top})
        return {
            'tabla': 'ventasgeneral2',
            'criterio': 'CodigoDocumento = 07; ranking por COUNT(*) por CodigoCoorporativo',
            'periodo': {'desde': d1, 'hasta': d2},
            'total_lineas_nc': total_lineas,
            'total_valor_nc': total_valor_nc,
            'filas': filas,
            'paginacion': _pagination_meta(len(filas_all), pagina, por_pagina),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('ventasgeneral_mix_tdoc')
    def _mix_tdoc(self, args):
        d1, d2 = _parse_date_range(args)
        sql = ("SELECT COALESCE(NULLIF(TRIM(CodigoDocumento),''),'(sin TDoc)') AS tdoc,"
               " COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor"
               " FROM ventasgeneral2 WHERE FechaContable BETWEEN %(d1)s AND %(d2)s"
               " GROUP BY COALESCE(NULLIF(TRIM(CodigoDocumento),''),'(sin TDoc)')"
               " ORDER BY suma_valor DESC")
        params = {'d1': d1, 'd2': d2}
        rows = _q(self._conn, sql, params)
        total = sum(float(r.get('suma_valor') or 0) for r in rows)
        filas = []
        for r in rows:
            sv = float(r.get('suma_valor') or 0)
            filas.append({
                'tdoc': str(r.get('tdoc') or ''),
                'lineas': int(r.get('lineas') or 0),
                'suma_valor': sv,
                'pct_del_total': round(sv / total * 100, 2) if total else 0.0,
            })
        q = _qs({'desde': d1, 'hasta': d2})
        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'mix_tdoc',
            'periodo': {'desde': d1, 'hasta': d2},
            'total_valor': total,
            'filas': filas,
            'reporte_url': report_slug_url(REPORT_SLUG_VENTAS_MIX_TDOC, q),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('ventasgeneral_barras_ruta_comercial')
    def _barras_ruta(self, args):
        d1, d2 = _parse_date_range(args)
        top = _int_arg(args.get('top_n'), 15, 1, 100)
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)
        expr = _col_etiqueta('ruta')
        sql = (f"SELECT {expr} AS ruta, COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor"
               f" FROM ventasgeneral2 WHERE FechaContable BETWEEN %(d1)s AND %(d2)s"
               f" GROUP BY {expr} ORDER BY suma_valor DESC LIMIT {top}")
        params = {'d1': d1, 'd2': d2}
        rows = _q(self._conn, sql, params)
        filas_all = [dict(r) for r in rows]
        filas = _paginate_list(filas_all, pagina, por_pagina)
        q = _qs({'desde': d1, 'hasta': d2, 'top': top})
        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'barras_ruta',
            'periodo': {'desde': d1, 'hasta': d2},
            'filas': filas,
            'paginacion': _pagination_meta(len(filas_all), pagina, por_pagina),
            'reporte_url': report_slug_url(REPORT_SLUG_VENTAS_BARRAS_RUTA, q),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('ventasgeneral_barras_corporativo')
    def _barras_corporativo(self, args):
        d1, d2 = _parse_date_range(args)
        top = _int_arg(args.get('top_n'), 15, 1, 100)
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)
        expr = _col_etiqueta('corporativo')
        where_extra = ''
        params = {'d1': d1, 'd2': d2}
        nom_cli = str(args.get('nombre_cliente') or '').strip()
        if nom_cli:
            where_extra += ' AND NombreCliente LIKE %(nom_cli)s'
            params['nom_cli'] = f'%{nom_cli}%'
        nom_corp = str(args.get('nombre_corporativo') or '').strip()
        if nom_corp:
            where_extra += f' AND {expr} LIKE %(nom_corp)s'
            params['nom_corp'] = f'%{nom_corp}%'
        sql = (f"SELECT {expr} AS nombre_coorporativo,"
               f" MAX(COALESCE(NULLIF(TRIM(CodigoCoorporativo),''),'')) AS cod_coorporativo,"
               f" COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor"
               f" FROM ventasgeneral2 WHERE FechaContable BETWEEN %(d1)s AND %(d2)s{where_extra}"
               f" GROUP BY {expr} ORDER BY suma_valor DESC LIMIT {top}")
        rows = _q(self._conn, sql, params)
        filas_all = [dict(r) for r in rows]
        filas = _paginate_list(filas_all, pagina, por_pagina)
        q_params = {'desde': d1, 'hasta': d2, 'top': top}
        if nom_cli:
            q_params['nombre_cliente'] = nom_cli
        if nom_corp:
            q_params['nombre_corporativo'] = nom_corp
        q = _qs(q_params)
        result = {
            'tabla': 'ventasgeneral2',
            'tipo': 'barras_corporativo',
            'periodo': {'desde': d1, 'hasta': d2},
            'filas': filas,
            'paginacion': _pagination_meta(len(filas_all), pagina, por_pagina),
            'reporte_url': report_slug_url(REPORT_SLUG_VENTAS_BARRAS_CORPORATIVO, q),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }
        if nom_cli:
            result['filtro_nombre_cliente'] = nom_cli
        if nom_corp:
            result['filtro_nombre_corporativo'] = nom_corp
        return result

    @tool('ventasgeneral_serie_mensual_valor')
    def _serie_mensual(self, args):
        d1, d2 = _parse_date_range(args)
        sql = ("SELECT DATE_FORMAT(FechaContable, '%%Y-%%m') AS mes,"
               " COALESCE(SUM(Valor),0) AS suma_valor, COUNT(*) AS lineas"
               " FROM ventasgeneral2 WHERE FechaContable BETWEEN %(d1)s AND %(d2)s"
               " GROUP BY DATE_FORMAT(FechaContable, '%%Y-%%m') ORDER BY mes")
        params = {'d1': d1, 'd2': d2}
        rows = _q(self._conn, sql, params)
        q = _qs({'desde': d1, 'hasta': d2})
        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'serie_mensual_valor',
            'periodo': {'desde': d1, 'hasta': d2},
            'filas': [dict(r) for r in rows],
            'reporte_url': report_slug_url(REPORT_SLUG_VENTAS_SERIE_MENSUAL, q),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('ventasgeneral_resumen_diario')
    def _resumen_diario(self, args):
        d1, d2 = _parse_date_range(args)
        orden = str(args.get('orden') or 'valor').strip().lower()
        order_col = 'suma_valor' if orden != 'cantidad' and orden != 'peso' else f'suma_{orden}'
        linea = str(args.get('linea_comercial') or '').strip()
        params = {'d1': d1, 'd2': d2}
        extra_where = ''
        if linea:
            _linea_where, _linea_bind = linea_where_fragment(self._conn, linea, style='pyformat')
            extra_where += _linea_where
            params.update(_linea_bind)
        prov = str(args.get('provincia') or '').strip()
        if prov:
            extra_where += ' AND Provincia LIKE %(prov)s'
            params['prov'] = f'%{prov}%'
        sql = (
            "SELECT FechaContable AS fecha,"
            " COUNT(*) AS registros,"
            " COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
            " COALESCE(SUM(Peso),0) AS suma_peso,"
            " COALESCE(SUM(Valor),0) AS suma_valor"
            " FROM ventasgeneral2"
            " WHERE FechaContable BETWEEN %(d1)s AND %(d2)s"
            + extra_where +
            f" GROUP BY FechaContable ORDER BY {order_col} DESC"
        )
        rows = _q(self._conn, sql, params)
        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'resumen_diario',
            'periodo': {'desde': d1, 'hasta': d2},
            'filas': [dict(r) for r in rows],
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('ventasgeneral_resumen_semanal')
    def _resumen_semanal(self, args):
        d1, d2 = _parse_date_range(args)
        linea = str(args.get('linea_comercial') or '').strip()
        params = {'d1': d1, 'd2': d2}
        extra_where = ''
        if linea:
            _linea_where, _linea_bind = linea_where_fragment(self._conn, linea, style='pyformat')
            extra_where += _linea_where
            params.update(_linea_bind)
        prov = str(args.get('provincia') or '').strip()
        if prov:
            extra_where += ' AND Provincia LIKE %(prov)s'
            params['prov'] = f'%{prov}%'
        sql = (
            "SELECT YEARWEEK(FechaContable, 1) AS semana_num,"
            " MIN(FechaContable) AS semana_inicio,"
            " MAX(FechaContable) AS semana_fin,"
            " COUNT(*) AS registros,"
            " COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
            " COALESCE(SUM(Peso),0) AS suma_peso,"
            " COALESCE(SUM(Valor),0) AS suma_valor"
            " FROM ventasgeneral2"
            " WHERE FechaContable BETWEEN %(d1)s AND %(d2)s"
            + extra_where +
            " GROUP BY YEARWEEK(FechaContable, 1)"
            " ORDER BY semana_num"
        )
        rows = _q(self._conn, sql, params)
        q = _qs({'desde': d1, 'hasta': d2,
                 'linea_comercial': linea or None,
                 'provincia': prov or None})
        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'resumen_semanal',
            'periodo': {'desde': d1, 'hasta': d2},
            'filas': [dict(r) for r in rows],
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('ventasgeneral_linea_resumen_provincia')
    def _linea_resumen_provincia(self, args):
        d1, d2 = _parse_date_range(args)
        linea = str(args.get('linea_comercial') or '').strip()
        if not linea:
            raise ValueError("Falta linea_comercial (ej. 'Pollo Vivo')")
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)
        offset = _pagination_offset(pagina, por_pagina)
        cod_item = str(args.get('cod_item') or '').strip()
        mercado = str(args.get('mercado') or '').strip().upper()
        _linea_where, _linea_bind = linea_where_fragment(self._conn, linea, style='pyformat')
        _from_v2 = ' FROM ventasgeneral2' + index_hint_ventasgeneral2(self._conn, linea, 'contable')

        where_sql = (_from_v2
                     + " WHERE FechaContable BETWEEN %(d1)s AND %(d2)s"
                     + _linea_where)
        params = {'d1': d1, 'd2': d2, **_linea_bind}
        if cod_item:
            where_sql += " AND CodigoItem = %(cod_item)s"
            params['cod_item'] = cod_item
        if mercado:
            where_sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE %(prefzo)s"
            params['prefzo'] = mercado + '%'

        group_by = " GROUP BY provincia, CodigoCliente"
        sql_count = (
            "SELECT COUNT(*) AS total FROM (SELECT 1"
            + where_sql + group_by + ") AS sub"
        )
        total_rows = _count_query(self._conn, sql_count, params)

        sql_select = (
            "SELECT COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') AS provincia,"
            " CodigoCliente AS cod_cliente,"
            " MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,"
            " COUNT(*) AS lineas,"
            " COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
            " COALESCE(SUM(Peso),0) AS suma_peso,"
            " COALESCE(SUM(Valor),0) AS suma_valor"
            + where_sql + group_by
            + f" ORDER BY suma_peso DESC LIMIT {por_pagina} OFFSET {offset}"
        )
        rows = _q(self._conn, sql_select, params)
        qparams = {'desde': d1, 'hasta': d2, 'linea': linea,
                   'cod_item': cod_item or None, 'mercado': mercado or None,
                   'pagina': pagina, 'por_pagina': por_pagina}
        q = _qs(qparams)
        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'linea_resumen_provincia_cliente',
            'linea_comercial': linea,
            'periodo': {'desde': d1, 'hasta': d2},
            'filas': [dict(r) for r in rows],
            'paginacion': _pagination_meta(total_rows, pagina, por_pagina),
            'reporte_url': report_slug_url(REPORT_SLUG_VENTAS_LINEA_RESUMEN_PROVINCIA, q),
            '_sql_traces': [
                {'sql': sql_count, 'params': params},
                {'sql': sql_select, 'params': params},
            ],
        }

    @tool('ventasgeneral_linea_diario_provincia')
    def _linea_diario_provincia(self, args):
        d1, d2 = _parse_date_range(args)
        linea = str(args.get('linea_comercial') or '').strip()
        if not linea:
            raise ValueError("Falta linea_comercial (ej. 'Pollo Vivo')")
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)
        offset = _pagination_offset(pagina, por_pagina)
        cod_item = str(args.get('cod_item') or '').strip()
        mercado = str(args.get('mercado') or '').strip().upper()
        _linea_where, _linea_bind = linea_where_fragment(self._conn, linea, style='pyformat')
        _from_v2 = ' FROM ventasgeneral2' + index_hint_ventasgeneral2(self._conn, linea, 'contable')

        where_sql = (_from_v2
                     + " WHERE FechaContable BETWEEN %(d1)s AND %(d2)s"
                     + _linea_where)
        params = {'d1': d1, 'd2': d2, **_linea_bind}
        if cod_item:
            where_sql += " AND CodigoItem = %(cod_item)s"
            params['cod_item'] = cod_item
        if mercado:
            where_sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE %(prefzo)s"
            params['prefzo'] = mercado + '%'

        group_by = " GROUP BY FechaContable, provincia, CodigoCliente"
        sql_count = (
            "SELECT COUNT(*) AS total FROM (SELECT 1"
            + where_sql + group_by + ") AS sub"
        )
        total_rows = _count_query(self._conn, sql_count, params)

        sql_select = (
            "SELECT FechaContable AS fecha,"
            " COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') AS provincia,"
            " CodigoCliente AS cod_cliente,"
            " MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,"
            " COUNT(*) AS lineas,"
            " COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
            " COALESCE(SUM(Peso),0) AS suma_peso,"
            " COALESCE(SUM(Valor),0) AS suma_valor"
            + where_sql + group_by
            + f" ORDER BY fecha ASC, suma_peso DESC LIMIT {por_pagina} OFFSET {offset}"
        )
        rows = _q(self._conn, sql_select, params)
        q = _qs({'desde': d1, 'hasta': d2, 'linea': linea,
                 'cod_item': cod_item or None, 'mercado': mercado or None,
                 'pagina': pagina, 'por_pagina': por_pagina})
        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'linea_diario_provincia_cliente',
            'linea_comercial': linea,
            'periodo': {'desde': d1, 'hasta': d2},
            'filas': [dict(r) for r in rows],
            'paginacion': _pagination_meta(total_rows, pagina, por_pagina),
            'reporte_url': report_slug_url(REPORT_SLUG_VENTAS_LINEA_DIARIO_PROVINCIA, q),
            '_sql_traces': [
                {'sql': sql_count, 'params': params},
                {'sql': sql_select, 'params': params},
            ],
        }

    @tool('ventasgeneral_linea_precio_diario')
    def _linea_precio_diario(self, args):
        d1, d2 = _parse_date_range(args)
        linea = str(args.get('linea_comercial') or '').strip()
        if not linea:
            raise ValueError("Falta linea_comercial (ej. 'Pollo Vivo')")
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)
        offset = _pagination_offset(pagina, por_pagina)
        cod_item = str(args.get('cod_item') or '').strip()
        mercado = str(args.get('mercado') or '').strip().upper()
        _linea_where, _linea_bind = linea_where_fragment(self._conn, linea, style='pyformat')
        _from_v2 = ' FROM ventasgeneral2' + index_hint_ventasgeneral2(self._conn, linea, 'contable')

        where_sql = (_from_v2
                     + " WHERE FechaContable BETWEEN %(d1)s AND %(d2)s"
                     + _linea_where)
        params = {'d1': d1, 'd2': d2, **_linea_bind}
        if cod_item:
            where_sql += " AND CodigoItem = %(cod_item)s"
            params['cod_item'] = cod_item
        if mercado:
            where_sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE %(prefzo)s"
            params['prefzo'] = mercado + '%'

        group_by = " GROUP BY FechaContable, provincia, CodigoCliente"
        sql_count = (
            "SELECT COUNT(*) AS total FROM (SELECT 1"
            + where_sql + group_by + ") AS sub"
        )
        total_rows = _count_query(self._conn, sql_count, params)

        sql_select = (
            "SELECT FechaContable AS fecha,"
            " COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') AS provincia,"
            " CodigoCliente AS cod_cliente,"
            " MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,"
            " COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
            " COALESCE(SUM(Peso),0) AS suma_peso,"
            " COALESCE(SUM(Valor),0) AS suma_valor,"
            " CASE WHEN COALESCE(SUM(Peso),0) > 0"
            "      THEN ROUND(COALESCE(SUM(Valor),0) / COALESCE(SUM(Peso),0), 4)"
            "      ELSE NULL END AS precio_kg"
            + where_sql + group_by
            + f" ORDER BY precio_kg DESC, fecha ASC, suma_peso DESC LIMIT {por_pagina} OFFSET {offset}"
        )
        rows = _q(self._conn, sql_select, params)
        q = _qs({'desde': d1, 'hasta': d2, 'linea': linea,
                 'cod_item': cod_item or None, 'mercado': mercado or None,
                 'pagina': pagina, 'por_pagina': por_pagina})
        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'linea_precio_diario_provincia_cliente',
            'linea_comercial': linea,
            'periodo': {'desde': d1, 'hasta': d2},
            'filas': [dict(r) for r in rows],
            'paginacion': _pagination_meta(total_rows, pagina, por_pagina),
            'reporte_url': report_slug_url(REPORT_SLUG_VENTAS_LINEA_PRECIO_DIARIO, q),
            '_sql_traces': [
                {'sql': sql_count, 'params': params},
                {'sql': sql_select, 'params': params},
            ],
        }

    @tool('ventasgeneral_linea_top_clientes_precio_kg')
    def _linea_top_clientes_precio_kg(self, args):
        d1, d2 = _parse_date_range(args)
        linea = str(args.get('linea_comercial') or '').strip()
        if not linea:
            raise ValueError("Falta linea_comercial (ej. 'Pollo Vivo')")
        top = _int_arg(args.get('top_n'), 10, 1, 100)
        cod_item = str(args.get('cod_item') or '').strip()
        mercado = str(args.get('mercado') or '').strip().upper()
        _linea_where, _linea_bind = linea_where_fragment(self._conn, linea, style='pyformat')
        _from_v2 = ' FROM ventasgeneral2' + index_hint_ventasgeneral2(self._conn, linea, 'contable')

        where_sql = (_from_v2
                     + " WHERE FechaContable BETWEEN %(d1)s AND %(d2)s"
                     + _linea_where)
        params = {'d1': d1, 'd2': d2, **_linea_bind}
        if cod_item:
            where_sql += " AND CodigoItem = %(cod_item)s"
            params['cod_item'] = cod_item
        if mercado:
            where_sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE %(prefzo)s"
            params['prefzo'] = mercado + '%'

        group_by = " GROUP BY CodigoCliente"
        having_sql = " HAVING COALESCE(SUM(Peso),0) > 0"
        sql_count = (
            "SELECT COUNT(*) AS total FROM (SELECT 1"
            + where_sql + group_by + having_sql + ") AS sub"
        )
        total_rows = _count_query(self._conn, sql_count, params)

        sql_select = (
            "SELECT CodigoCliente AS cod_cliente,"
            " MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,"
            " MAX(COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)')) AS provincia,"
            " COUNT(*) AS lineas,"
            " COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
            " COALESCE(SUM(Peso),0) AS suma_peso,"
            " COALESCE(SUM(Valor),0) AS suma_valor,"
            " ROUND(COALESCE(SUM(Valor),0) / COALESCE(SUM(Peso),0), 4) AS precio_kg"
            + where_sql + group_by + having_sql
            + f" ORDER BY precio_kg DESC LIMIT {top}"
        )
        rows = _q(self._conn, sql_select, params)
        q = _qs({'desde': d1, 'hasta': d2, 'linea': linea,
                 'cod_item': cod_item or None, 'mercado': mercado or None})
        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'linea_precio_top_clientes',
            'linea_comercial': linea,
            'mercado': mercado or None,
            'periodo': {'desde': d1, 'hasta': d2},
            'top_n': top,
            'total_clientes': total_rows,
            'filas': [dict(r) for r in rows],
            'reporte_url': report_slug_url(REPORT_SLUG_VENTAS_LINEA_PRECIO_DIARIO, q),
            '_sql_traces': [
                {'sql': sql_count, 'params': params},
                {'sql': sql_select, 'params': params},
            ],
        }

    @tool('ventasgeneral_linea_precio_resumen_provincia')
    def _linea_precio_resumen_provincia(self, args):
        d1, d2 = _parse_date_range(args)
        linea = str(args.get('linea_comercial') or '').strip()
        if not linea:
            raise ValueError("Falta linea_comercial (ej. 'Pollo Vivo')")
        cod_item = str(args.get('cod_item') or '').strip()
        mercado = str(args.get('mercado') or '').strip().upper()
        _linea_where, _linea_bind = linea_where_fragment(self._conn, linea, style='pyformat')
        _from_v2 = ' FROM ventasgeneral2' + index_hint_ventasgeneral2(self._conn, linea, 'contable')
        sql = ("SELECT"
               " COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') AS provincia,"
               " COUNT(*) AS lineas,"
               " COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
               " COALESCE(SUM(Peso),0) AS suma_peso,"
               " COALESCE(SUM(Valor),0) AS suma_valor,"
               " CASE WHEN COALESCE(SUM(Peso),0) > 0"
               "      THEN ROUND(COALESCE(SUM(Valor),0) / COALESCE(SUM(Peso),0), 4)"
               "      ELSE NULL END AS precio_kg"
               + _from_v2
               + " WHERE FechaContable BETWEEN %(d1)s AND %(d2)s"
               + _linea_where)
        params = {'d1': d1, 'd2': d2, **_linea_bind}
        if cod_item:
            sql += " AND CodigoItem = %(cod_item)s"
            params['cod_item'] = cod_item
        if mercado:
            sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE %(prefzo)s"
            params['prefzo'] = mercado + '%'
        sql += " GROUP BY provincia ORDER BY precio_kg DESC"
        rows = _q(self._conn, sql, params)
        filas = []
        total_peso = 0.0
        total_valor = 0.0
        for r in rows:
            sp = float(r.get('suma_peso') or 0)
            sv = float(r.get('suma_valor') or 0)
            pk = r.get('precio_kg')
            total_peso += sp
            total_valor += sv
            filas.append({
                'provincia': str(r.get('provincia') or ''),
                'lineas': int(r.get('lineas') or 0),
                'suma_cantidad': float(r.get('suma_cantidad') or 0),
                'suma_peso': sp,
                'suma_valor': sv,
                'precio_kg': float(pk) if pk is not None else None,
            })
        total_precio_kg = round(total_valor / total_peso, 4) if total_peso > 0 else None
        q = _qs({'desde': d1, 'hasta': d2, 'linea': linea,
                 'cod_item': cod_item or None, 'mercado': mercado or None})
        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'linea_precio_resumen_provincia',
            'linea_comercial': linea,
            'periodo': {'desde': d1, 'hasta': d2},
            'total_peso': total_peso,
            'total_valor': total_valor,
            'total_precio_kg': total_precio_kg,
            'filas': filas,
            'reporte_url': report_slug_url(REPORT_SLUG_VENTAS_LINEA_PRECIO_RESUMEN_PROV, q),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('ventasgeneral_linea_mix_productos')
    def _linea_mix_productos(self, args):
        d1, d2 = _parse_date_range(args)
        linea = str(args.get('linea_comercial') or '').strip()
        if not linea:
            raise ValueError("Falta linea_comercial (ej. 'Pollo Vivo')")
        mercado = str(args.get('mercado') or '').strip().upper()
        _linea_where, _linea_bind = linea_where_fragment(self._conn, linea, style='pyformat')
        _from_v2 = ' FROM ventasgeneral2' + index_hint_ventasgeneral2(self._conn, linea, 'contable')
        sql = ("SELECT CodigoItem AS cod_item,"
               " MAX(COALESCE(NULLIF(TRIM(GlosaDetalle),''),'(sin glosa)')) AS glosa,"
               " COUNT(*) AS lineas,"
               " COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
               " COALESCE(SUM(Peso),0) AS suma_peso,"
               " COALESCE(SUM(Valor),0) AS suma_valor,"
               " CASE WHEN COALESCE(SUM(Peso),0) > 0"
               "      THEN ROUND(COALESCE(SUM(Valor),0) / COALESCE(SUM(Peso),0), 4)"
               "      ELSE NULL END AS precio_kg"
               + _from_v2
               + " WHERE FechaContable BETWEEN %(d1)s AND %(d2)s"
               + _linea_where)
        params = {'d1': d1, 'd2': d2, **_linea_bind}
        if mercado:
            sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE %(prefzo)s"
            params['prefzo'] = mercado + '%'
        sql += " GROUP BY CodigoItem ORDER BY suma_peso DESC"
        rows = _q(self._conn, sql, params)
        total_peso = sum(float(r.get('suma_peso') or 0) for r in rows)
        total_valor = sum(float(r.get('suma_valor') or 0) for r in rows)
        filas = []
        for r in rows:
            sp = float(r.get('suma_peso') or 0)
            pk = r.get('precio_kg')
            filas.append({
                'cod_item': str(r.get('cod_item') or ''),
                'glosa': str(r.get('glosa') or ''),
                'lineas': int(r.get('lineas') or 0),
                'suma_cantidad': float(r.get('suma_cantidad') or 0),
                'suma_peso': sp,
                'suma_valor': float(r.get('suma_valor') or 0),
                'precio_kg': float(pk) if pk is not None else None,
                'pct_peso': round(sp / total_peso * 100, 2) if total_peso else 0.0,
            })
        q = _qs({'desde': d1, 'hasta': d2, 'linea': linea, 'mercado': mercado or None})
        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'linea_mix_productos',
            'linea_comercial': linea,
            'mercado': mercado or None,
            'periodo': {'desde': d1, 'hasta': d2},
            'total_peso': total_peso,
            'total_valor': total_valor,
            'filas': filas,
            'reporte_url': report_slug_url(REPORT_SLUG_VENTAS_LINEA_MIX_PRODUCTOS, q),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('ventasgeneral_resumen_por_linea')
    def _resumen_por_linea(self, args):
        d1, d2 = _parse_date_range(args)
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)

        where_sql = ' FROM ventasgeneral2 WHERE FechaContable BETWEEN %(d1)s AND %(d2)s'
        params: dict = {'d1': d1, 'd2': d2}

        provincia = str(args.get('provincia') or '').strip()
        if provincia:
            where_sql += ' AND Provincia LIKE %(prov)s'
            params['prov'] = f'%{provincia}%'

        prefijo = str(args.get('prefijo_descri_zona_precio') or '').strip().upper()
        if prefijo:
            where_sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE %(prefzo)s"
            params['prefzo'] = prefijo + '%'

        lineas_raw = str(args.get('lineas_comerciales') or '').strip()
        lineas_list = [l.strip() for l in lineas_raw.split(',') if l.strip()] if lineas_raw else []
        if lineas_list:
            placeholders = ', '.join(f'%(lin{i})s' for i in range(len(lineas_list)))
            where_sql += f' AND LineaComercial IN ({placeholders})'
            for i, lin in enumerate(lineas_list):
                params[f'lin{i}'] = lin

        sql = (
            "SELECT COALESCE(NULLIF(TRIM(LineaComercial),''),'(sin línea)') AS linea_comercial,"
            " COUNT(*) AS lineas,"
            " COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
            " COALESCE(SUM(Peso),0) AS suma_peso,"
            " COALESCE(SUM(Valor),0) AS suma_valor"
            + where_sql
            + " GROUP BY COALESCE(NULLIF(TRIM(LineaComercial),''),'(sin línea)')"
            " ORDER BY suma_valor DESC"
        )
        rows = _q(self._conn, sql, params)

        total_valor = sum(float(r.get('suma_valor') or 0) for r in rows)
        filas_all = []
        for r in rows:
            sv = float(r.get('suma_valor') or 0)
            filas_all.append({
                'linea_comercial': str(r.get('linea_comercial') or ''),
                'lineas': int(r.get('lineas') or 0),
                'suma_cantidad': float(r.get('suma_cantidad') or 0),
                'suma_peso': float(r.get('suma_peso') or 0),
                'suma_valor': sv,
                'pct_del_total': round(sv / total_valor * 100, 2) if total_valor else 0.0,
            })
        filas = _paginate_list(filas_all, pagina, por_pagina)

        q_params: dict = {'desde': d1, 'hasta': d2}
        if provincia:
            q_params['provincia'] = provincia
        if prefijo:
            q_params['prefijo'] = prefijo
        if lineas_raw:
            q_params['lineas'] = lineas_raw
        q = _qs(q_params)

        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'resumen_por_linea',
            'periodo': {'desde': d1, 'hasta': d2},
            'total_valor': total_valor,
            'filas': filas,
            'paginacion': _pagination_meta(len(filas_all), pagina, por_pagina),
            'reporte_url': report_slug_url(REPORT_SLUG_VENTAS_RESUMEN_POR_LINEA, q),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('ventasgeneral_resumen_por_provincia')
    def _resumen_por_provincia(self, args):
        d1, d2 = _parse_date_range(args)
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)

        where_sql = ' FROM ventasgeneral2 WHERE FechaContable BETWEEN %(d1)s AND %(d2)s'
        params: dict = {'d1': d1, 'd2': d2}

        linea = str(args.get('linea_comercial') or '').strip()
        if linea:
            _linea_where, _linea_bind = linea_where_fragment(self._conn, linea, style='pyformat')
            where_sql += _linea_where
            params.update(_linea_bind)

        zona = str(args.get('zona_comercial') or '').strip()
        if zona:
            where_sql += ' AND ZonaComercial LIKE %(zona)s'
            params['zona'] = f'%{zona}%'

        cod = str(args.get('cod_cliente') or '').strip()
        if cod:
            where_sql += ' AND CodigoCliente = %(cod)s'
            params['cod'] = cod

        pref_z = str(args.get('prefijo_descri_zona_precio') or '').strip().upper()
        if pref_z:
            where_sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE %(prefzp)s"
            params['prefzp'] = pref_z + '%'

        tdoc = str(args.get('tipo_documento') or '').strip()
        if tdoc:
            where_sql += ' AND TipoDocumento LIKE %(tdoc)s'
            params['tdoc'] = f'%{tdoc}%'

        cod_doc = str(args.get('codigo_documento') or '').strip()
        if cod_doc:
            where_sql += ' AND CodigoDocumento = %(cod_doc)s'
            params['cod_doc'] = cod_doc

        sql = (
            "SELECT COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') AS provincia,"
            " COUNT(*) AS lineas,"
            " COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
            " COALESCE(SUM(Peso),0) AS suma_peso,"
            " COALESCE(SUM(Valor),0) AS suma_valor"
            + where_sql
            + " GROUP BY COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)')"
            " ORDER BY suma_valor DESC"
        )
        rows = _q(self._conn, sql, params)

        total_valor = sum(float(r.get('suma_valor') or 0) for r in rows)
        filas_all = []
        for r in rows:
            sv = float(r.get('suma_valor') or 0)
            filas_all.append({
                'provincia': str(r.get('provincia') or ''),
                'lineas': int(r.get('lineas') or 0),
                'suma_cantidad': float(r.get('suma_cantidad') or 0),
                'suma_peso': float(r.get('suma_peso') or 0),
                'suma_valor': sv,
                'pct_del_total': round(sv / total_valor * 100, 2) if total_valor else 0.0,
            })
        filas = _paginate_list(filas_all, pagina, por_pagina)

        q = {'fecha_desde': d1, 'fecha_hasta': d2}
        if linea:
            q['linea_comercial'] = linea
        if zona:
            q['zona_comercial'] = zona
        if cod:
            q['cod_cliente'] = cod
        if pref_z:
            q['prefijo_descri_zona_precio'] = pref_z
        if tdoc:
            q['tipo_documento'] = tdoc
        if cod_doc:
            q['codigo_documento'] = cod_doc

        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'resumen_por_provincia',
            'periodo': {'desde': d1, 'hasta': d2},
            'total_valor': total_valor,
            'filas': filas,
            'paginacion': _pagination_meta(len(filas_all), pagina, por_pagina),
            'reporte_url': report_slug_url(REPORT_SLUG_VENTAS_RESUMEN_POR_PROVINCIA, _qs(q)),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @staticmethod
    def _regresion_lineal(series: list[float]) -> tuple[float, float]:
        """Devuelve (pendiente m, intercepto b) para la serie dada."""
        n = len(series)
        sum_x = sum_y = sum_xy = sum_xx = 0.0
        for i, y in enumerate(series):
            x = float(i)
            sum_x += x
            sum_y += y
            sum_xy += x * y
            sum_xx += x * x
        denom = n * sum_xx - sum_x * sum_x
        if denom == 0:
            return 0.0, sum_y / n
        m = (n * sum_xy - sum_x * sum_y) / denom
        b = (sum_y - m * sum_x) / n
        return m, b

    @tool('ventasgeneral_proyeccion_ventas')
    def _proyeccion(self, args):
        d1, d2 = _parse_date_range(args)
        meses = _int_arg(args.get('meses_a_proyectar'), 3, 1, 12)
        linea    = str(args.get('linea_comercial') or '').strip()
        provincia = str(args.get('provincia') or '').strip()
        zona     = str(args.get('zona_comercial') or '').strip()
        pref_z   = str(args.get('prefijo_descri_zona_precio') or '').strip().upper()

        sql = ("SELECT DATE_FORMAT(FechaContable, '%%Y-%%m') AS mes,"
               " COALESCE(SUM(Valor),0) AS suma_valor,"
               " COALESCE(SUM(Cantidad),0) AS suma_cantidad,"
               " COALESCE(SUM(Peso),0) AS suma_peso"
               " FROM ventasgeneral2 WHERE FechaContable BETWEEN %(d1)s AND %(d2)s")
        params: dict = {'d1': d1, 'd2': d2}
        if linea:
            sql += " AND LineaComercial = %(linea)s"
            params['linea'] = linea
        if provincia:
            sql += " AND Provincia LIKE %(prov)s"
            params['prov'] = f'%{provincia}%'
        if zona:
            sql += " AND ZonaComercial LIKE %(zona)s"
            params['zona'] = f'%{zona}%'
        if pref_z:
            sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE %(pref_z)s"
            params['pref_z'] = pref_z + '%'
        sql += " GROUP BY DATE_FORMAT(FechaContable, '%%Y-%%m') ORDER BY mes"

        filas = _q(self._conn, sql, params)
        if len(filas) < 2:
            raise ValueError('Se necesitan al menos 2 meses de datos históricos para proyectar')

        n = len(filas)
        serie_valor    = [float(r.get('suma_valor') or 0) for r in filas]
        serie_cantidad = [float(r.get('suma_cantidad') or 0) for r in filas]
        serie_peso     = [float(r.get('suma_peso') or 0) for r in filas]
        serie_peso_prom = [
            sp / sq if sq > 0 else 0.0
            for sp, sq in zip(serie_peso, serie_cantidad)
        ]

        mv, bv = self._regresion_lineal(serie_valor)
        mc, bc = self._regresion_lineal(serie_cantidad)
        mp, bp = self._regresion_lineal(serie_peso_prom)

        last_mes = str(filas[-1]['mes'])
        y_base, mo_base = int(last_mes[:4]), int(last_mes[5:7])
        proyecciones = []
        for i in range(1, meses + 1):
            mo = mo_base + i
            yr = y_base + (mo - 1) // 12
            mo = ((mo - 1) % 12) + 1
            cant_proj = max(0.0, mc * (n + i - 1) + bc)
            peso_prom_proj = max(0.0, mp * (n + i - 1) + bp)
            proyecciones.append({
                'mes': f'{yr:04d}-{mo:02d}',
                'valor_proyectado':    max(0.0, mv * (n + i - 1) + bv),
                'cantidad_proyectada': cant_proj,
                'peso_prom_proyectado': peso_prom_proj,
                'peso_total_proyectado': cant_proj * peso_prom_proj,
            })

        filtros = {}
        if linea:    filtros['linea_comercial'] = linea
        if provincia: filtros['provincia'] = provincia
        if zona:     filtros['zona_comercial'] = zona
        if pref_z:   filtros['prefijo_descri_zona_precio'] = pref_z
        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'proyeccion_ventas',
            'periodo_historico': {'desde': d1, 'hasta': d2},
            'filtros': filtros or None,
            'proyecciones': proyecciones,
            'nota': 'Proyección basada en datos actuales.',
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    _CATALOGO_CAMPOS = {
        'provincia':       'Provincia',
        'linea_comercial': 'LineaComercial',
        'corporativo':     'NombreCoorporativo',
        'zona_precio':     'DescripcionZonaPrecio',
        'zona_comercial':  'ZonaComercial',
        'ruta':            'RutaComercial',
        'tipo_documento':  'TipoDocumento',
        'cliente':         'NombreCliente',
        'glosa':           'GlosaDetalle',
    }

    @tool('ventasgeneral_clientes_corporativo')
    def _clientes_corporativo(self, args):
        nom_corp = str(args.get('nombre_corporativo') or '').strip()
        if not nom_corp:
            raise ValueError('nombre_corporativo es obligatorio')

        d1 = _parse_date(args.get('fecha_desde'), 'fecha_desde', required=False)
        d2 = _parse_date(args.get('fecha_hasta'), 'fecha_hasta', required=False)

        where = ' WHERE NombreCoorporativo LIKE %(nom_corp)s'
        params: dict = {'nom_corp': f'%{nom_corp}%'}
        if d1 and d2:
            where += ' AND FechaContable BETWEEN %(d1)s AND %(d2)s'
            params.update({'d1': d1, 'd2': d2})
        elif d1:
            where += ' AND FechaContable >= %(d1)s'
            params['d1'] = d1
        elif d2:
            where += ' AND FechaContable <= %(d2)s'
            params['d2'] = d2

        sql = (
            'SELECT CodigoCliente AS codigo_cliente,'
            ' MAX(NombreCliente) AS nombre_cliente,'
            ' COUNT(*) AS lineas,'
            ' COALESCE(SUM(Peso),0) AS suma_peso,'
            ' COALESCE(SUM(Valor),0) AS suma_valor,'
            ' MIN(FechaContable) AS primera_venta,'
            ' MAX(FechaContable) AS ultima_venta'
            ' FROM ventasgeneral2' + where +
            ' GROUP BY CodigoCliente ORDER BY nombre_cliente'
        )
        rows = _q(self._conn, sql, params)
        filas = [{
            'codigo_cliente': str(r.get('codigo_cliente') or ''),
            'nombre_cliente': str(r.get('nombre_cliente') or ''),
            'lineas': int(r.get('lineas') or 0),
            'suma_peso': float(r.get('suma_peso') or 0),
            'suma_valor': float(r.get('suma_valor') or 0),
            'primera_venta': str(r.get('primera_venta') or ''),
            'ultima_venta': str(r.get('ultima_venta') or ''),
        } for r in rows]

        q_params = {'corporativo': nom_corp}
        if d1:
            q_params['desde'] = d1
        if d2:
            q_params['hasta'] = d2
        return {
            'tabla': 'ventasgeneral2',
            'tipo': 'clientes_corporativo',
            'nombre_corporativo': nom_corp,
            'total_clientes': len(filas),
            'filas': filas,
            'reporte_url': report_slug_url(REPORT_SLUG_VENTAS_CLIENTES_CORPORATIVO, _qs(q_params)),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('consulta_libre')
    def _consulta_libre(self, args):
        raw_sql = str(args.get('sql') or '').strip()
        if not raw_sql:
            raise ValueError('Falta el parámetro sql.')
        clean_sql = validate_select_sql(raw_sql)  # SqlGuardError extiende ValueError

        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)

        sql_count = build_count_sql(clean_sql)
        total_rows = _count_query(self._conn, sql_count, None)

        sql_data = apply_pagination(clean_sql, pagina, por_pagina)
        rows = _q(self._conn, sql_data, None)

        return {
            'tipo': 'consulta_libre',
            'total_filas': total_rows,
            'paginacion': _pagination_meta(total_rows, pagina, por_pagina),
            'filas': [dict(r) for r in rows],
            '_sql_traces': [
                {'sql': sql_count, 'params': {}},
                {'sql': sql_data, 'params': {}},
            ],
        }

    @tool('ventasgeneral_catalogo')
    def _catalogo(self, args):
        campo = str(args.get('campo') or '').strip().lower()
        col = self._CATALOGO_CAMPOS.get(campo)
        if not col:
            raise ValueError(f"campo no reconocido: '{campo}'. Opciones: {', '.join(self._CATALOGO_CAMPOS)}")

        d1 = _parse_date(args.get('fecha_desde'), 'fecha_desde', required=False)
        d2 = _parse_date(args.get('fecha_hasta'), 'fecha_hasta', required=False)
        linea = str(args.get('linea_comercial') or '').strip()
        cod_doc = str(args.get('codigo_documento') or '').strip()

        sql = (f"SELECT DISTINCT TRIM(COALESCE({col},'')) AS valor"
               f" FROM ventasgeneral2"
               f" WHERE TRIM(COALESCE({col},'')) != ''")
        params: dict = {}
        if d1 and d2:
            sql += " AND FechaContable BETWEEN %(d1)s AND %(d2)s"
            params.update({'d1': d1, 'd2': d2})
        if linea:
            sql += " AND LineaComercial = %(linea)s"
            params['linea'] = linea
        if cod_doc:
            sql += " AND CodigoDocumento = %(cod_doc)s"
            params['cod_doc'] = cod_doc
        sql += " ORDER BY valor"

        rows = _q(self._conn, sql, params)
        valores = [str(r.get('valor') or '') for r in rows if (r.get('valor') or '').strip()]

        return {
            'campo': campo,
            'columna_bd': col,
            'total': len(valores),
            'valores': valores,
            'filtros': {
                'linea_comercial': linea or None,
                'codigo_documento': cod_doc or None,
            },
            'periodo': {'desde': d1, 'hasta': d2} if d1 and d2 else None,
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    # ──────────────────────────────────────────────────────────────────
    # META-CONSULTAS: estadísticas sobre el propio historial del chatbot
    # Tablas: app_chat_messages (m), app_chat_threads (t), app_users (u)
    # m.role ∈ ('user', 'assistant'). Solo cuentan como "preguntas" m.role='user'.
    # ──────────────────────────────────────────────────────────────────

    def _chat_periodo_where(self, args, required=True):
        """Construye fragmento WHERE para filtrar m.created_at por rango (inclusivo full-day).

        - Si required=True, exige fecha_desde y fecha_hasta.
        - Devuelve (lista_de_clausulas, params, d1, d2).
        """
        d1 = _parse_date(args.get('fecha_desde'), 'fecha_desde', required=required)
        d2 = _parse_date(args.get('fecha_hasta'), 'fecha_hasta', required=required)
        if d1 and d2 and d1 > d2:
            raise ValueError('fecha_desde no puede ser mayor que fecha_hasta')
        where = []
        params = {}
        if d1:
            where.append('m.created_at >= %(d1)s')
            params['d1'] = d1
        if d2:
            where.append('m.created_at < DATE_ADD(%(d2)s, INTERVAL 1 DAY)')
            params['d2'] = d2
        return where, params, d1, d2

    @tool('chat_usuario_estadisticas')
    def _chat_usuario_estadisticas(self, args):
        where, params, d1, d2 = self._chat_periodo_where(args, required=True)
        username = str(args.get('username') or '').strip()

        sql = (
            'SELECT COUNT(*) AS total_preguntas,'
            ' COUNT(DISTINCT t.id) AS total_chats,'
            ' MIN(m.created_at) AS primera_pregunta_at,'
            ' MAX(m.created_at) AS ultima_pregunta_at'
            ' FROM app_chat_messages m'
            ' INNER JOIN app_chat_threads t ON t.id = m.thread_id'
            " WHERE m.role = 'user'"
        )
        for w in where:
            sql += ' AND ' + w
        if username:
            sql += ' AND t.username = %(username)s'
            params['username'] = username

        row = _q1(self._conn, sql, params) or {}
        agregados = {
            'total_preguntas': int(row.get('total_preguntas') or 0),
            'total_chats': int(row.get('total_chats') or 0),
            'primera_pregunta_at': str(row.get('primera_pregunta_at')) if row.get('primera_pregunta_at') else None,
            'ultima_pregunta_at': str(row.get('ultima_pregunta_at')) if row.get('ultima_pregunta_at') else None,
        }
        return {
            'tabla': 'app_chat_messages',
            'tipo': 'chat_usuario_estadisticas',
            'periodo': {'desde': d1, 'hasta': d2},
            'filtro': {'username': username or '(todos)'},
            'agregados': agregados,
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('chat_top_usuarios')
    def _chat_top_usuarios(self, args):
        where, params, d1, d2 = self._chat_periodo_where(args, required=True)
        top = _int_arg(args.get('top_n'), 10, 1, 100)
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)

        base_where = " m.role = 'user'"
        for w in where:
            base_where += ' AND ' + w

        sql = (
            'SELECT t.username,'
            " COALESCE(MAX(u.display_name),'') AS display_name,"
            " COALESCE(MAX(u.role),'') AS user_role,"
            ' COUNT(*) AS total_preguntas,'
            ' COUNT(DISTINCT t.id) AS total_chats,'
            ' MIN(m.created_at) AS primera_pregunta_at,'
            ' MAX(m.created_at) AS ultima_pregunta_at'
            ' FROM app_chat_messages m'
            ' INNER JOIN app_chat_threads t ON t.id = m.thread_id'
            ' LEFT JOIN app_users u ON u.username = t.username'
            ' WHERE ' + base_where +
            ' GROUP BY t.username'
            f' ORDER BY total_preguntas DESC, t.username ASC LIMIT {top}'
        )
        raw = _q(self._conn, sql, params)
        filas_all = [{
            'username': str(r.get('username') or ''),
            'display_name': str(r.get('display_name') or ''),
            'user_role': str(r.get('user_role') or ''),
            'total_preguntas': int(r.get('total_preguntas') or 0),
            'total_chats': int(r.get('total_chats') or 0),
            'primera_pregunta_at': str(r.get('primera_pregunta_at')) if r.get('primera_pregunta_at') else None,
            'ultima_pregunta_at': str(r.get('ultima_pregunta_at')) if r.get('ultima_pregunta_at') else None,
        } for r in raw]
        filas = _paginate_list(filas_all, pagina, por_pagina)
        return {
            'tabla': 'app_chat_messages',
            'tipo': 'chat_top_usuarios',
            'periodo': {'desde': d1, 'hasta': d2},
            'top_n': top,
            'filas_ranking': filas,
            'paginacion': _pagination_meta(len(filas_all), pagina, por_pagina),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('chat_actividad_por_dia')
    def _chat_actividad_por_dia(self, args):
        where, params, d1, d2 = self._chat_periodo_where(args, required=True)
        username = str(args.get('username') or '').strip()

        sql = (
            'SELECT DATE(m.created_at) AS dia,'
            ' COUNT(*) AS total_preguntas,'
            ' COUNT(DISTINCT t.username) AS usuarios_activos,'
            ' COUNT(DISTINCT t.id) AS chats_activos'
            ' FROM app_chat_messages m'
            ' INNER JOIN app_chat_threads t ON t.id = m.thread_id'
            " WHERE m.role = 'user'"
        )
        for w in where:
            sql += ' AND ' + w
        if username:
            sql += ' AND t.username = %(username)s'
            params['username'] = username
        orden = str(args.get('orden') or 'asc').strip().lower()
        order_col = 'total_preguntas DESC' if orden == 'desc' else 'dia ASC'
        top_n = _int_arg(args.get('top_n'), 0, 0, 100)
        sql += f' GROUP BY DATE(m.created_at) ORDER BY {order_col}'
        if top_n:
            sql += f' LIMIT {top_n}'

        rows = _q(self._conn, sql, params)
        filas = [{
            'dia': str(r.get('dia') or ''),
            'total_preguntas': int(r.get('total_preguntas') or 0),
            'usuarios_activos': int(r.get('usuarios_activos') or 0),
            'chats_activos': int(r.get('chats_activos') or 0),
        } for r in rows]
        return {
            'tabla': 'app_chat_messages',
            'tipo': 'chat_actividad_por_dia',
            'periodo': {'desde': d1, 'hasta': d2},
            'filtro': {'username': username or '(todos)'},
            'filas': filas,
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('chat_listar_preguntas')
    def _chat_listar_preguntas(self, args):
        where, params, d1, d2 = self._chat_periodo_where(args, required=False)
        username = str(args.get('username') or '').strip()
        role = str(args.get('role') or '').strip().lower()
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)
        offset = _pagination_offset(pagina, por_pagina)

        # JOIN con app_users solo si se filtra por rol
        join_users = ' INNER JOIN app_users u ON u.username = t.username' if role else ''

        base_where = " m.role = 'user'"
        for w in where:
            base_where += ' AND ' + w
        if username:
            base_where += ' AND t.username = %(username)s'
            params['username'] = username
        if role:
            base_where += ' AND LOWER(TRIM(u.role)) = %(role)s'
            params['role'] = role

        from_clause = (
            ' FROM app_chat_messages m'
            ' INNER JOIN app_chat_threads t ON t.id = m.thread_id'
            + join_users
        )

        sql_count = 'SELECT COUNT(*) AS total' + from_clause + ' WHERE ' + base_where
        total = _count_query(self._conn, sql_count, params)

        sql = (
            'SELECT m.id AS message_id,'
            ' t.username,'
            ' t.title AS thread_title,'
            ' t.id AS thread_id,'
            ' m.content,'
            ' m.created_at'
            + from_clause
            + ' WHERE ' + base_where
            + f' ORDER BY m.created_at DESC, m.id DESC LIMIT {int(por_pagina)} OFFSET {int(offset)}'
        )
        rows = _q(self._conn, sql, params)
        filas = [{
            'message_id': int(r.get('message_id') or 0),
            'thread_id': int(r.get('thread_id') or 0),
            'username': str(r.get('username') or ''),
            'thread_title': str(r.get('thread_title') or ''),
            'content': str(r.get('content') or ''),
            'created_at': str(r.get('created_at')) if r.get('created_at') else '',
        } for r in rows]
        return {
            'tabla': 'app_chat_messages',
            'tipo': 'chat_listar_preguntas',
            'periodo': {'desde': d1, 'hasta': d2},
            'filtro': {'username': username or '(todos)', 'role': role or '(todos)'},
            'filas': filas,
            'paginacion': _pagination_meta(total, pagina, por_pagina),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('chat_buscar_pregunta')
    def _chat_buscar_pregunta(self, args):
        texto = str(args.get('texto') or '').strip()
        if not texto:
            raise ValueError("Falta 'texto' a buscar dentro de las preguntas")
        if len(texto) < 2:
            raise ValueError("El parámetro 'texto' debe tener al menos 2 caracteres")

        where, params, d1, d2 = self._chat_periodo_where(args, required=False)
        username = str(args.get('username') or '').strip()
        pagina = _parse_pagina(args)
        por_pagina = _parse_por_pagina(args)
        offset = _pagination_offset(pagina, por_pagina)

        base_where = " m.role = 'user' AND m.content LIKE %(texto_like)s"
        params['texto_like'] = f'%{texto}%'
        for w in where:
            base_where += ' AND ' + w
        if username:
            base_where += ' AND t.username = %(username)s'
            params['username'] = username

        sql_count = (
            'SELECT COUNT(*) AS total'
            ' FROM app_chat_messages m'
            ' INNER JOIN app_chat_threads t ON t.id = m.thread_id'
            ' WHERE ' + base_where
        )
        total = _count_query(self._conn, sql_count, params)

        sql = (
            'SELECT m.id AS message_id,'
            ' t.username,'
            ' t.title AS thread_title,'
            ' t.id AS thread_id,'
            ' m.content,'
            ' m.created_at'
            ' FROM app_chat_messages m'
            ' INNER JOIN app_chat_threads t ON t.id = m.thread_id'
            ' WHERE ' + base_where +
            f' ORDER BY m.created_at DESC, m.id DESC LIMIT {int(por_pagina)} OFFSET {int(offset)}'
        )
        rows = _q(self._conn, sql, params)
        filas = [{
            'message_id': int(r.get('message_id') or 0),
            'thread_id': int(r.get('thread_id') or 0),
            'username': str(r.get('username') or ''),
            'thread_title': str(r.get('thread_title') or ''),
            'content': str(r.get('content') or ''),
            'created_at': str(r.get('created_at')) if r.get('created_at') else '',
        } for r in rows]
        return {
            'tabla': 'app_chat_messages',
            'tipo': 'chat_buscar_pregunta',
            'texto_buscado': texto,
            'periodo': {'desde': d1, 'hasta': d2} if (d1 or d2) else None,
            'filtro': {'username': username or '(todos)'},
            'filas': filas,
            'paginacion': _pagination_meta(total, pagina, por_pagina),
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('chat_resumen_threads')
    def _chat_resumen_threads(self, args):
        where, params, d1, d2 = self._chat_periodo_where(args, required=True)
        username = str(args.get('username') or '').strip()

        # Para "actividad del período" filtramos por mensajes (no por created_at del thread)
        base_where = ' 1=1'
        for w in where:
            base_where += ' AND ' + w
        if username:
            base_where += ' AND t.username = %(username)s'
            params['username'] = username

        sql = (
            'SELECT t.username,'
            " COALESCE(MAX(u.display_name),'') AS display_name,"
            " COALESCE(MAX(u.role),'') AS user_role,"
            ' COUNT(DISTINCT t.id) AS total_chats,'
            ' COUNT(m.id) AS total_mensajes,'
            " SUM(CASE WHEN m.role = 'user' THEN 1 ELSE 0 END) AS total_preguntas,"
            " SUM(CASE WHEN m.role = 'assistant' THEN 1 ELSE 0 END) AS total_respuestas,"
            ' MIN(m.created_at) AS primer_mensaje_at,'
            ' MAX(m.created_at) AS ultimo_mensaje_at'
            ' FROM app_chat_threads t'
            ' INNER JOIN app_chat_messages m ON m.thread_id = t.id'
            ' LEFT JOIN app_users u ON u.username = t.username'
            ' WHERE ' + base_where +
            ' GROUP BY t.username'
            ' ORDER BY total_preguntas DESC, t.username ASC'
        )
        rows = _q(self._conn, sql, params)
        filas = [{
            'username': str(r.get('username') or ''),
            'display_name': str(r.get('display_name') or ''),
            'user_role': str(r.get('user_role') or ''),
            'total_chats': int(r.get('total_chats') or 0),
            'total_mensajes': int(r.get('total_mensajes') or 0),
            'total_preguntas': int(r.get('total_preguntas') or 0),
            'total_respuestas': int(r.get('total_respuestas') or 0),
            'primer_mensaje_at': str(r.get('primer_mensaje_at')) if r.get('primer_mensaje_at') else None,
            'ultimo_mensaje_at': str(r.get('ultimo_mensaje_at')) if r.get('ultimo_mensaje_at') else None,
        } for r in rows]
        return {
            'tabla': 'app_chat_threads',
            'tipo': 'chat_resumen_threads',
            'periodo': {'desde': d1, 'hasta': d2},
            'filtro': {'username': username or '(todos)'},
            'filas': filas,
            '_sql_traces': [{'sql': sql, 'params': params}],
        }

    @tool('filtrar_previo')
    def _filtrar_previo(self, args):
        """Filtra/ordena el resultado de la consulta anterior sin tocar la BD."""
        if not self._prev_result:
            return {'error': 'No hay resultado previo en caché. Hacé primero una consulta a la BD.'}

        data = self._prev_result
        rows = None
        rows_key = None
        for key in ('filas', 'filas_ranking', 'filas_pareto', 'filas_diario'):
            if isinstance(data.get(key), list):
                rows = list(data[key])
                rows_key = key
                break

        if rows is None:
            return {'error': 'El resultado previo no contiene filas filtrables.'}

        # Filtrar
        campo = str(args.get('campo') or '').strip()
        valor = str(args.get('valor_filtro') or '').strip()
        comparador = str(args.get('comparador') or 'igual').lower()

        if campo and valor:
            filtered = []
            for row in rows:
                cell = str(row.get(campo, '')).strip()
                if comparador == 'contiene':
                    match = valor.lower() in cell.lower()
                elif comparador == 'mayor':
                    try:
                        match = float(cell.replace(',', '')) > float(valor.replace(',', ''))
                    except (ValueError, TypeError):
                        match = False
                elif comparador == 'menor':
                    try:
                        match = float(cell.replace(',', '')) < float(valor.replace(',', ''))
                    except (ValueError, TypeError):
                        match = False
                else:  # igual (default)
                    match = cell.lower() == valor.lower()
                if match:
                    filtered.append(row)
            rows = filtered

        # Ordenar
        ordenar_por = str(args.get('ordenar_por') or '').strip()
        orden = str(args.get('orden') or 'desc').lower()

        if ordenar_por:
            reverse = orden != 'asc'
            def _sort_key(row):
                v = row.get(ordenar_por)
                if v is None:
                    return (1, 0, '')
                try:
                    return (0, float(str(v).replace(',', '')), '')
                except (ValueError, TypeError):
                    return (0, 0, str(v).lower())
            rows = sorted(rows, key=_sort_key, reverse=reverse)

        # Limitar
        top_n = args.get('top_n')
        if top_n is not None:
            try:
                top_n = max(1, min(500, int(top_n)))
                rows = rows[:top_n]
            except (ValueError, TypeError):
                pass

        return {
            rows_key: rows,
            '_origen': 'cache_previo',
            '_total_filtrado': len(rows),
        }
