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


def enrich_reply(reply: str, groq_messages: list) -> str:
    reply = _sanitize_urls(reply.strip())
    payload = _last_tool_payload(groq_messages)
    if payload is None:
        if _uses_generic_labels(reply):
            url = _extract_reporte_url(reply)
            note = ('Los nombres de cliente no están disponibles porque el asistente respondió desde el historial '
                    'sin consultar la base de datos. '
                    'Hacé la misma pregunta de nuevo para obtener los datos actualizados.')
            return (note + '\n\n' + url).strip() if url else note
        return reply

    summary = _format_payload(payload)
    if not summary:
        return reply

    if _uses_generic_labels(reply):
        return _summary_with_url(summary, reply, payload)

    if _looks_like_ranking(reply):
        url = str(payload.get('reporte_url') or '').strip()
        if url and not _extract_reporte_url(reply):
            reply = (reply + '\n\n' + url).strip()
        return _dedup_module_url(reply)

    head = summary[:120]
    if head and reply and summary[:60].lower() in reply.lower():
        return reply

    return (summary + ('\n\n' + reply if reply else '')).strip()


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


def _lines_linea_resumen_provincia(filas):
    out = []
    for i, r in enumerate(filas, 1):
        nom = str(r.get('nombre_cliente') or '')
        prov = str(r.get('provincia') or '')
        ln = int(r.get('lineas') or 0)
        cant = _fmt_num(r.get('suma_cantidad') or 0)
        peso = _fmt_num(r.get('suma_peso') or 0)
        v = _fmt_num(r.get('suma_valor') or 0)
        out.append(f'{i}. {nom} ({prov}): {ln:,} líneas, {cant} unidades, {peso} kg, S/ {v}')
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
        out.append(f'{i}. {prov}: {precio_s} ({ln:,} líneas, {peso} kg, S/ {v})')
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
