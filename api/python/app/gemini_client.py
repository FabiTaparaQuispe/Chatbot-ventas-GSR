from __future__ import annotations

import json
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
        contents.append({"role": "user" if role == "user" else "model", "parts": [{"text": txt}]})
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

        for iteration in range(1, MAX_ITERATIONS + 1):
            resp = self._generate(system_text, contents, function_decls if iteration == 1 else [])
            candidates = resp.get("candidates")
            cand0 = candidates[0] if isinstance(candidates, list) and candidates else {}
            content = cand0.get("content") if isinstance(cand0, dict) else {}
            parts = (content or {}).get("parts") if isinstance(content, dict) else []
            if not isinstance(parts, list):
                parts = []

            text_out = ""
            tool_calls: list[dict[str, Any]] = []
            for p in parts:
                if not isinstance(p, dict):
                    continue
                if isinstance(p.get("text"), str):
                    text_out += p["text"]
                fc = p.get("functionCall")
                if isinstance(fc, dict):
                    name = fc.get("name")
                    args = fc.get("args")
                    if isinstance(name, str) and name.strip():
                        if not isinstance(args, dict):
                            args = {}
                        tool_calls.append({"name": name.strip(), "args": args})

            if tool_calls:
                contents.append({"role": "model", "parts": parts})
                for tc in tool_calls:
                    tool_json = _clamp_tool_json(run_tool(tc["name"], tc["args"]))
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

            return {"reply": (text_out or "").strip(), "messages": messages}

        return {"reply": "Se alcanzó el límite de iteraciones con herramientas.", "messages": messages}

    def _generate(
        self, system_text: str | None, contents: list[dict[str, Any]], function_decls: list[dict[str, Any]]
    ) -> dict[str, Any]:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent"
            f"?key={self._api_key}"
        )
        body: dict[str, Any] = {"contents": contents, "generationConfig": {"temperature": 0.2}}
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
            raw = e.read().decode("utf-8", "replace")
            if e.code in (429, 503):
                raise RuntimeError("Límite de consultas Gemini. Intentá de nuevo en unos segundos.") from e
            if e.code in (401, 403):
                raise RuntimeError("Gemini rechazó la API key. Verificá GEMINI_API_KEY.") from e
            raise RuntimeError(f"Gemini HTTP {e.code}: {raw[:500]}") from e
        except URLError as e:
            raise RuntimeError(f"No se pudo conectar a Gemini: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Error llamando a Gemini: {e}") from e

