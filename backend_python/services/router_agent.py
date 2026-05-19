"""Router agent: decide entre tool_call | sql_generation | ask_user | propose_new_tool.

Carga el prompt en `backend_python/prompts/router_system_prompt.md`, lo rellena con
el schema fijo y las tools dinámicas (`ventas_tool_definitions`), llama al LLM
configurado vía `resolve_llm_provider()` (Groq si hay ambas claves y no se fija
`LLM_PROVIDER`; Gemini con `LLM_PROVIDER=gemini` o solo `GEMINI_API_KEY`), pidiendo JSON
estricto, y devuelve una decisión validada.

Uso:
    from services.router_agent import route_user_query, RouterError
    try:
        decision = route_user_query("top 10 clientes en LAJOYA marzo 2024")
    except RouterError as e:
        ...
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from openai import OpenAI

from services.llm_provider import resolve_llm_provider
from services.tools_definitions import chat_history_tool_definitions, ventas_tool_definitions


def _all_tool_definitions() -> list:
    return ventas_tool_definitions() + chat_history_tool_definitions()

ROUTER_PROMPT_PATH = Path(__file__).resolve().parent.parent / 'prompts' / 'router_system_prompt.md'

VALID_ROUTES = ('tool_call', 'sql_generation', 'ask_user', 'propose_new_tool')

def _build_schema_text() -> str:
    today = date.today()
    current_year = today.year
    current_date = today.isoformat()
    return f"""Tabla: ventasgeneral2 (ETL desnormalizada de ventas, lista para consultar sin JOINs)

FECHA ACTUAL: {current_date}. AÑO EN CURSO: {current_year}.

COLUMNAS PRINCIPALES:
- id (INT, PRIMARY KEY)
- FechaContable (DATE, YYYY-MM-DD) -> FILTRO PRINCIPAL OBLIGATORIO
- CodigoCliente (VARCHAR), NombreCliente (VARCHAR)
- CodigoCoorporativo (VARCHAR), NombreCoorporativo (VARCHAR)
- CodigoDocumento (VARCHAR): '01'=Factura, '03'=Boleta, '07'=Nota Credito
- TipoDocumento (VARCHAR): 'Factura', 'Boleta de Venta', 'Nota de Credito'
- SerieDocumento, NumeroDocumento, NumeroFactura (VARCHAR)
- CodigoItem (VARCHAR), GlosaDetalle (VARCHAR) -> descripcion producto
- Cantidad (DECIMAL) -> unidades >= 0
- Peso (DECIMAL) -> kilogramos >= 0
- Valor (DECIMAL) -> soles; >0 venta neta, <0 NC/devolucion
- ZonaComercial (VARCHAR), DescripcionZonaPrecio (VARCHAR) -> ej. 'AQPMERCADO', 'TACNA'
- RutaComercial (VARCHAR)
- Provincia (VARCHAR) -> ej. 'AREQUIPA', 'TACNA', 'MOQUEGUA'
- LineaComercial (VARCHAR) -> valores reales: 'Pollo Vivo', 'Pollo Beneficiado',
  'Pollo trozado Seco', 'Embutidos', 'Menudencia', 'Semielaborados', 'Pavos',
  'Precocidos', 'Huevos SF', 'Pollo Congelado San Fer.', 'Cerdos',
  'Promociones embutidos', 'Venta de insumos', 'Envases'.

PRODUCTOS DENTRO DE LINEAS:
- Pollo Vivo: CodigoItem 100 = carne, 103 = brasa.
- Mercados Pollo Vivo (DescripcionZonaPrecio): AQPMERCADO, TACNA, ILO, MOQUEGUA,
  MOLLENDO, CAMANA, LAJOYA, PEDREGAL.

PAGINACION (route=tool_call o sql_generation):
- pagina: entero >= 1 (pagina 1 = primeros registros). Default 1.
- por_pagina: entero entre 10 y 100. Default 50.
- Formula backend: OFFSET = (pagina - 1) * por_pagina, LIMIT = por_pagina.
- En route=sql_generation NUNCA escribas LIMIT/OFFSET; el backend los inyecta.

REGLAS DE NEGOCIO:
1. Fechas: SIEMPRE BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'. Considera bisiestos.
2. AÑO POR DEFECTO: Si el usuario NO especifica el año, usa {current_year} (año en curso).
   Ejemplos: "abril" → '{{current_year}}-04-01' / '{{current_year}}-04-30';
             "enero" → '{current_year}-01-01' / '{current_year}-01-31'.
   NUNCA pidas el año si el usuario solo menciona un mes o un día.
3. DIA UNICO: Si el usuario da solo un día (ej. "el 01 de enero 2026", "hoy"),
   usa ESE DIA como fecha_desde Y fecha_hasta (mismo valor en ambos campos).
4. Valor: SUM(Valor) puede ser negativo si hay NC (CodigoDocumento='07').
5. DescripcionZonaPrecio: usa LIKE 'PREFIJO%' (ej. 'LAJOYA%').
6. Provincia: usar igualdad (Provincia = 'VALOR') con valor exacto cuando se conozca.
7. LineaComercial: comparacion case-insensitive contra los valores reales listados.
8. Tabla desnormalizada: NO uses JOINs.
"""


class RouterError(RuntimeError):
    """Error de enrutamiento (LLM no devolvio JSON valido o decision invalida)."""


def load_router_prompt(tools: list[dict[str, Any]] | None = None) -> str:
    """Lee el template y rellena {SCHEMA} + {TOOLS_DEFINITIONS}.

    Las tools se serializan como JSON conservando solo `function` (name, description,
    parameters), que es lo que el modelo necesita para enrutar.
    """
    if tools is None:
        tools = _all_tool_definitions()
    template = ROUTER_PROMPT_PATH.read_text(encoding='utf-8')
    fn_blocks = [t.get('function') for t in tools if isinstance(t, dict) and 'function' in t]
    tools_json = json.dumps(fn_blocks, ensure_ascii=False, indent=2)
    return template.replace('{SCHEMA}', _build_schema_text()).replace('{TOOLS_DEFINITIONS}', tools_json)


def _post_gemini_json(api_key: str, model: str, system: str, user_msg: str,
                     history: list[dict[str, str]]) -> str:
    """Llama a Gemini pidiendo JSON estricto. Devuelve el texto JSON (sin parsear)."""
    contents: list[dict[str, Any]] = []
    for h in history:
        role = 'user' if h.get('role') == 'user' else 'model'
        contents.append({'role': role, 'parts': [{'text': str(h.get('content') or '')}]})
    contents.append({'role': 'user', 'parts': [{'text': user_msg}]})
    body = {
        'systemInstruction': {'parts': [{'text': system}]},
        'contents': contents,
        'generationConfig': {
            'temperature': 0.1,
            'responseMimeType': 'application/json',
        },
    }
    url = (f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
           f'?key={api_key}')
    req = Request(url, data=json.dumps(body).encode('utf-8'),
                  headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except HTTPError as e:
        raise RouterError(f'Gemini HTTP {e.code}: {e.read().decode("utf-8", errors="ignore")[:300]}')
    except URLError as e:
        raise RouterError(f'Gemini URL error: {e}')
    try:
        return payload['candidates'][0]['content']['parts'][0]['text']
    except (KeyError, IndexError, TypeError):
        raise RouterError(f'Respuesta Gemini sin texto: {json.dumps(payload)[:300]}')


def _complete_groq_json(api_key: str, model: str, system: str, user_msg: str,
                       history: list[dict[str, str]]) -> str:
    """Llama a Groq pidiendo JSON estricto. Devuelve el texto JSON (sin parsear)."""
    client = OpenAI(api_key=api_key, base_url='https://api.groq.com/openai/v1')
    messages: list[dict[str, str]] = [{'role': 'system', 'content': system}]
    for h in history:
        role = h.get('role')
        if role in ('user', 'assistant'):
            messages.append({'role': role, 'content': str(h.get('content') or '')})
    messages.append({'role': 'user', 'content': user_msg})
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1,
        response_format={'type': 'json_object'},
    )
    if not resp.choices:
        raise RouterError('Groq devolvió respuesta vacía.')
    return resp.choices[0].message.content or ''


def _validate_decision(decision: Any) -> dict[str, Any]:
    """Valida la estructura del JSON devuelto por el LLM. Lanza RouterError si falla."""
    if not isinstance(decision, dict):
        raise RouterError('Decisión del router no es un objeto JSON.')
    route = decision.get('route')
    if route not in VALID_ROUTES:
        raise RouterError(f'route inválida: {route!r}. Permitidas: {VALID_ROUTES}.')
    reason = decision.get('reason')
    if not isinstance(reason, str) or not reason.strip():
        raise RouterError('Falta "reason" (string no vacío).')

    payload = decision.get('payload')
    proposal = decision.get('new_tool_proposal')

    if route == 'tool_call':
        if not isinstance(payload, dict):
            raise RouterError('tool_call: payload debe ser objeto.')
        tool_name = payload.get('tool_name')
        tool_args = payload.get('tool_args')
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise RouterError('tool_call: tool_name vacío o inválido.')
        if not isinstance(tool_args, dict):
            raise RouterError('tool_call: tool_args debe ser objeto.')
        valid_names = {t['function']['name'] for t in _all_tool_definitions()
                       if isinstance(t, dict) and isinstance(t.get('function'), dict)}
        if tool_name not in valid_names:
            raise RouterError(f'tool_call: tool_name no existe en catálogo ({tool_name!r}).')
    elif route == 'sql_generation':
        if not isinstance(payload, dict):
            raise RouterError('sql_generation: payload debe ser objeto.')
        sql = payload.get('sql')
        if not isinstance(sql, str) or not sql.strip():
            raise RouterError('sql_generation: sql vacío.')
    elif route == 'ask_user':
        if payload is not None:
            decision['payload'] = None
    elif route == 'propose_new_tool':
        if not isinstance(proposal, dict):
            raise RouterError('propose_new_tool: new_tool_proposal debe ser objeto.')
        name = proposal.get('name')
        if not isinstance(name, str) or not name.strip():
            raise RouterError('propose_new_tool: name vacío.')
        params = proposal.get('parameters')
        if not isinstance(params, dict) or params.get('type') != 'object':
            raise RouterError('propose_new_tool: parameters debe ser JSON Schema object.')

    return decision


def route_user_query(user_msg: str,
                    history: list[dict[str, str]] | None = None,
                    *,
                    provider: str | None = None,
                    model: str | None = None,
                    api_key: str | None = None) -> dict[str, Any]:
    """Devuelve la decisión del router como dict ya validado.

    `provider` ∈ {'groq', 'gemini'}. Si None, usa services.llm_provider.resolve_llm_provider().
    `model` y `api_key` se toman de env si no se pasan.
    """
    if not isinstance(user_msg, str) or not user_msg.strip():
        raise RouterError('user_msg vacío.')
    history = history or []

    provider = (provider or resolve_llm_provider()).strip().lower()
    system_prompt = load_router_prompt()

    if provider == 'gemini':
        api_key = api_key or os.getenv('GEMINI_API_KEY', '')
        if not api_key:
            raise RouterError('Configure GEMINI_API_KEY en .env')
        model = model or os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
        raw = _post_gemini_json(api_key, model, system_prompt, user_msg, history)
    else:
        api_key = api_key or os.getenv('GROQ_API_KEY', '')
        if not api_key:
            raise RouterError('Configure GROQ_API_KEY en .env')
        model = model or os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')
        raw = _complete_groq_json(api_key, model, system_prompt, user_msg, history)

    raw = (raw or '').strip()
    if raw.startswith('```'):
        raw = raw.strip('`')
        if raw.lower().startswith('json'):
            raw = raw[4:]
        raw = raw.strip()
    try:
        decision = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RouterError(f'JSON inválido del LLM: {e}. Raw: {raw[:300]!r}')

    return _validate_decision(decision)
