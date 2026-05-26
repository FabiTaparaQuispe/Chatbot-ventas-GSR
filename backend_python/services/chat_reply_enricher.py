import json
import re

TDOC_MAP = {
    '01': 'Factura', '02': 'Recibo por honorarios', '03': 'Boleta de venta',
    '04': 'Liquidación de compra', '05': 'Boletos de transporte',
    '06': 'Carta de porte aéreo', '07': 'Nota de crédito', '08': 'Nota de débito',
    '09': 'Guía de remisión remitente', '11': 'Póliza emitida por el SNCE',
    '12': 'Ticket o cinta de máquina registradora',
    '13': 'Documento emitido por bancos e instituciones financieras',
    '14': 'Recibo por servicios públicos', '15': 'Boletos emitidos por el SNCE',
    '16': 'Ticket de viaje', '18': 'Documento emitido por AFP',
    '20': 'Comprobante de retención', '21': 'Conocimiento de embarque',
    '22': 'Documentos emitidos por las COFOPRI', '23': 'Guía de remisión transportista',
    '24': 'Documento del operador', '25': 'Documento autorizado en el SNCE',
    '40': 'Comprobante de percepción', '99': 'Otros',
}


def _tdoc_etiqueta(tdoc: str) -> str:
    raw = tdoc.strip()
    if not raw or raw.lower() == '(sin tdoc)':
        return 'Sin tipo indicado'
    if raw in TDOC_MAP:
        return TDOC_MAP[raw]
    digits = re.sub(r'\D', '', raw)
    if digits:
        norm = digits.zfill(2) if len(digits) <= 2 else digits
        if norm in TDOC_MAP:
            return TDOC_MAP[norm]
    return 'Tipo ' + raw


def _fmt_num(v, decimals=2) -> str:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return str(v)
    s = f'{n:,.{decimals}f}'
    return s


def _fmt_int(v) -> str:
    """Entero con separador de miles (unidades, líneas, etc.)."""
    try:
        return f'{int(float(v)):,}'
    except (TypeError, ValueError):
        return str(v)


_FAKE_DOMAIN_RE = re.compile(
    r'https?://(?:example\.com|localhost(?::\d+)?|127\.0\.0\.1(?::\d+)?)(?::\d+)?(/[^\s<>"\']*)',
    re.IGNORECASE,
)
_HASH_FRAGMENT_RE = re.compile(r'(/modules/[^\s<>"\']+?)#\w+', re.IGNORECASE)


def _sanitize_urls(text: str) -> str:
    """Strip fake domains (example.com/localhost) and URL fragments from /modules/ paths."""
    text = _FAKE_DOMAIN_RE.sub(r'\1', text)
    text = _HASH_FRAGMENT_RE.sub(r'\1', text)
    return text


def _normalize_minus_signs(text: str) -> str:
    """Reemplaza signos menos tipográficos (U+2212, en-dash U+2013) con ASCII '-' antes de dígitos."""
    return re.sub(r'[−–](\d)', r'-\1', text)


def _clean_table_asterisks(text: str) -> str:
    """Elimina marcadores ** sueltos dentro de celdas de tabla markdown."""
    # | ** | → quitar fila completa si la celda es solo asteriscos
    text = re.sub(r'\n?\|[^|\n]*\|\s*\*\*\s*\|\s*\n', '\n', text)
    # **texto** dentro de celda → texto (sin negrita)
    text = re.sub(r'\*\*([^*\n|]+)\*\*', r'\1', text)
    # ** al inicio de celda: | ** valor | → | valor |
    text = re.sub(r'\|\s*\*\*\s*([^*|])', r'| \1', text)
    # asteriscos sueltos restantes en celdas
    text = re.sub(r'(?<=\|)\s*\*+\s*(?=\|)', ' ', text)
    return text


def _format_display_numbers(text: str) -> str:
    """Aplica separador de miles a unidades, kg, líneas y montos S/ en texto libre."""
    if not text:
        return text
    s = str(text)

    def _fmt_token(num_str: str, decimals: int | None = None) -> str:
        raw = num_str.strip()
        if ',' in raw:
            return raw
        try:
            n = float(raw.replace(',', ''))
        except (TypeError, ValueError):
            return raw
        if decimals is not None:
            return f'{n:,.{decimals}f}'
        if '.' in raw:
            dec = len(raw.split('.')[1])
            return f'{n:,.{dec}f}'
        return f'{int(n):,}'

    s = re.sub(
        r'\bS/\s*(\d+(?:\.\d+)?)\b',
        lambda m: 'S/ ' + _fmt_token(m.group(1), 2 if '.' in m.group(1) else None),
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r'(\d+(?:\.\d+)?)\s+unidades\b',
        lambda m: _fmt_token(m.group(1)) + ' unidades',
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r'(\d+(?:\.\d+)?)\s+kg\b',
        lambda m: _fmt_token(m.group(1)) + ' kg',
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r'(\d+(?:\.\d+)?)\s+líneas\b',
        lambda m: _fmt_token(m.group(1)) + ' líneas',
        s,
        flags=re.IGNORECASE,
    )
    return s


def _dedup_module_url(text: str) -> str:
    """Remove a duplicate /modules/... URL line when the same URL already appears in the text."""
    lines = text.splitlines()
    seen_urls: set = set()
    out = []
    for line in lines:
        stripped = line.strip()
        is_url_line = bool(re.match(r'^/modules/\S+\?\S', stripped))
        if is_url_line:
            key = stripped.split('#')[0]
            if key in seen_urls:
                continue
            seen_urls.add(key)
        else:
            m = re.search(r'/modules/\S+\?\S+', stripped)
            if m:
                key = m.group(0).split('#')[0]
                seen_urls.add(key)
        out.append(line)
    return '\n'.join(out)


def _append_url(text: str, url: str) -> str:
    if url and not _extract_reporte_url(text):
        return (text + '\n\n' + url).strip()
    return text


def enrich_reply(reply: str, groq_messages: list, last_tool_json: str | None = None) -> str:
    reply = _format_display_numbers(_clean_table_asterisks(_normalize_minus_signs(_sanitize_urls(reply.strip()))))
    payload = _payload_from_json(last_tool_json) if last_tool_json else _last_tool_payload(groq_messages)
    if payload is None:
        if _uses_generic_labels(reply):
            url = _extract_reporte_url(reply)
            note = ('Los nombres de cliente no están disponibles porque el asistente respondió desde el historial '
                    'sin consultar la base de datos. '
                    'Hacé la misma pregunta de nuevo para obtener los datos actualizados.')
            return _format_display_numbers((note + '\n\n' + url).strip() if url else note)
        return reply

    summary = _format_payload(payload)
    report_url = str(payload.get('reporte_url') or '').strip()

    if not summary:
        return _format_display_numbers(_append_url(reply, report_url))

    if _uses_generic_labels(reply):
        return _format_display_numbers(_summary_with_url(summary, reply, payload))

    if _looks_like_ranking(reply):
        return _format_display_numbers(_dedup_module_url(_append_url(reply, report_url)))

    head = summary[:120]
    if head and reply and summary[:60].lower() in reply.lower():
        return _format_display_numbers(_append_url(reply, report_url))

    result = _format_display_numbers((summary + ('\n\n' + reply if reply else '')).strip())
    return _append_url(result, report_url)


def _payload_from_json(tool_json: str):
    """Parse a raw tool JSON string into a payload dict (returns None on error or if contains error key)."""
    try:
        decoded = json.loads(tool_json)
    except Exception:
        return None
    if not isinstance(decoded, dict) or decoded.get('error'):
        return None
    return decoded


def _last_tool_payload(messages: list):
    last = None
    for m in messages:
        if not isinstance(m, dict) or m.get('role') != 'tool':
            continue
        raw = m.get('content') or ''
        if not raw:
            continue
        try:
            decoded = json.loads(raw)
        except Exception:
            continue
        if not isinstance(decoded, dict):
            continue
        if decoded.get('error'):
            continue
        last = decoded
    return last


def _looks_like_ranking(reply: str) -> bool:
    return bool(reply and len(re.findall(r'^\d+\.\s+', reply, re.MULTILINE)) >= 2)


def _uses_generic_labels(reply: str) -> bool:
    return bool(re.search(r'^\d+\.\s*Cliente\s+\d+', reply, re.MULTILINE | re.IGNORECASE))


def _extract_reporte_url(reply: str) -> str:
    reply = re.sub(r'[​-‍﻿ ]', '', reply)
    reply = re.sub(
        r'https?://(?:example\.com|localhost|127\.0\.0\.1|[a-z0-9_-]+\.example\.com)(?::\d+)?/',
        '', reply
    )
    m = re.search(
        r'(https?://[^\s<]+|/modules/[^\s<]+\?[^\s<>"\']+|(?:ventas_(?:barras_dimension|comparativo|top_productos|top_clientes_global|top_clientes_nc|mix_tdoc|barras_ruta|barras_corporativo|serie_mensual)|pareto_(?:nc_zona|clientes_zona)(?:_tabla)?|ventasgeneral_(?:buscar|resumen)(?:_tabla)?)\.php\?[^\s<>"\']+)',
        reply,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).rstrip('),.;\'"` ')
    return ''


def _summary_with_url(summary: str, reply: str, payload: dict) -> str:
    url = str(payload.get('reporte_url') or '').strip()
    if not url:
        url = _extract_reporte_url(reply)
    if url:
        return (summary + '\n\n' + url).strip()
    return summary.strip()


def _format_payload(payload: dict) -> str:
    # Meta-consultas del chatbot (app_chat_*): no usar la rama de "resumen ventas" por agregados.
    if str(payload.get('tipo') or '').startswith('chat_'):
        return ''

    # Búsqueda de filas individuales o clientes de corporativo: el LLM ya formatea bien la tabla, solo añadir URL.
    if str(payload.get('tipo') or '') in ('buscar', 'clientes_corporativo'):
        return ''

    if 'agregados' in payload and isinstance(payload['agregados'], dict) and 'filas' not in payload:
        a = payload['agregados']
        p = payload.get('periodo') or {}
        d1 = str(p.get('desde') or '') if isinstance(p, dict) else ''
        d2 = str(p.get('hasta') or '') if isinstance(p, dict) else ''
        filas_n = str(a.get('filas') or '')
        sv = _fmt_num(a.get('suma_valor') or 0)
        period_s = f' {d1} – {d2}' if d1 and d2 else ''
        return f'Resumen del periodo{period_s}: {filas_n} líneas de detalle, importe total S/ {sv}.'

    filas = None
    if isinstance(payload.get('filas_pareto'), list):
        filas = payload['filas_pareto']
    elif isinstance(payload.get('filas_ranking'), list):
        filas = payload['filas_ranking']
    elif isinstance(payload.get('filas'), list):
        filas = payload['filas']
    elif isinstance(payload.get('proyecciones'), list):
        return _lines_proyecciones(payload['proyecciones'], payload)

    if not filas:
        return ''

    criterio = str(payload.get('criterio') or '')
    first = filas[0] if filas else {}
    if not isinstance(first, dict):
        return ''

    if str(payload.get('tipo') or '') == 'resumen_por_provincia':
        return _lines_resumen_por_provincia(filas)

    if str(payload.get('tipo') or '') == 'clientes_corporativo':
        return _lines_clientes_corporativo(filas, payload)

    if str(payload.get('tipo') or '') == 'linea_resumen_provincia_cliente':
        return _lines_linea_resumen_provincia(filas)

    if str(payload.get('tipo') or '') == 'linea_precio_resumen_provincia':
        return _lines_linea_precio_resumen_provincia(filas, payload)

    if 'zona' in first and 'lineas_nc' in first and 'impacto_abs_valor' in first:
        return _lines_pareto_nc(filas)
    if 'nombre_cliente' in first and 'lineas_venta' in first and 'suma_valor' in first:
        return _lines_top_zona(filas)
    if 'nombre_cliente' in first and 'lineas' in first and 'suma_valor' in first:
        is_nc = any(x in criterio.lower() for x in ['tdoc', 'nota', '07'])
        return _lines_top_nc(filas) if is_nc else _lines_top_global(filas)
    if 'etiqueta' in first and 'suma_valor' in first and 'valor_periodo_a' not in first:
        return _lines_etiqueta(filas)
    if ('glosa' in first or 'cod_item' in first) and 'suma_valor' in first:
        return _lines_productos(filas)
    if 'tdoc' in first and 'suma_valor' in first:
        return _lines_mix_tdoc(filas)
    if 'valor_periodo_a' in first and 'valor_periodo_b' in first and 'etiqueta' in first:
        return _lines_comparativo(filas)
    if 'ruta' in first and 'suma_valor' in first:
        return _lines_named(filas, 'ruta')
    if 'nombre_coorporativo' in first and 'suma_valor' in first:
        return _lines_named(filas, 'nombre_coorporativo')
    if 'mes' in first and 'suma_valor' in first:
        return _lines_serie_mensual(filas)
    return _lines_generic(filas)


def _lines_pareto_nc(filas):
    out = []
    for i, r in enumerate(filas[:25], 1):
        z = str(r.get('zona') or '')
        n = int(r.get('lineas_nc') or 0)
        v = _fmt_num(r.get('impacto_abs_valor') or 0)
        out.append(f'{i}. {z}: {n} líneas NC, impacto en importe (soles) S/ {v}')
    return '\n'.join(out)


def _lines_top_zona(filas):
    out = []
    for i, r in enumerate(filas[:25], 1):
        nom = str(r.get('nombre_cliente') or '')
        ln = int(r.get('lineas_venta') or 0)
        v = _fmt_num(r.get('suma_valor') or 0)
        out.append(f'{i}. {nom}: {ln} líneas, importe S/ {v}')
    return '\n'.join(out)


def _lines_top_nc(filas):
    out = []
    for i, r in enumerate(filas[:25], 1):
        nom = str(r.get('nombre_cliente') or '')
        ln = int(r.get('lineas') or 0)
        v = _fmt_num(r.get('suma_valor') or 0)
        out.append(f'{i}. {nom}: {ln} notas de crédito por valor de {v}')
    return '\n'.join(out)


def _lines_clientes_corporativo(filas, payload):
    corp = str(payload.get('nombre_corporativo') or '')
    total = len(filas)
    header = f'Corporativo: **{corp}** — {total} cliente(s)\n' if corp else f'{total} cliente(s)\n'
    lines = [header, '| # | Cliente | Líneas | Peso (kg) | Importe (S/) |', '| --- | --- | ---: | ---: | ---: |']
    for i, r in enumerate(filas, 1):
        nom = str(r.get('nombre_cliente') or '')
        ln = _fmt_int(r.get('lineas') or 0)
        peso = _fmt_num(r.get('suma_peso') or 0)
        val = _fmt_num(r.get('suma_valor') or 0)
        lines.append(f'| {i} | {nom} | {ln} | {peso} | {val} |')
    return '\n'.join(lines)


def _lines_resumen_por_provincia(filas):
    lines = ['| Provincia | Peso (kg) | Importe (S/) |', '| --- | ---: | ---: |']
    for r in filas:
        prov = str(r.get('provincia') or '')
        peso = _fmt_num(r.get('suma_peso') or 0)
        v = _fmt_num(r.get('suma_valor') or 0)
        lines.append(f'| {prov} | {peso} | S/ {v} |')
    return '\n'.join(lines)


def _lines_linea_resumen_provincia(filas):
    out = []
    for i, r in enumerate(filas, 1):
        nom = str(r.get('nombre_cliente') or '')
        prov = str(r.get('provincia') or '')
        ln = int(r.get('lineas') or 0)
        cant = _fmt_int(r.get('suma_cantidad') or 0)
        peso = _fmt_num(r.get('suma_peso') or 0)
        v = _fmt_num(r.get('suma_valor') or 0)
        out.append(f'{i}. {nom} ({prov}): {_fmt_int(ln)} líneas, {cant} unidades, {peso} kg, S/ {v}')
    return '\n'.join(out)


def _lines_linea_precio_resumen_provincia(filas, payload):
    out = []
    for i, r in enumerate(filas, 1):
        prov = str(r.get('provincia') or '')
        ln = int(r.get('lineas') or 0)
        peso = _fmt_num(r.get('suma_peso') or 0)
        v = _fmt_num(r.get('suma_valor') or 0)
        pk = r.get('precio_kg')
        precio_s = f'S/ {_fmt_num(pk, 2)}' if pk is not None else 'S/ —'
        out.append(f'{i}. {prov}: {precio_s} ({_fmt_int(ln)} líneas, {peso} kg, S/ {v})')
    total_pk = payload.get('total_precio_kg')
    if total_pk is not None:
        out.append(f'Total ponderado del período: S/ {_fmt_num(total_pk, 2)}')
    return '\n'.join(out)


def _lines_top_global(filas):
    out = []
    for i, r in enumerate(filas[:25], 1):
        nom = str(r.get('nombre_cliente') or '')
        ln = int(r.get('lineas') or 0)
        v = _fmt_num(r.get('suma_valor') or 0)
        pct = r.get('pct_del_total')
        pct_s = f', {_fmt_num(pct, 2)}% del total' if pct is not None else ''
        out.append(f'{i}. {nom}: {ln} líneas, importe S/ {v}{pct_s}')
    return '\n'.join(out)


def _lines_etiqueta(filas):
    out = []
    for i, r in enumerate(filas[:25], 1):
        e = str(r.get('etiqueta') or '')
        ln = int(r.get('lineas') or 0)
        v = _fmt_num(r.get('suma_valor') or 0)
        out.append(f'{i}. {e}: {ln} líneas, importe S/ {v}')
    return '\n'.join(out)


def _lines_productos(filas):
    out = []
    for i, r in enumerate(filas[:25], 1):
        g = str(r.get('glosa') or r.get('cod_item') or '')
        v = _fmt_num(r.get('suma_valor') or 0)
        ln = int(r.get('lineas') or 0)
        out.append(f'{i}. {g}: {ln} líneas, importe S/ {v}')
    return '\n'.join(out)


def _lines_mix_tdoc(filas):
    out = []
    for i, r in enumerate(filas[:25], 1):
        t = str(r.get('tdoc') or '')
        label = _tdoc_etiqueta(t)
        ln = int(r.get('lineas') or 0)
        v = _fmt_num(r.get('suma_valor') or 0)
        out.append(f'{i}. {label}: {ln} líneas, importe S/ {v}')
    return '\n'.join(out)


def _lines_comparativo(filas):
    out = []
    for i, r in enumerate(filas[:25], 1):
        e = str(r.get('etiqueta') or '')
        a = _fmt_num(r.get('valor_periodo_a') or 0)
        b = _fmt_num(r.get('valor_periodo_b') or 0)
        d = _fmt_num(r.get('delta') or 0)
        out.append(f'{i}. {e}: periodo A S/ {a}, periodo B S/ {b}, diferencia S/ {d}')
    return '\n'.join(out)


def _lines_named(filas, key):
    out = []
    for i, r in enumerate(filas[:25], 1):
        e = str(r.get(key) or '')
        ln = int(r.get('lineas') or 0)
        v = _fmt_num(r.get('suma_valor') or 0)
        out.append(f'{i}. {e}: {ln} líneas, importe S/ {v}')
    return '\n'.join(out)


def _lines_serie_mensual(filas):
    out = []
    for i, r in enumerate(filas[:40], 1):
        mes = str(r.get('mes') or '')
        v = _fmt_num(r.get('suma_valor') or 0)
        ln = int(r.get('lineas') or 0)
        out.append(f'{i}. {mes}: {ln} líneas, importe S/ {v}')
    return '\n'.join(out)


def _lines_generic(filas):
    out = []
    for n, r in enumerate(filas[:12], 1):
        parts = [f'{k}={v}' for k, v in list(r.items())[:4]]
        out.append(f'{n}. {", ".join(parts)}')
        if n == 12 and len(filas) > 12:
            out.append(f'(+{len(filas) - 12} filas más en el reporte.)')
            break
    return '\n'.join(out)


def _lines_proyecciones(proyecciones, payload):
    out = []
    meses_hist = int(payload.get('meses_historicos') or 0)
    pendiente = _fmt_num(payload.get('pendiente_tendencia') or 0)
    out.append(f'Proyección basada en {meses_hist} meses históricos (pendiente: {pendiente}).')
    for r in proyecciones:
        mes = str(r.get('mes') or '')
        valor = _fmt_num(r.get('valor_proyectado') or 0)
        out.append(f'{mes}: S/ {valor}')
    nota = str(payload.get('nota') or '')
    if nota:
        out.append(f'Nota: {nota}')
    return '\n'.join(out)
