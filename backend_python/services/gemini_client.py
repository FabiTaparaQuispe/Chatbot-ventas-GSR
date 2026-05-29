import asyncio
import json
import logging
from typing import Any, Callable

import google.generativeai as genai
from google.generativeai import protos

try:
    from google.api_core import exceptions as _google_exc
    _HAS_GOOGLE_EXC = True
except ImportError:
    _HAS_GOOGLE_EXC = False

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 10
MAX_TOOL_JSON_BYTES = 14000

_GENERATION_CONFIG = {
    "temperature": 0.2,
}


def _clamp_tool_json(json_str: str) -> str:
    if len(json_str) <= MAX_TOOL_JSON_BYTES:
        return json_str
    try:
        data = json.loads(json_str)
    except Exception:
        return json_str
    if not isinstance(data, dict):
        return json_str
    for key in ("filas", "filas_ranking", "filas_pareto"):
        if key not in data or not isinstance(data[key], list):
            continue
        all_rows = data[key]
        for n in (12, 8, 5, 3):
            data[key] = all_rows[:n]
            data["_nota"] = f"Respuesta truncada: primeras {n} filas en {key} (límite API)."
            out = json.dumps(data, ensure_ascii=False, default=str)
            if len(out) <= MAX_TOOL_JSON_BYTES:
                return out
        data[key] = all_rows
    return json.dumps(
        {"error": "respuesta_herramienta_muy_grande", "mensaje": "La consulta devolvió demasiados datos. Acote fechas o filtros."},
        ensure_ascii=False,
    )


_GEMINI_SCHEMA_ALLOWED = frozenset({
    'type', 'description', 'enum', 'items', 'properties', 'required', 'nullable', 'format',
})


def _sanitize_gemini_schema(schema: Any) -> Any:
    if not isinstance(schema, dict):
        return schema
    if 'anyOf' in schema or 'oneOf' in schema:
        variants = schema.get('anyOf') or schema.get('oneOf') or []
        chosen = 'string'
        for v in variants:
            if isinstance(v, dict) and v.get('type') in ('integer', 'number', 'boolean'):
                chosen = v['type']
                break
        out = {k: v for k, v in schema.items() if k not in ('anyOf', 'oneOf')}
        out['type'] = chosen
        return _sanitize_gemini_schema(out)
    result: dict[str, Any] = {}
    for key, val in schema.items():
        if key not in _GEMINI_SCHEMA_ALLOWED:
            continue
        if key == 'properties' and isinstance(val, dict):
            result[key] = {k: _sanitize_gemini_schema(v) for k, v in val.items()}
        elif key == 'items' and isinstance(val, dict):
            result[key] = _sanitize_gemini_schema(val)
        else:
            result[key] = val
    return result


def _openai_tools_to_gemini_function_declarations(openai_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decls: list[dict[str, Any]] = []
    for t in openai_tools or []:
        if not isinstance(t, dict) or t.get("type") != "function":
            continue
        fn = t.get("function") or {}
        if not isinstance(fn, dict):
            continue
        name = fn.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        desc = fn.get("description")
        params = fn.get("parameters")
        d: dict[str, Any] = {"name": name.strip()}
        if isinstance(desc, str) and desc.strip():
            d["description"] = desc.strip()
        if isinstance(params, dict):
            d["parameters"] = _sanitize_gemini_schema(params)
        decls.append(d)
    return decls


def _openai_messages_to_contents(messages: list[dict[str, Any]]) -> tuple[str | None, list]:
    system_text: str | None = None
    contents: list = []
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content")
        if role == "system":
            if isinstance(content, str) and content.strip():
                system_text = content
            continue
        if role not in ("user", "assistant"):
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        contents.append({
            "role": "user" if role == "user" else "model",
            "parts": [content.strip()],
        })
    return system_text, contents


class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self._api_key = (api_key or "").strip()
        self._model = (model or "gemini-2.5-flash").strip()
        if not self._api_key:
            raise RuntimeError("Configure GEMINI_API_KEY en .env")
        genai.configure(api_key=self._api_key)
        self._decls_cache: list[dict] | None = None
        self._decls_cache_len: int = -1
        self._model_cache: dict[tuple, Any] = {}

    # ── Caché de schemas y modelos ────────────────────────────────────────────

    def _get_function_decls(self, tools: list[dict]) -> list[dict]:
        n = len(tools)
        if self._decls_cache is None or self._decls_cache_len != n:
            self._decls_cache = _openai_tools_to_gemini_function_declarations(tools)
            self._decls_cache_len = n
        return self._decls_cache

    def _get_model(self, system_text: str | None, function_decls: list[dict]) -> genai.GenerativeModel:
        key = (system_text, bool(function_decls))
        if key not in self._model_cache:
            self._model_cache[key] = self._make_model(system_text, function_decls)
        return self._model_cache[key]

    def _make_model(self, system_text: str | None, function_decls: list[dict]) -> genai.GenerativeModel:
        tools = [{"function_declarations": function_decls}] if function_decls else None
        tool_config = {"function_calling_config": {"mode": "AUTO"}} if function_decls else None
        return genai.GenerativeModel(
            model_name=self._model,
            system_instruction=system_text or None,
            tools=tools,
            tool_config=tool_config,
            generation_config=_GENERATION_CONFIG,
        )

    # ── Llamada async con reintentos ──────────────────────────────────────────

    async def _generate(self, model: genai.GenerativeModel, contents: list) -> Any:
        _max_retries = 3
        last_exc: Exception = RuntimeError("Error desconocido")
        for attempt in range(_max_retries + 1):
            try:
                return await model.generate_content_async(contents)
            except Exception as e:
                last_exc = e
                if self._is_retryable(e) and attempt < _max_retries:
                    wait = 30
                    logger.info("Gemini retryable error → reintentando en %ss (intento %d/%d)", wait, attempt + 1, _max_retries)
                    await asyncio.sleep(wait)
                    continue
                break
        self._raise_friendly(last_exc)

    @staticmethod
    def _is_retryable(e: Exception) -> bool:
        msg = str(e)
        if '429' in msg or '503' in msg:
            return True
        if _HAS_GOOGLE_EXC and isinstance(e, (_google_exc.ResourceExhausted, _google_exc.ServiceUnavailable)):
            return True
        return False

    @staticmethod
    def _raise_friendly(e: Exception) -> None:
        msg = str(e)
        is_429 = '429' in msg or (_HAS_GOOGLE_EXC and isinstance(e, _google_exc.ResourceExhausted))
        is_503 = '503' in msg or (_HAS_GOOGLE_EXC and isinstance(e, _google_exc.ServiceUnavailable))
        is_auth = '403' in msg or '401' in msg or (_HAS_GOOGLE_EXC and isinstance(e, _google_exc.PermissionDenied))
        if is_429:
            raise RuntimeError("Intentá de nuevo en unos segundos.") from e
        if is_503:
            raise RuntimeError(
                "Gemini API no disponible temporalmente (503). Suele ser saturación del servicio de Google; "
                "reintentá en 1–5 minutos. Si persiste, probá otro modelo (GEMINI_MODEL en .env) o "
                "cambiá a Groq: LLM_PROVIDER=groq y GROQ_API_KEY."
            ) from e
        if is_auth:
            raise RuntimeError("Gemini rechazó la API key (403). Verificá GEMINI_API_KEY en .env.") from e
        raise RuntimeError(f"Error llamando a Gemini: {e}") from e

    # ── Helpers de respuesta ──────────────────────────────────────────────────

    @staticmethod
    def _extract_parts(response: Any) -> tuple[str, list[dict]]:
        text_out = ""
        tool_calls: list[dict] = []
        candidate = response.candidates[0] if response.candidates else None
        if not candidate or not candidate.content:
            return text_out, tool_calls
        for part in candidate.content.parts:
            if hasattr(part, "text") and part.text:
                text_out += part.text
            if hasattr(part, "function_call") and part.function_call and part.function_call.name:
                tool_calls.append({
                    "name": part.function_call.name,
                    "args": dict(part.function_call.args),
                })
        return text_out, tool_calls

    @staticmethod
    def _fn_response_content(results: list[tuple[str, Any]]) -> protos.Content:
        parts = [
            protos.Part(function_response=protos.FunctionResponse(
                name=name,
                response={"result": result},
            ))
            for name, result in results
        ]
        return protos.Content(role="user", parts=parts)

    # ── API pública async ─────────────────────────────────────────────────────

    async def chat_with_tools_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        run_tool: Callable,
        on_event: Callable,
        try_fast_format=None,
    ) -> tuple:
        system_text, contents = _openai_messages_to_contents(messages)
        function_decls = self._get_function_decls(tools)
        model_with_tools = self._get_model(system_text, function_decls)
        model_plain = self._get_model(system_text, [])

        for _iteration in range(1, MAX_ITERATIONS + 1):
            current_model = model_with_tools if _iteration == 1 else model_plain
            response = await self._generate(current_model, contents)
            text_out, tool_calls = self._extract_parts(response)

            if tool_calls:
                contents.append(response.candidates[0].content)
                tool_results: list[tuple[str, Any]] = []
                last_fn_name: str | None = None
                last_tool_json: str | None = None

                for tc in tool_calls:
                    label = (
                        "Consultando historial..."       if tc["name"].startswith("chat_") else
                        "Filtrando resultado anterior..." if tc["name"] == "filtrar_previo" else
                        "Consultando base de datos..."
                    )
                    await on_event({"type": "status", "text": label})
                    logger.info("[Gemini.stream] Ejecutando tool: %s | args=%s",
                                tc["name"], str(tc["args"])[:120])
                    tool_json = _clamp_tool_json(await run_tool(tc["name"], tc["args"]))
                    logger.info("[Gemini.stream] Tool %s → result_len=%d", tc["name"], len(tool_json))
                    last_fn_name = tc["name"]
                    last_tool_json = tool_json
                    try:
                        tool_obj = json.loads(tool_json)
                    except Exception:
                        tool_obj = {"raw": tool_json}
                    tool_results.append((tc["name"], tool_obj))

                contents.append(self._fn_response_content(tool_results))

                if try_fast_format and len(tool_calls) == 1 and last_fn_name and last_tool_json:
                    fast_reply = try_fast_format(last_fn_name, last_tool_json)
                    logger.info("[Gemini.stream] try_fast_format('%s') → %s",
                                last_fn_name, f"OK len={len(fast_reply)}" if fast_reply else "None (usará LLM)")
                    if fast_reply:
                        await on_event({"type": "reply", "text": fast_reply.strip()})
                        return fast_reply.strip(), messages

                # Respuesta final en streaming nativo async
                await on_event({"type": "status", "text": "Generando respuesta..."})
                full_text = ""
                chunks_total = 0
                chunks_con_texto = 0
                exc_stream = None
                try:
                    response_stream = await model_plain.generate_content_async(contents, stream=True)
                    async for chunk in response_stream:
                        chunks_total += 1
                        try:
                            token = chunk.text
                        except Exception as e:
                            # thinking tokens u otras partes no-texto
                            logger.debug("[Gemini.stream] chunk.text lanzó %s (thinking token?)", type(e).__name__)
                            token = ""
                        if token:
                            chunks_con_texto += 1
                            full_text += token
                            await on_event({"type": "token", "text": token})
                except Exception as e:
                    exc_stream = e
                    logger.warning("[Gemini.stream] EXCEPCIÓN durante stream: %s", e)
                    fb = await self._generate(model_plain, contents)
                    full_text, _ = self._extract_parts(fb)
                    if full_text:
                        await on_event({"type": "reply", "text": full_text})

                logger.info(
                    "[Gemini.stream] Stream terminado | chunks=%d | con_texto=%d | full_text_len=%d | exc=%s",
                    chunks_total, chunks_con_texto, len(full_text), exc_stream
                )

                # Fallback si el stream completó sin emitir texto
                if not full_text:
                    logger.warning("[Gemini.stream] full_text VACÍO → fallback sin streaming")
                    fb = await self._generate(model_plain, contents)
                    full_text, _ = self._extract_parts(fb)
                    logger.info("[Gemini.stream] Fallback → full_text_len=%d", len(full_text))
                    if full_text:
                        await on_event({"type": "reply", "text": full_text})

                logger.info("[Gemini.stream] RETORNO | full_text_len=%d | vacío=%s",
                            len(full_text), not full_text)
                contents.append({"role": "model", "parts": [full_text]})
                return full_text.strip(), messages

            reply = text_out.strip()
            logger.info("[Gemini.stream] Sin tools → reply directo | len=%d", len(reply))

            # Retry si Gemini devolvió texto vacío sin tools (candidato bloqueado/vacío)
            if not reply:
                logger.warning("[Gemini.stream] reply VACÍO sin tools → reintentando con model_with_tools")
                try:
                    fb = await self._generate(model_with_tools, contents)
                    fb_text, fb_tools = self._extract_parts(fb)
                    if fb_text:
                        reply = fb_text.strip()
                        logger.info("[Gemini.stream] Retry → reply_len=%d", len(reply))
                    elif fb_tools:
                        # El retry SÍ quiso llamar tools — forzar una respuesta de texto
                        logger.info("[Gemini.stream] Retry devolvió tools=%d, generando texto final", len(fb_tools))
                        contents_retry = list(contents)
                        contents_retry.append(fb.candidates[0].content)
                        contents_retry.append(protos.Content(role="user", parts=[
                            protos.Part(function_response=protos.FunctionResponse(
                                name=fb_tools[0]["name"],
                                response={"result": {"error": "No se pudo ejecutar en este momento. Intenta reformular la consulta."}},
                            ))
                        ]))
                        fb2 = await self._generate(model_plain, contents_retry)
                        fb2_text, _ = self._extract_parts(fb2)
                        reply = fb2_text.strip()
                except Exception as e:
                    logger.error("[Gemini.stream] Retry falló: %s", e)

            await on_event({"type": "reply", "text": reply})
            return reply, messages

        reply = "Se alcanzó el límite de iteraciones con herramientas."
        await on_event({"type": "reply", "text": reply})
        return reply, messages

    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        run_tool: Callable,
        try_fast_format=None,
    ) -> dict[str, Any]:
        system_text, contents = _openai_messages_to_contents(messages)
        function_decls = self._get_function_decls(tools)
        model_with_tools = self._get_model(system_text, function_decls)
        model_plain = self._get_model(system_text, [])

        for _iteration in range(1, MAX_ITERATIONS + 1):
            current_model = model_with_tools if _iteration == 1 else model_plain
            response = await self._generate(current_model, contents)
            text_out, tool_calls = self._extract_parts(response)

            if tool_calls:
                contents.append(response.candidates[0].content)
                tool_results: list[tuple[str, Any]] = []
                last_fn_name: str | None = None
                last_tool_json: str | None = None

                for tc in tool_calls:
                    tool_json = _clamp_tool_json(await run_tool(tc["name"], tc["args"]))
                    last_fn_name = tc["name"]
                    last_tool_json = tool_json
                    try:
                        tool_obj = json.loads(tool_json)
                    except Exception:
                        tool_obj = {"raw": tool_json}
                    tool_results.append((tc["name"], tool_obj))

                contents.append(self._fn_response_content(tool_results))

                if try_fast_format and len(tool_calls) == 1 and last_fn_name and last_tool_json:
                    fast_reply = try_fast_format(last_fn_name, last_tool_json)
                    if fast_reply:
                        return {"reply": fast_reply.strip(), "messages": messages}
                continue

            return {"reply": text_out.strip(), "messages": messages}

        return {"reply": "Se alcanzó el límite de iteraciones con herramientas.", "messages": messages}
