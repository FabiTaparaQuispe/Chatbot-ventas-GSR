import re
from typing import Any

_CATEGORIAS: list[tuple[str, str]] = [
    ("Clientes", r"/cliente|comprador|quién|quien|top.*client|client.*top/ui"),
    ("Productos", r"/producto|artículo|articulo|item|ítem/ui"),
    ("Por zona", r"/zona|región|region|mercado|tacna|arequipa|moquegua|lajoya|aqp/ui"),
    ("Notas de crédito", r"/nota.*créd|nota.*cred|devoluci|devoluc|\bnc\b|anulac|crédit.*nota|cred.*nota/ui"),
    ("Comparativos", r"/compar|versus|\bvs\.?\b|período.*vs|vs.*período/ui"),
    ("Proyecciones", r"/proyecc|proyect|tendencia|predi[cg]/ui"),
    ("Ventas / resumen", r"/venta|factur|resumen|total|importe|monto|valor|facturado/ui"),
]

SQL_HISTORIAL = """
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
WHERE m.role = 'user'
ORDER BY m.created_at DESC, m.id DESC
LIMIT 600
"""


def clasificar_pregunta(texto: str) -> str:
    for nombre, patron in _CATEGORIAS:
        if re.search(patron, texto, re.I):
            return nombre
    return "Otras"


def historial_preview(text: str, max_len: int = 220) -> str:
    t = re.sub(r"\s+", " ", str(text or "").strip())
    if not t:
        return "—"
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def fetch_historial_rows(conn) -> tuple[list[dict[str, Any]], str]:
    try:
        with conn.cursor() as cur:
            cur.execute(SQL_HISTORIAL)
            rows = cur.fetchall() or []
        return [dict(r) for r in rows], ""
    except Exception as e:
        raw = str(e)
        missing = "42S02" in raw or "doesn't exist" in raw.lower() or "unknown table" in raw.lower()
        err = (
            "Las tablas del chat aún no están creadas. Ejecute docs/schema_auth_chat.sql en la base de datos y recargue."
            if missing
            else "No se pudo leer el historial. Revise DB_DSN en .env y que existan app_chat_threads y app_chat_messages."
        )
        return [], err


def build_stats(rows: list[dict[str, Any]]) -> dict[str, int]:
    conteos: dict[str, int] = {nombre: 0 for nombre, _ in _CATEGORIAS}
    conteos["Otras"] = 0
    for r in rows:
        texto = str(r.get("pregunta") or "")
        cat = clasificar_pregunta(texto)
        conteos[cat] = conteos.get(cat, 0) + 1
    return dict(sorted(conteos.items(), key=lambda x: x[1], reverse=True))
