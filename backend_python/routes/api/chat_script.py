import json
import os
from flask import Blueprint, session, Response

from services.urlmap import chat_assistant_config_dict

bp = Blueprint("api_chat_script", __name__)

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_JS_PATH = os.path.join(_REPO_ROOT, "public", "assets", "js", "chat_assistant.js")

_JS_CACHE: str | None = None


def _load_js() -> str:
    global _JS_CACHE
    if _JS_CACHE is not None:
        return _JS_CACHE
    with open(_JS_PATH, "r", encoding="utf-8", errors="replace") as f:
        _JS_CACHE = f.read()
    return _JS_CACHE


@bp.route("/modules/chat-assistant")
@bp.route("/modules/chat_assistant_script.php")
def chat_script():
    user_key = str(session.get("usuario") or "anon")
    role = str(session.get("role") or "")
    cfg = chat_assistant_config_dict(user_key, role)
    header = (
        "window.__VENTAS_CHAT = window.__VENTAS_CHAT || {};\n"
        f"Object.assign(window.__VENTAS_CHAT, {json.dumps(cfg, ensure_ascii=False)});\n"
    )
    content = header + _load_js()
    resp = Response(content, mimetype="application/javascript")
    resp.headers["Cache-Control"] = "no-cache"
    return resp
