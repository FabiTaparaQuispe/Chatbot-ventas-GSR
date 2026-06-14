"""
Motor de IA basado en LangChain + Gemini (ChatGoogleGenerativeAI).

Reemplaza a GeminiClient manteniendo la MISMA interfaz
(chat_with_tools / chat_with_tools_stream) → es drop-in en
routes_fastapi/api/chat.py.

Primera versión de la migración:
- Usa bind_tools con las definiciones OpenAI-format que ya existen
  (services/tools_definitions.py) → NO hay que reescribir las tools.
- El SQL sigue viviendo en ToolExecutor; aquí solo se orquesta el agente.
- Respeta el "fast format" (responder sin otra llamada al LLM).

Pendiente para próximas iteraciones (ver notas en el chat):
- Streaming token-a-token real (esta versión emite la respuesta final).
- Redefinir cada tool como @tool de LangChain (auto-schema).
- Reintentos/diagnóstico equivalentes a los del cliente anterior.
"""
import logging

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

_MAX_TOOL_ITERS = 5


def _to_lc_messages(messages: list[dict]) -> list:
    """Convierte mensajes {'role','content'} al formato de LangChain."""
    out: list = []
    for m in messages:
        role = (m.get('role') or '').lower()
        content = str(m.get('content') or '')
        if role == 'system':
            out.append(SystemMessage(content=content))
        elif role == 'assistant':
            out.append(AIMessage(content=content))
        else:
            out.append(HumanMessage(content=content))
    return out


class LangChainGeminiClient:
    """Agente de tool-calling con Gemini vía LangChain."""

    def __init__(self, api_key: str, model: str):
        self._model = model
        self._llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0,
        )

    async def _run_agent(self, messages, tools, run_tool, try_fast_format=None):
        """Loop de tool-calling. Devuelve (reply, fast_reply_or_none, tool_msgs)."""
        llm = self._llm.bind_tools(tools)
        lc_msgs = _to_lc_messages(messages)
        tool_msgs: list[dict] = []  # {'role':'tool','content':json} para el route

        for _ in range(_MAX_TOOL_ITERS):
            ai = await llm.ainvoke(lc_msgs)
            tool_calls = getattr(ai, 'tool_calls', None) or []
            if not tool_calls:
                return str(ai.content or ''), None, tool_msgs

            lc_msgs.append(ai)
            fast_reply = None
            for tc in tool_calls:
                name = tc.get('name')
                args = tc.get('args') or {}
                tc_id = tc.get('id') or name
                logger.info("[LangChain] tool=%s args=%s", name, args)
                result_json = await run_tool(name, args)
                tool_msgs.append({'role': 'tool', 'content': result_json})
                # Fast format: si la tool tiene formato directo, úsalo como respuesta.
                if try_fast_format and fast_reply is None:
                    try:
                        ff = try_fast_format(name, result_json)
                        if ff:
                            fast_reply = ff
                    except Exception:
                        pass
                lc_msgs.append(ToolMessage(content=result_json, tool_call_id=tc_id))

            if fast_reply:
                return fast_reply, fast_reply, tool_msgs

        # Si se agotan las iteraciones, una última generación.
        ai = await llm.ainvoke(lc_msgs)
        return str(ai.content or ''), None, tool_msgs

    async def chat_with_tools(self, messages, tools, run_tool, try_fast_format=None):
        reply, _fast, tool_msgs = await self._run_agent(
            messages, tools, run_tool, try_fast_format
        )
        return {'reply': reply, 'messages': tool_msgs}

    async def chat_with_tools_stream(self, messages, tools, run_tool, on_event,
                                     try_fast_format=None):
        # Primera versión: no token-a-token; corre el agente y emite la respuesta final.
        await on_event({'type': 'status', 'text': 'Generando respuesta...'})
        reply, _fast, _msgs = await self._run_agent(
            messages, tools, run_tool, try_fast_format
        )
        await on_event({'type': 'reply', 'text': reply})
        return reply, []
