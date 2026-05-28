import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'), override=False)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

PUBLIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'public'))

app = FastAPI(
    title='Chatbot Ventas GSR',
    version='1.0.0',
    docs_url='/docs',
    redoc_url='/redoc',
)

# ── Sesiones (equivalente a Flask secret_key + session) ──────────────────────
secret = os.getenv('FLASK_SECRET', '').strip()
if not secret:
    raise RuntimeError('FLASK_SECRET no configurado en .env')
app.add_middleware(SessionMiddleware, secret_key=secret, max_age=8 * 3600)

# ── Rate limiting + security headers ─────────────────────────────────────────
_RL_WINDOW = 60
_RL_MAX_API = 30
_rl_counters: dict = defaultdict(list)


@app.middleware('http')
async def security_middleware(request: Request, call_next):
    if request.url.path.startswith('/api/chat'):
        ip = request.headers.get('X-Forwarded-For', request.client.host or '').split(',')[0].strip()
        now = time.time()
        _rl_counters[ip] = [t for t in _rl_counters[ip] if now - t < _RL_WINDOW]
        if len(_rl_counters[ip]) >= _RL_MAX_API:
            return JSONResponse({'ok': False, 'error': 'Demasiadas solicitudes. Esperá un minuto.'}, status_code=429)
        _rl_counters[ip].append(now)

    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response


# ── Cierre de conexión DB al final de cada request ───────────────────────────
@app.middleware('http')
async def db_teardown(request: Request, call_next):
    response = await call_next(request)
    from services.db import close_request_connection
    close_request_connection()
    return response


# ── Archivos estáticos ────────────────────────────────────────────────────────
app.mount('/assets', StaticFiles(directory=os.path.join(PUBLIC_DIR, 'assets')), name='assets')
app.mount('/modules', StaticFiles(directory=os.path.join(PUBLIC_DIR, 'modules')), name='modules')

# ── Routers ───────────────────────────────────────────────────────────────────
from routes_fastapi.auth import router as auth_router
from routes_fastapi.pages import router as pages_router
from routes_fastapi.api.ventas_dt import router as ventas_dt_router
from routes_fastapi.api.chat_threads import router as chat_threads_router
from routes_fastapi.api.stats import router as stats_router
from routes_fastapi.api.ventas_kpi import router as ventas_kpi_router
from routes_fastapi.api.chat_script import router as chat_script_router
from routes_fastapi.api.chat import router as chat_router

app.include_router(auth_router)
app.include_router(pages_router)
app.include_router(ventas_dt_router)
app.include_router(chat_threads_router)
app.include_router(stats_router)
app.include_router(ventas_kpi_router)
app.include_router(chat_script_router)
app.include_router(chat_router)


if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv('FLASK_PORT', 5000))
    uvicorn.run('app_fastapi:app', host='0.0.0.0', port=port, reload=True)
