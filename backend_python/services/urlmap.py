"""
URLs canónicas (sin .php). Las rutas legacy *.php siguen registradas en paralelo en los blueprints.
"""
from __future__ import annotations

# API
API_CHAT = '/api/chat'
API_CHAT_THREADS = '/api/chat_threads'
API_VENTAS_DT = '/api/ventasgeneral'
API_STATS = '/api/stats'

# Bundle dinámico (inyecta __VENTAS_CHAT + chat_assistant.js)
MODULES_CHAT_ASSISTANT = '/modules/chat-assistant'

# Informes con implementación completa
REPORT_VENTASGENERAL_RESUMEN_TABLA = '/modules/ventasgeneral/resumen-tabla'
REPORT_VENTASGENERAL_BUSCAR_TABLA = '/modules/ventasgeneral/buscar-tabla'

# Informes aún no portados a HTML completo (placeholder con mismo query que esperaba el módulo PHP)
REPORT_SLUG_PARETO_NC_ZONA = 'pareto-nc-zona'
REPORT_SLUG_PARETO_CLIENTES_ZONA = 'pareto-clientes-zona'
REPORT_SLUG_VENTAS_BARRAS_DIMENSION = 'ventas-barras-dimension'
REPORT_SLUG_VENTAS_COMPARATIVO = 'ventas-comparativo'
REPORT_SLUG_VENTAS_TOP_PRODUCTOS = 'ventas-top-productos'
REPORT_SLUG_VENTAS_TOP_CLIENTES_GLOBAL = 'ventas-top-clientes-global'
REPORT_SLUG_VENTAS_TOP_CLIENTES_NC = 'ventas-top-clientes-nc'
REPORT_SLUG_VENTAS_MIX_TDOC = 'ventas-mix-tdoc'
REPORT_SLUG_VENTAS_BARRAS_RUTA = 'ventas-barras-ruta'
REPORT_SLUG_VENTAS_BARRAS_CORPORATIVO = 'ventas-barras-corporativo'
REPORT_SLUG_VENTAS_SERIE_MENSUAL = 'ventas-serie-mensual'

REPORTS_PREFIX = '/modules/reports/'


def report_slug_url(slug: str, query: str) -> str:
    q = (query or '').strip()
    if q.startswith('?'):
        q = q[1:].lstrip()
    base = REPORTS_PREFIX + slug
    return base + ('?' + q if q else '')


def chat_assistant_config_dict(user_key: str) -> dict[str, str]:
    return {
        'chatApi': API_CHAT,
        'publicBase': '/',
        'modulesBase': '/modules/',
        'userKey': user_key,
        'threadsApi': API_CHAT_THREADS,
    }
