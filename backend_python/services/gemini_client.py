import asyncio
import json
import logging
from typing import Any, Callable

from google import genai
from google.genai import errors as _genai_errors
from google.genai import types

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 10
MAX_TOOL_JSON_BYTES = 14000


# ── Helpers de JSON ───────────────────────────────────────────────────────────

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
        {"error": "respuesta_herramienta_muy_grande",
         "mensaje": "La consulta devolvió demasiados datos. Acote fechas o filtros."},
        ensure_ascii=False,
    )


# ── Conversión de schemas OpenAI → Gemini ────────────────────────────────────

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
        contents.append(types.Content(
            role="user" if role == "user" else "model",
            parts=[types.Part(text=content.strip())],
        ))
    return system_text, contents


# ── Cliente Gemini (google-genai SDK) ─────────────────────────────────────────

class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self._api_key = (api_key or "").strip()
        self._model = (model or "gemini-2.0-flash").strip()
        if not self._api_key:
            raise RuntimeError("Configure GEMINI_API_KEY en .env")
        self._client = genai.Client(api_key=self._api_key)
        self._decls_cache: list[dict] | None = None
        self._decls_cache_len: int = -1

    # ── Helpers de configuración ──────────────────────────────────────────────

    def _get_function_decls(self, tools: list[dict]) -> list[dict]:
        n = len(tools)
        if self._decls_cache is None or self._decls_cache_len != n:
            self._decls_cache = _openai_tools_to_gemini_function_declarations(tools)
            self._decls_cache_len = n
        return self._decls_cache

    def _make_config(self, system_text: str | None, function_decls: list[dict],
                     mode: str = 'AUTO') -> types.GenerateContentConfig:
        kwargs: dict[str, Any] = {
            'system_instruction': system_text or None,
            'temperature': 0.2,
            # Desactivar AFC: el nuevo SDK lo activa por defecto y entra en conflicto
            # con nuestro loop manual de tool calling
            'automatic_function_calling': types.AutomaticFunctionCallingConfig(disable=True),
        }
        if function_decls:
            kwargs['tools'] = [types.Tool(function_declarations=function_decls)]
            kwargs['tool_config'] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode=mode)
            )
        return types.GenerateContentConfig(**kwargs)

    # ── Llamada async con reintentos ──────────────────────────────────────────

    async def _generate(self, contents: list, config: types.GenerateContentConfig) -> Any:
        _max_retries = 3
        last_exc: Exception = RuntimeError("Error desconocido")
        for attempt in range(_max_retries + 1):
            try:
                return await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=config,
                )
            except Exception as e:
                last_exc = e
                if self._is_retryable(e) and attempt < _max_retries:
                    wait = 30
                    logger.info("Gemini retryable error → reintentando en %ss (intento %d/%d)",
                                wait, attempt + 1, _max_retries)
                    await asyncio.sleep(wait)
                    continue
                break
        self._raise_friendly(last_exc)

    @staticmethod
    def _is_retryable(e: Exception) -> bool:
        msg = str(e)
        if '429' in msg or '503' in msg or 'RESOURCE_EXHAUSTED' in msg or 'UNAVAILABLE' in msg:
            return True
        if isinstance(e, _genai_errors.ServerError):
            return True
        return False

    @staticmethod
    def _raise_friendly(e: Exception) -> None:
        msg = str(e)
        is_429 = '429' in msg or 'RESOURCE_EXHAUSTED' in msg or (
            isinstance(e, _genai_errors.ClientError) and '429' in str(e.code or '')
        )
        is_503 = '503' in msg or 'UNAVAILABLE' in msg or isinstance(e, _genai_errors.ServerError)
        is_auth = '403' in msg or '401' in msg or 'PERMISSION_DENIED' in msg
        if is_429:
            raise RuntimeError("Intentá de nuevo en unos segundos.") from e
        if is_503:
            raise RuntimeError(
                "Gemini API no disponible temporalmente (503). "
                "Reintentá en 1–5 minutos o cambiá a Groq: LLM_PROVIDER=groq."
            ) from e
        if is_auth:
            raise RuntimeError("Gemini rechazó la API key (403). Verificá GEMINI_API_KEY en .env.") from e
        raise RuntimeError(f"Error llamando a Gemini: {e}") from e

    # ── Helpers de respuesta ──────────────────────────────────────────────────

    @staticmethod
    def _extract_parts(response: Any) -> tuple[str, list[dict]]:
        text_out = ""
        tool_calls: list[dict] = []
        try:
            candidate = response.candidates[0] if response.candidates else None
            if not candidate or not candidate.content:
                return text_out, tool_calls
            for part in (candidate.content.parts or []):  # parts puede ser None en el nuevo SDK
                if hasattr(part, "text") and part.text:
                    text_out += part.text
                if hasattr(part, "function_call") and part.function_call and part.function_call.name:
                    tool_calls.append({
                        "name": part.function_call.name,
                        "args": dict(part.function_call.args),
                    })
        except Exception as e:
            logger.error("[Gemini] Error extrayendo partes de la respuesta: %s", e)
        return text_out, tool_calls

    @staticmethod
    def _fn_response_content(results: list[tuple[str, Any]]) -> types.Content:
        parts = [
            types.Part(function_response=types.FunctionResponse(
                name=name,
                response={"result": result},
            ))
            for name, result in results
        ]
        return types.Content(role="user", parts=parts)

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
        config_with_tools = self._make_config(system_text, function_decls, mode='AUTO')
        config_plain = self._make_config(system_text, [], mode='AUTO')

        last_user = next((m.get('content', '')[:80] for m in reversed(messages) if m.get('role') == 'user'), '')
        logger.info("[Gemini.stream] INICIO | model=%s | user='%s'", self._model, last_user)

        for _iteration in range(1, MAX_ITERATIONS + 1):
            config = config_with_tools if _iteration == 1 else config_plain
            logger.info("[Gemini.stream] iter=%d → llamada LLM", _iteration)

            response = await self._generate(contents, config)
            text_out, tool_calls = self._extract_parts(response)
            logger.info("[Gemini.stream] iter=%d → tools=%d | text_len=%d",
                        _iteration, len(tool_calls), len(text_out))

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

                # Respuesta final en streaming — nuevo SDK: chunk.text devuelve None en lugar de lanzar excepción
                await on_event({"type": "status", "text": "Generando respuesta..."})
                full_text = ""
                chunks_total = 0
                exc_stream = None
                try:
                    async for chunk in await self._client.aio.models.generate_content_stream(
                        model=self._model,
                        contents=contents,
                        config=config_plain,
                    ):
                        chunks_total += 1
                        token = chunk.text or ""  # None para thinking/no-text, sin excepción
                        if token:
                            full_text += token
                            await on_event({"type": "token", "text": token})
                except Exception as e:
                    exc_stream = e
                    logger.warning("[Gemini.stream] EXCEPCIÓN durante stream: %s", e)
                    try:
                        fb = await self._generate(contents, config_plain)
                        full_text, _ = self._extract_parts(fb)
                        if full_text:
                            await on_event({"type": "reply", "text": full_text})
                    except Exception as e2:
                        logger.error("[Gemini.stream] Fallback también falló: %s", e2)

                logger.info("[Gemini.stream] Stream terminado | chunks=%d | full_text_len=%d | exc=%s",
                            chunks_total, len(full_text), exc_stream)

                # Fallback si el stream completó sin emitir texto
                if not full_text:
                    logger.warning("[Gemini.stream] full_text VACÍO → fallback sin streaming")
                    try:
                        fb = await self._generate(contents, config_plain)
                        full_text, _ = self._extract_parts(fb)
                        logger.info("[Gemini.stream] Fallback → full_text_len=%d", len(full_text))
                        if full_text:
                            await on_event({"type": "reply", "text": full_text})
                    except Exception as e:
                        logger.error("[Gemini.stream] Fallback sin streaming falló: %s", e)

                logger.info("[Gemini.stream] RETORNO | full_text_len=%d | vacío=%s",
                            len(full_text), not full_text)
                contents.append(types.Content(
                    role="model",
                    parts=[types.Part(text=full_text or " ")]
                ))
                return full_text.strip(), messages

            # Sin tool calls — respuesta directa de texto
            reply = text_out.strip()
            logger.info("[Gemini.stream] Sin tools → reply directo | len=%d", len(reply))

            # Hasta 3 reintentos si Gemini devuelve vacío
            # Reintento 1: AUTO (igual que el primero, por si fue transitorio)
            # Reintentos 2-3: REQUIRED (fuerza al modelo a llamar una herramienta)
            if not reply:
                config_required = self._make_config(system_text, function_decls, mode='ANY')
                for _retry_n in range(1, 4):
                    modo = 'AUTO' if _retry_n == 1 else 'REQUIRED'
                    cfg_retry = config_with_tools if _retry_n == 1 else config_required
                    logger.warning("[Gemini.stream] reply VACÍO → reintento %d/3 modo=%s (pausa 1s)",
                                   _retry_n, modo)
                    await asyncio.sleep(1)
                    try:
                        fb = await self._generate(contents, cfg_retry)
                        fb_text, fb_tools = self._extract_parts(fb)
                        if fb_text:
                            reply = fb_text.strip()
                            logger.info("[Gemini.stream] Reintento %d → reply_len=%d", _retry_n, len(reply))
                            break
                        if fb_tools:
                            logger.info("[Gemini.stream] Reintento %d → tools=%d, procesando", _retry_n, len(fb_tools))
                            contents.append(fb.candidates[0].content)
                            retry_results = []
                            for tc in fb_tools:
                                await on_event({"type": "status", "text": "Consultando base de datos..."})
                                tool_json = _clamp_tool_json(await run_tool(tc["name"], tc["args"]))
                                try:
                                    tool_obj = json.loads(tool_json)
                                except Exception:
                                    tool_obj = {"raw": tool_json}
                                retry_results.append((tc["name"], tool_obj))
                            contents.append(self._fn_response_content(retry_results))
                            await on_event({"type": "status", "text": "Generando respuesta..."})
                            fb2 = await self._generate(contents, config_plain)
                            reply = self._extract_parts(fb2)[0].strip()
                            logger.info("[Gemini.stream] Reintento %d con tools → reply_len=%d", _retry_n, len(reply))
                            break
                        logger.warning("[Gemini.stream] Reintento %d también devolvió vacío", _retry_n)
                    except Exception as e:
                        logger.error("[Gemini.stream] Reintento %d falló: %s", _retry_n, e)

            await on_event({"type": "reply", "text": reply})
            return reply, messages

        reply = "Se alcanzó el límite de iteraciones con herramientas."
        logger.warning("[Gemini.stream] Límite de iteraciones alcanzado")
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
        config_with_tools = self._make_config(system_text, function_decls, mode='AUTO')
        config_plain = self._make_config(system_text, [], mode='AUTO')

        for _iteration in range(1, MAX_ITERATIONS + 1):
            config = config_with_tools if _iteration == 1 else config_plain
            response = await self._generate(contents, config)
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

            reply = text_out.strip()
            if not reply and _iteration == 1:
                # Retry si la primera respuesta fue vacía
                logger.warning("[Gemini] chat_with_tools: reply vacío en iter=1, reintentando")
                try:
                    fb = await self._generate(contents, config_with_tools)
                    fb_text, fb_tools = self._extract_parts(fb)
                    if fb_text:
                        reply = fb_text.strip()
                    elif fb_tools:
                        # Procesar tools del retry
                        contents.append(fb.candidates[0].content)
                        retry_results = []
                        for tc in fb_tools:
                            tool_json = _clamp_tool_json(await run_tool(tc["name"], tc["args"]))
                            try:
                                tool_obj = json.loads(tool_json)
                            except Exception:
                                tool_obj = {"raw": tool_json}
                            retry_results.append((tc["name"], tool_obj))
                        contents.append(self._fn_response_content(retry_results))
                        fb2 = await self._generate(contents, config_plain)
                        reply = self._extract_parts(fb2)[0].strip()
                except Exception as e:
                    logger.error("[Gemini] chat_with_tools retry falló: %s", e)

            return {"reply": reply, "messages": messages}

        return {"reply": "Se alcanzó el límite de iteraciones con herramientas.", "messages": messages}
