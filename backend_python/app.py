import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, send_from_directory
from dotenv import load_dotenv

# En Windows es común que queden variables viejas en el entorno.
# Forzamos que `.env` tenga prioridad para que cambios de modelo/proveedor apliquen tras reiniciar.
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'), override=True)

PUBLIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'public'))

app = Flask(
    __name__,
    template_folder='templates',
    static_folder=None,
)
app.secret_key = os.getenv('FLASK_SECRET', 'cambiar-en-produccion-usar-valor-aleatorio-largo')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

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
