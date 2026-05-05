from __future__ import annotations

import json
import re
import time
from typing import Any, Callable

from openai import OpenAI

MAX_ITERATIONS = 10
MAX_TOOL_JSON_BYTES = 14000
MAX_429_RETRIES = 3
_MAX_WAIT_SEC = 25.0


class GroqClient:
    def __init__(self, api_key: str, model: str = "llama-3.1-8b-instant") -> None:
        self._client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
        self._model = model

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        run_tool: Callable[[str, dict[str, Any]], str],
    ) -> dict[str, Any]:
        working = list(messages)
        iteration = 0
        while iteration < MAX_ITERATIONS:
            iteration += 1
            use_tools = tools if iteration == 1 else []
            response = self._request_completion(working, use_tools)
            choice = response.choices[0]
            msg = choice.message
            tool_calls = getattr(msg, "tool_calls", None) or []

            assistant_payload: dict[str, Any] = {
                "role": "assistant",
                "content": msg.content,
            }
            if tool_calls:
                assistant_payload["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ]
            working.append(assistant_payload)

            if not tool_calls:
                return {"reply": msg.content or "", "messages": working}

            for tc in tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                tool_json = self._clamp_tool_json(run_tool(tc.function.name, args))
                working.append({"role": "tool", "tool_call_id": tc.id, "content": tool_json})

        return {
            "reply": "Se alcanzó el límite de iteraciones con herramientas.",
            "messages": working,
        }

    def _request_completion(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Any:
        params: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        last_err: Exception | None = None
        for attempt in range(1, MAX_429_RETRIES + 1):
            try:
                return self._client.chat.completions.create(**params)
            except Exception as e:
                last_err = e
                msg = str(e)
                if self._is_groq_daily_token_limit(msg):
                    raise RuntimeError(self._friendly_daily(msg)) from e
                if self._is_rate_limit(msg) and attempt < MAX_429_RETRIES:
                    sleep_sec = self._get_wait_seconds(e, msg)
                    if sleep_sec > _MAX_WAIT_SEC:
                        raise RuntimeError(self._friendly_wait_long(sleep_sec)) from e
                    time.sleep(sleep_sec)
                    continue
                raise RuntimeError(self._friendly_error(msg)) from e
        raise RuntimeError(str(last_err) if last_err else "Groq: sin respuesta")

    @staticmethod
    def _is_groq_daily_token_limit(message: str) -> bool:
        m = message.lower()
        return "tokens per day" in m or "tpd" in m

    @staticmethod
    def _is_rate_limit(message: str) -> bool:
        m = message.lower()
        return (
            "rate_limit" in m
            or "rate limit" in m
            or "too many requests" in m
            or "429" in m
        )

    @staticmethod
    def _friendly_daily(raw: str) -> str:
        hint = ""
        m2 = re.search(r"try again in\s+([^\n.]+)", raw, flags=re.I)
        if m2:
            hint = " Indicación de Groq: esperar ~" + m2.group(1).strip() + "."
        return (
            "Se alcanzó el límite diario de tokens (TPD) de Groq para este modelo." + hint
            + " Reduce uso (menos preguntas repetidas, menos historial en el chat), prueba otro modelo en GROQ_MODEL (.env), o revisa tu cuota en console.groq.com."
            + " [Detalle] " + raw
        )

    @staticmethod
    def _friendly_error(raw: str) -> str:
        if GroqClient._is_rate_limit(raw):
            wait = GroqClient._parse_retry_seconds(raw)
            if wait >= 1.0:
                mins = int(wait // 60)
                secs = int(wait % 60)
                wait_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                return f"Límite de consultas Groq. Intentá de nuevo en {wait_str}."
            return "Límite de consultas Groq. Intentá de nuevo en unos minutos."
        return "Groq error: " + raw

    @staticmethod
    def _friendly_wait_long(wait_sec: float) -> str:
        mins = int(wait_sec // 60)
        secs = int(wait_sec % 60)
        wait_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
        return f"Límite de consultas Groq. Intentá de nuevo en {wait_str}."

    @classmethod
    def _get_wait_seconds(cls, exc: Exception, msg: str) -> float:
        try:
            ra = exc.response.headers.get("retry-after") or exc.response.headers.get("Retry-After")  # type: ignore[attr-defined]
            if ra:
                return min(300.0, max(1.0, float(ra)))
        except Exception:
            pass
        return cls._parse_retry_seconds(msg)

    @staticmethod
    def _parse_retry_seconds(message: str) -> float:
        m = re.search(r"try again in\s+(?:(\d+)h\s*)?(?:(\d+)m\s*)?([\d.]+)\s*s", message, flags=re.I)
        if m:
            h = float(m.group(1) or 0)
            mn = float(m.group(2) or 0)
            s = float(m.group(3) or 0)
            return min(300.0, max(0.5, h * 3600 + mn * 60 + s))
        return 3.0

    def _clamp_tool_json(self, json_str: str) -> str:
        if len(json_str) <= MAX_TOOL_JSON_BYTES:
            return json_str
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
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
            {
                "error": "respuesta_herramienta_muy_grande",
                "mensaje": "La consulta devolvió demasiados datos. Acote fechas o filtros.",
            },
            ensure_ascii=False,
        )
