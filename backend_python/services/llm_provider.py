"""Resolución del proveedor LLM (Groq vs Gemini) desde variables de entorno."""
from __future__ import annotations

import os


def resolve_llm_provider() -> str:
    """
    Devuelve 'groq' o 'gemini'.

    - Si LLM_PROVIDER es explícitamente groq o gemini, se respeta.
    - Si LLM_PROVIDER no está: solo GEMINI_API_KEY → gemini; solo GROQ_API_KEY
      → groq; si hay ambas claves, por defecto groq (compatibilidad).
    """
    raw = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if raw == "gemini":
        return "gemini"
    if raw == "groq":
        return "groq"

    gem = (os.getenv("GEMINI_API_KEY") or "").strip()
    groq = (os.getenv("GROQ_API_KEY") or "").strip()
    if gem and not groq:
        return "gemini"
    if groq and not gem:
        return "groq"
    if gem and groq:
        return "groq"
    return "groq"
