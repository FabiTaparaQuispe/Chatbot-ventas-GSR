import os
import sys
import time
from collections import defaultdict
from datetime import timedelta

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, send_from_directory, request, jsonify, g
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'), override=False)

PUBLIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'public'))

app = Flask(
    __name__,
    template_folder='templates',
    static_folder=None,
)

secret = os.getenv('FLASK_SECRET', '').strip()
if not secret:
    raise RuntimeError('FLASK_SECRET no configurado en .env — agrega una clave aleatoria larga.')
app.secret_key = secret

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)  # sesión expira en 8h

# ── Rate limiting en memoria (simple, reinicia con el servidor) ──────────────
_RL_WINDOW = 60          # ventana en segundos
_RL_MAX_API = 30         # máx llamadas al /api/chat por IP por minuto
_rl_counters: dict = defaultdict(list)

def _check_rate_limit(ip: str, limit: int) -> bool:
    """Retorna True si la IP superó el límite. Limpia entradas viejas."""
    now = time.time()
    hits = _rl_counters[ip]
    _rl_counters[ip] = [t for t in hits if now - t < _RL_WINDOW]
    if len(_rl_counters[ip]) >= limit:
        return True
    _rl_counters[ip].append(now)
    return False


@app.before_request
def _security_checks():
    # Rate limit solo en endpoints de chat (protege el crédito de Gemini)
    if request.path.startswith('/api/chat'):
        ip = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()
        if _check_rate_limit(ip, _RL_MAX_API):
            return jsonify({'ok': False, 'error': 'Demasiadas solicitudes. Esperá un minuto.'}), 429


@app.after_request
def _security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# Rutas JSON/HTML específicas primero (antes del catch-all /modules/…)
from routes.auth import bp as auth_bp
from routes.pages import bp as pages_bp
from routes.api.chat import bp as chat_bp
from routes.api.chat_route import bp as chat_route_bp
from routes.api.chat_threads import bp as chat_threads_bp
from routes.api.ventas_dt import bp as ventas_dt_bp
from routes.api.chat_script import bp as chat_script_bp
from routes.api.stats import bp as stats_bp
from routes.api.ventas_kpi import bp as ventas_kpi_bp
from routes.reports_modules import bp as reports_modules_bp

app.register_blueprint(auth_bp)
app.register_blueprint(pages_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(chat_route_bp)
app.register_blueprint(chat_threads_bp)
app.register_blueprint(ventas_dt_bp)
app.register_blueprint(chat_script_bp)
app.register_blueprint(stats_bp)
app.register_blueprint(ventas_kpi_bp)
app.register_blueprint(reports_modules_bp)


@app.teardown_appcontext
def _teardown_db_conn(_exc):
    from services.db import close_request_connection

    close_request_connection()


@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory(os.path.join(PUBLIC_DIR, 'assets'), filename)


@app.route('/modules/<path:filename>')
def serve_modules_static(filename):
    from flask import abort

    if filename.endswith('.php'):
        abort(404)
    return send_from_directory(os.path.join(PUBLIC_DIR, 'modules'), filename)


if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', '1') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)
