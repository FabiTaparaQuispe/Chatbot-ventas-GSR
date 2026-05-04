from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import quote, urlencode

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app import ventas_queries as vq
from app.sql_interpolate import interpolate_sql


class ToolExecutor:
    MAX_LIMIT = 100
    DEFAULT_LIMIT = 50

    def __init__(self, conn: Connection) -> None:
        self._conn = conn
        self._sql_bloques: list[str] = []

    def pull_sql_bloques(self) -> list[str]:
        return self._sql_bloques

    def _absorb_traces(self, result: dict[str, Any]) -> None:
        tr = result.pop("_sql_traces", None)
        if not isinstance(tr, list):
            return
        for item in tr:
            if not isinstance(item, dict):
                continue
            sql = item.get("sql")
            params = item.get("params")
            if isinstance(sql, str) and isinstance(params, dict):
                self._sql_bloques.append(interpolate_sql(sql, params))

    def execute(self, name: str, args: dict[str, Any]) -> str:
        try:
            result = self._dispatch(name, args)
        except Exception as e:
            result = {"error": str(e)}
        if isinstance(result, dict):
            self._absorb_traces(result)
        return json.dumps(result, ensure_ascii=False, default=str)

    def _dispatch(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        m = {
            "ventasgeneral_resumen": self._resumen,
            "ventasgeneral_buscar": self._buscar,
            "ventasgeneral_pareto_nc_zonaprecio": self._pareto_nc,
            "ventasgeneral_top_clientes_zona_precio": self._top_zona,
            "ventasgeneral_barras_ventas_dimension": self._barras_dim,
            "ventasgeneral_comparativo_periodos": self._comparativo,
            "ventasgeneral_top_productos": self._top_prod,
            "ventasgeneral_top_clientes_globales": self._top_cli_glob,
            "ventasgeneral_top_clientes_nota_credito": self._top_nc,
            "ventasgeneral_mix_tdoc": self._mix_tdoc,
            "ventasgeneral_barras_ruta_comercial": self._barras_ruta,
            "ventasgeneral_barras_corporativo": self._barras_corp,
            "ventasgeneral_serie_mensual_valor": self._serie,
            "ventasgeneral_proyeccion_ventas": self._proyeccion,
        }
        fn = m.get(name)
        if fn is None:
            return {"error": f"Función no reconocida: {name}"}
        return fn(args)

    def _parse_date(self, key: str, args: dict[str, Any], required: bool = True) -> str | None:
        if key not in args or args[key] in (None, ""):
            if required:
                raise ValueError(f"Falta parámetro de fecha: {key}")
            return None
        s = str(args[key]).strip()
        try:
            d = datetime.strptime(s, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Fecha inválida (use YYYY-MM-DD): {key}") from e
        if d.strftime("%Y-%m-%d") != s:
            raise ValueError(f"Fecha inválida (use YYYY-MM-DD): {key}")
        return s

    def _parse_range(
        self, args: dict[str, Any], fk: str = "fecha_desde", tk: str = "fecha_hasta"
    ) -> tuple[str, str]:
        d1 = self._parse_date(fk, args)
        d2 = self._parse_date(tk, args)
        assert d1 is not None and d2 is not None
        if d1 > d2:
            raise ValueError(f"{fk} no puede ser mayor que {tk}")
        return d1, d2

    def _int_arg(self, v: Any, default: int, lo: int, hi: int) -> int:
        if v in (None, ""):
            return default
        try:
            n = int(v) if not isinstance(v, float) else int(v)
        except (TypeError, ValueError):
            return default
        return max(lo, min(hi, n))

    def _dim_pc(self, v: Any) -> str:
        d = str(v or "precio").strip().lower()
        if d not in ("precio", "comercial"):
            raise ValueError("dimension debe ser precio o comercial")
        return d

    def _resumen(self, args: dict[str, Any]) -> dict[str, Any]:
        d1, d2 = self._parse_range(args)
        sql = """SELECT COUNT(*) AS filas, COALESCE(SUM(Valor),0) AS suma_valor,
            COALESCE(SUM(Cantidad),0) AS suma_cantidad, COALESCE(SUM(Peso),0) AS suma_peso
            FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2"""
        params: dict[str, Any] = {":d1": d1, ":d2": d2}
        bind = {"d1": d1, "d2": d2}

        zona = str(args.get("zona_comercial") or "").strip()
        if zona:
            sql += " AND ZonaComercial LIKE :zona"
            bind["zona"] = f"%{zona}%"
            params[":zona"] = bind["zona"]

        cod = str(args.get("cod_cliente") or "").strip()
        if cod:
            sql += " AND CodigoCliente = :cod"
            bind["cod"] = cod
            params[":cod"] = cod

        pref_z = str(args.get("prefijo_descri_zona_precio") or "").strip().upper()
        if pref_z:
            sql += " AND UPPER(TRIM(COALESCE(DescripcionZonaPrecio,''))) LIKE :prefzp"
            bind["prefzp"] = pref_z + "%"
            params[":prefzp"] = bind["prefzp"]

        prov = str(args.get("provincia") or "").strip()
        if prov:
            sql += " AND Provincia LIKE :prov"
            bind["prov"] = f"%{prov}%"
            params[":prov"] = bind["prov"]

        tdoc = str(args.get("tipo_documento") or "").strip()
        if tdoc:
            sql += " AND TipoDocumento LIKE :tdoc"
            bind["tdoc"] = f"%{tdoc}%"
            params[":tdoc"] = bind["tdoc"]

        row = dict(self._conn.execute(text(sql), bind).mappings().one())
        tabla_q: dict[str, str] = {"fecha_desde": d1, "fecha_hasta": d2}
        if zona:
            tabla_q["zona_comercial"] = zona
        if cod:
            tabla_q["cod_cliente"] = cod
        if pref_z:
            tabla_q["prefijo_descri_zona_precio"] = pref_z
        if prov:
            tabla_q["provincia"] = prov
        if tdoc:
            tabla_q["tipo_documento"] = tdoc
        reporte_url = "ventasgeneral_resumen_tabla.php?" + urlencode(tabla_q, safe="", quote_via=quote)

        return {
            "tabla": "ventasgeneral",
            "periodo": {"desde": d1, "hasta": d2},
            "agregados": row,
            "reporte_url": reporte_url,
            "_sql_traces": [{"sql": sql, "params": params}],
        }

    def _buscar(self, args: dict[str, Any]) -> dict[str, Any]:
        out = vq.buscar(self._conn, args)
        tr = out.pop("_sql_traces", [])
        reporte_url = str(out.pop("reporte_url", "") or "")
        return {
            "tabla": "ventasgeneral",
            "count_devuelto": len(out["filas"]),
            "limit": out["limit"],
            "offset": out["offset"],
            "filas": out["filas"],
            "reporte_url": reporte_url,
            "_sql_traces": tr if isinstance(tr, list) else [],
        }

    def _pareto_nc(self, args: dict[str, Any]) -> dict[str, Any]:
        d1, d2 = self._parse_range(args)
        max_z = self._int_arg(args.get("max_zonas"), 100, 1, 200)
        data = vq.pareto_nc_zonaprecio(self._conn, d1, d2, max_z)
        tr = data.pop("_sql_traces", [])
        q = urlencode({"desde": d1, "hasta": d2, "max": max_z}, safe="", quote_via=quote)
        return {
            "tabla": "ventasgeneral",
            "criterio_nc": "TDoc = '07' (notas de crédito en ETL ventasgeneral)",
            "agrupacion": "DescripcionZonaPrecio",
            "periodo": data["periodo"],
            "total_impacto_nc_valor_abs": data["total_impacto_nc"],
            "filas_pareto": data["filas"],
            "zonas_hasta_80pct_aprox": data["zonas_contadas_hasta_80pct_aprox"],
            "reporte_url": "pareto_nc_zona.php?" + q,
            "_sql_traces": tr,
        }

    def _top_zona(self, args: dict[str, Any]) -> dict[str, Any]:
        d1, d2 = self._parse_range(args)
        pref = str(args.get("prefijo_descri_zona_precio") or "").strip()
        if not pref:
            raise ValueError("Falta prefijo_descri_zona_precio (ej. LAJOYA)")
        top = self._int_arg(args.get("top_n"), 10, 1, 100)
        data = vq.top_clientes_zona_precio(self._conn, d1, d2, pref, top)
        tr = data.pop("_sql_traces", [])
        q = urlencode(
            {
                "desde": d1,
                "hasta": d2,
                "prefijo": data["prefijo_descri_zona_precio"],
                "top": top,
            },
            safe="",
            quote_via=quote,
        )
        return {
            "tabla": "ventasgeneral",
            "criterio": "SUM(Valor) por CodigoCliente; solo líneas con DescripcionZonaPrecio LIKE prefijo%",
            "agrupacion": "CodigoCliente (NombreCliente)",
            "periodo": data["periodo"],
            "prefijo_descri_zona_precio": data["prefijo_descri_zona_precio"],
            "total_valor_zona": data["total_valor_zona"],
            "filas_ranking": data["filas"],
            "clientes_hasta_80pct_aprox": data["clientes_contados_hasta_80pct_aprox"],
            "reporte_url": "pareto_clientes_zona.php?" + q,
            "_sql_traces": tr,
        }

    def _barras_dim(self, args: dict[str, Any]) -> dict[str, Any]:
        d1, d2 = self._parse_range(args)
        dim = self._dim_pc(args.get("dimension"))
        top = self._int_arg(args.get("top_n"), 20, 1, 100)
        data = vq.barras_por_dimension(self._conn, d1, d2, dim, top)
        tr = data.pop("_sql_traces", [])
        q = urlencode({"desde": d1, "hasta": d2, "dim": dim, "top": top}, safe="", quote_via=quote)
        return {
            "tabla": "ventasgeneral",
            "tipo": f"barras_por_{dim}",
            "periodo": data["periodo"],
            "total_valor_periodo": data["total_valor"],
            "filas": data["filas"],
            "reporte_url": "ventas_barras_dimension.php?" + q,
            "_sql_traces": tr,
        }

    def _comparativo(self, args: dict[str, Any]) -> dict[str, Any]:
        a1, a2 = self._parse_range(args, "fecha_desde_a", "fecha_hasta_a")
        b1, b2 = self._parse_range(args, "fecha_desde_b", "fecha_hasta_b")
        dim = self._dim_pc(args.get("dimension"))
        top = self._int_arg(args.get("top_n"), 15, 1, 80)
        data = vq.comparativo_dos_periodos(self._conn, a1, a2, b1, b2, dim, top)
        tr = data.pop("_sql_traces", [])
        q = urlencode(
            {"a_desde": a1, "a_hasta": a2, "b_desde": b1, "b_hasta": b2, "dim": dim, "top": top},
            safe="",
            quote_via=quote,
        )
        return {
            "tabla": "ventasgeneral",
            "tipo": "comparativo_periodos",
            "periodo_a": data["periodo_a"],
            "periodo_b": data["periodo_b"],
            "dimension": dim,
            "filas": data["filas"],
            "reporte_url": "ventas_comparativo.php?" + q,
            "_sql_traces": tr,
        }

    def _top_prod(self, args: dict[str, Any]) -> dict[str, Any]:
        d1, d2 = self._parse_range(args)
        top = self._int_arg(args.get("top_n"), 15, 1, 100)
        data = vq.top_productos(self._conn, d1, d2, top)
        tr = data.pop("_sql_traces", [])
        q = urlencode({"desde": d1, "hasta": d2, "top": top}, safe="", quote_via=quote)
        return {
            "tabla": "ventasgeneral",
            "tipo": "top_productos",
            "periodo": data["periodo"],
            "filas": data["filas"],
            "reporte_url": "ventas_top_productos.php?" + q,
            "_sql_traces": tr,
        }

    def _top_cli_glob(self, args: dict[str, Any]) -> dict[str, Any]:
        d1, d2 = self._parse_range(args)
        top = self._int_arg(args.get("top_n"), 10, 1, 100)
        data = vq.top_clientes_global(self._conn, d1, d2, top)
        tr = data.pop("_sql_traces", [])
        q = urlencode({"desde": d1, "hasta": d2, "top": top}, safe="", quote_via=quote)
        return {
            "tabla": "ventasgeneral",
            "tipo": "top_clientes_global",
            "periodo": data["periodo"],
            "total_valor": data["total_valor"],
            "filas": data["filas"],
            "reporte_url": "ventas_top_clientes_global.php?" + q,
            "_sql_traces": tr,
        }

    def _top_nc(self, args: dict[str, Any]) -> dict[str, Any]:
        d1, d2 = self._parse_range(args)
        top = self._int_arg(args.get("top_n"), 10, 1, 100)
        data = vq.top_clientes_nota_credito(self._conn, d1, d2, top)
        tr = data.pop("_sql_traces", [])
        q = urlencode({"desde": d1, "hasta": d2, "top": top}, safe="", quote_via=quote)
        return {
            "tabla": "ventasgeneral",
            "criterio": "CodigoDocumento = 07; ranking por COUNT(*) por CodigoCliente (notas de crédito)",
            "periodo": data["periodo"],
            "total_lineas_nc": data["total_lineas_nc"],
            "total_valor_nc": data["total_valor_nc"],
            "filas": data["filas"],
            "reporte_url": "ventas_top_clientes_nc.php?" + q,
            "_sql_traces": tr,
        }

    def _mix_tdoc(self, args: dict[str, Any]) -> dict[str, Any]:
        d1, d2 = self._parse_range(args)
        data = vq.mix_por_tdoc(self._conn, d1, d2)
        tr = data.pop("_sql_traces", [])
        q = urlencode({"desde": d1, "hasta": d2}, safe="", quote_via=quote)
        return {
            "tabla": "ventasgeneral",
            "tipo": "mix_tdoc",
            "periodo": data["periodo"],
            "total_valor": data["total_valor"],
            "filas": data["filas"],
            "reporte_url": "ventas_mix_tdoc.php?" + q,
            "_sql_traces": tr,
        }

    def _barras_ruta(self, args: dict[str, Any]) -> dict[str, Any]:
        d1, d2 = self._parse_range(args)
        top = self._int_arg(args.get("top_n"), 15, 1, 100)
        data = vq.top_ruta_comercial(self._conn, d1, d2, top)
        tr = data.pop("_sql_traces", [])
        q = urlencode({"desde": d1, "hasta": d2, "top": top}, safe="", quote_via=quote)
        return {
            "tabla": "ventasgeneral",
            "tipo": "barras_ruta",
            "periodo": data["periodo"],
            "filas": data["filas"],
            "reporte_url": "ventas_barras_ruta.php?" + q,
            "_sql_traces": tr,
        }

    def _barras_corp(self, args: dict[str, Any]) -> dict[str, Any]:
        d1, d2 = self._parse_range(args)
        top = self._int_arg(args.get("top_n"), 15, 1, 100)
        data = vq.top_corporativo(self._conn, d1, d2, top)
        tr = data.pop("_sql_traces", [])
        q = urlencode({"desde": d1, "hasta": d2, "top": top}, safe="", quote_via=quote)
        return {
            "tabla": "ventasgeneral",
            "tipo": "barras_corporativo",
            "periodo": data["periodo"],
            "filas": data["filas"],
            "reporte_url": "ventas_barras_corporativo.php?" + q,
            "_sql_traces": tr,
        }

    def _serie(self, args: dict[str, Any]) -> dict[str, Any]:
        d1, d2 = self._parse_range(args)
        data = vq.serie_mensual_valor(self._conn, d1, d2)
        tr = data.pop("_sql_traces", [])
        q = urlencode({"desde": d1, "hasta": d2}, safe="", quote_via=quote)
        return {
            "tabla": "ventasgeneral",
            "tipo": "serie_mensual_valor",
            "periodo": data["periodo"],
            "filas": data["filas"],
            "reporte_url": "ventas_serie_mensual.php?" + q,
            "_sql_traces": tr,
        }

    def _proyeccion(self, args: dict[str, Any]) -> dict[str, Any]:
        d1, d2 = self._parse_range(args)
        meses = self._int_arg(args.get("meses_a_proyectar"), 3, 1, 12)
        sql = """SELECT DATE_FORMAT(FechaContable, '%Y-%m') AS mes, SUM(Valor) AS suma_valor
            FROM ventasgeneral2 WHERE FechaContable BETWEEN :d1 AND :d2
            GROUP BY DATE_FORMAT(FechaContable, '%Y-%m') ORDER BY mes"""
        params = {":d1": d1, ":d2": d2}
        filas = []
        for r in self._conn.execute(text(sql), {"d1": d1, "d2": d2}):
            d = dict(r._mapping)
            sv = d.get("suma_valor")
            if isinstance(sv, Decimal):
                d["suma_valor"] = float(sv)
            elif sv is not None:
                d["suma_valor"] = float(sv)
            filas.append(d)
        if len(filas) < 2:
            raise ValueError("Se necesitan al menos 2 meses de datos históricos para proyectar")
        n = len(filas)
        sum_x = sum_y = sum_xy = sum_xx = 0.0
        for i, row in enumerate(filas):
            x = float(i)
            y = float(row.get("suma_valor") or 0)
            sum_x += x
            sum_y += y
            sum_xy += x * y
            sum_xx += x * x
        denom = n * sum_xx - sum_x * sum_x
        m = (n * sum_xy - sum_x * sum_y) / denom if denom != 0 else 0.0
        b = (sum_y - m * sum_x) / n
        last_mes = str(filas[-1].get("mes") or "")
        proyecciones = []
        for i in range(1, meses + 1):
            proyecciones.append(
                {
                    "mes": vq.ym_add_months(last_mes, i),
                    "valor_proyectado": max(0.0, m * (n + i - 1) + b),
                }
            )
        return {
            "tabla": "ventasgeneral",
            "tipo": "proyeccion_ventas",
            "periodo_historico": {"desde": d1, "hasta": d2},
            "meses_historicos": n,
            "pendiente_tendencia": m,
            "intercepto": b,
            "proyecciones": proyecciones,
            "nota": "Proyección basada en regresión lineal simple. No considera estacionalidad ni factores externos.",
            "_sql_traces": [{"sql": sql, "params": params}],
        }
