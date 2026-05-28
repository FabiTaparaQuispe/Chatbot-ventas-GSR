import json
import os

from fastapi import APIRouter, Request
from fastapi.responses import Response

from services.urlmap import chat_assistant_config_dict

router = APIRouter()

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
_JS_PATH = os.path.join(_REPO_ROOT, 'public', 'assets', 'js', 'chat_assistant.js')
_JS_CACHE: str | None = None


def _load_js() -> str:
    global _JS_CACHE
    if _JS_CACHE is not None:
        return _JS_CACHE
    with open(_JS_PATH, 'r', encoding='utf-8', errors='replace') as f:
        _JS_CACHE = f.read()
    return _JS_CACHE


@router.get('/modules/chat-assistant')
@router.get('/modules/chat_assistant_script.php')
async def chat_script(request: Request):
    user_key = str(request.session.get('usuario') or 'anon')
    role = str(request.session.get('role') or '')
    cfg = chat_assistant_config_dict(user_key, role)
    header = (
        'window.__VENTAS_CHAT = window.__VENTAS_CHAT || {};\n'
        f'Object.assign(window.__VENTAS_CHAT, {json.dumps(cfg, ensure_ascii=False)});\n'
    )
    content = header + _load_js()
    return Response(content=content, media_type='application/javascript',
                    headers={'Cache-Control': 'no-cache'})
