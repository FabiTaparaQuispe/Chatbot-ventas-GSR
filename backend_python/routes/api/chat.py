import os
import re
from flask import Blueprint, request, jsonify
from services.db import get_connection, db_label
from services.groq_client import GroqClient
from services.tool_executor import ToolExecutor
from services.tools_definitions import ventas_tool_definitions
from services.chat_reply_enricher import enrich_reply

bp = Blueprint('api_chat', __name__)

SYSTEM_TEMPLATE = """Asistente ventasgeneral2 (MySQL {db_label}). Solo tabla ventasgeneral2; no uses sale. Fechas YYYY-MM-DD; "marzo 2026" → 2026-03-01..2026-03-31.

FECHAS OBLIGATORIAS: si el usuario no da rango claro (dos fechas YYYY-MM-DD o mes+año explícito), pregúntale primero por fecha_desde y fecha_hasta antes de llamar herramientas que las requieran; no asumas un mes por defecto salvo que el usuario lo confirme.

ZONA OBLIGATORIA: ventasgeneral_top_clientes_zona_precio requiere un prefijo_descri_zona_precio REAL (AQP, TACNA, MOQUEGUA, LAJOYA, etc.). Si el usuario dice "por zona", "por provincia" o "por región" sin especificar cuál, NO inventes el prefijo — usá ventasgeneral_top_clientes_globales (ranking global) y avisa que muestra el top sin filtrar por zona. Para ver el top dentro de una zona específica pide que indique el prefijo.

Ciudad/mercado: sin campo ciudad; usa prefijo_descri_zona_precio (AQP, MOQUEGUA, TACNA, LAJOYA, etc.) sobre DescripcionZonaPrecio. TDoc NC = 07.

NUEVOS FILTROS DISPONIBLES en ventasgeneral_buscar y ventasgeneral_resumen: provincia (filtra por Provincia, ej. "AREQUIPA", "TACNA") y tipo_documento (filtra por TipoDocumento, ej. "Boleta de Venta", "Factura"). Úsalos cuando el usuario pida filtrar o consultar por provincia o tipo de documento.

INTEGRIDAD ESTRICTA: PROHIBIDO inventar, estimar o completar datos.
Si llamaste una herramienta, los nombres y cifras que escribas en el texto DEBEN coincidir exactamente con los valores del campo "filas", "filas_ranking" o "filas_pareto" del JSON devuelto — sin redondear, sin sustituir por "Cliente 1/2/3", "Cliente A/B", "Empresa X" ni por ningún valor ficticio.
Si NO llamaste ninguna herramienta, JAMÁS generes listas numeradas de clientes, productos ni cifras. Responde únicamente: "No tengo datos suficientes para responder esa consulta; por favor repite la pregunta."
Si el JSON devuelve filas vacías o un campo "error", escribe únicamente: "No tengo datos suficientes para responder esa consulta en el período indicado."
Si la pregunta no tiene ninguna herramienta disponible que la responda (tema ajeno a ventas, preguntas generales, etc.), responde únicamente: "No tengo información para responder esa pregunta; solo manejo datos de ventas."
Nunca uses ejemplos ficticios ni rellenes con valores hipotéticos.

Para preguntas de "compraron más", "clientes compradores", "ventas", "facturado", "valor vendido" o similar, usa ventasgeneral_top_clientes_globales o ventasgeneral_top_productos/ventasgeneral_resumen según convenga.
Solo usa ventasgeneral_top_clientes_nota_credito si el usuario pide explícitamente notas de crédito, NC, TDoc=07, devoluciones o anulaciones.
Si hay filas de ranking/top, escribe primero la lista numerada (1. nombre: N líneas o notas, importe S/ X) y al final UNA línea con reporte_url; no respondas solo con el gráfico ni repitas el mismo párrafo.

COMPARATIVO ESTRICTO: cuando el usuario pide comparar dos períodos (dos meses, A vs B, enero vs febrero, etc.) DEBES llamar UNA SOLA VEZ a ventasgeneral_comparativo_periodos con periodo_a_desde, periodo_a_hasta, periodo_b_desde, periodo_b_hasta. NUNCA llames ventasgeneral_barras_ventas_dimension dos veces ni calcules tú mismo la diferencia — el resultado sería inventado.

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
- líneas sueltas → ventasgeneral_buscar
- totales → ventasgeneral_resumen

URL RELATIVA OBLIGATORIA: escribe ÚNICAMENTE la ruta absoluta del sitio empezando por / (ej: /modules/ventasgeneral/resumen-tabla?fecha_desde=2026-01-01&fecha_hasta=2026-03-31). JAMÁS pongas https://, http://, example.com, localhost ni ningún dominio — si lo haces, el enlace quedará roto.
Un reporte_url por respuesta, copiado tal cual en UNA sola línea (no partas fechas YYYY-MM-DD ni la URL; sin backticks). Resumen/buscar: /modules/ventasgeneral/resumen-tabla o …/buscar-tabla. Otros informes: /modules/reports/<slug>?… Opcional #grafico.

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


@bp.route('/api/chat', methods=['POST'])
@bp.route('/api/chat.php', methods=['POST'])
def chat():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'JSON inválido'}), 400

    messages_in = data.get('messages')
    if not isinstance(messages_in, list):
        return jsonify({'error': 'Falta messages (array)'}), 400

    api_key = os.getenv('GROQ_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'Configure GROQ_API_KEY en .env'}), 503

    model = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')
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

    if len(sanitized) > 4:
        sanitized = sanitized[-4:]

    if not sanitized:
        return jsonify({'error': 'No hay mensajes válidos'}), 400

    messages = [system] + sanitized

    try:
        conn = get_connection()
        executor = ToolExecutor(conn)
        groq = GroqClient(api_key, model)
        tools = ventas_tool_definitions()

        result = groq.chat_with_tools(
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
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
