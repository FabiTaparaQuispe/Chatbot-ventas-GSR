import re
from datetime import date
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

# ── Detección automática de "la IA no pudo contestar" ───────────────────────
# Frases reales que el sistema devuelve cuando no logra responder (ver
# routes_fastapi/api/chat.py y services/fast_format.py). Se comparan en
# minúsculas. Una respuesta vacía también cuenta como fallo.
_FALLO_FRASES: tuple[str, ...] = (
    "no pude generar",      # fallback del LLM (chat.py)
    "no se encontr",        # "No se encontraron registros/ventas/clientes…"
    "no encontr",           # "No encontré…"
    "lo siento",
    "error llamando",       # "Error llamando a Gemini"
    "error al generar",
    "no hay datos",
    "no dispongo",
)
# Misma lista como alternancia para MySQL REGEXP (sin caracteres especiales).
_FALLO_REGEXP = "|".join(_FALLO_FRASES)


def _fallo_sql(col: str) -> str:
    """Expresión SQL booleana: la respuesta en `col` es un fallo automático
    (vacía o contiene una frase de error). NO incluye el voto manual."""
    return (
        f"({col} IS NULL OR TRIM({col}) = '' "
        f"OR LOWER({col}) REGEXP '{_FALLO_REGEXP}')"
    )


def estado_respuesta(feedback: Any, extracto: str | None) -> str:
    """Clasifica la respuesta del asistente para mostrarla en el historial.
    Devuelve: 'bueno' | 'malo' | 'fallo' | 'sin_respuesta' | 'ok'.
    El voto manual (👍/👎) siempre manda sobre la detección automática."""
    if feedback == 1:
        return "bueno"
    if feedback == -1:
        return "malo"
    txt = str(extracto or "").strip()
    if not txt:
        return "sin_respuesta"
    low = txt.lower()
    if any(frase in low for frase in _FALLO_FRASES):
        return "fallo"
    return "ok"


SQL_HISTORIAL_SELECT = """
SELECT
    m.id         AS msg_id,
    m.created_at AS preguntado_en,
    m.content    AS pregunta,
    t.username   AS usuario,
    t.client_thread_id AS thread_id,
    t.title      AS chat_titulo,
    LEFT(a.content, 180) AS respuesta_extracto,
    a.feedback   AS respuesta_feedback,
    a.id         AS respuesta_id
FROM app_chat_messages m
INNER JOIN app_chat_threads t ON t.id = m.thread_id
LEFT JOIN app_chat_messages a ON a.id = (
    SELECT m2.id
    FROM app_chat_messages m2
    WHERE m2.thread_id = m.thread_id
      AND m2.role      = 'assistant'
      AND m2.id        > m.id
    ORDER BY m2.id ASC
    LIMIT 1
)
"""


def _parse_hist_date(val: str | None) -> tuple[str | None, str | None]:
    """Devuelve (YYYY-MM-DD o None, mensaje_error o None)."""
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


def fetch_historial_rows(
    conn,
    *,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    username: str | None = None,
    feedback: str | None = None,
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
        where.append("m.created_at >= %(d1)s")
        params["d1"] = d1
    if d2:
        where.append("m.created_at < DATE_ADD(%(d2)s, INTERVAL 1 DAY)")
        params["d2"] = d2
    if user_f:
        where.append("t.username = %(u)s")
        params["u"] = user_f

    # Filtro por evaluación de la respuesta del asistente (a.*).
    fb = str(feedback or "").strip().lower()
    if fb == "buenos":
        where.append("a.feedback = 1")
    elif fb == "malos":
        where.append("a.feedback = -1")
    elif fb == "sin_voto":
        where.append("a.feedback IS NULL")
    elif fb == "fallos":
        # Fallo = sin respuesta, dislike manual, o detección automática (sin 👍).
        where.append(
            "(a.id IS NULL OR a.feedback = -1 OR "
            f"(a.feedback IS NULL AND {_fallo_sql('a.content')}))"
        )

    sql = (
        SQL_HISTORIAL_SELECT.strip()
        + " WHERE "
        + " AND ".join(where)
        + " ORDER BY m.created_at DESC, m.id DESC LIMIT 600"
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
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


def fetch_historial_usernames(conn) -> tuple[list[str], str]:
    sql = (
        "SELECT DISTINCT t.username AS u "
        "FROM app_chat_threads t "
        "INNER JOIN app_chat_messages m ON m.thread_id = t.id AND m.role = 'user' "
        "WHERE TRIM(COALESCE(t.username,'')) != '' "
        "ORDER BY t.username ASC"
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall() or []
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


def fetch_efectividad_stats(conn) -> dict[str, Any]:
    """Métricas de efectividad de las respuestas del asistente.

    Un FALLO ("la IA no pudo contestar") es:
      - dislike manual (feedback = -1), o
      - detección automática (respuesta vacía o con frase de error),
        salvo que tenga 👍 (feedback = 1), que siempre cuenta como acierto.

    efectividad % = aciertos / total * 100  (aciertos = total − fallos).
    """
    base: dict[str, Any] = {
        "ok": False, "total": 0, "buenos": 0, "malos": 0, "fallo_auto": 0,
        "sin_voto": 0, "fallos": 0, "aciertos": 0, "efectividad": 0.0,
    }
    fallo = _fallo_sql("content")
    sql = (
        "SELECT COUNT(*) AS total,"
        " COALESCE(SUM(feedback = 1), 0)  AS buenos,"
        " COALESCE(SUM(feedback = -1), 0) AS malos,"
        f" COALESCE(SUM(feedback IS NULL AND {fallo}), 0) AS fallo_auto"
        " FROM app_chat_messages WHERE role = 'assistant'"
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            r = cur.fetchone() or {}
    except Exception:
        return base

    total = int(r.get("total") or 0)
    buenos = int(r.get("buenos") or 0)
    malos = int(r.get("malos") or 0)
    fallo_auto = int(r.get("fallo_auto") or 0)
    fallos = malos + fallo_auto
    aciertos = total - fallos
    return {
        "ok": True,
        "total": total,
        "buenos": buenos,
        "malos": malos,
        "fallo_auto": fallo_auto,
        "sin_voto": total - buenos - malos,
        "fallos": fallos,
        "aciertos": aciertos,
        "efectividad": round(aciertos / total * 100, 1) if total else 0.0,
    }


def is_historial_filter_validation_error(msg: str) -> bool:
    """True si el mensaje viene de filtros (fecha/usuario), no de fallo de BD."""
    m = (msg or "").strip()
    if not m:
        return False
    return m.startswith(
        ("Fecha inválida", "Use fechas", "La fecha desde"),
    )
