import json
import logging
import os
import queue
import re
import threading
from datetime import date
from flask import Blueprint, request, jsonify, Response, stream_with_context
from services.db import get_connection, db_label
from services.groq_client import GroqClient
from services.gemini_client import GeminiClient
from services.llm_provider import resolve_llm_provider
from services.tool_executor import ToolExecutor
from services.tools_definitions import ventas_tool_definitions, chat_history_tool_definitions
from services.chat_reply_enricher import enrich_reply
from services.fast_format import try_fast_format

bp = Blueprint('api_chat', __name__)
_log = logging.getLogger(__name__)

SYSTEM_TEMPLATE = """Asistente ventasgeneral2 (MySQL {db_label}). Solo tabla ventasgeneral2. Fechas YYYY-MM-DD; "marzo 2026"→2026-03-01..2026-03-31; "enero 2026 a febrero 2026"→fecha_desde=2026-01-01,fecha_hasta=2026-02-28 (último día del mes destino); FEBRERO: el último día es SIEMPRE el 28 — nunca uses el 29 aunque el año sea bisiesto (la base de datos no registra ventas el 29 de febrero); "Q1 2026"→2026-01-01..2026-03-31. FECHA HOY: {today}. AÑO EN CURSO: {current_year}. AÑO POR DEFECTO: si el usuario menciona un mes o día sin especificar año, usa {current_year} — NUNCA preguntes el año. DÍA ÚNICO: si el usuario da solo un día, usa ese mismo día como fecha_desde Y fecha_hasta — NUNCA preguntes "fecha fin". YTD/HASTA HOY: "en lo que va del año", "hasta hoy", "hasta la fecha", "hasta donde hay datos" → fecha_desde={current_year}-01-01, fecha_hasta={today} — NUNCA preguntes la fecha de corte.

PARÁMETROS OBLIGATORIOS: si faltan fecha_desde/hasta que el usuario no dio explícitamente, pregúntaselos antes de llamar la herramienta; nunca inventes valores por defecto. CONSULTAS GENERALES (sin línea comercial mencionada): usa ventasgeneral_resumen directamente — NUNCA preguntes la línea comercial para consultas generales; linea_comercial solo es obligatoria en herramientas que la requieren (linea_resumen_provincia, linea_diario_provincia, etc.) y únicamente cuando el usuario la omitió en ese contexto. INDEPENDENCIA DE CONSULTAS: cada pregunta es independiente — NUNCA heredes filtros (tipo_documento, linea_comercial, zona, cod_item, etc.) de preguntas anteriores en el historial; aplica SOLO los filtros que el usuario menciona en su mensaje actual. zona/mercado/prefijo_descri_zona_precio son SIEMPRE opcionales — si el usuario no los menciona, no los pidas. Sin campo ciudad: usa prefijo_descri_zona_precio (AQP, TACNA, MOQUEGUA, LAJOYA…) solo cuando el usuario especificó una zona. Si dice "por zona" sin especificar cuál, usa ventasgeneral_top_clientes_globales. TDoc NC=07. Filtros extra en buscar/resumen: provincia y tipo_documento.

NOTAS DE CRÉDITO: para filtrar NCs en ventasgeneral_resumen usar SIEMPRE codigo_documento="07" (NUNCA tipo_documento para NCs). Toda consulta sobre notas de crédito → llamar TAMBIÉN ventasgeneral_nc_por_corporativo con el mismo rango de fechas para mostrar el desglose por corporativo. Nunca omitas esa segunda llamada en preguntas de NCs.

INTEGRIDAD: PROHIBIDO inventar. Con herramienta: datos deben coincidir exactamente con el JSON (no "Cliente 1", no redondear). Sin herramienta por parámetros faltantes: solo pregunta, jamás listes cifras. Sin herramienta y no es por datos faltantes: "No tengo datos suficientes para responder esa consulta; por favor repite la pregunta." JSON con error: pide el dato correcto. Filas vacías sin error: "No tengo datos suficientes para responder esa consulta en el período indicado." Tema ajeno a ventas/chatbot: "No tengo información para responder esa pregunta; solo manejo datos de ventas y estadísticas del uso del asistente (herramientas chat_*)." Catálogo de valores existentes: usa ventasgeneral_catalogo.

COMPARATIVO: una sola llamada a ventasgeneral_comparativo_periodos con los 4 parámetros de período. Nunca llames barras_dimension dos veces.

CORPORATIVOS: "ventas de X con sus corporativos" → ventasgeneral_barras_corporativo con nombre_cliente="X" (filtra por NombreCliente). Si X es el nombre del corporativo → nombre_corporativo="X".

LÍNEA COMERCIAL: LineaComercial es texto. Valores: "Pollo Vivo"|"Pollo Beneficiado"|"Pollo trozado Seco"|"Embutidos"|"Menudencia"|"Semielaborados"|"Pavos"|"Precocidos"|"Huevos SF"|"Pollo Congelado San Fer."|"Cerdos"|"Promociones embutidos"|"Venta de insumos"|"Envases". Línea 601="Pollo Vivo"; cod_item 100=carne, 103=brasa. Mercados Pollo Vivo: AQPMERCADO,TACNA,ILO,MOQUEGUA,MOLLENDO,CAMANA,LAJOYA,PEDREGAL. HERRAMIENTA DE LÍNEAS — REGLA CRÍTICA: si el usuario pide "todas las líneas", "cada línea", "resumen por línea", "cuánto vendió cada línea", "ventas por línea" → usar SIEMPRE ventasgeneral_resumen_por_linea SIN pasar lineas_comerciales. NUNCA preguntes qué línea en ese caso. GRUPO POLLO: "línea de pollo"/"grupo pollo" → ventasgeneral_resumen_por_linea con lineas_comerciales="Pollo Vivo,Pollo Beneficiado,Pollo trozado Seco,Menudencia". TOTAL DE UNA LÍNEA ESPECÍFICA (sin desglose): "ventas de Pollo Vivo en enero", "cuánto vendió Embutidos en marzo" → usar ventasgeneral_resumen con linea_comercial="Pollo Vivo" (NO usar resumen_por_linea para esto). Detalle provincia/cliente de UNA línea específica→linea_resumen_provincia; diario UNA línea→linea_diario_provincia; precio/día→linea_precio_diario; precio prom prov→linea_precio_resumen_provincia; mix carne/brasa→linea_mix_productos. Para linea_resumen_provincia y similares, si falta la línea específica pregúntala. Mercado/zona OPCIONAL en todas; NUNCA pidas zona si el usuario no la mencionó.

AUDITORÍA CHATBOT: señales "preguntas del chatbot","cuánto se usó","qué preguntó X","actividad del chat" → herramientas chat_*: estadísticas→chat_usuario_estadisticas; ranking→chat_top_usuarios; diario→chat_actividad_por_dia; lista→chat_listar_preguntas; búsqueda→chat_buscar_pregunta; threads→chat_resumen_threads. Fechas obligatorias salvo chat_buscar_pregunta y chat_listar_preguntas. chat_listar_preguntas acepta role (cargo/rol) en vez de username: "gerente"→role="gerencia", "administrador"→role="administrador", "operativo"→role="operativo", "analista"→role="analista". Para "últimas N preguntas de gerente" usa chat_listar_preguntas con role="gerencia" y por_pagina=N (sin fechas). Sin reporte_url en herramientas chat.

FORMATO TABLAS: una sola tabla con columnas horizontales (una fila por ítem). NUNCA uses `**` en ninguna parte de una celda de tabla — ni al inicio, ni al final, ni como encabezado de grupo. Cada celda solo texto plano o número. Para resumen_por_linea usa columnas: Línea | Peso (kg) | Valor (S/) | % del total.
URL: solo /modules/... sin dominio ni #fragmento, sin backticks, una sola por respuesta.
Moneda S/ (S/ 1,234,567.89). Di "importe"/"monto" no "Valor"/"SUM". Español, breve."""


def _unify_pareto_links(reply: str) -> str:
    if not reply or not re.search(
        r'pareto_(?:clientes|nc)_zona\.php\?|/modules/reports/pareto-(?:nc-zona|clientes-zona)\?',
        reply,
        re.IGNORECASE,
    ):
        return reply
    reply = re.sub(
        r'\s*(?:Y la tabla[^\n]*\n)?\s*pareto_(?:clientes|nc)_zona_tabla\.php\?[^\s<>"\']+',
        '',
        reply,
        flags=re.IGNORECASE | re.UNICODE,
    )
    reply = re.sub(r'\n{3,}', '\n\n', reply)
    return reply.strip()


def _parse_retry_after_seconds(msg: str) -> int | None:
    if not msg:
        return None
    m = re.search(r"try again in\s+([\d.]+)\s*s", msg, flags=re.I)
    sec: float | None = None
    if m:
        try:
            sec = float(m.group(1))
        except Exception:
            sec = None
    if sec is None:
        m0 = re.search(r"(?:please\s+)?retry in\s+([\d.]+)\s*s", msg, flags=re.I)
        if m0:
            try:
                sec = float(m0.group(1))
            except Exception:
                sec = None
    if sec is None:
        m_es = re.search(
            r"(?:intent[aá]\s+de\s+nuevo|reintent[aá])\s+en\s+([\d.]+)\s*s",
            msg,
            flags=re.I,
        )
        if m_es:
            try:
                sec = float(m_es.group(1))
            except Exception:
                sec = None
    if sec is None:
        m2 = re.search(r"en\s+(?:(\d+)\s*m\s*)?([\d.]+)\s*s\b", msg, flags=re.I)
        if m2:
            try:
                mins = float(m2.group(1) or 0)
                secs = float(m2.group(2) or 0)
                sec = mins * 60 + secs
            except Exception:
                sec = None
    if sec is None:
        return None
    if sec <= 0:
        return None
    n = int(sec)
    if float(n) < sec:
        n += 1
    return max(1, min(3600, n))


def _get_llm_client():
    """
    Crea el cliente LLM según LLM_PROVIDER (.env) o detección por claves API.
    Soporta: groq, gemini.
    """
    provider = resolve_llm_provider()

    if provider == 'gemini':
        api_key = os.getenv('GEMINI_API_KEY', '')
        if not api_key:
            raise RuntimeError('Configure GEMINI_API_KEY en .env')
        model = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
        return GeminiClient(api_key, model), provider

    # Default: groq
    api_key = os.getenv('GROQ_API_KEY', '')
    if not api_key:
        raise RuntimeError('Configure GROQ_API_KEY en .env')
    model = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')
    return GroqClient(api_key, model), provider


def _is_rate_limit_error(msg: str) -> bool:
    """Errores transitorios del proveedor LLM (cuota, saturación, 503)."""
    m = msg.lower()
    return any(k in m for k in (
        'límite de consultas',
        'limite de consultas',
        'rate limit',
        'rate_limit',
        'too many requests',
        'tokens per day',
        'tpd',
        'límite diario',
        'limite diario',
        '429',
        '503',
        'resource exhausted',
        'quota exceeded',
        'intentá de nuevo',
        'intenta de nuevo',
        'service unavailable',
        'no disponible temporalmente',
    ))


_LINEA_TOOLS = {
    'ventasgeneral_linea_resumen_provincia',
    'ventasgeneral_linea_diario_provincia',
    'ventasgeneral_linea_precio_diario',
    'ventasgeneral_linea_precio_resumen_provincia',
    'ventasgeneral_linea_mix_productos',
}
_CHAT_TOOLS = {
    'chat_usuario_estadisticas',
    'chat_top_usuarios',
    'chat_actividad_por_dia',
    'chat_listar_preguntas',
    'chat_buscar_pregunta',
    'chat_resumen_threads',
}
_NC_TOOLS = {
    'ventasgeneral_top_clientes_nota_credito',
    'ventasgeneral_pareto_nc_zonaprecio',
}

_LINEA_KW = ('línea', 'linea', 'pollo', 'embutido', 'menudencia', 'semielaborado',
              'pavos', 'pavo', 'precocido', 'huevo', 'cerdo', 'promocion',
              'insumo', 'envase', 'brasa', 'trozado', 'beneficiado', 'congelado',
              'precio por', 'carne', 'lineacomercial')
_CHAT_KW  = ('chatbot', 'chat', 'bot', 'preguntas que', 'preguntó', 'pregunto',
             'actividad del', 'auditoría', 'auditoria', 'cuánto se usó', 'cuanto se uso',
             'quién preguntó', 'quien pregunto', 'threads', 'hilos', 'usuarios del',
             'últimas preguntas', 'ultimas preguntas', 'preguntas de ', 'pregunta de ',
             'gerente', 'gerencia', 'operativo', 'analista', 'estrategico', 'estratégico',
             'tactico', 'táctico')
_NC_KW    = ('nota', ' nc ', 'nc,', 'nc.', 'devolución', 'devolucion',
             'anulación', 'anulacion', 'crédito', 'credito', 'nota de crédito',
             'nota de credito')


def _filter_tools(user_message: str, all_tools: list) -> list:
    msg = (' ' + (user_message or '').lower() + ' ')
    exclude: set = set()
    if not any(k in msg for k in _LINEA_KW):
        exclude |= _LINEA_TOOLS
    if not any(k in msg for k in _CHAT_KW):
        exclude |= _CHAT_TOOLS
    if not any(k in msg for k in _NC_KW):
        exclude |= _NC_TOOLS
    if not exclude:
        return all_tools
    return [t for t in all_tools if t.get('function', {}).get('name', '') not in exclude]


@bp.route("/api/health_llm", methods=["GET"])
def health_llm():
    provider = resolve_llm_provider()

    info = {
        "ok": True,
        "llm_provider": provider,
    }

    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY", "") or ""
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash") or "gemini-2.0-flash"
        info["gemini_model"] = model
        info["gemini_api_key_configured"] = bool(api_key.strip())
        info["gemini_api_key_len"] = len(api_key.strip())
    else:
        api_key = os.getenv("GROQ_API_KEY", "") or ""
        model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant") or "llama-3.1-8b-instant"
        info["groq_model"] = model
        info["groq_api_key_configured"] = bool(api_key.strip())
        info["groq_api_key_len"] = len(api_key.strip())

    return jsonify(info)


@bp.route('/api/chat', methods=['POST'])
@bp.route('/api/chat.php', methods=['POST'])
def chat():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'JSON inválido'}), 400

    messages_in = data.get('messages')
    if not isinstance(messages_in, list):
        return jsonify({'error': 'Falta messages (array)'}), 400

    # ── Crear cliente LLM dinámicamente ──
    try:
        llm_client, provider = _get_llm_client()
    except RuntimeError as e:
        _log.error("/api/chat no se pudo crear cliente LLM | %s", str(e)[:500])
        return jsonify({'ok': False, 'error': str(e)}), 503

    label = db_label()

    system = {
        'role': 'system',
        'content': SYSTEM_TEMPLATE.format(db_label=label, today=date.today().isoformat(), current_year=date.today().year),
    }

    user_context = ''
    if isinstance(data.get('user_context'), str):
        user_context = data['user_context'].strip()[:800]
        user_context = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', user_context)
    if user_context:
        system['content'] += (' Preferencias opcionales declaradas por el usuario '
                              '(no invalidan datos de herramientas ni permiten inventar cifras; solo guían tono o foco): '
                              + user_context)

    # Resultado previo en caché (encadenamiento secuencial sin BD)
    prev_result_parsed = None
    raw_prev = data.get('prev_result')
    if isinstance(raw_prev, str) and raw_prev.strip():
        try:
            prev_result_parsed = json.loads(raw_prev)
        except Exception:
            prev_result_parsed = None
    if isinstance(prev_result_parsed, dict):
        for key in ('filas', 'filas_ranking', 'filas_pareto', 'filas_diario'):
            rows = prev_result_parsed.get(key)
            if isinstance(rows, list) and rows:
                campos = list(rows[0].keys())[:12]
                system['content'] += (
                    f'\n\nRESULTADO PREVIO EN CACHÉ ({len(rows)} filas, campos: {", ".join(campos)}): '
                    'disponible para subgrupos sin ir a la BD. '
                    'Si el usuario pide filtrar/ordenar/extraer un subgrupo de la última consulta, '
                    'llama filtrar_previo ANTES de consultar la BD.'
                )
                break

    sanitized = []
    for m in messages_in:
        if not isinstance(m, dict):
            continue
        role = m.get('role', '')
        if role not in ('user', 'assistant'):
            continue
        content = m.get('content', '')
        if not isinstance(content, str):
            continue
        if role == 'assistant' and content:
            sql_markers = ['\n\nSELECT ', '\nSELECT ', '\n\nSentencia SQL', '\nSentencia SQL', '\n\n---\n']
            cut_at = -1
            for marker in sql_markers:
                pos = content.find(marker)
                if pos != -1 and (cut_at < 0 or pos < cut_at):
                    cut_at = pos
            if cut_at > 20:
                content = content[:cut_at].rstrip()
            # Conservar solo la primera oración del asistente en el historial para evitar
            # que fechas y valores concretos de respuestas anteriores contaminen la siguiente consulta.
            for sep in ('\n\n', '\n', '. '):
                idx = content.find(sep)
                if 0 < idx <= 220:
                    content = content[:idx].rstrip()
                    break
            if len(content) > 220:
                content = content[:220].rstrip() + '…'
        if len(content) > 4000:
            content = content[:4000]
        if not content:
            continue
        sanitized.append({'role': role, 'content': content})

    sanitized = [
        m for m in sanitized
        if m['role'] != 'assistant' or not re.search(r'^\s*\d+\.\s*(?:Cliente|Empresa|Clientes?)\s+\d+', m['content'], re.MULTILINE | re.IGNORECASE)
    ]

    if len(sanitized) > 4:
        sanitized = sanitized[-4:]

    if not sanitized:
        return jsonify({'error': 'No hay mensajes válidos'}), 400

    messages = [system] + sanitized

    try:
        conn = get_connection()
        executor = ToolExecutor(conn, prev_result=prev_result_parsed)
        _all_tools = ventas_tool_definitions() + chat_history_tool_definitions()
        _last_user = next((m['content'] for m in reversed(messages) if m.get('role') == 'user'), '')
        tools = _filter_tools(_last_user, _all_tools)

        result = llm_client.chat_with_tools(
            messages, tools,
            lambda name, args: executor.execute(name, args),
            try_fast_format=try_fast_format,
        )

        reply = enrich_reply(str(result.get('reply') or ''), result.get('messages') or [])

        sql_traces = executor.pull_sql_traces()
        suffix = ''
        if sql_traces:
            suffix += '\n\n' + '\n\n'.join(sql_traces)
            suffix += '\n\n---\nSentencia SQL ejecutada (texto plano):\n' + '\n\n'.join(sql_traces)

        if suffix:
            reply = (reply + suffix).strip()

        # Extraer el último resultado de herramienta para encadenamiento secuencial
        last_result = None
        for msg in reversed(result.get('messages') or []):
            if msg.get('role') == 'tool':
                try:
                    parsed = json.loads(msg.get('content', ''))
                    if not isinstance(parsed, dict):
                        break
                    parsed.pop('_sql_traces', None)
                    for key in ('filas', 'filas_ranking', 'filas_pareto', 'filas_diario'):
                        rows = parsed.get(key)
                        if isinstance(rows, list) and 0 < len(rows) <= 500:
                            last_result = json.dumps(parsed, ensure_ascii=False, default=str)
                            break
                except Exception:
                    pass
                break

        return jsonify({'reply': _unify_pareto_links(reply), 'ok': True, 'last_result': last_result})

    except RuntimeError as e:
        msg = str(e)
        if _is_rate_limit_error(msg):
            _log.warning(
                "/api/chat LLM transitorio | provider=%s | http_cliente=429 | %s",
                provider,
                msg[:800],
            )
            ra = _parse_retry_after_seconds(msg)
            resp = jsonify({'ok': False, 'error': msg})
            if ra is not None:
                resp.headers['Retry-After'] = str(ra)
            return resp, 429
        _log.error(
            "/api/chat LLM RuntimeError | provider=%s | http_cliente=500 | %s",
            provider,
            msg[:800],
        )
        return jsonify({'ok': False, 'error': msg}), 500

    except Exception as e:
        msg = str(e)
        if _is_rate_limit_error(msg):
            _log.warning(
                "/api/chat LLM transitorio | provider=%s | http_cliente=429 | %s",
                provider,
                msg[:800],
            )
            ra = _parse_retry_after_seconds(msg)
            resp = jsonify({'ok': False, 'error': msg})
            if ra is not None:
                resp.headers['Retry-After'] = str(ra)
            return resp, 429
        _log.exception(
            "/api/chat error inesperado | provider=%s | http_cliente=500",
            provider,
        )
        return jsonify({'ok': False, 'error': msg}), 500


def _extract_last_result(working: list) -> str | None:
    """Extrae el último resultado de herramienta cacheable de la lista de mensajes."""
    for msg in reversed(working or []):
        if msg.get('role') != 'tool':
            continue
        try:
            parsed = json.loads(msg.get('content', ''))
            if not isinstance(parsed, dict):
                break
            parsed.pop('_sql_traces', None)
            for key in ('filas', 'filas_ranking', 'filas_pareto', 'filas_diario'):
                rows = parsed.get(key)
                if isinstance(rows, list) and 0 < len(rows) <= 500:
                    return json.dumps(parsed, ensure_ascii=False, default=str)
        except Exception:
            pass
        break
    return None


def _build_messages(data: dict) -> tuple:
    """
    Parsea y sanitiza el request. Retorna (messages, prev_result_parsed, system_content, error_response).
    error_response es distinto de None si hay un error que debe retornarse al cliente.
    """
    messages_in = data.get('messages')
    if not isinstance(messages_in, list):
        return None, None, None, (jsonify({'error': 'Falta messages (array)'}), 400)

    try:
        llm_client, _ = _get_llm_client()
    except RuntimeError as e:
        return None, None, None, (jsonify({'ok': False, 'error': str(e)}), 503)

    label = db_label()
    system = {'role': 'system', 'content': SYSTEM_TEMPLATE.format(db_label=label, today=date.today().isoformat(), current_year=date.today().year)}

    user_context = ''
    if isinstance(data.get('user_context'), str):
        user_context = data['user_context'].strip()[:800]
        user_context = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', user_context)
    if user_context:
        system['content'] += (' Preferencias opcionales declaradas por el usuario '
                              '(no invalidan datos de herramientas ni permiten inventar cifras; solo guían tono o foco): '
                              + user_context)

    prev_result_parsed = None
    raw_prev = data.get('prev_result')
    if isinstance(raw_prev, str) and raw_prev.strip():
        try:
            prev_result_parsed = json.loads(raw_prev)
        except Exception:
            prev_result_parsed = None
    if isinstance(prev_result_parsed, dict):
        for key in ('filas', 'filas_ranking', 'filas_pareto', 'filas_diario'):
            rows = prev_result_parsed.get(key)
            if isinstance(rows, list) and rows:
                campos = list(rows[0].keys())[:12]
                system['content'] += (
                    f'\n\nRESULTADO PREVIO EN CACHÉ ({len(rows)} filas, campos: {", ".join(campos)}): '
                    'disponible para subgrupos sin ir a la BD. '
                    'Si el usuario pide filtrar/ordenar/extraer un subgrupo de la última consulta, '
                    'llama filtrar_previo ANTES de consultar la BD.'
                )
                break

    sanitized = []
    for m in messages_in:
        if not isinstance(m, dict):
            continue
        role = m.get('role', '')
        if role not in ('user', 'assistant'):
            continue
        content = m.get('content', '')
        if not isinstance(content, str):
            continue
        if role == 'assistant' and content:
            sql_markers = ['\n\nSELECT ', '\nSELECT ', '\n\nSentencia SQL', '\nSentencia SQL', '\n\n---\n']
            cut_at = -1
            for marker in sql_markers:
                pos = content.find(marker)
                if pos != -1 and (cut_at < 0 or pos < cut_at):
                    cut_at = pos
            if cut_at > 20:
                content = content[:cut_at].rstrip()
            for sep in ('\n\n', '\n', '. '):
                idx = content.find(sep)
                if 0 < idx <= 220:
                    content = content[:idx].rstrip()
                    break
            if len(content) > 220:
                content = content[:220].rstrip() + '…'
        if len(content) > 4000:
            content = content[:4000]
        if not content:
            continue
        sanitized.append({'role': role, 'content': content})

    sanitized = [
        m for m in sanitized
        if m['role'] != 'assistant' or not re.search(
            r'^\s*\d+\.\s*(?:Cliente|Empresa|Clientes?)\s+\d+', m['content'], re.MULTILINE | re.IGNORECASE)
    ]
    if len(sanitized) > 4:
        sanitized = sanitized[-4:]
    if not sanitized:
        return None, None, None, (jsonify({'error': 'No hay mensajes válidos'}), 400)

    return [system] + sanitized, prev_result_parsed, llm_client, None


@bp.route('/api/chat/stream', methods=['POST'])
@bp.route('/api/chat/stream.php', methods=['POST'])
def chat_stream():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'JSON inválido'}), 400

    messages, prev_result_parsed, llm_client, err = _build_messages(data)
    if err:
        return err

    q = queue.Queue()

    def worker():
        try:
            conn = get_connection()
            executor = ToolExecutor(conn, prev_result=prev_result_parsed)
            _all_tools = ventas_tool_definitions() + chat_history_tool_definitions()
            _last_user = next((m['content'] for m in reversed(messages) if m.get('role') == 'user'), '')
            tools = _filter_tools(_last_user, _all_tools)

            def on_event(event):
                q.put(event)

            reply, working = llm_client.chat_with_tools_stream(
                messages, tools,
                lambda name, args: executor.execute(name, args),
                on_event,
                try_fast_format=try_fast_format,
            )

            reply = enrich_reply(str(reply or ''), working)
            reply = _unify_pareto_links(reply)

            sql_traces = executor.pull_sql_traces()
            sql_suffix = ''
            if sql_traces:
                sql_suffix = ('\n\n' + '\n\n'.join(sql_traces)
                              + '\n\n---\nSentencia SQL ejecutada (texto plano):\n'
                              + '\n\n'.join(sql_traces))

            q.put({
                'type': 'done',
                'reply': reply + sql_suffix if sql_suffix else reply,
                'last_result': _extract_last_result(working),
            })
        except Exception as e:
            _log.exception("/api/chat/stream worker error")
            q.put({'type': 'error', 'text': str(e)})
        finally:
            q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def generate():
        while True:
            try:
                event = q.get(timeout=20)
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue
            if event is None:
                break
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'},
    )