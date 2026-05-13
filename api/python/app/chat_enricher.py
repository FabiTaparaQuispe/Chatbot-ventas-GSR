from __future__ import annotations

import json
import re
from typing import Any

from app.documento_tipo import etiqueta_documento


def _fmt_num(v: Any, decimals: int = 2) -> str:
    try:
        return f"{float(v):,.{decimals}f}"
    except (TypeError, ValueError):
        return str(v)


def last_tool_payload(groq_messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    last: dict[str, Any] | None = None
    for m in groq_messages:
        if m.get("role") != "tool":
            continue
        raw = m.get("content")
        if not isinstance(raw, str) or not raw.strip():
            continue
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(decoded, dict):
            continue
        err = decoded.get("error")
        if isinstance(err, str) and err.strip():
            continue
        last = decoded
    return last


def reply_looks_like_ranking(reply: str) -> bool:
    if not reply.strip():
        return False
    return len(re.findall(r"^\d+\.\s+", reply, flags=re.M)) >= 2


def reply_uses_generic_cliente_labels(reply: str) -> bool:
    return bool(re.search(r"^\d+\.\s*Cliente\s+\d+", reply, flags=re.M | re.I))


def extract_reporte_php_url_from_reply(reply: str) -> str:
    reply = re.sub(r"[\u200B-\u200D\uFEFF\u00A0]", "", reply)
    reply = re.sub(
        r"https?://(?:example\.com|localhost|127\.0\.0\.1|[a-z0-9_-]+\.example\.com)(?::\d+)?/",
        "",
        reply,
        flags=re.I,
    )
    pat = re.compile(
        r"(https?://[^\s<]+|(?:ventas_(?:barras_dimension|comparativo|top_productos|top_clientes_global|top_clientes_nc|mix_tdoc|barras_ruta|barras_corporativo|serie_mensual)|pareto_(?:nc_zona|clientes_zona)(?:_tabla)?|ventasgeneral_(?:buscar|resumen)(?:_tabla)?)\.php\?[^\s<>\"']+|ventas-linea-(?:resumen-provincia|diario-provincia|precio-diario|mix-productos)\?[^\s<>\"']+)",
        flags=re.I,
    )
    m = pat.search(reply)
    if not m:
        return ""
    return re.sub(r"[\),.;'\"`]+$", "", m.group(1).rstrip())


def _lines_pareto_nc(filas: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for i, row in enumerate(filas[:25], start=1):
        z = str(row.get("zona") or "")
        n = int(row.get("lineas_nc") or 0)
        v = _fmt_num(row.get("impacto_abs_valor") or 0)
        out.append(f"{i}. {z}: {n} líneas NC, impacto en importe (soles) S/ {v}")
    return "\n".join(out)


def _lines_top_zona_precio(filas: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for i, row in enumerate(filas[:25], start=1):
        nom = str(row.get("nombre_cliente") or "")
        ln = int(row.get("lineas_venta") or 0)
        v = _fmt_num(row.get("suma_valor") or 0)
        out.append(f"{i}. {nom}: {ln} líneas, importe S/ {v}")
    return "\n".join(out)


def _lines_top_nc(filas: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for i, row in enumerate(filas[:25], start=1):
        nom = str(row.get("nombre_cliente") or "")
        ln = int(row.get("lineas") or 0)
        v = _fmt_num(row.get("suma_valor") or 0)
        out.append(f"{i}. {nom}: {ln} notas de crédito por valor de {v}")
    return "\n".join(out)


def _lines_linea_resumen_provincia(filas: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for i, row in enumerate(filas, start=1):
        nom = str(row.get("nombre_cliente") or "")
        prov = str(row.get("provincia") or "")
        ln = int(row.get("lineas") or 0)
        cant = _fmt_num(row.get("suma_cantidad") or 0)
        peso = _fmt_num(row.get("suma_peso") or 0)
        v = _fmt_num(row.get("suma_valor") or 0)
        out.append(
            f"{i}. {nom} ({prov}): {ln:,} líneas, {cant} unidades, {peso} kg, S/ {v}"
        )
    return "\n".join(out)


def _lines_top_clientes_global(filas: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for i, row in enumerate(filas[:25], start=1):
        nom = str(row.get("nombre_cliente") or "")
        ln = int(row.get("lineas") or 0)
        v = _fmt_num(row.get("suma_valor") or 0)
        pct = row.get("pct_del_total")
        pct_s = f", {_fmt_num(pct, 2)}% del total" if pct is not None and str(pct) != "" else ""
        out.append(f"{i}. {nom}: {ln} líneas, importe S/ {v}{pct_s}")
    return "\n".join(out)


def _lines_etiqueta_valor(filas: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for i, row in enumerate(filas[:25], start=1):
        e = str(row.get("etiqueta") or "")
        ln = int(row.get("lineas") or 0)
        v = _fmt_num(row.get("suma_valor") or 0)
        out.append(f"{i}. {e}: {ln} líneas, importe S/ {v}")
    return "\n".join(out)


def _lines_productos(filas: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for i, row in enumerate(filas[:25], start=1):
        g = str(row.get("glosa") or row.get("cod_item") or "")
        v = _fmt_num(row.get("suma_valor") or 0)
        ln = int(row.get("lineas") or 0)
        out.append(f"{i}. {g}: {ln} líneas, importe S/ {v}")
    return "\n".join(out)


def _lines_mix_tdoc(filas: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for i, row in enumerate(filas[:25], start=1):
        t = str(row.get("tdoc") or "")
        label = etiqueta_documento(t)
        ln = int(row.get("lineas") or 0)
        v = _fmt_num(row.get("suma_valor") or 0)
        out.append(f"{i}. {label}: {ln} líneas, importe S/ {v}")
    return "\n".join(out)


def _lines_comparativo(filas: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for i, row in enumerate(filas[:25], start=1):
        e = str(row.get("etiqueta") or "")
        a = _fmt_num(row.get("valor_periodo_a") or 0)
        b = _fmt_num(row.get("valor_periodo_b") or 0)
        d = _fmt_num(row.get("delta") or 0)
        out.append(f"{i}. {e}: periodo A S/ {a}, periodo B S/ {b}, diferencia S/ {d}")
    return "\n".join(out)


def _lines_etiqueta_named(filas: list[dict[str, Any]], key: str) -> str:
    out: list[str] = []
    for i, row in enumerate(filas[:25], start=1):
        e = str(row.get(key) or "")
        ln = int(row.get("lineas") or 0)
        v = _fmt_num(row.get("suma_valor") or 0)
        out.append(f"{i}. {e}: {ln} líneas, importe S/ {v}")
    return "\n".join(out)


def _lines_serie_mensual(filas: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for i, row in enumerate(filas[:40], start=1):
        m = str(row.get("mes") or "")
        v = _fmt_num(row.get("suma_valor") or 0)
        ln = int(row.get("lineas") or 0)
        out.append(f"{i}. {m}: {ln} líneas, importe S/ {v}")
    return "\n".join(out)


def _lines_generic_buscar(filas: list[dict[str, Any]]) -> str:
    max_rows = 12
    out: list[str] = []
    for idx, row in enumerate(filas[:max_rows], start=1):
        parts: list[str] = []
        for j, (col, val) in enumerate(row.items()):
            if j >= 4:
                break
            parts.append(f"{col}={val if isinstance(val, (str, int, float)) else '…'}")
        out.append(f"{idx}. " + ", ".join(parts))
    rest = len(filas) - max_rows
    if rest > 0:
        out.append(f"(+{rest} filas más en el reporte.)")
    return "\n".join(out)


def _lines_proyecciones(proyecciones: list[dict[str, Any]], payload: dict[str, Any]) -> str:
    out: list[str] = []
    meses_hist = int(payload.get("meses_historicos") or 0)
    pendiente = _fmt_num(payload.get("pendiente_tendencia") or 0)
    out.append(f"Proyección basada en {meses_hist} meses históricos (pendiente: {pendiente}).")
    for row in proyecciones:
        if not isinstance(row, dict):
            continue
        mes = str(row.get("mes") or "")
        valor = _fmt_num(row.get("valor_proyectado") or 0)
        out.append(f"{mes}: S/ {valor}")
    nota = str(payload.get("nota") or "")
    if nota:
        out.append(f"Nota: {nota}")
    return "\n".join(out)


def format_payload(payload: dict[str, Any]) -> str:
    if "agregados" in payload and isinstance(payload["agregados"], dict) and "filas" not in payload:
        a = payload["agregados"]
        p = payload.get("periodo") or {}
        d1 = str(p.get("desde") or "") if isinstance(p, dict) else ""
        d2 = str(p.get("hasta") or "") if isinstance(p, dict) else ""
        filas = str(a.get("filas") or "")
        sv = _fmt_num(a.get("suma_valor") or 0)
        suf = f" {d1} – {d2}" if d1 and d2 else ""
        return f"Resumen del periodo{suf}: {filas} líneas de detalle, importe total S/ {sv}."

    filas: list[dict[str, Any]] | None = None
    if isinstance(payload.get("filas_pareto"), list):
        filas = payload["filas_pareto"]
    elif isinstance(payload.get("filas_ranking"), list):
        filas = payload["filas_ranking"]
    elif isinstance(payload.get("filas"), list):
        filas = payload["filas"]
    elif isinstance(payload.get("proyecciones"), list):
        return _lines_proyecciones(payload["proyecciones"], payload)

    if not filas:
        return ""

    criterio = str(payload.get("criterio") or "")
    first = filas[0]
    if not isinstance(first, dict):
        return ""

    if str(payload.get("tipo") or "") == "linea_resumen_provincia_cliente":
        return _lines_linea_resumen_provincia(filas)

    if all(k in first for k in ("zona", "lineas_nc", "impacto_abs_valor")):
        return _lines_pareto_nc(filas)
    if all(k in first for k in ("nombre_cliente", "lineas_venta", "suma_valor")):
        return _lines_top_zona_precio(filas)
    if all(k in first for k in ("nombre_cliente", "lineas", "suma_valor")):
        cr = criterio.casefold()
        is_nc = "nota" in cr or "07" in criterio or "tdoc" in cr
        return _lines_top_nc(filas) if is_nc else _lines_top_clientes_global(filas)
    if "etiqueta" in first and "suma_valor" in first:
        return _lines_etiqueta_valor(filas)
    if ("glosa" in first or "cod_item" in first) and "suma_valor" in first:
        return _lines_productos(filas)
    if "tdoc" in first and "suma_valor" in first:
        return _lines_mix_tdoc(filas)
    if all(k in first for k in ("valor_periodo_a", "valor_periodo_b", "etiqueta")):
        return _lines_comparativo(filas)
    if "ruta" in first and "suma_valor" in first:
        return _lines_etiqueta_named(filas, "ruta")
    if "nombre_coorporativo" in first and "suma_valor" in first:
        return _lines_etiqueta_named(filas, "nombre_coorporativo")
    if "mes" in first and "suma_valor" in first:
        return _lines_serie_mensual(filas)

    return _lines_generic_buscar(filas)


def _summary_with_reporte_url(summary: str, reply: str, payload: dict[str, Any]) -> str:
    url = str(payload.get("reporte_url") or "").strip()
    if not url:
        url = extract_reporte_php_url_from_reply(reply)
    if url:
        return (summary + "\n\n" + url).strip()
    return summary.strip()


def enrich_reply(reply: str, groq_messages: list[dict[str, Any]]) -> str:
    reply = reply.strip()
    payload = last_tool_payload(groq_messages)
    if payload is None:
        if reply_uses_generic_cliente_labels(reply):
            url = extract_reporte_php_url_from_reply(reply)
            note = (
                "Los nombres de cliente no están disponibles porque el asistente respondió desde el historial sin consultar la base de datos. "
                "Hacé la misma pregunta de nuevo para obtener los datos actualizados."
            )
            return (note + "\n\n" + url).strip() if url else note
        return reply

    summary = format_payload(payload)
    if not summary:
        return reply

    if reply_uses_generic_cliente_labels(reply):
        return _summary_with_reporte_url(summary, reply, payload)

    if reply_looks_like_ranking(reply):
        u = str(payload.get("reporte_url") or "").strip()
        if u and not extract_reporte_php_url_from_reply(reply):
            return (reply + "\n\n" + u).strip()
        return reply

    head = summary[:120]
    if head and reply and head[:60].lower() in reply.lower():
        return reply

    return (summary + ("\n\n" + reply if reply else "")).strip()


def unificar_enlaces_pareto(reply: str) -> str:
    if not reply or not re.search(r"pareto_(?:clientes|nc)_zona\.php\?", reply, flags=re.I):
        return reply
    reply = re.sub(
        r"\s*(?:Y la tabla[^\n]*\n)?\s*pareto_(?:clientes|nc)_zona_tabla\.php\?[^\s<>\"']+",
        "",
        reply,
        flags=re.I,
    )
    reply = re.sub(r"\n{3,}", "\n\n", reply)
    return reply.strip()
