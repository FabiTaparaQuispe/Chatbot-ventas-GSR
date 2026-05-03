import json
import os
import re
from flask import Blueprint, session, Response

bp = Blueprint('api_chat_script', __name__)

PHP_FILE = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', 'public', 'modules', 'chat_assistant_script.inc.php'
)

_JS_CACHE = None


def _load_js_base() -> str:
    global _JS_CACHE
    if _JS_CACHE is not None:
        return _JS_CACHE
    with open(PHP_FILE, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    content = re.sub(r'<\?php.*?\?>', '', content, flags=re.DOTALL)
    content = re.sub(r'^\s*<script[^>]*>', '', content, count=1, flags=re.IGNORECASE)
    content = re.sub(r'</script>\s*$', '', content, flags=re.IGNORECASE)

    for pattern in [
        r'const CHAT_API\s*=\s*<\?=.*?\?>;',
        r'const VENTAS_PUBLIC_BASE\s*=\s*<\?=.*?\?>;',
        r'const VENTAS_MODULES_WEB_BASE\s*=\s*<\?=.*?\?>;',
        r'const USER_KEY_RAW\s*=\s*<\?=.*?\?>;',
    ]:
        content = re.sub(pattern, '', content, flags=re.DOTALL)

    _JS_CACHE = content
    return content


@bp.route('/modules/chat_assistant_script.php')
def chat_script():
    chat_api = 'api/chat.php'
    public_base = '/'
    modules_base = '/modules/'
    user_key = str(session.get('usuario') or 'anon')

    js_base = _load_js_base()

    header = (
        f'const CHAT_API = {json.dumps(chat_api)};\n'
        f'const VENTAS_PUBLIC_BASE = {json.dumps(public_base)};\n'
        f'const VENTAS_MODULES_WEB_BASE = {json.dumps(modules_base)};\n'
        f'const USER_KEY_RAW = {json.dumps(user_key)};\n'
    )

    content = header + js_base

    resp = Response(content, mimetype='application/javascript')
    resp.headers['Cache-Control'] = 'no-cache'
    return resp
