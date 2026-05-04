from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import unquote_plus

from fastapi import Request


def parse_date_string(raw: str) -> str | None:
    s = raw.strip().strip(" \t\n\r\0\x0b\"'()[]<>")
    if not s:
        return None
    try:
        d = datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None
    return d.strftime("%Y-%m-%d")


def query_string_pairs(raw_qs: str) -> list[tuple[str, str]]:
    qs = raw_qs.replace("&amp;", "&")
    if not qs:
        return []
    out: list[tuple[str, str]] = []
    for chunk in re.split(r"[&;]", qs):
        if not chunk or "=" not in chunk:
            continue
        k, v = chunk.split("=", 1)
        out.append((unquote_plus(k.replace("+", " ")), unquote_plus(v.replace("+", " "))))
    return out


def parse_date_get(request: Request, key: str) -> str | None:
    v = request.query_params.get(key)
    return parse_date_string(v) if v else None


def parse_date_get_any(request: Request, keys: list[str]) -> str | None:
    for key in keys:
        d = parse_date_get(request, key)
        if d:
            return d
    return None


def int_from_get(request: Request, keys: list[str], default: int, min_v: int, max_v: int) -> int:
    for key in keys:
        v = request.query_params.get(key)
        if v is None or v == "":
            continue
        try:
            n = int(v)
        except ValueError:
            continue
        return max(min_v, min(max_v, n))
    return max(min_v, min(max_v, default))


def get_dim_precio_comercial(request: Request) -> str:
    for key in ("dim", "dimension"):
        v = (request.query_params.get(key) or "").strip().lower()
        if v in ("precio", "comercial"):
            return v
    return "precio"


def get_dim_ruta_corporativo(request: Request) -> str:
    for key in ("dim", "dimension"):
        v = (request.query_params.get(key) or "").strip().lower()
        if v in ("ruta", "corporativo"):
            return v
    return "ruta"


def comparativo_fechas_desde_hasta_repetidas(request: Request) -> tuple[str, str, str, str] | None:
    desdes: list[str] = []
    hastas: list[str] = []
    for k, v in query_string_pairs(request.url.query):
        if k not in ("desde", "hasta"):
            continue
        d = parse_date_string(v)
        if not d:
            continue
        if k == "desde":
            desdes.append(d)
        else:
            hastas.append(d)
    if len(desdes) >= 2 and len(hastas) >= 2:
        return desdes[0], hastas[0], desdes[1], hastas[1]
    return None


def comparativo_fechas_fecha_desde_hasta_repetidas(request: Request) -> tuple[str, str, str, str] | None:
    desdes: list[str] = []
    hastas: list[str] = []
    for k, v in query_string_pairs(request.url.query):
        if k not in ("fecha_desde", "fecha_hasta"):
            continue
        d = parse_date_string(v)
        if not d:
            continue
        if k == "fecha_desde":
            desdes.append(d)
        else:
            hastas.append(d)
    if len(desdes) >= 2 and len(hastas) >= 2:
        return desdes[0], hastas[0], desdes[1], hastas[1]
    return None


def comparativo_extrae_cuatro_fechas_en_orden(qs: str) -> tuple[str, str, str, str] | None:
    if not qs:
        return None
    pat = re.compile(r"\b(20[0-9]{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01]))\b")
    out: list[str] = []
    for m in pat.finditer(qs):
        d = parse_date_string(m.group(1))
        if d:
            out.append(d)
        if len(out) >= 4:
            break
    if len(out) < 4:
        return None
    return out[0], out[1], out[2], out[3]


def comparativo_parse_four_dates(request: Request) -> tuple[str | None, str | None, str | None, str | None]:
    a1 = parse_date_get_any(request, ["a_desde", "fecha_desde_a", "desde_a", "periodo_a_desde"])
    a2 = parse_date_get_any(request, ["a_hasta", "fecha_hasta_a", "hasta_a", "periodo_a_hasta"])
    b1 = parse_date_get_any(request, ["b_desde", "fecha_desde_b", "desde_b", "periodo_b_desde"])
    b2 = parse_date_get_any(request, ["b_hasta", "fecha_hasta_b", "hasta_b", "periodo_b_hasta"])
    if a1 and a2 and b1 and b2:
        return a1, a2, b1, b2
    for fn in (
        comparativo_fechas_desde_hasta_repetidas,
        comparativo_fechas_fecha_desde_hasta_repetidas,
    ):
        dup = fn(request)
        if dup:
            return dup[0], dup[1], dup[2], dup[3]
    o = comparativo_extrae_cuatro_fechas_en_orden(request.url.query)
    if o:
        return o[0], o[1], o[2], o[3]
    return a1, a2, b1, b2


def resumen_parse_date(request: Request, key: str) -> str | None:
    v = (request.query_params.get(key) or "").strip()
    return parse_date_string(v) if v else None
