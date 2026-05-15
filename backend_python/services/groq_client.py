import json
import os
import time
import re
from openai import OpenAI, APIStatusError

MAX_ITERATIONS = 10
MAX_TOOL_JSON_BYTES = 14000
MAX_429_RETRIES = 5          # ← subido de 3 a 5
_MAX_WAIT_SEC = 65.0         # ← subido de 25 a 65 (Groq free tier puede pedir hasta ~60s)
_DEFAULT_WAIT_SEC = 5.0      # ← subido de 3 a 5


class GroqClient:
    def __init__(self, api_key: str, model: str = 'llama-3.1-8b-instant'):
        self.model = model
        self._client = OpenAI(
            api_key=api_key,
            base_url='https://api.groq.com/openai/v1',
            timeout=45.0,
        )

    def chat_with_tools_stream(self, messages: list, tools: list, run_tool, on_event,
                               try_fast_format=None) -> tuple:
        """
        Igual que chat_with_tools pero llama on_event({'type':...}) para status/tokens.
        Retorna (reply_text, working_messages).
        """
        working = list(messages)
        has_tool_results = False

        for iteration in range(1, MAX_ITERATIONS + 1):
            available_tools = tools if iteration == 1 else []

            if has_tool_results:
                # Iteración final: streamear la respuesta
                on_event({'type': 'status', 'text': 'Generando respuesta...'})
                full_text = ''
                try:
                    stream = self._client.chat.completions.create(
                        model=self.model,
                        messages=working,
                        temperature=0.2,
                        stream=True,
                    )
                    for chunk in stream:
                        choice = chunk.choices[0] if chunk.choices else None
                        if not choice:
                            continue
                        delta = choice.delta
                        if delta and delta.content:
                            full_text += delta.content
                            on_event({'type': 'token', 'text': delta.content})
                        if choice.finish_reason:
                            break
                except Exception:
                    # Fallback sin streaming
                    response = self._request_completion(working, [])
                    choice = response.choices[0] if response.choices else None
                    full_text = str(choice.message.content or '') if choice else ''
                    on_event({'type': 'reply', 'text': full_text})
                working.append({'role': 'assistant', 'content': full_text})
                return full_text, working

            # Llamada no-streaming para detectar tool calls
            response = self._request_completion(working, available_tools)
            choice = response.choices[0] if response.choices else None
            if choice is None:
                return 'Respuesta vacía del modelo.', working

            msg = choice.message
            tool_calls = msg.tool_calls or []

            assistant_payload = {'role': 'assistant', 'content': msg.content}
            if tool_calls:
                assistant_payload['tool_calls'] = [
                    {'id': tc.id, 'type': tc.type,
                     'function': {'name': tc.function.name, 'arguments': tc.function.arguments}}
                    for tc in tool_calls
                ]
            working.append(assistant_payload)

            if not tool_calls:
                full_text = str(msg.content or '')
                on_event({'type': 'reply', 'text': full_text})
                return full_text, working

            has_tool_results = True
            last_fn_name = None
            last_tool_json = None
            for tc in tool_calls:
                fn_name = tc.function.name
                label = 'Consultando historial...' if fn_name.startswith('chat_') else (
                    'Filtrando resultado anterior...' if fn_name == 'filtrar_previo' else
                    'Consultando base de datos...'
                )
                on_event({'type': 'status', 'text': label})
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                tool_json = self._clamp_tool_json(run_tool(fn_name, args))
                working.append({'role': 'tool', 'tool_call_id': tc.id, 'content': tool_json})
                last_fn_name = fn_name
                last_tool_json = tool_json

            # Formateo rápido en Python: evita el 2do call al LLM
            if try_fast_format and len(tool_calls) == 1 and last_fn_name and last_tool_json:
                fast_reply = try_fast_format(last_fn_name, last_tool_json)
                if fast_reply:
                    working.append({'role': 'assistant', 'content': fast_reply})
                    on_event({'type': 'reply', 'text': fast_reply})
                    return fast_reply, working

        return 'Se alcanzó el límite de iteraciones.', working

    def chat_with_tools(self, messages: list, tools: list, run_tool,
                        try_fast_format=None) -> dict:
        working = list(messages)
        for iteration in range(1, MAX_ITERATIONS + 1):
            response = self._request_completion(working, tools if iteration == 1 else [])
            choice = response.choices[0] if response.choices else None
            if choice is None:
                return {'reply': 'Respuesta vacía del modelo.', 'messages': working}

            msg = choice.message
            tool_calls = msg.tool_calls or []

            assistant_payload = {'role': 'assistant', 'content': msg.content}
            if tool_calls:
                assistant_payload['tool_calls'] = [
                    {
                        'id': tc.id,
                        'type': tc.type,
                        'function': {'name': tc.function.name, 'arguments': tc.function.arguments},
                    }
                    for tc in tool_calls
                ]
            working.append(assistant_payload)

            if not tool_calls:
                return {'reply': str(msg.content or ''), 'messages': working}

            last_fn_name = None
            last_tool_json = None
            for tc in tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                tool_json = self._clamp_tool_json(run_tool(tc.function.name, args))
                working.append({
                    'role': 'tool',
                    'tool_call_id': tc.id,
                    'content': tool_json,
                })
                last_fn_name = tc.function.name
                last_tool_json = tool_json

            # Formateo rápido en Python: evita el 2do call al LLM
            if try_fast_format and len(tool_calls) == 1 and last_fn_name and last_tool_json:
                fast_reply = try_fast_format(last_fn_name, last_tool_json)
                if fast_reply:
                    working.append({'role': 'assistant', 'content': fast_reply})
                    return {'reply': fast_reply, 'messages': working}

        return {'reply': 'Se alcanzó el límite de iteraciones con herramientas.', 'messages': working}

    def _request_completion(self, messages: list, tools: list):
        params = {
            'model': self.model,
            'messages': messages,
            'temperature': 0.2,
        }
        if tools:
            params['tools'] = tools
            params['tool_choice'] = 'auto'

        last_err: Exception | None = None
        for attempt in range(1, MAX_429_RETRIES + 1):
            try:
                return self._client.chat.completions.create(**params)
            except APIStatusError as e:
                last_err = e
                msg = str(e)

                # ── Límite diario (TPD): no tiene sentido reintentar ──
                if self._is_daily_limit(msg):
                    raise RuntimeError(self._friendly_daily_limit(msg))

                # ── Rate limit (RPM / TPM): reintentar con backoff ──
                if self._is_rate_limit(msg) and attempt < MAX_429_RETRIES:
                    sleep_sec = self._get_wait_seconds(e, msg, attempt)
                    if sleep_sec > _MAX_WAIT_SEC:
                        raise RuntimeError(self._friendly_wait_long(sleep_sec))
                    print(f"[GroqClient] Rate limit (intento {attempt}/{MAX_429_RETRIES}). "
                          f"Esperando {sleep_sec:.1f}s...")
                    time.sleep(sleep_sec)
                    continue

                # ── Otros errores de API ──
                raise RuntimeError(self._friendly_error(msg))

        raise RuntimeError(self._friendly_error(str(last_err) if last_err else 'Groq: sin respuesta'))

    @staticmethod
    def _is_daily_limit(msg: str) -> bool:
        m = msg.lower()
        return 'tokens per day' in m or 'tpd' in m

    @staticmethod
    def _is_rate_limit(msg: str) -> bool:
        m = msg.lower()
        return (
            'rate_limit' in m
            or 'rate limit' in m
            or 'too many requests' in m
            or '429' in m
        )

    @staticmethod
    def _friendly_daily_limit(raw: str) -> str:
        hint = ''
        m = re.search(r'try again in\s+([^\n.]+)', raw, re.IGNORECASE)
        if m:
            hint = ' Indicación de Groq: esperar ~' + m.group(1).strip() + '.'
        return ('Se alcanzó el límite diario de tokens (TPD) de Groq para este modelo.' + hint
                + ' Reduce uso, prueba otro modelo en GROQ_MODEL (.env), o revisa tu cuota en console.groq.com.'
                + ' [Detalle] ' + raw)

    def _friendly_error(self, raw: str) -> str:
        if self._is_rate_limit(raw):
            wait = self._parse_retry_seconds(raw)
            if wait >= 1.0:
                mins = int(wait // 60)
                secs = int(wait % 60)
                wait_str = f'{mins}m {secs}s' if mins > 0 else f'{secs}s'
                return f'Límite de consultas Groq. Intentá de nuevo en {wait_str}.'
            return 'Límite de consultas Groq. Intentá de nuevo en unos minutos.'
        return 'Groq error: ' + raw

    @staticmethod
    def _friendly_wait_long(wait_sec: float) -> str:
        mins = int(wait_sec // 60)
        secs = int(wait_sec % 60)
        wait_str = f'{mins}m {secs}s' if mins > 0 else f'{secs}s'
        return f'Límite de consultas Groq. Intentá de nuevo en {wait_str}.'

    @classmethod
    def _get_wait_seconds(cls, exc: APIStatusError, msg: str, attempt: int = 1) -> float:
        """
        Determina cuánto esperar. Prioridad:
        1. Header Retry-After de Groq
        2. Parsear "try again in Xs" del mensaje
        3. Backoff exponencial: 5s, 10s, 20s, 40s...
        """
        # 1. Header
        try:
            ra = exc.response.headers.get('retry-after') or exc.response.headers.get('Retry-After')
            if ra:
                val = float(ra)
                if 0.5 <= val <= 300.0:
                    return val + 1.0  # margen de seguridad
        except Exception:
            pass

        # 2. Parsear mensaje
        parsed = cls._parse_retry_seconds(msg)
        if parsed > 1.0:
            return parsed + 1.0  # margen de seguridad

        # 3. Backoff exponencial con base _DEFAULT_WAIT_SEC
        return min(60.0, _DEFAULT_WAIT_SEC * (2 ** (attempt - 1)))

    @staticmethod
    def _parse_retry_seconds(msg: str) -> float:
        m = re.search(r'try again in\s+(?:(\d+)h\s*)?(?:(\d+)m\s*)?([\d.]+)\s*s', msg, re.IGNORECASE)
        if m:
            h = float(m.group(1) or 0)
            mn = float(m.group(2) or 0)
            s = float(m.group(3) or 0)
            return min(300.0, max(0.5, h * 3600 + mn * 60 + s))
        return 0.0  # ← cambiado de 3.0 a 0.0 para que el backoff exponencial tome el control

    def _clamp_tool_json(self, json_str: str) -> str:
        if len(json_str) <= MAX_TOOL_JSON_BYTES:
            return json_str
        try:
            data = json.loads(json_str)
        except Exception:
            return json_str
        slice_keys = ['filas', 'filas_ranking', 'filas_pareto']
        for key in slice_keys:
            if not isinstance(data, dict) or key not in data or not isinstance(data[key], list):
                continue
            all_rows = data[key]
            for n in [12, 8, 5, 3]:
                data[key] = all_rows[:n]
                data['_nota'] = f'Respuesta truncada: primeras {n} filas en {key} (límite API).'
                out = json.dumps(data, ensure_ascii=False)
                if len(out) <= MAX_TOOL_JSON_BYTES:
                    return out
            data[key] = all_rows
        return json.dumps({
            'error': 'respuesta_herramienta_muy_grande',
            'mensaje': 'La consulta devolvió demasiados datos. Acote fechas o filtros.',
        }, ensure_ascii=False)