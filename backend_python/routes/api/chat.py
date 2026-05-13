import os
import re
from flask import Blueprint, request, jsonify
from services.db import get_connection, db_label
from services.groq_client import GroqClient
from services.gemini_client import GeminiClient
from services.llm_provider import resolve_llm_provider
from services.tool_executor import ToolExecutor
from services.tools_definitions import ventas_tool_definitions
from services.chat_reply_enricher import enrich_reply

bp = Blueprint('api_chat', __name__)

SYSTEM_TEMPLATE = """Asistente ventasgeneral2 (MySQL {db_label}). Solo tabla ventasgeneral2; no uses sale. Fechas YYYY-MM-DD; "marzo 2026" → 2026-03-01..2026-03-31.

COMPORTAMIENTO PROACTIVO (prioridad alta): antes de llamar una herramienta, verificá que el hilo tenga todos los datos que esa función exige. Si falta algo que solo el usuario puede dar, NO llames la herramienta en ese turno: respondé solo con preguntas breves y concretas en español pidiendo lo que falta (fechas desde/hasta o mes+año, línea comercial, prefijo de zona, etc.). Prohibido rellenar con fechas inventadas, "mes actual" o valores por defecto no dichos por el usuario. Cuando el usuario responda en un mensaje siguiente, combiná esa respuesta con la consulta anterior y entonces llamá la herramienta con parámetros completos.

FECHAS OBLIGATORIAS: si el usuario no da rango claro (dos fechas YYYY-MM-DD o mes+año explícito), pregúntale primero por fecha_desde y fecha_hasta (o por el mes y año) antes de llamar herramientas que las requieran; no asumas un mes por defecto salvo que el usuario lo confirme explícitamente.

ZONA OBLIGATORIA: ventasgeneral_top_clientes_zona_precio requiere un prefijo_descri_zona_precio REAL (AQP, TACNA, MOQUEGUA, LAJOYA, etc.). Si el usuario dice "por zona", "por provincia" o "por región" sin especificar cuál, NO inventes el prefijo — usá ventasgeneral_top_clientes_globales (ranking global) y avisa que muestra el top sin filtrar por zona. Para ver el top dentro de una zona específica pide que indique el prefijo.

Ciudad/mercado: sin campo ciudad; usa prefijo_descri_zona_precio (AQP, MOQUEGUA, TACNA, LAJOYA, etc.) sobre DescripcionZonaPrecio. TDoc NC = 07.

NUEVOS FILTROS DISPONIBLES en ventasgeneral_buscar y ventasgeneral_resumen: provincia (filtra por Provincia, ej. "AREQUIPA", "TACNA") y tipo_documento (filtra por TipoDocumento, ej. "Boleta de Venta", "Factura"). Úsalos cuando el usuario pida filtrar o consultar por provincia o tipo de documento.

INTEGRIDAD ESTRICTA: PROHIBIDO inventar, estimar o completar datos.
Si llamaste una herramienta, los nombres y cifras que escribas en el texto DEBEN coincidir exactamente con los valores del campo "filas", "filas_ranking" o "filas_pareto" del JSON devuelto — sin redondear, sin sustituir por "Cliente 1/2/3", "Cliente A/B", "Empresa X" ni por ningún valor ficticio.
Si NO llamaste ninguna herramienta porque faltan parámetros obligatorios (fechas, línea, zona, etc.), respondé solo con preguntas para obtenerlos; JAMÁS listas de clientes ni cifras.
Si NO llamaste ninguna herramienta y no es por datos faltantes obvios, JAMÁS generes listas numeradas de clientes, productos ni cifras. Responde únicamente: "No tengo datos suficientes para responder esa consulta; por favor repite la pregunta."
Si el JSON devuelve un "error" por parámetro faltante o fecha inválida, preguntá al usuario por el dato correcto; no uses el mensaje de período vacío.
Si el JSON devuelve consulta válida pero filas vacías (sin "error" de parámetros), escribe únicamente: "No tengo datos suficientes para responder esa consulta en el período indicado."
Si la pregunta no tiene ninguna herramienta disponible que la responda (tema ajeno a ventas, preguntas generales, etc.), responde únicamente: "No tengo información para responder esa pregunta; solo manejo datos de ventas."
Preguntas sobre qué valores existen en la BD ("¿qué provincias hay?", "¿qué líneas hay?", "¿qué corporativos están registrados?", "¿qué zonas de precio existen?") SÍ son respondibles usando ventasgeneral_catalogo.
Nunca uses ejemplos ficticios ni rellenes con valores hipotéticos.

Para preguntas de "compraron más", "clientes compradores", "ventas", "facturado", "valor vendido" o similar, usa ventasgeneral_top_clientes_globales o ventasgeneral_top_productos/ventasgeneral_resumen según convenga.
Solo usa ventasgeneral_top_clientes_nota_credito si el usuario pide explícitamente notas de crédito, NC, TDoc=07, devoluciones o anulaciones.
Si hay filas de ranking/top, escribe primero la lista numerada (1. nombre: N líneas o notas, importe S/ X) y al final UNA línea con reporte_url; no respondas solo con el gráfico ni repitas el mismo párrafo.

COMPARATIVO ESTRICTO: cuando el usuario pide comparar dos períodos (dos meses, A vs B, enero vs febrero, etc.) DEBES llamar UNA SOLA VEZ a ventasgeneral_comparativo_periodos con periodo_a_desde, periodo_a_hasta, periodo_b_desde, periodo_b_hasta. NUNCA llames ventasgeneral_barras_ventas_dimension dos veces ni calcules tú mismo la diferencia — el resultado sería inventado.

LÍNEA COMERCIAL: cuando el usuario pregunte por una línea usa las herramientas de línea. El campo LineaComercial guarda texto, no códigos numéricos. Valores reales en la base de datos:
"Pollo Vivo" | "Pollo Beneficiado" | "Pollo trozado Seco" | "Embutidos" | "Menudencia" | "Semielaborados" | "Pavos" | "Precocidos" | "Huevos SF" | "Pollo Congelado San Fer." | "Cerdos" | "Promociones embutidos" | "Venta de insumos" | "Envases"
Mapeo de códigos que puede mencionar el usuario: línea 601 = "Pollo Vivo". Si el usuario dice "pollo vivo" o "línea 601" → linea_comercial="Pollo Vivo".
Productos dentro de Pollo Vivo: cod_item 100 = carne, cod_item 103 = brasa. Usa cod_item cuando el usuario filtre por tipo de producto.
Mercados (DescripcionZonaPrecio) disponibles para Pollo Vivo: AQPMERCADO, TACNA, ILO, MOQUEGUA, MOLLENDO, CAMANA, LAJOYA, PEDREGAL. Pasa el valor como parámetro "mercado" cuando el usuario filtre por mercado/zona.
- resumen provincia/cliente → ventasgeneral_linea_resumen_provincia (linea_comercial obligatorio, pasar el texto exacto). No pases top_n salvo que el usuario pida explícitamente un top N; sin top_n se devuelven todas las filas provincia+cliente.
- ventas por día provincia/cliente → ventasgeneral_linea_diario_provincia
- precio por día provincia/cliente (resumen con cantidad/peso/valor, orden por fecha y por peso dentro de cada día) → ventasgeneral_linea_precio_diario
- precio resumen por provincia (UNA fila por provincia, SIN clientes ni días, con precio/kg ponderado del período) → ventasgeneral_linea_precio_resumen_provincia. Úsala cuando el usuario pida "precio por provincia", "precio resumen por provincia" o "precio promedio por provincia" sin querer ver clientes ni diario. Requiere fecha_desde/fecha_hasta y linea_comercial; si falta período o línea, pregúntalos antes de llamar.
- mix carne vs brasa / comparar productos → ventasgeneral_linea_mix_productos (agrupa por CodigoItem, incluye pct_peso)
La comparación es case-insensitive. Si el usuario no especifica la línea, pregúntala antes de llamar la herramienta.

Mapeo herramientas:
- más NC por cliente → ventasgeneral_top_clientes_nota_credito (URL: /modules/reports/ventas-top-clientes-nc?desde=&hasta=&top=)
- pareto NC por zona → ventasgeneral_pareto_nc_zonaprecio (/modules/reports/pareto-nc-zona?…, no por cliente)
- top compra global → ventasgeneral_top_clientes_globales
- top por zona precio → ventasgeneral_top_clientes_zona_precio
- barras dimensión → ventasgeneral_barras_ventas_dimension
- comparativo 2 períodos → ventasgeneral_comparativo_periodos (UNA llamada, no dos barras)
- productos → ventasgeneral_top_productos
- mix TDoc → ventasgeneral_mix_tdoc
- ruta/corp → ventasgeneral_barras_ruta_comercial / ventasgeneral_barras_corporativo
- serie mensual → ventasgeneral_serie_mensual_valor
- proyección ventas → ventasgeneral_proyeccion_ventas
- ventas línea resumen → ventasgeneral_linea_resumen_provincia
- ventas línea por día → ventasgeneral_linea_diario_provincia
- precio línea por día → ventasgeneral_linea_precio_diario
- precio línea resumen por provincia → ventasgeneral_linea_precio_resumen_provincia
- mix productos / carne vs brasa → ventasgeneral_linea_mix_productos
- líneas sueltas → ventasgeneral_buscar
- totales → ventasgeneral_resumen
- catálogo/maestro de valores → ventasgeneral_catalogo (campo: provincia, linea_comercial, corporativo, zona_precio, zona_comercial, ruta, tipo_documento). Usar para preguntas como "¿qué provincias hay?", "¿qué líneas comerciales existen?", "¿qué corporativos están registrados?", "¿qué zonas de precio hay?", "¿qué tipos de documento hay?". Las fechas son opcionales.

URL RELATIVA OBLIGATORIA: escribe ÚNICAMENTE la ruta que empieza por /modules/ (ej: /modules/ventasgeneral/resumen-tabla?fecha_desde=2026-01-01&fecha_hasta=2026-03-31). JAMÁS uses https://, http://, example.com, localhost ni ningún dominio — el enlace quedaría roto. JAMÁS agregues fragmentos #grafico ni #nada.
Un solo reporte_url por respuesta, en UNA línea sin backticks, sin partir la URL. Resumen/buscar: /modules/ventasgeneral/resumen-tabla o …/buscar-tabla. Otros: /modules/reports/<slug>?desde=YYYY-MM-DD&hasta=YYYY-MM-DD&…

Moneda: importes en soles peruanos con prefijo S/ (ej. S/ 1,234,567.89). No uses $ ni USD.
Lenguaje: evita jerga de BD (no "Valor", "SUM(Valor)", "Cantidad" como etiqueta técnica). Usá "importe", "monto en soles", "unidades", "cantidad vendida", "peso total".
Español, breve."""


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
        'resource exhausted',
        'quota exceeded',
    ))


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
        return jsonify({'ok': False, 'error': str(e)}), 503

    label = db_label()

    system = {
        'role': 'system',
        'content': SYSTEM_TEMPLATE.format(db_label=label),
    }

    user_context = ''
    if isinstance(data.get('user_context'), str):
        user_context = data['user_context'].strip()[:800]
        user_context = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', user_context)
    if user_context:
        system['content'] += (' Preferencias opcionales declaradas por el usuario '
                              '(no invalidan datos de herramientas ni permiten inventar cifras; solo guían tono o foco): '
                              + user_context)

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
        if len(content) > 4000:
            content = content[:4000]
        if not content:
            continue
        sanitized.append({'role': role, 'content': content})

    sanitized = [
        m for m in sanitized
        if m['role'] != 'assistant' or not re.search(r'^\s*\d+\.\s*(?:Cliente|Empresa|Clientes?)\s+\d+', m['content'], re.MULTILINE | re.IGNORECASE)
    ]

    if len(sanitized) > 6:
        sanitized = sanitized[-6:]

    if not sanitized:
        return jsonify({'error': 'No hay mensajes válidos'}), 400

    messages = [system] + sanitized

    try:
        conn = get_connection()
        executor = ToolExecutor(conn)
        tools = ventas_tool_definitions()

        result = llm_client.chat_with_tools(
            messages, tools,
            lambda name, args: executor.execute(name, args)
        )

        reply = enrich_reply(str(result.get('reply') or ''), result.get('messages') or [])

        sql_traces = executor.pull_sql_traces()
        suffix = ''
        if sql_traces:
            suffix += '\n\n' + '\n\n'.join(sql_traces)
            suffix += '\n\n---\nSentencia SQL ejecutada (texto plano):\n' + '\n\n'.join(sql_traces)

        if suffix:
            reply = (reply + suffix).strip()

        return jsonify({'reply': _unify_pareto_links(reply), 'ok': True})

    except RuntimeError as e:
        msg = str(e)
        if _is_rate_limit_error(msg):
            ra = _parse_retry_after_seconds(msg)
            resp = jsonify({'ok': False, 'error': msg})
            if ra is not None:
                resp.headers['Retry-After'] = str(ra)
            return resp, 429
        return jsonify({'ok': False, 'error': msg}), 500

    except Exception as e:
        msg = str(e)
        if _is_rate_limit_error(msg):
            ra = _parse_retry_after_seconds(msg)
            resp = jsonify({'ok': False, 'error': msg})
            if ra is not None:
                resp.headers['Retry-After'] = str(ra)
            return resp, 429
        return jsonify({'ok': False, 'error': msg}), 500