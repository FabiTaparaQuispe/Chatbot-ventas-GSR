import json
import os
import re
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MAX_ITERATIONS = 10
MAX_TOOL_JSON_BYTES = 14000


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
            d["parameters"] = params
        decls.append(d)
    return decls


def _messages_to_gemini_contents(messages: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
    """
    OpenAI messages -> Gemini contents + systemInstruction (texto).
    - system se devuelve por separado.
    - user/assistant -> role user/model con parts[{text}]
    """
    system_text: str | None = None
    contents: list[dict[str, Any]] = []
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content")
        if role == "system" and isinstance(content, str) and content.strip():
            system_text = content
            continue
        if role not in ("user", "assistant"):
            continue
        if not isinstance(content, str):
            continue
        txt = content.strip()
        if not txt:
            continue
        contents.append(
            {
                "role": "user" if role == "user" else "model",
                "parts": [{"text": txt}],
            }
        )
    return system_text, contents


class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash") -> None:
        self._api_key = (api_key or "").strip()
        self._model = (model or "gemini-1.5-flash").strip()
        if not self._api_key:
            raise RuntimeError("Configure GEMINI_API_KEY en .env")

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        run_tool: Callable[[str, dict[str, Any]], str],
    ) -> dict[str, Any]:
        system_text, contents = _messages_to_gemini_contents(messages)
        function_decls = _openai_tools_to_gemini_function_declarations(tools)

        for _iteration in range(1, MAX_ITERATIONS + 1):
            resp = self._generate(system_text, contents, function_decls if _iteration == 1 else [])
            candidate = (resp.get("candidates") or [{}])[0] if isinstance(resp.get("candidates"), list) else {}
            content = candidate.get("content") or {}
            parts = content.get("parts") or []
            if not isinstance(parts, list):
                parts = []

            # Texto normal
            text_out = ""
            tool_calls: list[dict[str, Any]] = []
            for p in parts:
                if not isinstance(p, dict):
                    continue
                if "text" in p and isinstance(p["text"], str):
                    text_out += p["text"]
                if "functionCall" in p and isinstance(p["functionCall"], dict):
                    fc = p["functionCall"]
                    name = fc.get("name")
                    args = fc.get("args")
                    if isinstance(name, str) and name.strip():
                        if not isinstance(args, dict):
                            args = {}
                        tool_calls.append({"name": name.strip(), "args": args})

            if tool_calls:
                # Guardamos el turno del modelo (opcional, para trazas)
                contents.append({"role": "model", "parts": parts})
                for tc in tool_calls:
                    tool_json = _clamp_tool_json(run_tool(tc["name"], tc["args"]))
                    # functionResponse debe ser un objeto, no string.
                    try:
                        tool_obj = json.loads(tool_json)
                    except Exception:
                        tool_obj = {"raw": tool_json}
                    contents.append(
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "functionResponse": {
                                        "name": tc["name"],
                                        "response": {"result": tool_obj},
                                    }
                                }
                            ],
                        }
                    )
                continue

            # Sin herramientas: devolvemos respuesta final
            contents.append({"role": "model", "parts": [{"text": text_out}]})
            return {"reply": (text_out or "").strip(), "messages": messages}

        return {"reply": "Se alcanzó el límite de iteraciones con herramientas.", "messages": messages}

    def _generate(
        self,
        system_text: str | None,
        contents: list[dict[str, Any]],
        function_decls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent"
            f"?key={self._api_key}"
        )
        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": 0.2},
        }
        if system_text:
            body["systemInstruction"] = {"parts": [{"text": system_text}]}
        if function_decls:
            body["tools"] = [{"functionDeclarations": function_decls}]
            body["toolConfig"] = {"functionCallingConfig": {"mode": "AUTO"}}

        req = Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=60) as r:
                raw = r.read().decode("utf-8", "replace")
                return json.loads(raw) if raw else {}
        except HTTPError as e:
            print(f"error: {e}.")
            raw = e.read().decode("utf-8", "replace")
            # Mapear errores comunes a mensajes claros
            if e.code in (429, 503):
                hint = self._extract_retry_hint(raw)
                if hint:
                    
                    raise RuntimeError(f"Límite de consultas Gemini. Intentá de nuevo en {hint}.") from e
                raise RuntimeError("Límite de consultas Gemini. Intentá de nuevo en unos segundos.") from e
            if e.code in (401, 403):
                # 403 suele ocurrir con API keys restringidas a navegador (HTTP referrer) o API no habilitada.
                raise RuntimeError(
                    "Gemini rechazó la API key (403). Si la key está restringida por HTTP referrer/navegador, "
                    "no funcionará desde el backend. Crea una API key de servidor (sin restricción de referer), "
                    "habilita la Generative Language API y vuelve a intentar."
                ) from e
            raise RuntimeError(f"Gemini HTTP {e.code}: {raw[:500]}") from e
        except URLError as e:
            raise RuntimeError(f"No se pudo conectar a Gemini: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Error llamando a Gemini: {e}") from e

    @staticmethod
    def _extract_retry_hint(raw: str) -> str | None:
        """
        Intenta extraer un tiempo humano desde el JSON de error de Gemini.
        Ejemplos típicos: "Please retry in 23.8s", retryDelay, etc.
        """
        if not raw:
            return None
        m = re.search(r"retry in\s+([\d.]+)\s*s", raw, flags=re.I)
        if m:
            return f"{float(m.group(1)):.1f}s"
        m2 = re.search(r"Please retry in\s+([\d.]+)\s*s", raw, flags=re.I)
        if m2:
            return f"{float(m2.group(1)):.1f}s"
        # A veces viene como seconds en JSON (best-effort)
        m3 = re.search(r'"seconds"\s*:\s*"?([\d.]+)"?', raw, flags=re.I)
        if m3:
            return f"{float(m3.group(1)):.1f}s"
        return None

