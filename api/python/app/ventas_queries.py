from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import quote, urlencode

from sqlalchemy import text
from sqlalchemy.engine import Connection


def _row(r: Any) -> dict[str, Any]:
    d = dict(r._mapping)
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    return out


def _rows(result: Any) -> list[dict[str, Any]]:
    return [_row(r) for r in result]


def _trace(sql: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"sql": sql, "params": params}


def col_etiqueta(dimension: str) -> str:
    if dimension == "precio":
        return "COALESCE(NULLIF(TRIM(DescripcionZonaPrecio),''),'(sin zona precio)')"
    if dimension == "comercial":
        return "COALESCE(NULLIF(TRIM(ZonaComercial),''),'(sin zona comercial)')"
    if dimension == "ruta":
        return "COALESCE(NULLIF(TRIM(RutaComercial),''),'(sin ruta)')"
    if dimension == "corporativo":
        return "COALESCE(NULLIF(TRIM(NombreCoorporativo),''),'(sin corporativo)')"
    raise ValueError("dimension inválida")


def barras_por_dimension(
    conn: Connection, d1: str, d2: str, dimension: str, limit: int
) -> dict[str, Any]:
    limit = max(1, min(100, limit))
    expr = col_etiqueta(dimension)
    sql = f"""SELECT {expr} AS etiqueta, COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor,
            COALESCE(SUM(Cantidad),0) AS suma_cantidad, COALESCE(SUM(Peso),0) AS suma_peso
        FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2
        GROUP BY {expr}
        ORDER BY suma_valor DESC
        LIMIT {limit}"""
    params = {":d1": d1, ":d2": d2}
    raw = _rows(conn.execute(text(sql), {"d1": d1, "d2": d2}))
    sql_t = "SELECT COALESCE(SUM(Valor),0) AS t FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2"
    total = float(
        (_row(conn.execute(text(sql_t), {"d1": d1, "d2": d2}).one()))["t"] or 0
    )
    filas: list[dict[str, Any]] = []
    for row in raw:
        sv = float(row.get("suma_valor") or 0)
        filas.append(
            {
                "etiqueta": str(row.get("etiqueta") or ""),
                "lineas": int(row.get("lineas") or 0),
                "suma_valor": sv,
                "suma_cantidad": float(row.get("suma_cantidad") or 0),
                "suma_peso": float(row.get("suma_peso") or 0),
                "pct_del_total": round((sv / total) * 100, 2) if total > 0 else 0.0,
            }
        )
    return {
        "filas": filas,
        "total_valor": total,
        "periodo": {"desde": d1, "hasta": d2},
        "dimension": dimension,
        "_sql_traces": [_trace(sql, params), _trace(sql_t, params)],
    }


def comparativo_dos_periodos(
    conn: Connection, a1: str, a2: str, b1: str, b2: str, dimension: str, limit: int
) -> dict[str, Any]:
    limit = max(1, min(80, limit))
    expr = col_etiqueta(dimension)
    sql = f"""SELECT etiqueta,
            SUM(va) AS valor_a,
            SUM(vb) AS valor_b
        FROM (
            SELECT {expr} AS etiqueta, COALESCE(SUM(Valor),0) AS va, 0 AS vb
            FROM ventasgeneral2 WHERE FechaContable BETWEEN :a1 AND :a2
            GROUP BY {expr}
            UNION ALL
            SELECT {expr}, 0, COALESCE(SUM(Valor),0)
            FROM ventasgeneral2 WHERE FechaContable BETWEEN :b1 AND :b2
            GROUP BY {expr}
        ) u
        GROUP BY etiqueta
        HAVING ABS(SUM(va)) + ABS(SUM(vb)) > 0
        ORDER BY GREATEST(ABS(SUM(va)), ABS(SUM(vb))) DESC
        LIMIT {limit}"""
    params = {":a1": a1, ":a2": a2, ":b1": b1, ":b2": b2}
    bind = {"a1": a1, "a2": a2, "b1": b1, "b2": b2}
    raw = _rows(conn.execute(text(sql), bind))
    filas = []
    for row in raw:
        va = float(row.get("valor_a") or 0)
        vb = float(row.get("valor_b") or 0)
        filas.append(
            {
                "etiqueta": str(row.get("etiqueta") or ""),
                "valor_periodo_a": va,
                "valor_periodo_b": vb,
                "delta": round(vb - va, 2),
            }
        )
    return {
        "filas": filas,
        "periodo_a": {"desde": a1, "hasta": a2},
        "periodo_b": {"desde": b1, "hasta": b2},
        "dimension": dimension,
        "_sql_traces": [_trace(sql, params)],
    }


def top_productos(conn: Connection, d1: str, d2: str, top: int) -> dict[str, Any]:
    top = max(1, min(100, top))
    sql = f"""SELECT CodigoItem AS cod_item, MAX(COALESCE(NULLIF(TRIM(GlosaDetalle),''),'(sin glosa)')) AS glosa,
            COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor, COALESCE(SUM(Cantidad),0) AS suma_cantidad
        FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2
        GROUP BY CodigoItem
        ORDER BY suma_valor DESC
        LIMIT {top}"""
    params = {":d1": d1, ":d2": d2}
    filas = _rows(conn.execute(text(sql), {"d1": d1, "d2": d2}))
    return {
        "filas": filas,
        "periodo": {"desde": d1, "hasta": d2},
        "_sql_traces": [_trace(sql, params)],
    }


def top_clientes_global(conn: Connection, d1: str, d2: str, top: int) -> dict[str, Any]:
    top = max(1, min(100, top))
    sql = f"""SELECT CodigoCliente AS cod_cliente,
            MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,
            COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor
        FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2
        GROUP BY CodigoCliente
        ORDER BY suma_valor DESC
        LIMIT {top}"""
    params = {":d1": d1, ":d2": d2}
    raw = _rows(conn.execute(text(sql), {"d1": d1, "d2": d2}))
    sql_t = "SELECT COALESCE(SUM(Valor),0) AS t FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2"
    total = float((_row(conn.execute(text(sql_t), {"d1": d1, "d2": d2}).one()))["t"] or 0)
    cum = 0.0
    filas = []
    for row in raw:
        sv = float(row.get("suma_valor") or 0)
        pct = (sv / total) * 100.0 if total > 0 else 0.0
        cum += pct
        filas.append(
            {
                "cod_cliente": str(row.get("cod_cliente") or ""),
                "nombre_cliente": str(row.get("nombre_cliente") or ""),
                "lineas": int(row.get("lineas") or 0),
                "suma_valor": sv,
                "pct_del_total": round(pct, 2),
                "pct_acumulado": round(cum, 2),
            }
        )
    return {
        "filas": filas,
        "total_valor": total,
        "periodo": {"desde": d1, "hasta": d2},
        "_sql_traces": [_trace(sql, params), _trace(sql_t, params)],
    }


def top_clientes_nota_credito(conn: Connection, d1: str, d2: str, top: int) -> dict[str, Any]:
    top = max(1, min(100, top))
    tdoc_cond = "COALESCE(NULLIF(TRIM(CodigoDocumento),''),'') = '07'"
    sql = f"""SELECT CodigoCliente AS cod_cliente,
            MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,
            COUNT(*) AS lineas,
            COALESCE(SUM(Valor),0) AS suma_valor
        FROM ventasgeneral2
        WHERE FechaContable BETWEEN :d1 AND :d2 AND {tdoc_cond}
        GROUP BY CodigoCliente
        ORDER BY lineas DESC, suma_valor ASC
        LIMIT {top}"""
    params = {":d1": d1, ":d2": d2}
    raw = _rows(conn.execute(text(sql), {"d1": d1, "d2": d2}))
    sql_tot = f"SELECT COUNT(*) AS n, COALESCE(SUM(Valor),0) AS v FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2 AND {tdoc_cond}"
    tot_row = _row(conn.execute(text(sql_tot), {"d1": d1, "d2": d2}).one())
    total_lineas = int(tot_row.get("n") or 0)
    total_valor_nc = float(tot_row.get("v") or 0)
    cum = 0.0
    filas = []
    for row in raw:
        ln = int(row.get("lineas") or 0)
        pct = (ln / total_lineas) * 100.0 if total_lineas > 0 else 0.0
        cum += pct
        filas.append(
            {
                "cod_cliente": str(row.get("cod_cliente") or ""),
                "nombre_cliente": str(row.get("nombre_cliente") or ""),
                "lineas": ln,
                "suma_valor": float(row.get("suma_valor") or 0),
                "pct_lineas_del_total": round(pct, 2),
                "pct_lineas_acumulado": round(cum, 2),
            }
        )
    return {
        "filas": filas,
        "total_lineas_nc": total_lineas,
        "total_valor_nc": total_valor_nc,
        "periodo": {"desde": d1, "hasta": d2},
        "_sql_traces": [_trace(sql, params), _trace(sql_tot, params)],
    }


def mix_por_tdoc(conn: Connection, d1: str, d2: str) -> dict[str, Any]:
    sql = """SELECT COALESCE(NULLIF(TRIM(CodigoDocumento),''),'(sin TDoc)') AS tdoc, COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor
        FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2
        GROUP BY COALESCE(NULLIF(TRIM(CodigoDocumento),''),'(sin TDoc)')
        ORDER BY suma_valor DESC"""
    params = {":d1": d1, ":d2": d2}
    rows = _rows(conn.execute(text(sql), {"d1": d1, "d2": d2}))
    total = sum(float(r.get("suma_valor") or 0) for r in rows)
    filas = []
    for r in rows:
        sv = float(r.get("suma_valor") or 0)
        filas.append(
            {
                "tdoc": str(r.get("tdoc") or ""),
                "lineas": int(r.get("lineas") or 0),
                "suma_valor": sv,
                "pct_del_total": round((sv / total) * 100, 2) if total > 0 else 0.0,
            }
        )
    return {
        "filas": filas,
        "total_valor": total,
        "periodo": {"desde": d1, "hasta": d2},
        "_sql_traces": [_trace(sql, params)],
    }


def top_ruta_comercial(conn: Connection, d1: str, d2: str, top: int) -> dict[str, Any]:
    top = max(1, min(100, top))
    expr = col_etiqueta("ruta")
    sql = f"""SELECT {expr} AS ruta, COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor
        FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2
        GROUP BY {expr}
        ORDER BY suma_valor DESC
        LIMIT {top}"""
    params = {":d1": d1, ":d2": d2}
    return {
        "filas": _rows(conn.execute(text(sql), {"d1": d1, "d2": d2})),
        "periodo": {"desde": d1, "hasta": d2},
        "_sql_traces": [_trace(sql, params)],
    }


def top_corporativo(conn: Connection, d1: str, d2: str, top: int) -> dict[str, Any]:
    top = max(1, min(100, top))
    expr = col_etiqueta("corporativo")
    sql = f"""SELECT {expr} AS nombre_coorporativo,
            MAX(COALESCE(NULLIF(TRIM(CodigoCoorporativo),''),'')) AS cod_coorporativo,
            COUNT(*) AS lineas, COALESCE(SUM(Valor),0) AS suma_valor
        FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2
        GROUP BY {expr}
        ORDER BY suma_valor DESC
        LIMIT {top}"""
    params = {":d1": d1, ":d2": d2}
    return {
        "filas": _rows(conn.execute(text(sql), {"d1": d1, "d2": d2})),
        "periodo": {"desde": d1, "hasta": d2},
        "_sql_traces": [_trace(sql, params)],
    }


def serie_mensual_valor(conn: Connection, d1: str, d2: str) -> dict[str, Any]:
    sql = """SELECT DATE_FORMAT(FechaContable, '%Y-%m') AS mes, COALESCE(SUM(Valor),0) AS suma_valor, COUNT(*) AS lineas
        FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2
        GROUP BY DATE_FORMAT(FechaContable, '%Y-%m')
        ORDER BY mes"""
    params = {":d1": d1, ":d2": d2}
    return {
        "filas": _rows(conn.execute(text(sql), {"d1": d1, "d2": d2})),
        "periodo": {"desde": d1, "hasta": d2},
        "_sql_traces": [_trace(sql, params)],
    }


def pareto_nc_zonaprecio(conn: Connection, d1: str, d2: str, max_zonas: int) -> dict[str, Any]:
    max_zonas = max(1, min(200, max_zonas))
    sql = f"""SELECT COALESCE(NULLIF(TRIM(DescripcionZonaPrecio),''),'(sin zona)') AS zona,
            COUNT(*) AS lineas_nc,
            COALESCE(SUM(ABS(Valor)),0) AS impacto_abs_valor
        FROM ventasgeneral2
        WHERE FechaContable BETWEEN :d1 AND :d2 AND CodigoDocumento = '07'
        GROUP BY COALESCE(NULLIF(TRIM(DescripcionZonaPrecio),''),'(sin zona)')
        ORDER BY impacto_abs_valor DESC
        LIMIT {max_zonas}"""
    params = {":d1": d1, ":d2": d2}
    raw = _rows(conn.execute(text(sql), {"d1": d1, "d2": d2}))
    total = sum(float(r.get("impacto_abs_valor") or 0) for r in raw)
    cum = 0.0
    filas = []
    for row in raw:
        imp = float(row.get("impacto_abs_valor") or 0)
        pct_fila = (imp / total) * 100.0 if total > 0 else 0.0
        cum += pct_fila
        filas.append(
            {
                "zona": str(row.get("zona") or ""),
                "lineas_nc": int(row.get("lineas_nc") or 0),
                "impacto_abs_valor": imp,
                "pct_del_total": round(pct_fila, 2),
                "pct_acumulado": round(cum, 2),
            }
        )
    hasta80 = 0
    for i, f in enumerate(filas):
        hasta80 = i + 1
        if float(f["pct_acumulado"]) >= 80.0:
            break
    return {
        "filas": filas,
        "total_impacto_nc": total,
        "zonas_contadas_hasta_80pct_aprox": hasta80,
        "periodo": {"desde": d1, "hasta": d2},
        "_sql_traces": [_trace(sql, params)],
    }


def top_clientes_zona_precio(conn: Connection, d1: str, d2: str, prefijo: str, top_n: int) -> dict[str, Any]:
    top_n = max(1, min(100, top_n))
    pref = prefijo.strip().upper()
    if not pref:
        raise ValueError("prefijo_descri_zona_precio no puede estar vacío")
    like = pref + "%"
    sql_total = """SELECT COALESCE(SUM(Valor), 0) AS total_valor
        FROM ventasgeneral2
        WHERE FechaContable BETWEEN :d1 AND :d2
        AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio, ''))) LIKE :pref"""
    params_t = {":d1": d1, ":d2": d2, ":pref": like}
    total_zona = float(
        (_row(conn.execute(text(sql_total), {"d1": d1, "d2": d2, "pref": like}).one())).get("total_valor")
        or 0
    )
    sql = f"""SELECT CodigoCliente,
            MAX(COALESCE(NULLIF(TRIM(NombreCliente), ''), '(sin nombre)')) AS nombre_cliente,
            COALESCE(SUM(Valor), 0) AS suma_valor,
            COUNT(*) AS lineas_venta
        FROM ventasgeneral2
        WHERE FechaContable BETWEEN :d1 AND :d2
        AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio, ''))) LIKE :pref
        GROUP BY CodigoCliente
        ORDER BY suma_valor DESC
        LIMIT {top_n}"""
    params = {":d1": d1, ":d2": d2, ":pref": like}
    raw = _rows(conn.execute(text(sql), {"d1": d1, "d2": d2, "pref": like}))
    cum = 0.0
    filas = []
    for row in raw:
        sv = float(row.get("suma_valor") or 0)
        pct_fila = (sv / total_zona) * 100.0 if total_zona != 0.0 else 0.0
        cum += pct_fila
        filas.append(
            {
                "cod_cliente": str(row.get("CodigoCliente") or ""),
                "nombre_cliente": str(row.get("nombre_cliente") or ""),
                "suma_valor": sv,
                "lineas_venta": int(row.get("lineas_venta") or 0),
                "pct_del_total_zona": round(pct_fila, 2),
                "pct_acumulado": round(cum, 2),
            }
        )
    hasta80 = 0
    for i, f in enumerate(filas):
        hasta80 = i + 1
        if float(f["pct_acumulado"]) >= 80.0:
            break
    return {
        "filas": filas,
        "total_valor_zona": total_zona,
        "clientes_contados_hasta_80pct_aprox": hasta80,
        "periodo": {"desde": d1, "hasta": d2},
        "prefijo_descri_zona_precio": pref,
        "_sql_traces": [_trace(sql_total, params_t), _trace(sql, params)],
    }


def buscar(conn: Connection, args: dict[str, Any]) -> dict[str, Any]:
    max_limit = 100
    default_limit = 50

    def clamp_limit(n: int | None) -> int:
        if n is None:
            return default_limit
        return max(1, min(max_limit, n))

    try:
        li = int(args["limit"]) if args.get("limit") not in (None, "") else None
    except (TypeError, ValueError):
        li = None
    limit = clamp_limit(li)

    try:
        off = max(0, int(args.get("offset") or 0))
    except (TypeError, ValueError):
        off = 0

    def parse_date_optional(key: str) -> str | None:
        v = args.get(key)
        if v is None or str(v).strip() == "":
            return None
        s = str(v).strip()
        try:
            datetime.strptime(s, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError("Fecha inválida (YYYY-MM-DD)") from e
        return s

    sql = """SELECT id, FechaContable, CodigoCoorporativo, NombreCoorporativo, CodigoCliente, NombreCliente, CodigoDocumento, TipoDocumento, SerieDocumento, NumeroDocumento, NumeroFactura, CodigoItem, GlosaDetalle, Cantidad, Peso, Valor, ZonaComercial, DescripcionZonaPrecio, RutaComercial, Provincia, LineaComercial
        FROM ventasgeneral2 WHERE 1=1"""
    params: dict[str, Any] = {}

    fd = parse_date_optional("fecha_desde")
    fh = parse_date_optional("fecha_hasta")

    if fd is not None and fh is not None:
        if fd > fh:
            raise ValueError("fecha_desde no puede ser mayor que fecha_hasta")
        sql += " AND FechaContable BETWEEN :fd AND :fh"
        params["fd"] = fd
        params["fh"] = fh
    elif fd is not None:
        sql += " AND FechaContable >= :fd"
        params["fd"] = fd
    elif fh is not None:
        sql += " AND FechaContable <= :fh"
        params["fh"] = fh

    nom = str(args.get("nombre_cliente") or "").strip()
    if nom:
        sql += " AND NombreCliente LIKE :nom"
        params["nom"] = f"%{nom}%"

    ndoc = str(args.get("numero_doc") or "").strip()
    if ndoc:
        sql += " AND NumeroFactura LIKE :ndoc"
        params["ndoc"] = f"%{ndoc}%"

    item = str(args.get("cod_item") or "").strip()
    if item:
        sql += " AND CodigoItem = :item"
        params["item"] = item

    tdoc = str(args.get("tdoc") or "").strip()
    if tdoc:
        if len(tdoc) > 4:
            raise ValueError("tdoc demasiado largo")
        sql += " AND CodigoDocumento = :tdoc"
        params["tdoc"] = tdoc

    pref_z = str(args.get("prefijo_descri_zona_precio") or "").strip().upper()
    if pref_z:
        sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzp"
        params["prefzp"] = pref_z + "%"

    prov = str(args.get("provincia") or "").strip()
    if prov:
        sql += " AND Provincia LIKE :prov"
        params["prov"] = f"%{prov}%"

    tdoctipo = str(args.get("tipo_documento") or "").strip()
    if tdoctipo:
        sql += " AND TipoDocumento LIKE :tdoctipo"
        params["tdoctipo"] = f"%{tdoctipo}%"

    sql += f" ORDER BY FechaContable DESC, id DESC LIMIT {int(limit)} OFFSET {int(off)}"

    trace_params = {f":{k}": v for k, v in params.items()}
    rows = _rows(conn.execute(text(sql), params))

    q: dict[str, str] = {}
    for k in (
        "fecha_desde",
        "fecha_hasta",
        "nombre_cliente",
        "numero_doc",
        "cod_item",
        "tdoc",
        "prefijo_descri_zona_precio",
        "provincia",
        "tipo_documento",
    ):
        v = args.get(k)
        if v is not None and str(v).strip() != "":
            q[k] = str(v)
    q["limit"] = str(limit)
    q["offset"] = str(off)

    reporte_url = "ventasgeneral_buscar_tabla.php?" + urlencode(q, safe="", quote_via=quote)

    return {
        "filas": rows,
        "limit": limit,
        "offset": off,
        "_sql_traces": [{"sql": sql, "params": trace_params}],
        "reporte_url": reporte_url,
    }


def ym_add_months(ym: str, add: int) -> str:
    y, mo = map(int, ym.split("-"))
    mo += add
    y += (mo - 1) // 12
    mo = (mo - 1) % 12 + 1
    return f"{y:04d}-{mo:02d}"


def _linea_extra_filters(
    sql: str, bind: dict[str, Any], params: dict[str, Any],
    cod_item: str | None, prefijo_zona: str | None
) -> str:
    if cod_item:
        sql += " AND CodigoItem = :cod_item"
        bind["cod_item"] = cod_item
        params[":cod_item"] = cod_item
    if prefijo_zona:
        like = prefijo_zona.upper() + "%"
        sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo"
        bind["prefzo"] = like
        params[":prefzo"] = like
    return sql


def ventas_linea_resumen_provincia(
    conn: Connection,
    d1: str,
    d2: str,
    linea: str,
    top: int | None = None,
    cod_item: str | None = None,
    prefijo_zona: str | None = None,
) -> dict[str, Any]:
    """top=None o <=0: sin LIMIT (todas las filas agrupadas). Si top>0, como máximo 100000."""
    limit_clause = ""
    if top is not None and top > 0:
        lim = max(1, min(100_000, int(top)))
        limit_clause = f" LIMIT {lim}"
    base = """SELECT
            COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') AS provincia,
            CodigoCliente AS cod_cliente,
            MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,
            COUNT(*) AS lineas,
            COALESCE(SUM(Cantidad),0) AS suma_cantidad,
            COALESCE(SUM(Peso),0) AS suma_peso,
            COALESCE(SUM(Valor),0) AS suma_valor
        FROM ventasgeneral2
        WHERE FechaContable BETWEEN :d1 AND :d2
        AND LOWER(TRIM(LineaComercial)) = LOWER(TRIM(:linea))"""
    bind: dict[str, Any] = {"d1": d1, "d2": d2, "linea": linea}
    params: dict[str, Any] = {":d1": d1, ":d2": d2, ":linea": linea}
    base = _linea_extra_filters(base, bind, params, cod_item, prefijo_zona)
    sql = base + f" GROUP BY provincia, CodigoCliente ORDER BY suma_peso DESC{limit_clause}"
    filas = _rows(conn.execute(text(sql), bind))
    return {
        "filas": filas,
        "linea_comercial": linea,
        "cod_item": cod_item,
        "mercado": prefijo_zona,
        "periodo": {"desde": d1, "hasta": d2},
        "_sql_traces": [_trace(sql, params)],
    }


def ventas_linea_diario_provincia(
    conn: Connection, d1: str, d2: str, linea: str, top: int,
    cod_item: str | None = None, prefijo_zona: str | None = None
) -> dict[str, Any]:
    top = max(1, min(1000, top))
    base = """SELECT
            FechaContable AS fecha,
            COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') AS provincia,
            CodigoCliente AS cod_cliente,
            MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,
            COUNT(*) AS lineas,
            COALESCE(SUM(Cantidad),0) AS suma_cantidad,
            COALESCE(SUM(Peso),0) AS suma_peso,
            COALESCE(SUM(Valor),0) AS suma_valor
        FROM ventasgeneral2
        WHERE FechaContable BETWEEN :d1 AND :d2
        AND LOWER(TRIM(LineaComercial)) = LOWER(TRIM(:linea))"""
    bind: dict[str, Any] = {"d1": d1, "d2": d2, "linea": linea}
    params: dict[str, Any] = {":d1": d1, ":d2": d2, ":linea": linea}
    base = _linea_extra_filters(base, bind, params, cod_item, prefijo_zona)
    sql = base + f" GROUP BY fecha, provincia, CodigoCliente ORDER BY fecha ASC, suma_peso DESC LIMIT {top}"
    filas = _rows(conn.execute(text(sql), bind))
    return {
        "filas": filas,
        "linea_comercial": linea,
        "cod_item": cod_item,
        "mercado": prefijo_zona,
        "periodo": {"desde": d1, "hasta": d2},
        "_sql_traces": [_trace(sql, params)],
    }


def ventas_linea_precio_diario(
    conn: Connection, d1: str, d2: str, linea: str, top: int,
    cod_item: str | None = None, prefijo_zona: str | None = None
) -> dict[str, Any]:
    top = max(1, min(1000, top))
    base = """SELECT
            FechaContable AS fecha,
            COALESCE(NULLIF(TRIM(Provincia),''),'(sin provincia)') AS provincia,
            CodigoCliente AS cod_cliente,
            MAX(COALESCE(NULLIF(TRIM(NombreCliente),''),'(sin nombre)')) AS nombre_cliente,
            COALESCE(SUM(Cantidad),0) AS suma_cantidad,
            COALESCE(SUM(Peso),0) AS suma_peso,
            COALESCE(SUM(Valor),0) AS suma_valor,
            CASE WHEN COALESCE(SUM(Peso),0) > 0
                 THEN ROUND(COALESCE(SUM(Valor),0) / COALESCE(SUM(Peso),0), 4)
                 ELSE NULL END AS precio_kg
        FROM ventasgeneral2
        WHERE FechaContable BETWEEN :d1 AND :d2
        AND LOWER(TRIM(LineaComercial)) = LOWER(TRIM(:linea))"""
    bind: dict[str, Any] = {"d1": d1, "d2": d2, "linea": linea}
    params: dict[str, Any] = {":d1": d1, ":d2": d2, ":linea": linea}
    base = _linea_extra_filters(base, bind, params, cod_item, prefijo_zona)
    sql = base + f" GROUP BY fecha, provincia, CodigoCliente ORDER BY fecha ASC, suma_peso DESC LIMIT {top}"
    filas = _rows(conn.execute(text(sql), bind))
    return {
        "filas": filas,
        "linea_comercial": linea,
        "cod_item": cod_item,
        "mercado": prefijo_zona,
        "periodo": {"desde": d1, "hasta": d2},
        "_sql_traces": [_trace(sql, params)],
    }


def ventas_linea_mix_productos(
    conn: Connection, d1: str, d2: str, linea: str,
    prefijo_zona: str | None = None
) -> dict[str, Any]:
    base = """SELECT
            CodigoItem AS cod_item,
            MAX(COALESCE(NULLIF(TRIM(GlosaDetalle),''),'(sin glosa)')) AS glosa,
            COUNT(*) AS lineas,
            COALESCE(SUM(Cantidad),0) AS suma_cantidad,
            COALESCE(SUM(Peso),0) AS suma_peso,
            COALESCE(SUM(Valor),0) AS suma_valor,
            CASE WHEN COALESCE(SUM(Peso),0) > 0
                 THEN ROUND(COALESCE(SUM(Valor),0) / COALESCE(SUM(Peso),0), 4)
                 ELSE NULL END AS precio_kg
        FROM ventasgeneral2
        WHERE FechaContable BETWEEN :d1 AND :d2
        AND LOWER(TRIM(LineaComercial)) = LOWER(TRIM(:linea))"""
    bind: dict[str, Any] = {"d1": d1, "d2": d2, "linea": linea}
    params: dict[str, Any] = {":d1": d1, ":d2": d2, ":linea": linea}
    if prefijo_zona:
        like = prefijo_zona.upper() + "%"
        base += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzo"
        bind["prefzo"] = like
        params[":prefzo"] = like
    sql = base + " GROUP BY CodigoItem ORDER BY suma_peso DESC"
    filas = _rows(conn.execute(text(sql), bind))
    total_peso = sum(float(r.get("suma_peso") or 0) for r in filas)
    total_valor = sum(float(r.get("suma_valor") or 0) for r in filas)
    for r in filas:
        sp = float(r.get("suma_peso") or 0)
        r["pct_peso"] = round(sp / total_peso * 100, 2) if total_peso else 0.0
    return {
        "filas": filas,
        "linea_comercial": linea,
        "mercado": prefijo_zona,
        "total_peso": total_peso,
        "total_valor": total_valor,
        "periodo": {"desde": d1, "hasta": d2},
        "_sql_traces": [_trace(sql, params)],
    }
