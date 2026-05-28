"""Templates Jinja2 compartidas con url_for compatible con Flask."""
import os
from urllib.parse import urlencode

from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

_TEMPLATES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'templates')
)

templates = Jinja2Templates(directory=_TEMPLATES_DIR)

# Mapeo Flask blueprint.funcion → path FastAPI
_ROUTE_MAP: dict[str, str] = {
    'pages.index': '/',
    'auth.login': '/login',
    'auth.logout': '/logout',
    'pages.change_password': '/api/change_password',
}


@pass_context
def _url_for(context: dict, name: str, **kwargs) -> str:
    """Reemplaza url_for de Flask en los templates Jinja2."""
    path = _ROUTE_MAP.get(name)
    if path is None:
        # Intentar con el nombre FastAPI directamente
        try:
            request = context.get('request')
            if request:
                return str(request.url_for(name, **kwargs))
        except Exception:
            pass
        return f'/{name}'
    if kwargs:
        path = f'{path}?{urlencode(kwargs)}'
    return path


templates.env.globals['url_for'] = _url_for
