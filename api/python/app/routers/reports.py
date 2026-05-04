from __future__ import annotations

import json
from datetime import date, timedelta
from html import escape as html_escape
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from sqlalchemy import text

from app.db import get_engine
from app.deps import templates
from app.documento_tipo import enriquecer_filas_mix_tdoc
from app import ventas_queries as vq
from app.ventas_parse import (
    comparativo_parse_four_dates,
    int_from_get,
    parse_date_get_any,
    parse_date_string,
    resumen_parse_date,
)

router = APIRouter(prefix="/modules", tags=["reports"])


def _short(s: str, n: int = 30) -> str:
    s = str(s or "")
    return s if len(s) <= n else s[: max(1, n - 1)] + "…"


def _bad(msg: str) -> PlainTextResponse:
    return PlainTextResponse(msg, status_code=400)


@router.get("/pareto_nc_zona_tabla.php")
def pareto_nc_tabla_redirect(request: Request) -> Any:
    q = request.url.query
    return RedirectResponse("/modules/pareto_nc_zona.php" + ("?" + q if q else ""), status_code=302)


@router.get("/pareto_clientes_zona_tabla.php")
def pareto_cli_tabla_redirect(request: Request) -> Any:
    q = request.url.query
    return RedirectResponse("/modules/pareto_clientes_zona.php" + ("?" + q if q else ""), status_code=302)


@router.get("/ventas_barras_dimension.php")
def ventas_barras_dimension(request: Request) -> Any:
    desde = parse_date_get_any(request, ["desde", "fecha_desde"])
    hasta = parse_date_get_any(request, ["hasta", "fecha_hasta"])
    if not desde or not hasta or desde > hasta:
        return _bad("Parámetros: desde, hasta (YYYY-MM-DD); alias fecha_desde, fecha_hasta. dim|dimension=precio|comercial, top|top_n=20")
    dim = "comercial" if (request.query_params.get("dim") or request.query_params.get("dimension") or "").lower().strip() == "comercial" else "precio"
    top = int_from_get(request, ["top", "top_n"], 20, 1, 100)
    try:
        engine = get_engine()
        with engine.connect() as conn:
            data = vq.barras_por_dimension(conn, desde, hasta, dim, top)
    except ValueError as e:
        return _bad(str(e))
    dim_label = "Zona comercial" if dim == "comercial" else "Zona precio"
    rows: list[list[str]] = []
    for i, f in enumerate(data["filas"], start=1):
        rows.append(
            [
                str(i),
                str(f.get("etiqueta") or ""),
                str(int(f.get("lineas") or 0)),
                f"{float(f.get('suma_valor') or 0):,.2f}",
                str(f.get("pct_del_total") or ""),
                str(f.get("suma_cantidad") or ""),
                str(f.get("suma_peso") or ""),
            ]
        )
    labels = [_short(f.get("etiqueta")) for f in data["filas"]]
    valores = [float(f.get("suma_valor") or 0) for f in data["filas"]]
    payload = {"labels": labels, "valores": valores, "label": "Importe (soles)"}
    ctx = {
        "request": request,
        "browser_title": f"Barras · {dim_label}",
        "h1": f"Importe por {dim_label}",
        "meta": f"{desde} — {hasta} · Top {top}",
        "pdf_h2": f"Ranking por {dim_label}",
        "pdf_name": f"ventas_barras_{dim}_{desde}_{hasta}.pdf",
        "table_headers": ["N°", "Etiqueta", "Líneas", "Importe", "% del total", "Cantidad", "Peso"],
        "table_rows": rows,
        "chart_payload": payload,
    }
    return templates(request).TemplateResponse("reports/chart_hbar.html", ctx)


@router.get("/ventas_top_productos.php")
def ventas_top_productos(request: Request) -> Any:
    desde = parse_date_get_any(request, ["desde", "fecha_desde"])
    hasta = parse_date_get_any(request, ["hasta", "fecha_hasta"])
    top = int_from_get(request, ["top", "top_n"], 15, 1, 100)
    if not desde or not hasta or desde > hasta:
        return _bad("Parámetros: desde, hasta, top=15")
    engine = get_engine()
    with engine.connect() as conn:
        data = vq.top_productos(conn, desde, hasta, top)
    rows = []
    for i, f in enumerate(data["filas"], start=1):
        rows.append(
            [
                str(i),
                str(f.get("cod_item") or ""),
                str(f.get("glosa") or ""),
                str(int(f.get("lineas") or 0)),
                f"{float(f.get('suma_valor') or 0):,.2f}",
                str(f.get("suma_cantidad") or ""),
            ]
        )
    labels = []
    vals = []
    for f in data["filas"]:
        g = str(f.get("glosa") or f.get("cod_item") or "")
        labels.append(_short(g, 30))
        vals.append(float(f.get("suma_valor") or 0))
    ctx = {
        "request": request,
        "browser_title": "Top productos",
        "h1": "Top productos por importe",
        "meta": f"{desde} — {hasta} · Top {top}",
        "pdf_h2": "Top productos",
        "pdf_name": f"top_productos_{desde}_{hasta}.pdf",
        "table_headers": ["N°", "Código ítem", "Descripción", "Líneas", "Importe", "Cantidad"],
        "table_rows": rows,
        "chart_payload": {"labels": labels, "valores": vals, "label": "Importe"},
    }
    return templates(request).TemplateResponse("reports/chart_hbar.html", ctx)


@router.get("/ventas_top_clientes_global.php")
def ventas_top_clientes_global(request: Request) -> Any:
    desde = parse_date_get_any(request, ["desde", "fecha_desde"])
    hasta = parse_date_get_any(request, ["hasta", "fecha_hasta"])
    top = int_from_get(request, ["top", "top_n"], 15, 1, 100)
    if not desde or not hasta or desde > hasta:
        return _bad("Parámetros: desde, hasta, top=15")
    engine = get_engine()
    with engine.connect() as conn:
        data = vq.top_clientes_global(conn, desde, hasta, top)
    rows = []
    for i, f in enumerate(data["filas"], start=1):
        rows.append(
            [
                str(i),
                str(f.get("cod_cliente") or ""),
                str(f.get("nombre_cliente") or ""),
                str(int(f.get("lineas") or 0)),
                f"{float(f.get('suma_valor') or 0):,.2f}",
                str(f.get("pct_del_total") or ""),
                str(f.get("pct_acumulado") or ""),
            ]
        )
    labels = [_short(f.get("nombre_cliente")) for f in data["filas"]]
    vals = [float(f.get("suma_valor") or 0) for f in data["filas"]]
    ctx = {
        "request": request,
        "browser_title": "Top clientes",
        "h1": "Top clientes (todas las zonas)",
        "meta": f"{desde} — {hasta} · Total: {float(data['total_valor']):,.2f}",
        "pdf_h2": "Ranking global clientes",
        "pdf_name": f"top_clientes_{desde}_{hasta}.pdf",
        "table_headers": ["N°", "Cód. cliente", "Nombre cliente", "Líneas", "Importe", "% del total", "% acumulado"],
        "table_rows": rows,
        "chart_payload": {"labels": labels, "valores": vals, "label": "Importe"},
    }
    return templates(request).TemplateResponse("reports/chart_hbar.html", ctx)


@router.get("/ventas_top_clientes_nc.php")
def ventas_top_clientes_nc(request: Request) -> Any:
    desde = parse_date_get_any(request, ["desde", "fecha_desde"])
    hasta = parse_date_get_any(request, ["hasta", "fecha_hasta"])
    top = int_from_get(request, ["top", "top_n"], 15, 1, 100)
    if not desde or not hasta or desde > hasta:
        return _bad("Parámetros: desde, hasta, top=15")
    engine = get_engine()
    with engine.connect() as conn:
        data = vq.top_clientes_nota_credito(conn, desde, hasta, top)
    rows = []
    for i, f in enumerate(data["filas"], start=1):
        rows.append(
            [
                str(i),
                str(f.get("cod_cliente") or ""),
                str(f.get("nombre_cliente") or ""),
                str(int(f.get("lineas") or 0)),
                f"{float(f.get('suma_valor') or 0):,.2f}",
                str(f.get("pct_lineas_del_total") or ""),
                str(f.get("pct_lineas_acumulado") or ""),
            ]
        )
    labels = [_short(f.get("nombre_cliente")) for f in data["filas"]]
    vals = [float(f.get("lineas") or 0) for f in data["filas"]]
    ctx = {
        "request": request,
        "browser_title": "Top clientes NC",
        "h1": "Top clientes por notas de crédito (TDoc = 07)",
        "meta": f"{desde} — {hasta} · Líneas NC: {int(data.get('total_lineas_nc') or 0)} · Importe NC: {float(data.get('total_valor_nc') or 0):,.2f}",
        "pdf_h2": "Ranking clientes (notas de crédito)",
        "pdf_name": f"top_clientes_nc_{desde}_{hasta}.pdf",
        "table_headers": ["N°", "Cód. cliente", "Nombre cliente", "Líneas NC", "Importe", "% líneas", "% acum. líneas"],
        "table_rows": rows,
        "chart_payload": {"labels": labels, "valores": vals, "label": "Líneas NC"},
    }
    return templates(request).TemplateResponse("reports/chart_hbar.html", ctx)


@router.get("/ventas_barras_ruta.php")
def ventas_barras_ruta(request: Request) -> Any:
    desde = parse_date_get_any(request, ["desde", "fecha_desde"])
    hasta = parse_date_get_any(request, ["hasta", "fecha_hasta"])
    top = int_from_get(request, ["top", "top_n"], 15, 1, 100)
    if not desde or not hasta or desde > hasta:
        return _bad("Parámetros: desde, hasta, top=15")
    engine = get_engine()
    with engine.connect() as conn:
        data = vq.top_ruta_comercial(conn, desde, hasta, top)
    rows = []
    for i, f in enumerate(data["filas"], start=1):
        rows.append([str(i), str(f.get("ruta") or ""), str(int(f.get("lineas") or 0)), f"{float(f.get('suma_valor') or 0):,.2f}"])
    labels = [_short(f.get("ruta")) for f in data["filas"]]
    vals = [float(f.get("suma_valor") or 0) for f in data["filas"]]
    ctx = {
        "request": request,
        "browser_title": "Ruta comercial",
        "h1": "Importe por ruta comercial",
        "meta": f"{desde} — {hasta} · Top {top}",
        "pdf_h2": "Rutas comerciales",
        "pdf_name": f"ventas_ruta_{desde}_{hasta}.pdf",
        "table_headers": ["N°", "Ruta", "Líneas", "Importe"],
        "table_rows": rows,
        "chart_payload": {"labels": labels, "valores": vals, "label": "Importe"},
    }
    return templates(request).TemplateResponse("reports/chart_hbar.html", ctx)


@router.get("/ventas_barras_corporativo.php")
def ventas_barras_corporativo(request: Request) -> Any:
    desde = parse_date_get_any(request, ["desde", "fecha_desde"])
    hasta = parse_date_get_any(request, ["hasta", "fecha_hasta"])
    top = int_from_get(request, ["top", "top_n"], 15, 1, 100)
    if not desde or not hasta or desde > hasta:
        return _bad("Parámetros: desde, hasta, top=15")
    engine = get_engine()
    with engine.connect() as conn:
        data = vq.top_corporativo(conn, desde, hasta, top)
    rows = []
    for i, f in enumerate(data["filas"], start=1):
        rows.append(
            [
                str(i),
                str(f.get("nombre_coorporativo") or ""),
                str(f.get("cod_coorporativo") or ""),
                str(int(f.get("lineas") or 0)),
                f"{float(f.get('suma_valor') or 0):,.2f}",
            ]
        )
    labels = [_short(f.get("nombre_coorporativo")) for f in data["filas"]]
    vals = [float(f.get("suma_valor") or 0) for f in data["filas"]]
    ctx = {
        "request": request,
        "browser_title": "Corporativo",
        "h1": "Importe por corporativo",
        "meta": f"{desde} — {hasta} · Top {top}",
        "pdf_h2": "Corporativo",
        "pdf_name": f"ventas_corporativo_{desde}_{hasta}.pdf",
        "table_headers": ["N°", "Corporativo", "Código", "Líneas", "Importe"],
        "table_rows": rows,
        "chart_payload": {"labels": labels, "valores": vals, "label": "Importe"},
    }
    return templates(request).TemplateResponse("reports/chart_hbar.html", ctx)


@router.get("/ventas_mix_tdoc.php")
def ventas_mix_tdoc(request: Request) -> Any:
    desde = parse_date_get_any(request, ["desde", "fecha_desde"])
    hasta = parse_date_get_any(request, ["hasta", "fecha_hasta"])
    if not desde or not hasta or desde > hasta:
        return _bad("Parámetros: desde, hasta")
    engine = get_engine()
    with engine.connect() as conn:
        data = vq.mix_por_tdoc(conn, desde, hasta)
    filas = enriquecer_filas_mix_tdoc(list(data["filas"]))
    rows = []
    for i, f in enumerate(filas, start=1):
        rows.append(
            [
                str(i),
                str(f.get("tdoc_etiqueta") or ""),
                str(int(f.get("lineas") or 0)),
                f"{float(f.get('suma_valor') or 0):,.2f}",
                str(f.get("pct_del_total") or ""),
            ]
        )
    labels = [str(f.get("tdoc_etiqueta") or "") for f in filas]
    vals = [float(f.get("suma_valor") or 0) for f in filas]
    ctx = {
        "request": request,
        "browser_title": "Mix TDoc",
        "h1": "Ventas por tipo de documento",
        "meta": f"{desde} — {hasta}",
        "pdf_h2": "Mix por tipo de documento",
        "pdf_name": f"mix_tdoc_{desde}_{hasta}.pdf",
        "table_headers": ["N°", "Tipo documento", "Líneas", "Importe", "% del total"],
        "table_rows": rows,
        "chart_payload": {"labels": labels, "valores": vals},
    }
    return templates(request).TemplateResponse("reports/chart_doughnut.html", ctx)


@router.get("/ventas_serie_mensual.php")
def ventas_serie_mensual(request: Request) -> Any:
    desde = parse_date_get_any(request, ["desde", "fecha_desde"])
    hasta = parse_date_get_any(request, ["hasta", "fecha_hasta"])
    if not desde or not hasta or desde > hasta:
        return _bad("Parámetros: desde, hasta")
    engine = get_engine()
    with engine.connect() as conn:
        data = vq.serie_mensual_valor(conn, desde, hasta)
    rows = []
    for i, f in enumerate(data["filas"], start=1):
        rows.append([str(i), str(f.get("mes") or ""), str(int(f.get("lineas") or 0)), f"{float(f.get('suma_valor') or 0):,.2f}"])
    labels = [str(f.get("mes") or "") for f in data["filas"]]
    vals = [float(f.get("suma_valor") or 0) for f in data["filas"]]
    ctx = {
        "request": request,
        "browser_title": "Serie mensual",
        "h1": "Serie mensual de importe",
        "meta": f"{desde} — {hasta}",
        "pdf_h2": "Serie mensual",
        "pdf_name": f"serie_mensual_{desde}_{hasta}.pdf",
        "table_headers": ["N°", "Mes", "Líneas", "Importe"],
        "table_rows": rows,
        "chart_payload": {"labels": labels, "valores": vals},
    }
    return templates(request).TemplateResponse("reports/chart_line.html", ctx)


@router.get("/ventas_comparativo.php")
def ventas_comparativo(request: Request) -> Any:
    a1, a2, b1, b2 = comparativo_parse_four_dates(request)
    dim = "comercial" if (request.query_params.get("dim") or request.query_params.get("dimension") or "").lower().strip() == "comercial" else "precio"
    top = int_from_get(request, ["top", "top_n"], 15, 1, 80)
    if not a1 or not a2 or not b1 or not b2 or a1 > a2 or b1 > b2:
        return _bad(
            "Parámetros: a_desde, a_hasta, b_desde, b_hasta (YYYY-MM-DD). "
            "Alias y pares repetidos desde/hasta como en PHP. dim|dimension=precio|comercial, top|top_n=15"
        )
    try:
        engine = get_engine()
        with engine.connect() as conn:
            data = vq.comparativo_dos_periodos(conn, a1, a2, b1, b2, dim, top)
    except ValueError as e:
        return _bad(str(e))
    dim_label = "Zona comercial" if dim == "comercial" else "Zona precio"
    rows = []
    for i, f in enumerate(data["filas"], start=1):
        rows.append(
            [
                str(i),
                str(f.get("etiqueta") or ""),
                f"{float(f.get('valor_periodo_a') or 0):,.2f}",
                f"{float(f.get('valor_periodo_b') or 0):,.2f}",
                f"{float(f.get('delta') or 0):,.2f}",
            ]
        )
    labels = [_short(f.get("etiqueta")) for f in data["filas"]]
    va = [float(f.get("valor_periodo_a") or 0) for f in data["filas"]]
    vb = [float(f.get("valor_periodo_b") or 0) for f in data["filas"]]
    ctx = {
        "request": request,
        "browser_title": "Comparativo",
        "h1": f"Comparativo de importe por {dim_label}",
        "meta": f"Periodo A: {a1} — {a2} · Periodo B: {b1} — {b2}",
        "pdf_h2": f"Comparativo por {dim_label}",
        "pdf_name": f"comparativo_{a1}_{a2}_{b1}_{b2}.pdf",
        "table_headers": ["N°", "Etiqueta", "Importe periodo A", "Importe periodo B", "Diferencia (B − A)"],
        "table_rows": rows,
        "chart_payload": {
            "labels": labels,
            "valor_a": va,
            "valor_b": vb,
            "label_a": f"A ({a1}…{a2})",
            "label_b": f"B ({b1}…{b2})",
        },
    }
    return templates(request).TemplateResponse("reports/chart_comparativo.html", ctx)


@router.get("/pareto_nc_zona.php")
def pareto_nc_zona(request: Request) -> Any:
    desde = parse_date_get_any(request, ["desde", "fecha_desde"])
    hasta = parse_date_get_any(request, ["hasta", "fecha_hasta"])
    max_z = int_from_get(request, ["max", "max_zonas"], 100, 1, 200)
    if not desde or not hasta or desde > hasta:
        return _bad("Parámetros: desde, hasta, max=100")
    engine = get_engine()
    with engine.connect() as conn:
        data = vq.pareto_nc_zonaprecio(conn, desde, hasta, max_z)
    rows = []
    labels = []
    impactos = []
    pct_acum = []
    for i, f in enumerate(data["filas"], start=1):
        rows.append(
            [
                str(i),
                str(f.get("zona") or ""),
                str(int(f.get("lineas_nc") or 0)),
                f"{float(f.get('impacto_abs_valor') or 0):,.2f}",
                str(f.get("pct_del_total") or ""),
                str(f.get("pct_acumulado") or ""),
            ]
        )
        labels.append(_short(str(f.get("zona") or "")))
        impactos.append(float(f.get("impacto_abs_valor") or 0))
        pct_acum.append(float(f.get("pct_acumulado") or 0))
    ctx = {
        "request": request,
        "browser_title": "Pareto NC zona",
        "h1": "Pareto notas de crédito por zona precio",
        "meta": f"{desde} — {hasta} · Zonas (top {max_z})",
        "pdf_h2": "Pareto NC por zona",
        "pdf_meta": "",
        "pdf_name": f"pareto_nc_zona_{desde}_{hasta}.pdf",
        "table_headers": ["N°", "Zona", "Líneas NC", "Impacto |Valor|", "% del total", "% acumulado"],
        "table_rows": rows,
        "chart_payload": {
            "labels": labels,
            "valores": impactos,
            "pctAcum": pct_acum,
            "bar_label": "Impacto NC (|Valor|)",
            "line_label": "% acumulado",
        },
    }
    return templates(request).TemplateResponse("reports/chart_pareto.html", ctx)


@router.get("/pareto_clientes_zona.php")
def pareto_clientes_zona(request: Request) -> Any:
    desde = parse_date_get_any(request, ["desde", "fecha_desde"])
    hasta = parse_date_get_any(request, ["hasta", "fecha_hasta"])
    pref = str(request.query_params.get("prefijo_descri_zona_precio") or "").strip().upper()
    top_n = int_from_get(request, ["top", "top_n"], 15, 1, 100)
    if not desde or not hasta or desde > hasta or not pref:
        return _bad("Parámetros: desde, hasta, prefijo_descri_zona_precio (ej. AQP), top|top_n=15")
    try:
        engine = get_engine()
        with engine.connect() as conn:
            data = vq.top_clientes_zona_precio(conn, desde, hasta, pref, top_n)
    except ValueError as e:
        return _bad(str(e))
    rows = []
    labels = []
    vals = []
    pct_acum = []
    for i, f in enumerate(data["filas"], start=1):
        rows.append(
            [
                str(i),
                str(f.get("cod_cliente") or ""),
                str(f.get("nombre_cliente") or ""),
                f"{float(f.get('suma_valor') or 0):,.2f}",
                str(int(f.get("lineas_venta") or 0)),
                str(f.get("pct_del_total_zona") or ""),
                str(f.get("pct_acumulado") or ""),
            ]
        )
        labels.append(_short(str(f.get("nombre_cliente") or "")))
        vals.append(float(f.get("suma_valor") or 0))
        pct_acum.append(float(f.get("pct_acumulado") or 0))
    ctx = {
        "request": request,
        "browser_title": "Pareto clientes zona",
        "h1": "Pareto clientes en zona precio",
        "meta": f"{desde} — {hasta} · Prefijo {pref} · Top {top_n}",
        "pdf_h2": "Ranking de clientes (importe en zona)",
        "pdf_meta": f"Zona precio con prefijo {pref} · {desde} — {hasta}",
        "pdf_name": f"pareto_cli_zona_{pref}_{desde}_{hasta}.pdf",
        "table_headers": ["N°", "Cód. cliente", "Nombre cliente", "Importe", "Líneas", "% en zona", "% acumulado"],
        "table_rows": rows,
        "chart_payload": {
            "labels": labels,
            "valores": vals,
            "pctAcum": pct_acum,
            "bar_label": "Importe",
            "line_label": "% acumulado (sobre total zona)",
        },
    }
    return templates(request).TemplateResponse("reports/chart_pareto.html", ctx)


@router.get("/resumen.php")
def resumen_modulo(request: Request) -> Any:
    today = date.today()
    default_hasta = today.isoformat()
    default_desde = (today - timedelta(days=30)).isoformat()
    d1 = resumen_parse_date(request, "desde") or default_desde
    d2 = resumen_parse_date(request, "hasta") or default_hasta
    err = None
    vg = sale_fec = sale_tra = None
    if not d1 or not d2 or d1 > d2:
        err = "Use fechas YYYY-MM-DD válidas."
    else:
        try:
            engine = get_engine()
            with engine.connect() as conn:
                vg = dict(
                    conn.execute(
                        text(
                            "SELECT COUNT(*) AS filas, COALESCE(SUM(Valor),0) AS suma_valor, COALESCE(SUM(Cantidad),0) AS suma_cant, COALESCE(SUM(Peso),0) AS suma_peso "
                            "FROM ventasgeneral2 WHERE FechaContable BETWEEN :a AND :b"
                        ),
                        {"a": d1, "b": d2},
                    ).mappings().one()
                )
                sale_fec = dict(
                    conn.execute(
                        text(
                            "SELECT COUNT(*) AS filas, COALESCE(SUM(timport),0) AS suma_importe, COALESCE(SUM(tcantid),0) AS suma_cant "
                            "FROM sale WHERE tfecfac BETWEEN :a AND :b"
                        ),
                        {"a": d1, "b": d2},
                    ).mappings().one()
                )
                sale_tra = dict(
                    conn.execute(
                        text(
                            "SELECT COUNT(*) AS filas, COALESCE(SUM(timport),0) AS suma_importe, COALESCE(SUM(tcantid),0) AS suma_cant "
                            "FROM sale WHERE tfectra BETWEEN :a AND :b"
                        ),
                        {"a": d1, "b": d2},
                    ).mappings().one()
                )
        except Exception as e:
            err = str(e)
    html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Resumen · ventas</title>
<link rel="stylesheet" href="/assets/css/app.css"></head>
<body class="reporte-modulo-main">
<div class="reporte-page" style="padding:1rem;max-width:900px;margin:0 auto;">
<h1>Resumen por fechas</h1>
<form method="get" class="card-filtros-demo" style="padding:1rem;margin-bottom:1rem;">
<label>Desde <input type="date" name="desde" value="{d1}"></label>
<label>Hasta <input type="date" name="hasta" value="{d2}"></label>
<button type="submit" class="btn btn-primary">Actualizar</button>
</form>
"""
    if err:
        html += f'<p class="text-red-600">{html_escape(err)}</p></div></body></html>'
        return HTMLResponse(html)
    html += f"""
<div class="grid" style="display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));">
<section class="card-filtros-demo" style="padding:1rem;"><h2>ventasgeneral</h2>
<p>FechaContable entre {d1} y {d2}</p>
<ul><li>Filas: <strong>{vg['filas']}</strong></li>
<li>Suma Valor: <strong>{float(vg['suma_valor']):,.2f}</strong></li>
<li>Suma Cantidad: <strong>{float(vg['suma_cant']):,.4f}</strong></li>
<li>Suma Peso: <strong>{float(vg['suma_peso']):,.4f}</strong></li></ul></section>
<section class="card-filtros-demo" style="padding:1rem;"><h2>sale (tfecfac)</h2>
<ul><li>Filas: <strong>{sale_fec['filas']}</strong></li>
<li>Suma timport: <strong>{float(sale_fec['suma_importe']):,.2f}</strong></li>
<li>Suma tcantid: <strong>{float(sale_fec['suma_cant']):,.4f}</strong></li></ul></section>
<section class="card-filtros-demo" style="padding:1rem;"><h2>sale (tfectra)</h2>
<ul><li>Filas: <strong>{sale_tra['filas']}</strong></li>
<li>Suma timport: <strong>{float(sale_tra['suma_importe']):,.2f}</strong></li>
<li>Suma tcantid: <strong>{float(sale_tra['suma_cant']):,.4f}</strong></li></ul></section>
</div></div></body></html>"""
    return HTMLResponse(html)


@router.get("/ventasgeneral_resumen_tabla.php")
def ventasgeneral_resumen_tabla(request: Request) -> Any:
    d1 = resumen_parse_date(request, "fecha_desde") or resumen_parse_date(request, "desde")
    d2 = resumen_parse_date(request, "fecha_hasta") or resumen_parse_date(request, "hasta")
    if not d1 or not d2 or d1 > d2:
        return _bad("Parámetros: fecha_desde y fecha_hasta (YYYY-MM-DD); alias desde y hasta.")
    sql = """SELECT COUNT(*) AS filas, COALESCE(SUM(Valor),0) AS suma_valor,
        COALESCE(SUM(Cantidad),0) AS suma_cantidad, COALESCE(SUM(Peso),0) AS suma_peso
        FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2"""
    bind: dict[str, Any] = {"d1": d1, "d2": d2}
    zona = str(request.query_params.get("zona_comercial") or "").strip()
    if zona:
        sql += " AND ZonaComercial LIKE :zona"
        bind["zona"] = f"%{zona}%"
    cod = str(request.query_params.get("cod_cliente") or "").strip()
    if cod:
        sql += " AND CodigoCliente = :cod"
        bind["cod"] = cod
    pref_z = str(request.query_params.get("prefijo_descri_zona_precio") or "").strip().upper()
    if pref_z:
        sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzp"
        bind["prefzp"] = pref_z + "%"
    prov = str(request.query_params.get("provincia") or "").strip()
    if prov:
        sql += " AND Provincia LIKE :prov"
        bind["prov"] = f"%{prov}%"
    tdoctipo = str(request.query_params.get("tipo_documento") or "").strip()
    if tdoctipo:
        sql += " AND TipoDocumento LIKE :tdoctipo"
        bind["tdoctipo"] = f"%{tdoctipo}%"
    engine = get_engine()
    with engine.connect() as conn:
        row = dict(conn.execute(text(sql), bind).mappings().one())
    pdf_name = f"resumen_ventasgeneral_{d1}_{d2}.pdf"
    r0 = str(row.get("filas") or "")
    r1 = f"{float(row.get('suma_valor') or 0):,.2f}"
    r2 = f"{float(row.get('suma_cantidad') or 0):,.2f}"
    r3 = f"{float(row.get('suma_peso') or 0):,.2f}"
    pn_js = json.dumps(pdf_name, ensure_ascii=False)
    body = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tabla · Resumen ventasgeneral</title>
<link rel="stylesheet" href="/assets/css/app.css">
<style>body{{margin:0;}}main{{padding:1rem;max-width:980px;margin:0 auto;}} .wrap-dark{{background:var(--surface,#1e293b);border-radius:12px;padding:1rem;border:1px solid var(--border,#334155);}} .wrap-dark .pdf-meta{{color:var(--muted,#a1a1aa);}} #reporte-pdf-root table.data-table tbody td{{padding:0.65rem 0.85rem;}}</style>
</head><body><main><div class="wrap-dark">
<div class="reporte-toolbar"><button type="button" class="btn btn-primary" id="btn-pdf-resumen">Descargar PDF</button></div>
<div id="reporte-pdf-root">
<h2 class="pdf-h2">Agregados del periodo</h2>
<p class="pdf-meta">FechaContable entre las fechas indicadas (filtros opcionales aplicados).</p>
<div class="table-wrapper overflow-x-auto productos-dt-skin">
<table class="data-table config-table display stripe"><thead><tr><th>N°</th><th>Filas</th><th>Importe total</th><th>Cantidad total</th><th>Peso total</th></tr></thead>
<tbody><tr><td>1</td><td>{html_escape(r0)}</td><td>{html_escape(r1)}</td><td>{html_escape(r2)}</td><td>{html_escape(r3)}</td></tr></tbody>
</table></div></div></div></main>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js" crossorigin="anonymous"></script>
<script src="/assets/js/reporte_pdf.js"></script>
<script>ventasBindPdfDownload('btn-pdf-resumen', 'reporte-pdf-root', {pn_js});</script>
</body></html>"""
    return HTMLResponse(body)


@router.get("/ventasgeneral_buscar_tabla.php")
def ventasgeneral_buscar_tabla(request: Request) -> Any:
    fd = str(request.query_params.get("fecha_desde") or request.query_params.get("desde") or "").strip()
    fh = str(request.query_params.get("fecha_hasta") or request.query_params.get("hasta") or "").strip()
    args: dict[str, Any] = {
        "fecha_desde": fd,
        "fecha_hasta": fh,
        "nombre_cliente": str(request.query_params.get("nombre_cliente") or "").strip(),
        "numero_doc": str(request.query_params.get("numero_doc") or "").strip(),
        "cod_item": str(request.query_params.get("cod_item") or "").strip(),
        "tdoc": str(request.query_params.get("tdoc") or "").strip(),
        "prefijo_descri_zona_precio": str(request.query_params.get("prefijo_descri_zona_precio") or "").strip(),
    }
    for k in list(args.keys()):
        if args[k] == "":
            del args[k]
    try:
        li = request.query_params.get("limit")
        off = request.query_params.get("offset")
        if li is not None and str(li).strip() != "":
            args["limit"] = int(li)
        if off is not None and str(off).strip() != "":
            args["offset"] = int(off)
    except ValueError:
        return _bad("limit/offset inválidos")
    try:
        engine = get_engine()
        with engine.connect() as conn:
            out = vq.buscar(conn, args)
    except ValueError as e:
        return _bad(str(e))
    filas = out.get("filas") or []
    headers = [
        "id",
        "FechaContable",
        "CodigoCliente",
        "NombreCliente",
        "NumeroFactura",
        "CodigoItem",
        "GlosaDetalle",
        "Cantidad",
        "Valor",
        "ZonaComercial",
    ]
    row_html = ""
    for r in filas[:100]:
        d = dict(r) if not isinstance(r, dict) else r
        cells = "".join(f"<td>{html_escape(str(d.get(h) or ''))}</td>" for h in headers)
        row_html += f"<tr>{cells}</tr>"
    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>Buscar ventasgeneral</title>
<link rel="stylesheet" href="/assets/css/app.css"></head><body style="padding:1rem;">
<h1>Resultados ({len(filas)} filas, límite consulta {out.get('limit')})</h1>
<div style="overflow:auto"><table class="data-table"><thead><tr>{''.join(f'<th>{h}</th>' for h in headers)}</tr></thead><tbody>{row_html}</tbody></table></div>
</body></html>"""
    return HTMLResponse(html)


@router.get("/ventasgeneral_table.php")
def ventasgeneral_table(request: Request) -> Any:
    limit = max(1, min(100, int(request.query_params.get("limit") or 50)))
    offset = max(0, int(request.query_params.get("offset") or 0))
    desde = str(request.query_params.get("desde") or "").strip()
    hasta = str(request.query_params.get("hasta") or "").strip()
    qnom = str(request.query_params.get("nombre") or "").strip()
    qdoc = str(request.query_params.get("numero_doc") or "").strip()
    engine = get_engine()
    where = " WHERE 1=1"
    bind: dict[str, Any] = {}
    d1 = parse_date_string(desde) if desde else None
    d2 = parse_date_string(hasta) if hasta else None
    if d1:
        where += " AND FechaContable >= :d1"
        bind["d1"] = d1
    if d2:
        where += " AND FechaContable <= :d2"
        bind["d2"] = d2
    if qnom:
        where += " AND NombreCliente LIKE :nom"
        bind["nom"] = f"%{qnom}%"
    if qdoc:
        where += " AND NumeroFactura LIKE :ndoc"
        bind["ndoc"] = f"%{qdoc}%"
    with engine.connect() as conn:
        total = int(conn.execute(text("SELECT COUNT(*) FROM ventasgeneral2" + where), bind).scalar() or 0)
        sql = (
            "SELECT id, FechaContable, CodigoCliente, NombreCliente, NumeroFactura, CodigoItem, GlosaDetalle, Cantidad, Valor, ZonaComercial "
            "FROM ventasgeneral2" + where + f" ORDER BY FechaContable DESC, id DESC LIMIT {limit} OFFSET {offset}"
        )
        rows = [dict(r._mapping) for r in conn.execute(text(sql), bind).mappings().all()]
    body = ""
    for r in rows:
        body += f"""<tr><td>{r.get('id')}</td><td>{r.get('FechaContable')}</td><td>{r.get('NombreCliente')}</td>
<td>{r.get('NumeroFactura')}</td><td>{r.get('CodigoItem')}</td><td>{r.get('GlosaDetalle')}</td>
<td>{r.get('Cantidad')}</td><td>{r.get('Valor')}</td><td>{r.get('ZonaComercial')}</td></tr>"""
    prev = max(0, offset - limit)
    next_off = offset + limit if offset + limit < total else None
    qs = dict(request.query_params)
    nav = ""
    if offset > 0:
        qs["offset"] = str(prev)
        nav += f'<a class="btn" href="?{"&".join(f"{k}={v}" for k,v in qs.items())}">Anterior</a> '
    if next_off is not None:
        qs["offset"] = str(next_off)
        nav += f'<a class="btn" href="?{"&".join(f"{k}={v}" for k,v in qs.items())}">Siguiente</a>'
    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>Ventas general · tabla</title>
<link rel="stylesheet" href="/assets/css/app.css"></head><body style="padding:1rem;">
<h1>ventasgeneral</h1>
<p>Total: {total} · mostrando {len(rows)}</p>
<table class="data-table"><thead><tr>
<th>id</th><th>Fecha</th><th>Cliente</th><th>Doc</th><th>Ítem</th><th>Glosa</th><th>Cant</th><th>Valor</th><th>Zona</th>
</tr></thead><tbody>{body}</tbody></table><p>{nav}</p></body></html>"""
    return HTMLResponse(html)


@router.get("/sale_table.php")
def sale_table(request: Request) -> Any:
    limit = max(1, min(100, int(request.query_params.get("limit") or 50)))
    offset = max(0, int(request.query_params.get("offset") or 0))
    desde = str(request.query_params.get("desde") or "").strip()
    hasta = str(request.query_params.get("hasta") or "").strip()
    campo = "tfecfac" if (request.query_params.get("campo_fecha") or "") == "tfecfac" else "tfectra"
    tprocli = str(request.query_params.get("tprocli") or "").strip()
    tcodigo = str(request.query_params.get("tcodigo") or "").strip()
    d1 = parse_date_string(desde) if desde else None
    d2 = parse_date_string(hasta) if hasta else None
    where = " WHERE 1=1"
    bind: dict[str, Any] = {}
    if d1:
        where += f" AND {campo} >= :d1"
        bind["d1"] = d1
    if d2:
        where += f" AND {campo} <= :d2"
        bind["d2"] = d2
    if tprocli:
        where += " AND tprocli LIKE :tp"
        bind["tp"] = f"%{tprocli}%"
    if tcodigo:
        where += " AND tcodigo LIKE :tc"
        bind["tc"] = f"%{tcodigo}%"
    engine = get_engine()
    with engine.connect() as conn:
        total = int(conn.execute(text("SELECT COUNT(*) FROM sale" + where), bind).scalar() or 0)
        sql = f"SELECT * FROM sale{where} ORDER BY {campo} DESC LIMIT {limit} OFFSET {offset}"
        rows = [dict(r._mapping) for r in conn.execute(text(sql), bind).mappings().all()]
    cols = list(rows[0].keys()) if rows else ["(sin columnas)"]
    th = "".join(f"<th>{c}</th>" for c in cols)
    tb = ""
    for r in rows:
        tb += "<tr>" + "".join(f"<td>{r.get(c)}</td>" for c in cols) + "</tr>"
    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>sale · tabla</title>
<link rel="stylesheet" href="/assets/css/app.css"></head><body style="padding:1rem;"><h1>sale</h1>
<p>Total coincidencias: {total}</p><div style="overflow:auto"><table class="data-table"><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div></body></html>"""
    return HTMLResponse(html)
