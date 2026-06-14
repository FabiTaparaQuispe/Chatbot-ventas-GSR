import asyncio
import json
import logging
import os
import re
from datetime import date, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from services.db import get_connection, db_label
from services.groq_client import GroqClient
from services.gemini_client import GeminiClient
from services.llm_provider import resolve_llm_provider
from services.tool_executor import ToolExecutor
from services.tools_definitions import ventas_tool_definitions, chat_history_tool_definitions
from services.chat_reply_enricher import enrich_reply
from services.fast_format import try_fast_format
from services.sql_trace_display import format_sql_traces_for_display

from routes.api.chat import (
    SYSTEM_TEMPLATE,
    _unify_pareto_links,
    _parse_retry_after_seconds,
    _is_rate_limit_error,
    _filter_tools,
    _extract_last_result,
)

router = APIRouter()
_log = logging.getLogger(__name__)

_llm_client_singleton: tuple | None = None


def _get_llm_client():
    global _llm_client_singleton
    if _llm_client_singleton is not None:
        return _llm_client_singleton
    provider = resolve_llm_provider()
    if provider == 'gemini':
        api_key = os.getenv('GEMINI_API_KEY', '')
        if not api_key:
            raise RuntimeError('Configure GEMINI_API_KEY en .env')
        model = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
        _llm_client_singleton = (GeminiClient(api_key, model), provider)
    else:
        api_key = os.getenv('GROQ_API_KEY', '')
        if not api_key:
            raise RuntimeError('Configure GROQ_API_KEY en .env')
        model = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')
        _llm_client_singleton = (GroqClient(api_key, model), provider)
    return _llm_client_singleton


def _build_messages(data: dict) -> tuple:
    messages_in = data.get('messages')
    if not isinstance(messages_in, list):
        return None, None, None, JSONResponse({'error': 'Falta messages (array)'}, status_code=400)

    try:
        llm_client, _ = _get_llm_client()
    except RuntimeError as e:
        return None, None, None, JSONResponse({'ok': False, 'error': str(e)}, status_code=503)

    label = db_label()
    system = {
        'role': 'system',
        'content': SYSTEM_TEMPLATE.format(
            db_label=label, today=date.today().isoformat(),
            current_year=date.today().year,
            yesterday=(date.today() - timedelta(days=1)).isoformat(),
        ),
    }

    user_context = ''
    if isinstance(data.get('user_context'), str):
        user_context = data['user_context'].strip()[:800]
        user_context = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', user_context)
    if user_context:
        system['content'] += (' Preferencias opcionales declaradas por el usuario '
                              '(no invalidan datos de herramientas ni permiten inventar cifras; '
                              'solo guían tono o foco): ' + user_context)

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
            r'^\s*\d+\.\s*(?:Cliente|Empresa|Clientes?)\s+\d+',
            m['content'], re.MULTILINE | re.IGNORECASE)
    ]
    if len(sanitized) > 4:
        sanitized = sanitized[-4:]
    if not sanitized:
        return None, None, None, JSONResponse({'error': 'No hay mensajes válidos'}, status_code=400)

    return [system] + sanitized, prev_result_parsed, llm_client, None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get('/api/health_llm')
async def health_llm():
    provider = resolve_llm_provider()
    info: dict = {'ok': True, 'llm_provider': provider}
    if provider == 'gemini':
        api_key = os.getenv('GEMINI_API_KEY', '') or ''
        model = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash') or 'gemini-2.0-flash'
        info.update({'gemini_model': model, 'gemini_api_key_configured': bool(api_key.strip()),
                     'gemini_api_key_len': len(api_key.strip())})
    else:
        api_key = os.getenv('GROQ_API_KEY', '') or ''
        model = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant') or 'llama-3.1-8b-instant'
        info.update({'groq_model': model, 'groq_api_key_configured': bool(api_key.strip()),
                     'groq_api_key_len': len(api_key.strip())})
    return info


@router.post('/api/chat')
@router.post('/api/chat.php')
async def chat(request: Request):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({'error': 'JSON inválido'}, status_code=400)

    messages, prev_result_parsed, llm_client, err = _build_messages(data)
    if err:
        return err

    provider = resolve_llm_provider()
    try:
        conn = await asyncio.to_thread(get_connection)
        _role = str(request.session.get('role') or 'lector').lower().strip()
        executor = ToolExecutor(conn, prev_result=prev_result_parsed, role=_role)
        _all_tools = ventas_tool_definitions() + chat_history_tool_definitions()
        _last_user = next((m['content'] for m in reversed(messages) if m.get('role') == 'user'), '')
        tools = _filter_tools(_last_user, _all_tools)

        result = await llm_client.chat_with_tools(
            messages, tools,
            executor.execute_async,
            try_fast_format=try_fast_format,
        )

        last_tool_json = executor.pull_last_tool_json()
        reply = enrich_reply(str(result.get('reply') or ''), result.get('messages') or [],
                             last_tool_json=last_tool_json)
        sql_text = format_sql_traces_for_display(executor.pull_sql_traces())
        if sql_text:
            reply = (reply + '\n\n' + sql_text).strip()

        last_result = None
        for msg in reversed(result.get('messages') or []):
            if msg.get('role') == 'tool':
                try:
                    parsed = json.loads(msg.get('content', ''))
                    if isinstance(parsed, dict):
                        parsed.pop('_sql_traces', None)
                        for key in ('filas', 'filas_ranking', 'filas_pareto', 'filas_diario'):
                            rows = parsed.get(key)
                            if isinstance(rows, list) and 0 < len(rows) <= 500:
                                last_result = json.dumps(parsed, ensure_ascii=False, default=str)
                                break
                except Exception:
                    pass
                break

        if not reply:
            reply = 'No pude generar una respuesta. Por favor intentá de nuevo o reformulá la consulta.'
            _log.warning("/api/chat reply vacío → usando mensaje de fallback")

        return {'reply': _unify_pareto_links(reply), 'ok': True, 'last_result': last_result}

    except RuntimeError as e:
        msg = str(e)
        if _is_rate_limit_error(msg):
            ra = _parse_retry_after_seconds(msg)
            headers = {'Retry-After': str(ra)} if ra else {}
            return JSONResponse({'ok': False, 'error': msg}, status_code=429, headers=headers)
        _log.error("/api/chat LLM RuntimeError | provider=%s | %s", provider, msg[:800])
        return JSONResponse({'ok': False, 'error': msg}, status_code=500)
    except Exception as e:
        msg = str(e)
        if _is_rate_limit_error(msg):
            ra = _parse_retry_after_seconds(msg)
            headers = {'Retry-After': str(ra)} if ra else {}
            return JSONResponse({'ok': False, 'error': msg}, status_code=429, headers=headers)
        _log.exception("/api/chat error inesperado | provider=%s", provider)
        return JSONResponse({'ok': False, 'error': msg}, status_code=500)


@router.post('/api/chat/stream')
@router.post('/api/chat/stream.php')
async def chat_stream(request: Request):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({'error': 'JSON inválido'}, status_code=400)

    messages, prev_result_parsed, llm_client, err = _build_messages(data)
    if err:
        return err

    async def generate():
        q: asyncio.Queue = asyncio.Queue()

        async def on_event(event: dict) -> None:
            await q.put(event)

        async def run_llm() -> None:
            try:
                conn = await asyncio.to_thread(get_connection)
                _role = str(request.session.get('role') or 'lector').lower().strip()
                executor = ToolExecutor(conn, prev_result=prev_result_parsed, role=_role)
                _all_tools = ventas_tool_definitions() + chat_history_tool_definitions()
                _last_user = next(
                    (m['content'] for m in reversed(messages) if m.get('role') == 'user'), ''
                )
                tools = _filter_tools(_last_user, _all_tools)
                _log.info("[chat/stream] tools disponibles=%d | user='%s'",
                          len(tools), _last_user[:80])

                reply, working = await llm_client.chat_with_tools_stream(
                    messages, tools,
                    executor.execute_async,
                    on_event,
                    try_fast_format=try_fast_format,
                )

                _log.info("[chat/stream] LLM reply_raw_len=%d | vacío=%s", len(reply), not reply)

                last_tool_json = executor.pull_last_tool_json()
                _log.info("[chat/stream] last_tool_json=%s",
                          "presente" if last_tool_json else "None")

                reply = enrich_reply(str(reply or ''), working, last_tool_json=last_tool_json)
                _log.info("[chat/stream] enrich_reply → reply_len=%d | vacío=%s",
                          len(reply), not reply)

                reply = _unify_pareto_links(reply)
                sql_text = format_sql_traces_for_display(executor.pull_sql_traces())
                if sql_text:
                    reply = reply + '\n\n' + sql_text

                # Seguridad final: si el reply llegó vacío, evitar burbuja en blanco
                if not reply:
                    reply = 'No pude generar una respuesta. Por favor intentá de nuevo o reformulá la consulta.'
                    _log.warning("[chat/stream] reply vacío → usando mensaje de fallback")

                _log.info("[chat/stream] done | reply_final_len=%d", len(reply))
                await q.put({
                    'type': 'done',
                    'reply': reply,
                    'last_result': _extract_last_result(working),
                })
            except Exception as e:
                _log.exception("/api/chat/stream error")
                await q.put({'type': 'error', 'text': str(e)})
            finally:
                await q.put(None)  # sentinel

        llm_task = asyncio.create_task(run_llm())

        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=20)
            except asyncio.TimeoutError:
                yield ': keep-alive\n\n'
                continue
            if event is None:
                break
            yield f'data: {json.dumps(event, ensure_ascii=False)}\n\n'

        await llm_task

    return StreamingResponse(
        generate(),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'},
    )
