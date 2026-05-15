from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.deps import session_user

router = APIRouter(prefix="/api", tags=["chat_config"])


@router.get("/chat-config")
def chat_config(request: Request) -> dict[str, Any]:
    user = session_user(request)
    key = (user or {}).get("username") or "anon"
    return {
        "chatApi": "/api/chat",
        "publicBase": "/",
        "modulesBase": "/modules/",
        "userKey": key,
        "threadsApi": "/api/chat_threads.php",
        "chatbotPage": "/index.php?page=chatbot",
    }
