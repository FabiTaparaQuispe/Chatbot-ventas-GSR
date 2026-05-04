from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import get_engine

router = APIRouter(prefix="/api", tags=["datatables"])


def _parse_ymd(s: str) -> str | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        d = datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None
    if d.strftime("%Y-%m-%d") != s:
        return None
    return s


def _utf8_cell(v: Any) -> str:
    if v is None:
        return ""
    s = str(v)
    try:
        s.encode("utf-8")
        return s
    except UnicodeEncodeError:
        return s.encode("utf-8", errors="replace").decode("utf-8", errors="replace")


@router.get("/ventasgeneral_dt.php")
async def ventasgeneral_dt(request: Request) -> Any:
    qp = request.query_params
    draw = int(qp.get("draw") or 0)
    start = max(0, int(qp.get("start") or 0))
    length = max(1, min(200, int(qp.get("length") or 20)))
    search = str(qp.get("search") or qp.get("search[value]") or "").strip()
    desde = _parse_ymd(str(qp.get("desde") or ""))
    hasta = _parse_ymd(str(qp.get("hasta") or ""))
    nombre = str(qp.get("nombre") or "").strip()
    numero_doc = str(qp.get("numero_doc") or "").strip()
    tipo_documento = str(qp.get("tipo_documento") or "").strip()
    provincia = str(qp.get("provincia") or "").strip()

    try:
        engine = get_engine()
        with engine.connect() as conn:
            base_where = " WHERE 1=1"
            params: dict[str, Any] = {}
            if desde:
                base_where += " AND FechaContable >= :d1"
                params["d1"] = desde
            if hasta:
                base_where += " AND FechaContable <= :d2"
                params["d2"] = hasta
            if nombre:
                base_where += " AND NombreCliente LIKE :nom"
                params["nom"] = f"%{nombre}%"
            if numero_doc:
                base_where += " AND NumeroFactura LIKE :ndoc"
                params["ndoc"] = f"%{numero_doc}%"
            if tipo_documento:
                base_where += " AND TipoDocumento LIKE :tdoctipo"
                params["tdoctipo"] = f"%{tipo_documento}%"
            if provincia:
                base_where += " AND Provincia LIKE :prov"
                params["prov"] = f"%{provincia}%"

            records_total = int(conn.execute(text("SELECT COUNT(*) AS c FROM ventasgeneral2")).scalar() or 0)

            where = base_where
            if search:
                where += (
                    " AND (NombreCliente LIKE :s OR NumeroFactura LIKE :s OR CodigoItem LIKE :s "
                    "OR GlosaDetalle LIKE :s OR ZonaComercial LIKE :s OR TipoDocumento LIKE :s "
                    "OR Provincia LIKE :s OR LineaComercial LIKE :s)"
                )
                params["s"] = f"%{search}%"

            records_filtered = int(
                conn.execute(text("SELECT COUNT(*) AS c FROM ventasgeneral2" + where), params).scalar() or 0
            )

            sql = (
                "SELECT FechaContable, CodigoCliente, NombreCliente, NumeroFactura, CodigoItem, GlosaDetalle, "
                "Cantidad, Valor, ZonaComercial, TipoDocumento, Provincia, LineaComercial "
                "FROM ventasgeneral2" + where + " ORDER BY FechaContable DESC, NumeroFactura DESC, CodigoItem DESC LIMIT :lim OFFSET :off"
            )
            params2 = dict(params)
            params2["lim"] = length
            params2["off"] = start
            rows = conn.execute(text(sql), params2).mappings().all()
            data = []
            for i, r in enumerate(rows):
                data.append(
                    [
                        str(start + i + 1),
                        _utf8_cell(r.get("FechaContable")),
                        _utf8_cell(r.get("CodigoCliente")),
                        _utf8_cell(r.get("NombreCliente")),
                        _utf8_cell(r.get("NumeroFactura")),
                        _utf8_cell(r.get("CodigoItem")),
                        _utf8_cell(r.get("GlosaDetalle")),
                        _utf8_cell(r.get("Cantidad")),
                        _utf8_cell(r.get("Valor")),
                        _utf8_cell(r.get("ZonaComercial")),
                        _utf8_cell(r.get("TipoDocumento")),
                        _utf8_cell(r.get("Provincia")),
                        _utf8_cell(r.get("LineaComercial")),
                    ]
                )
            return {
                "draw": draw,
                "recordsTotal": records_total,
                "recordsFiltered": records_filtered,
                "data": data,
            }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "draw": draw,
                "recordsTotal": 0,
                "recordsFiltered": 0,
                "data": [],
                "error": str(e),
            },
        )
