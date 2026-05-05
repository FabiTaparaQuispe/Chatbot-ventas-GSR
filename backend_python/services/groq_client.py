import json
import os
import time
import re
from openai import OpenAI, APIStatusError

MAX_ITERATIONS = 10
MAX_TOOL_JSON_BYTES = 14000
MAX_429_RETRIES = 5


class GroqClient:
    def __init__(self, api_key: str, model: str = 'llama-3.1-8b-instant'):
        self.model = model
        self._client = OpenAI(
            api_key=api_key,
            base_url='https://api.groq.com/openai/v1',
        )

    def chat_with_tools(self, messages: list, tools: list, run_tool) -> dict:
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

        for attempt in range(1, MAX_429_RETRIES + 1):
            try:
                return self._client.chat.completions.create(**params)
            except APIStatusError as e:
                msg = str(e)
                if self._is_daily_limit(msg):
                    raise RuntimeError(self._friendly_daily_limit(msg))
                if self._is_rate_limit(msg) and attempt < MAX_429_RETRIES:
                    sleep_sec = self._parse_retry_seconds(msg)
                    if sleep_sec < 1.0:
                        sleep_sec = min(8.0, 2.0 * attempt)
                    time.sleep(sleep_sec)
                    continue
                raise RuntimeError(self._friendly_error(msg))

        raise RuntimeError('Groq: se agotaron los reintentos sin obtener una respuesta válida.')

    @staticmethod
    def _is_daily_limit(msg: str) -> bool:
        return 'tokens per day' in msg.lower() or 'TPD' in msg

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
            return 'Groq devolvió límite de velocidad (429). Espera unos minutos o cambia de modelo en GROQ_MODEL. [Detalle] ' + raw
        return 'Groq error: ' + raw

    @staticmethod
    def _parse_retry_seconds(msg: str) -> float:
        m = re.search(r'try again in ([\d.]+)\s*s', msg, re.IGNORECASE)
        if m:
            return min(30.0, max(0.5, float(m.group(1))))
        return 0.0

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
