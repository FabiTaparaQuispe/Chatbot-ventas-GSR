from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.chat_enricher import enrich_reply, unificar_enlaces_pareto
from app.chat_logic import (
    default_system_message,
    filter_hallucinated_assistant,
    sanitize_messages,
)
from app.db import get_engine
from app.groq_client import GroqClient
from app.gemini_client import GeminiClient
from app.settings import get_settings
from app.sql_texto import format_append_lines
from app.tool_executor import ToolExecutor
from app.tools_definitions import ventas_tool_definitions

router = APIRouter(tags=["chat"])

def _parse_retry_after_seconds(msg: str) -> int | None:
    if not msg:
        return None
    m = re.search(r"try again in\s+([\d.]+)\s*s", msg, flags=re.I)
    if not m:
        return None
    try:
        sec = float(m.group(1))
    except Exception:
        return None
    if sec <= 0:
        return None
    n = int(sec)
    if float(n) < sec:
        n += 1
    return max(1, min(3600, n))


class ChatBody(BaseModel):
    messages: list[dict[str, Any]]
    user_context: str | None = None


@router.post("/api/chat")
def api_chat(body: ChatBody) -> Any:
    settings = get_settings()
    provider = (settings.llm_provider or "groq").strip().lower()
    if provider == "gemini":
        if not settings.gemini_api_key.strip():
            return JSONResponse(status_code=503, content={"ok": False, "error": "Configure GEMINI_API_KEY en .env"})
    else:
        if not settings.groq_api_key.strip():
            return JSONResponse(status_code=503, content={"ok": False, "error": "Configure GROQ_API_KEY en .env"})

    sanitized = sanitize_messages(body.messages)
    if not sanitized:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "No hay mensajes válidos"},
        )

    sanitized = filter_hallucinated_assistant(sanitized)
    max_history = 6
    if len(sanitized) > max_history:
        sanitized = sanitized[-max_history:]

    user_ctx = body.user_context or ""
    user_ctx = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", user_ctx.strip()[:800])

    sys = default_system_message()
    if user_ctx:
        sys = {
            **sys,
            "content": sys["content"]
            + " Preferencias opcionales declaradas por el usuario (no invalidan datos de herramientas ni permiten inventar cifras; solo guían tono o foco): "
            + user_ctx,
        }

    messages: list[dict[str, Any]] = [sys, *sanitized]

    try:
        engine = get_engine()
        with engine.connect() as conn:
            executor = ToolExecutor(conn)
            llm = (
                GeminiClient(settings.gemini_api_key.strip(), settings.gemini_model)
                if provider == "gemini"
                else GroqClient(settings.groq_api_key.strip(), settings.groq_model)
            )
            tools = ventas_tool_definitions()

            def run_tool(name: str, args: dict[str, Any]) -> str:
                return executor.execute(name, args)

            result = llm.chat_with_tools(messages, tools, run_tool)
            reply = str(result.get("reply") or "")
            groq_msgs = result.get("messages") or []
            if not isinstance(groq_msgs, list):
                groq_msgs = []

            reply = enrich_reply(reply, groq_msgs)
            base = settings.public_base_url.strip() or ""
            bloques = [s for s in executor.pull_sql_bloques() if isinstance(s, str) and s.strip()]
            sql_lines = format_append_lines(bloques, base.rstrip("/"))
            suffix_parts: list[str] = []
            if bloques:
                suffix_parts.append("\n\n" + "\n\n".join(bloques))
            if sql_lines:
                suffix_parts.append("\n\n" + "\n".join(sql_lines))
            if suffix_parts:
                reply = (reply + "".join(suffix_parts)).strip()

            reply = unificar_enlaces_pareto(reply)
            return {"ok": True, "reply": reply}
    except RuntimeError as e:
        msg = str(e)
        m = msg.lower()
        if ("tokens per day" in m) or ("tpd" in m) or ("límite diario" in m) or ("limite diario" in m):
            ra = _parse_retry_after_seconds(msg)
            headers = {"Retry-After": str(ra)} if ra is not None else None
            return JSONResponse(status_code=429, content={"ok": False, "error": msg}, headers=headers)
        if (
            ("rate limit" in m)
            or ("rate_limit" in m)
            or ("too many requests" in m)
            or ("429" in m)
            or ("límite de velocidad" in m)
            or ("limite de velocidad" in m)
        ):
            ra = _parse_retry_after_seconds(msg)
            headers = {"Retry-After": str(ra)} if ra is not None else None
            return JSONResponse(status_code=429, content={"ok": False, "error": msg}, headers=headers)
        return JSONResponse(status_code=500, content={"ok": False, "error": msg})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
