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
from app.settings import get_settings
from app.sql_texto import format_append_lines
from app.tool_executor import ToolExecutor
from app.tools_definitions import ventas_tool_definitions

router = APIRouter(tags=["chat"])


class ChatBody(BaseModel):
    messages: list[dict[str, Any]]
    user_context: str | None = None


@router.post("/api/chat")
def api_chat(body: ChatBody) -> Any:
    settings = get_settings()
    if not settings.groq_api_key.strip():
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": "Configure GROQ_API_KEY en .env"},
        )

    sanitized = sanitize_messages(body.messages)
    if not sanitized:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "No hay mensajes válidos"},
        )

    sanitized = filter_hallucinated_assistant(sanitized)
    max_history = 4
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
            groq = GroqClient(settings.groq_api_key.strip(), settings.groq_model)
            tools = ventas_tool_definitions()

            def run_tool(name: str, args: dict[str, Any]) -> str:
                return executor.execute(name, args)

            result = groq.chat_with_tools(messages, tools, run_tool)
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
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
