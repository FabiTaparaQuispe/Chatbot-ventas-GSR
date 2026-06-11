"""
Formatea resultados de herramientas directamente en Python, sin llamada al LLM.
Elimina el segundo round-trip al LLM en el 80% de las consultas típicas.
Retorna None si el resultado es complejo o tiene error (el LLM se encarga).
"""
import json


def _m(val):
    """Formatea un número como importe en soles."""
    try:
        return f"S/ {float(val):,.2f}"
    except (ValueError, TypeError):
        return str(val)


def _n(val):
    """Formatea un entero con separador de miles."""
    try:
        return f"{int(float(val)):,}"
    except (ValueError, TypeError):
        return str(val)


def _periodo(result):
    p = result.get('periodo', {})
    if isinstance(p, dict):
        d, h = p.get('desde', ''), p.get('hasta', '')
        if d and h:
            return f"{d} al {h}"
    return ''


def _url(result):
    return str(result.get('reporte_url', '') or '')


def _ranking_clientes(filas, campo_valor='suma_valor', campo_nombre='nombre_cliente',
                      campo_lineas=None, campo_pct=None):
    lines = []
    for i, r in enumerate(filas, 1):
        nombre = r.get(campo_nombre) or r.get('nombre_cliente') or '?'
        valor = _m(r.get(campo_valor, 0))
        extra = []
        if campo_lineas and r.get(campo_lineas) is not None:
            extra.append(f"{_n(r[campo_lineas])} líneas")
        if campo_pct and r.get(campo_pct) is not None:
            extra.append(f"{float(r[campo_pct]):.1f}%")
        suffix = f" ({', '.join(extra)})" if extra else ''
        lines.append(f"{i}. {nombre}: {valor}{suffix}")
    return lines


def _auto_row_summary(row: dict) -> str:
    """Genera una línea de resumen de una fila con campos desconocidos."""
    money_fields = ('suma_valor', 'Valor', 'valor', 'importe', 'total')
    name_fields = ('nombre_cliente', 'glosa', 'etiqueta', 'nombre', 'Cliente', 'NombreCliente')
    label = next((str(row[k]) for k in name_fields if row.get(k)), None)
    amount = next((_m(row[k]) for k in money_fields if row.get(k) is not None), None)
    if label and amount:
        return f"{label}: {amount}"
    if label:
        return label
    # fallback: primeros 3 campos
    parts = [f"{k}={v}" for k, v in list(row.items())[:3]]
    return ', '.join(parts)


# ── Formatters por herramienta ────────────────────────────────────────────────

def _fmt_top_clientes_global(result):
    filas = result.get('filas', [])
    if not filas:
        return None
    per = _periodo(result)
    total = result.get('total_valor')
    header = "Top clientes"
    if per:
        header += f" del {per}"
    if total:
        header += f" (total período: {_m(total)})"
    lines = [header + ":\n"]
    lines += _ranking_clientes(filas, campo_lineas='lineas', campo_pct='pct_del_total')
    url = _url(result)
    if url:
        lines.append(f"\n{url}")
    return '\n'.join(lines)


def _fmt_top_clientes_zona(result):
    filas = result.get('filas_ranking', [])
    if not filas:
        return None
    zona = result.get('prefijo_descri_zona_precio', '')
    per = _periodo(result)
    total_zona = result.get('total_valor_zona')
    header = f"Top clientes zona {zona}" if zona else "Top clientes por zona"
    if per:
        header += f" ({per})"
    if total_zona:
        header += f" — total zona: {_m(total_zona)}"
    lines = [header + ":\n"]
    lines += _ranking_clientes(filas, campo_lineas='lineas_venta', campo_pct='pct_del_total_zona')
    url = _url(result)
    if url:
        lines.append(f"\n{url}")
    return '\n'.join(lines)


def _fmt_top_productos(result):
    filas = result.get('filas', [])
    if not filas:
        return None
    per = _periodo(result)
    header = "Top productos"
    if per:
        header += f" del {per}"
    lines = [header + ":\n"]
    for i, r in enumerate(filas, 1):
        glosa = r.get('glosa') or r.get('GlosaDetalle') or '?'
        valor = _m(r.get('suma_valor', 0))
        cant = r.get('suma_cantidad')
        suffix = f" (cantidad: {_n(cant)})" if cant is not None else ''
        lines.append(f"{i}. {glosa}: {valor}{suffix}")
    url = _url(result)
    if url:
        lines.append(f"\n{url}")
    return '\n'.join(lines)


def _fmt_resumen(result):
    agr = result.get('agregados', {})
    if not agr:
        return None
    per = _periodo(result)
    lines = [f"Resumen del {per}:\n" if per else "Resumen:\n"]
    n = agr.get('filas')
    if n is not None:
        lines.append(f"- Registros: {_n(n)}")
    sv = agr.get('suma_valor')
    if sv is not None:
        lines.append(f"- Importe total: {_m(sv)}")
    sc = agr.get('suma_cantidad')
    if sc is not None:
        lines.append(f"- Cantidad total: {_n(sc)}")
    sp = agr.get('suma_peso')
    if sp is not None:
        lines.append(f"- Peso total: {_n(sp)} kg")
    url = _url(result)
    if url:
        lines.append(f"\n{url}")
    return '\n'.join(lines)


def _fmt_barras_dimension(result):
    filas = result.get('filas', [])
    if not filas:
        return None
    per = _periodo(result)
    dim = result.get('dimension', '')
    header = f"Ventas por {'zona precio' if dim == 'precio' else 'zona comercial'}"
    if per:
        header += f" del {per}"
    lines = [header + ":\n"]
    for i, r in enumerate(filas, 1):
        etq = r.get('etiqueta') or '?'
        valor = _m(r.get('suma_valor', 0))
        lineas = r.get('lineas')
        suffix = f" ({_n(lineas)} líneas)" if lineas else ''
        lines.append(f"{i}. {etq}: {valor}{suffix}")
    url = _url(result)
    if url:
        lines.append(f"\n{url}")
    return '\n'.join(lines)


def _fmt_top_clientes_nc(result):
    filas = result.get('filas_ranking', [])
    if not filas:
        return None
    per = _periodo(result)
    header = "Top clientes con notas de crédito"
    if per:
        header += f" del {per}"
    lines = [header + ":\n"]
    for i, r in enumerate(filas, 1):
        nombre = r.get('nombre_cliente') or '?'
        valor = _m(r.get('suma_valor', 0))
        nc = r.get('num_nc') or r.get('lineas_nc')
        suffix = f" ({_n(nc)} NC)" if nc else ''
        lines.append(f"{i}. {nombre}: {valor}{suffix}")
    url = _url(result)
    if url:
        lines.append(f"\n{url}")
    return '\n'.join(lines)


def _fmt_filtrar_previo(result):
    rows = None
    for key in ('filas', 'filas_ranking', 'filas_pareto'):
        rows = result.get(key)
        if rows:
            break
    if not rows:
        return "No se encontraron registros con ese filtro en el resultado anterior."
    total = result.get('_total_filtrado', len(rows))
    lines = [f"Resultado filtrado ({_n(total)} registros):\n"]
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. {_auto_row_summary(r)}")
    return '\n'.join(lines)


def _fmt_catalogo(result):
    filas = result.get('filas', [])
    if not filas:
        return None
    campo = result.get('campo', '')
    header = f"Valores de {campo}" if campo else "Catálogo"
    lines = [header + ":\n"]
    for r in filas:
        val = next(iter(r.values()), '') if r else ''
        lines.append(f"- {val}")
    return '\n'.join(lines)


def _fmt_pareto_nc(result):
    filas = result.get('filas_pareto', [])
    if not filas:
        return None
    per = _periodo(result)
    total = result.get('total_impacto_nc_valor_abs')
    header = "Pareto NC por zona de precio"
    if per:
        header += f" del {per}"
    if total:
        header += f" (total NC: {_m(total)})"
    lines = [header + ":\n"]
    for i, r in enumerate(filas, 1):
        zona = r.get('zona') or '?'
        valor = _m(r.get('impacto_abs_valor', 0))
        lineas = r.get('lineas_nc')
        pct = r.get('pct_del_total')
        acum = r.get('pct_acumulado')
        parts = []
        if lineas is not None:
            parts.append(f"{_n(lineas)} líneas NC")
        if pct is not None:
            parts.append(f"{float(pct):.1f}% del total")
        if acum is not None:
            parts.append(f"acumulado: {float(acum):.1f}%")
        suffix = f" ({', '.join(parts)})" if parts else ''
        lines.append(f"{i}. **{zona}**: {valor}{suffix}")
    url = _url(result)
    if url:
        lines.append(f"\n{url}")
    return '\n'.join(lines)


def _fmt_barras_ruta(result):
    filas = result.get('filas', [])
    if not filas:
        return None
    per = _periodo(result)
    header = "Ventas por ruta comercial"
    if per:
        header += f" del {per}"
    lines = [header + ":\n"]
    for i, r in enumerate(filas, 1):
        etq = r.get('etiqueta') or r.get('ruta') or r.get('RutaComercial') or '?'
        valor = _m(r.get('suma_valor', 0))
        lineas = r.get('lineas')
        suffix = f" ({_n(lineas)} líneas)" if lineas else ''
        lines.append(f"{i}. {etq}: {valor}{suffix}")
    url = _url(result)
    if url:
        lines.append(f"\n{url}")
    return '\n'.join(lines)


def _fmt_resumen_por_provincia(result):
    filas = result.get('filas', [])
    if not filas:
        return None
    per = _periodo(result)
    header = 'Resumen de ventas por provincia'
    if per:
        header += f' del {per}'
    lines = [
        header + ':\n',
        '| Provincia | Peso (kg) | Importe (S/) |',
        '| --- | ---: | ---: |',
    ]
    for r in filas:
        prov = r.get('provincia') or '?'
        peso = f"{float(r.get('suma_peso') or 0):,.2f}"
        valor = _m(r.get('suma_valor', 0))
        lines.append(f'| {prov} | {peso} | {valor} |')
    url = _url(result)
    if url:
        lines.append(f'\n{url}')
    return '\n'.join(lines)


def _fmt_barras_corporativo(result):
    filas = result.get('filas', [])
    if not filas:
        return None
    per = _periodo(result)
    nom_cli = result.get('filtro_nombre_cliente', '')
    nom_corp = result.get('filtro_nombre_corporativo', '')
    if nom_cli:
        header = f"Corporativos del cliente '{nom_cli}'"
    elif nom_corp:
        header = f"Ventas del corporativo '{nom_corp}'"
    else:
        header = "Ventas por corporativo"
    if per:
        header += f" del {per}"
    lines = [header + ":\n"]
    for i, r in enumerate(filas, 1):
        etq = (
            r.get('etiqueta')
            or r.get('nombre_coorporativo')
            or r.get('NombreCoorporativo')
            or '?'
        )
        valor = _m(r.get('suma_valor', 0))
        lineas = r.get('lineas')
        suffix = f" ({_n(lineas)} líneas)" if lineas else ''
        lines.append(f"{i}. {etq}: {valor}{suffix}")
    url = _url(result)
    if url:
        lines.append(f"\n{url}")
    return '\n'.join(lines)


def _fmt_mix_tdoc(result):
    filas = result.get('filas', [])
    if not filas:
        return None
    per = _periodo(result)
    header = "Mix por tipo de documento"
    if per:
        header += f" del {per}"
    lines = [header + ":\n"]
    for i, r in enumerate(filas, 1):
        tdoc = r.get('tipo_documento') or r.get('TipoDocumento') or r.get('etiqueta') or '?'
        valor = _m(r.get('suma_valor', 0))
        pct = r.get('pct_del_total')
        suffix = f" ({float(pct):.1f}%)" if pct is not None else ''
        lines.append(f"{i}. {tdoc}: {valor}{suffix}")
    url = _url(result)
    if url:
        lines.append(f"\n{url}")
    return '\n'.join(lines)


def _fmt_serie_mensual(result):
    filas = result.get('filas', [])
    if not filas:
        return None
    per = _periodo(result)
    header = "Serie mensual de ventas"
    if per:
        header += f" ({per})"
    lines = [header + ":\n"]
    for r in filas:
        mes = r.get('mes') or r.get('periodo') or r.get('etiqueta') or '?'
        valor = _m(r.get('suma_valor', 0))
        lines.append(f"- {mes}: {valor}")
    url = _url(result)
    if url:
        lines.append(f"\n{url}")
    return '\n'.join(lines)


def _fmt_linea_precio_top_clientes(result):
    filas = result.get('filas', [])
    if not filas:
        return None
    linea = result.get('linea_comercial', '')
    mercado = result.get('mercado') or ''
    per = _periodo(result)
    header = f"Clientes por precio/kg: {linea}" if linea else "Clientes por precio/kg"
    if mercado:
        header += f" — mercado {mercado}"
    if per:
        header += f" ({per})"
    lines = [header + ":\n"]
    for i, r in enumerate(filas, 1):
        nom = r.get('nombre_cliente') or '?'
        pk = r.get('precio_kg')
        precio_s = f"S/ {float(pk):,.2f}/kg" if pk is not None else "S/ —/kg"
        peso = float(r.get('suma_peso') or 0)
        lines.append(f"{i}. {nom}: {precio_s} ({peso:,.2f} kg)")
    url = _url(result)
    if url:
        lines.append(f"\n{url}")
    return '\n'.join(lines)


def _fmt_linea_resumen(result):
    filas = result.get('filas', [])
    if not filas:
        return None
    linea = result.get('linea_comercial', '')
    per = _periodo(result)
    header = f"Resumen por cliente: {linea}" if linea else "Resumen por cliente"
    if per:
        header += f" del {per}"
    lines = [header + ":\n"]
    for i, r in enumerate(filas, 1):
        nom = r.get('nombre_cliente') or '?'
        prov = r.get('provincia') or '?'
        qty = r.get('suma_cantidad')
        peso = r.get('suma_peso')
        valor = float(r.get('suma_valor') or 0)
        parts = []
        if qty is not None:
            parts.append(f"{_n(qty)} unidades")
        if peso is not None:
            parts.append(f"{float(peso):,.2f} kg")
        parts.append(_m(valor))
        peso_f = float(peso) if peso is not None else 0
        if peso_f > 0:
            parts.append(f"precio S/ {valor / peso_f:.2f}/kg")
        lines.append(f"{i}. {nom} ({prov}): {', '.join(parts)}")
    url = _url(result)
    if url:
        lines.append(f"\n{url}")
    return '\n'.join(lines)


# ── Dispatcher ────────────────────────────────────────────────────────────────

def _fmt_proyeccion_dia(result):
    if result.get('tipo') != 'proyeccion_dia':
        return None
    valor = result.get('valor_proyectado')
    if valor is None:
        return None
    escala = str(result.get('escala', 'dia') or 'dia')
    filtros = result.get('filtros') or {}
    linea = filtros.get('linea_comercial')
    prov = filtros.get('provincia')
    sujeto = f"de {linea} " if linea else ""
    lugar = f" en {prov}" if prov else ""
    if escala == 'dia':
        dia = str(result.get('dia_semana', '') or '')
        fecha = str(result.get('fecha_inicio', '') or result.get('fecha_proyectada', '') or '')
        cuando = f"el {dia} {fecha}".strip() if dia else f"el {fecha}"
    else:
        etiqueta = {'semana': 'la próxima semana', 'quincena': 'la próxima quincena',
                    'mes': 'los próximos 30 días'}.get(escala, 'el período')
        d1 = str(result.get('fecha_inicio', '') or '')
        d2 = str(result.get('fecha_fin', '') or '')
        cuando = f"{etiqueta} (del {d1} al {d2})"
    cantidad = result.get('cantidad_proyectada')
    peso = result.get('peso_proyectado')
    lineas = [f"Proyección de venta {sujeto}para {cuando}{lugar}:", ""]
    lineas.append(f"- Importe: {_m(valor)}")
    if cantidad is not None:
        lineas.append(f"- Cantidad: {_n(cantidad)} unidades")
    if peso is not None:
        lineas.append(f"- Peso: {_n(peso)} kg")
    precio = result.get('precio_kg_usado')
    if precio:
        lineas.append(f"  (importe calculado a S/ {float(precio):,.2f} por kg sobre el peso proyectado)")
    url = _url(result)
    if url:
        lineas.append(f"\n{url}")
    lineas += ["", "Nota: Proyección basada en datos actuales."]
    return "\n".join(lineas)


def _fmt_proyeccion_ventas(result):
    if result.get('tipo') != 'proyeccion_ventas':
        return None
    proy = result.get('proyecciones') or []
    if not proy:
        return None
    lines = [
        "Proyección:",
        "| Mes | Valor (S/) | Unidades | Peso prom (kg/u) | Peso total (kg) |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for p in proy:
        mes = str(p.get('mes', '') or '')
        valor = f"{float(p.get('valor_proyectado') or 0):,.2f}"
        cant = f"{round(float(p.get('cantidad_proyectada') or 0)):,}"
        pprom = f"{float(p.get('peso_prom_proyectado') or 0):,.2f}"
        ptot = f"{float(p.get('peso_total_proyectado') or 0):,.2f}"
        lines.append(f"| {mes} | {valor} | {cant} | {pprom} | {ptot} |")
    lines.append(str(result.get('nota') or 'Nota: Proyección basada en datos actuales.'))
    return '\n'.join(lines)


def _fmt_proyeccion_ventas(result):
    proy = result.get('proyecciones')
    if not isinstance(proy, list) or not proy:
        return None
    lineas = ["Proyección:", "",
              "| Mes | Valor (S/) | Unidades | Peso prom (kg/u) | Peso total (kg) |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for p in proy:
        valor = format(float(p.get('valor_proyectado', 0) or 0), ',.2f')
        pprom = format(float(p.get('peso_prom_proyectado', 0) or 0), ',.2f')
        lineas.append(
            f"| {p.get('mes', '')} | {valor} | {_n(p.get('cantidad_proyectada', 0))} "
            f"| {pprom} | {_n(p.get('peso_total_proyectado', 0))} |"
        )
    precio = result.get('precio_kg_usado')
    if precio:
        lineas.append(f"\n(importe calculado a S/ {float(precio):,.2f} por kg sobre el peso proyectado)")
    url = _url(result)
    if url:
        lineas.append(f"\n{url}")
    lineas += ["", "Nota: Proyección basada en datos actuales."]
    return "\n".join(lineas)


def _fmt_cumplimiento(result):
    if result.get('tipo') != 'cumplimiento_pedidos':
        return None
    filas = result.get('filas') or []
    if not filas:
        return None
    lineas = [
        "Cumplimiento de pedidos (pedido vs vendido):", "",
        "| Cliente | Producto | Pedido (u) | Vendido (u) | Cumplimiento |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for f in filas:
        nombre = str(f.get('nombre') or f.get('cliente') or '')
        prod = str(f.get('producto') or f.get('item') or '')
        ped = _n(f.get('pedido_u', 0))
        ven = _n(f.get('vendido_u', 0))
        pct = f"{float(f.get('cumplimiento_pct') or 0):,.1f}%"
        lineas.append(f"| {nombre} | {prod} | {ped} | {ven} | {pct} |")
    tp = result.get('total_pedido')
    if tp is not None:
        tv = result.get('total_vendido')
        tpct = float(result.get('cumplimiento_total_pct') or 0)
        lineas.append("")
        lineas.append(f"Total: pedido {_n(tp)} u · vendido {_n(tv)} u · cumplimiento {tpct:,.1f}%")
    url = _url(result)
    if url:
        lineas.append(f"\n{url}")
    lineas += ["", "Nota: cumplimiento = vendido / pedido. Los datos de pedidos existen desde diciembre 2025."]
    return "\n".join(lineas)


_FORMATTERS = {
    'cumplimiento_pedidos':                   _fmt_cumplimiento,
    'ventasgeneral_proyeccion_dia':           _fmt_proyeccion_dia,
    'ventasgeneral_proyeccion_ventas':        _fmt_proyeccion_ventas,
    'ventasgeneral_proyeccion_ventas':        _fmt_proyeccion_ventas,
    'ventasgeneral_top_clientes_globales':    _fmt_top_clientes_global,
    'ventasgeneral_top_clientes_zona_precio': _fmt_top_clientes_zona,
    'ventasgeneral_top_productos':            _fmt_top_productos,
    'ventasgeneral_resumen':                  _fmt_resumen,
    'ventasgeneral_barras_ventas_dimension':  _fmt_barras_dimension,
    'ventasgeneral_top_clientes_nota_credito': _fmt_top_clientes_nc,
    'filtrar_previo':                         _fmt_filtrar_previo,
    'ventasgeneral_catalogo':                 _fmt_catalogo,
    'ventasgeneral_pareto_nc_zonaprecio':     _fmt_pareto_nc,
    'ventasgeneral_barras_ruta_comercial':    _fmt_barras_ruta,
    'ventasgeneral_barras_corporativo':       _fmt_barras_corporativo,
    'ventasgeneral_mix_tdoc':                 _fmt_mix_tdoc,
    'ventasgeneral_serie_mensual_valor':      _fmt_serie_mensual,
    'ventasgeneral_linea_resumen_provincia':  _fmt_linea_resumen,
    'ventasgeneral_linea_top_clientes_precio_kg': _fmt_linea_precio_top_clientes,
    'ventasgeneral_resumen_por_provincia':    _fmt_resumen_por_provincia,
}


def try_fast_format(tool_name: str, result_json: str) -> str | None:
    """
    Intenta formatear el resultado sin LLM.
    Retorna el texto formateado o None (el LLM debe hacerlo).
    """
    try:
        result = json.loads(result_json)
    except Exception:
        return None

    if not isinstance(result, dict):
        return None

    # Si hay error en el resultado, dejar al LLM para que lo explique bien
    if result.get('error'):
        return None

    fn = _FORMATTERS.get(tool_name)
    if fn is None:
        return None

    try:
        return fn(result)
    except Exception:
        return None
