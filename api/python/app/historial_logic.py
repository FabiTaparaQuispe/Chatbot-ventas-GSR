from __future__ import annotations

import re
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

_CATEGORIAS: list[tuple[str, str]] = [
    ("Clientes", r"/cliente|comprador|quién|quien|top.*client|client.*top/ui"),
    ("Productos", r"/producto|artículo|articulo|item|ítem/ui"),
    ("Por zona", r"/zona|región|region|mercado|tacna|arequipa|moquegua|lajoya|aqp/ui"),
    ("Notas de crédito", r"/nota.*créd|nota.*cred|devoluci|devoluc|\bnc\b|anulac|crédit.*nota|cred.*nota/ui"),
    ("Comparativos", r"/compar|versus|\bvs\.?\b|período.*vs|vs.*período/ui"),
    ("Proyecciones", r"/proyecc|proyect|tendencia|predi[cg]/ui"),
    ("Ventas / resumen", r"/venta|factur|resumen|total|importe|monto|valor|facturado/ui"),
]


def clasificar_pregunta(texto: str) -> str:
    for nombre, patron in _CATEGORIAS:
        if re.search(patron, texto, re.I):
            return nombre
    return "Otras"


def historial_preview(text: str, max_len: int = 220) -> str:
    t = re.sub(r"\s+", " ", text.strip())
    if not t:
        return "—"
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


SQL_HISTORIAL_SELECT = """
SELECT
    m.id         AS msg_id,
    m.created_at AS preguntado_en,
    m.content    AS pregunta,
    t.username   AS usuario,
    t.client_thread_id AS thread_id,
    t.title      AS chat_titulo,
    (
        SELECT LEFT(m2.content, 180)
        FROM app_chat_messages m2
        WHERE m2.thread_id = m.thread_id
          AND m2.role      = 'assistant'
          AND m2.id        > m.id
        ORDER BY m2.id ASC
        LIMIT 1
    ) AS respuesta_extracto
FROM app_chat_messages m
INNER JOIN app_chat_threads t ON t.id = m.thread_id
"""


def _parse_hist_date(val: str | None) -> tuple[str | None, str | None]:
    if val is None or str(val).strip() == "":
        return None, None
    s = str(val).strip()[:32]
    try:
        d = date.fromisoformat(s)
        if d.strftime("%Y-%m-%d") != s:
            return None, "Use fechas en formato YYYY-MM-DD."
    except ValueError:
        return None, "Fecha inválida (use YYYY-MM-DD)."
    return s, None


def _sanitize_hist_username(val: str | None) -> str | None:
    s = str(val or "").strip()
    if not s:
        return None
    return s[:120]


def fetch_historial_rows(
    conn: Connection,
    *,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    username: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    d1, err1 = _parse_hist_date(fecha_desde)
    if err1:
        return [], err1
    d2, err2 = _parse_hist_date(fecha_hasta)
    if err2:
        return [], err2
    if d1 and d2 and d1 > d2:
        return [], "La fecha desde no puede ser mayor que la fecha hasta."
    user_f = _sanitize_hist_username(username)

    where = ["m.role = 'user'"]
    params: dict[str, Any] = {}
    if d1:
        where.append("m.created_at >= :d1")
        params["d1"] = d1
    if d2:
        where.append("m.created_at < DATE_ADD(:d2, INTERVAL 1 DAY)")
        params["d2"] = d2
    if user_f:
        where.append("t.username = :u")
        params["u"] = user_f

    sql = (
        SQL_HISTORIAL_SELECT.strip()
        + " WHERE "
        + " AND ".join(where)
        + " ORDER BY m.created_at DESC, m.id DESC LIMIT 600"
    )
    try:
        rows = [dict(r._mapping) for r in conn.execute(text(sql), params).mappings().all()]
        return rows, ""
    except Exception as e:
        raw = str(e)
        missing = "42S02" in raw or "doesn't exist" in raw.lower() or "unknown table" in raw.lower()
        err = (
            "Las tablas del chat aún no están creadas. Ejecutá docs/schema_auth_chat.sql en la base de datos y recargá."
            if missing
            else "No se pudo leer el historial. Revisá DB_DSN en .env y que existan app_chat_threads y app_chat_messages."
        )
        return [], err


def fetch_historial_usernames(conn: Connection) -> tuple[list[str], str]:
    sql = (
        "SELECT DISTINCT t.username AS u "
        "FROM app_chat_threads t "
        "INNER JOIN app_chat_messages m ON m.thread_id = t.id AND m.role = 'user' "
        "WHERE TRIM(COALESCE(t.username,'')) != '' "
        "ORDER BY t.username ASC"
    )
    try:
        rows = conn.execute(text(sql)).mappings().all()
        out = [str(r.get("u") or "").strip() for r in rows if str(r.get("u") or "").strip()]
        return out, ""
    except Exception:
        return [], ""


def build_stats(rows: list[dict[str, Any]]) -> dict[str, int]:
    conteos: dict[str, int] = {nombre: 0 for nombre, _ in _CATEGORIAS}
    conteos["Otras"] = 0
    for r in rows:
        texto = str(r.get("pregunta") or "")
        cat = clasificar_pregunta(texto)
        conteos[cat] = conteos.get(cat, 0) + 1
    return dict(sorted(conteos.items(), key=lambda x: x[1], reverse=True))


def is_historial_filter_validation_error(msg: str) -> bool:
    m = (msg or "").strip()
    if not m:
        return False
    return m.startswith(("Fecha inválida", "Use fechas", "La fecha desde"))
