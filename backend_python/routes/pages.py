from flask import Blueprint, render_template, request, session, redirect
from functools import wraps

bp = Blueprint('pages', __name__)

APP_NAME = 'Ventas · cia2026'
APP_COMPANY = 'GRANJA RINCONADA DEL SUR S.A.'

ROLES_HOME_VENTAS = {'admin', 'gerencia', 'administrador', 'estrategico', 'tactico', 'operativo', 'analista'}
ROLES_VENTAS_GENERAL = ROLES_HOME_VENTAS | {'lector'}


def require_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('active'):
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated


def user_role() -> str:
    return str(session.get('role') or 'lector').lower().strip()


@bp.route('/')
@bp.route('/index.php')
@require_login
def index():
    page = request.args.get('page', '').strip()
    role = user_role()

    if not page:
        page = 'ventas' if role in ROLES_HOME_VENTAS else 'chatbot'

    if page == 'graficos':
        return redirect('/?page=chatbot')

    allowed = {'ventas', 'ventasgeneral2', 'chatbot', 'historial_preguntas', 'usuarios', 'gestion_usuarios'}
    if page not in allowed:
        page = 'ventas'

    if page == 'usuarios' and role != 'admin':
        return redirect('/')
    if page == 'gestion_usuarios' and role != 'administrador':
        return redirect('/')
    if page == 'historial_preguntas' and role not in ('estrategico', 'administrador'):
        return redirect('/')
    if page in ('ventas', 'ventasgeneral2') and role not in ROLES_VENTAS_GENERAL:
        return redirect('/')

    page_titles = {
        'chatbot': 'Chatbot',
        'historial_preguntas': 'Preguntas al chatbot',
        'usuarios': 'Usuarios',
        'gestion_usuarios': 'Creación de usuarios',
        'ventasgeneral2': 'Ventas general 2',
    }
    page_title = page_titles.get(page, 'Ventas general')

    load_ventas_assets = page in ('ventas', 'ventasgeneral2', 'usuarios', 'gestion_usuarios')
    skip_floating_chat = page == 'chatbot'
    body_class = ('app-page-chatbot' if page == 'chatbot'
                  else ('app-page-historial-chat' if page == 'historial_preguntas' else ''))

    usuario = session.get('usuario', '')
    nom_corto = ''
    if usuario:
        part = usuario.split('@')[0]
        part = part.replace('.', ' ').replace('_', ' ').replace('-', ' ').strip()
        if part:
            nom_corto = ', ' + part.capitalize()

    return render_template(
        f'pages/{page}.html',
        page=page,
        page_title=page_title,
        app_name=APP_NAME,
        app_company=APP_COMPANY,
        load_ventas_assets=load_ventas_assets,
        skip_floating_chat=skip_floating_chat,
        body_class=body_class,
        role=role,
        usuario=usuario,
        display_name=session.get('display_name', ''),
        nom_corto=nom_corto,
        ventas_public_base='/',
        ventas_modules_web_base='/modules/',
        ventas_chat_api_url='api/chat.php',
        ventas_chat_user_key=usuario or 'anon',
        roles_ventas_general=ROLES_VENTAS_GENERAL,
        roles_home_ventas=ROLES_HOME_VENTAS,
    )
