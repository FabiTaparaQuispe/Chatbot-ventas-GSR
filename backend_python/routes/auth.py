from flask import Blueprint, render_template, request, session, redirect, url_for
from werkzeug.security import check_password_hash
from services.db import get_connection

bp = Blueprint('auth', __name__)

VALID_ROLES = {'admin', 'administrador', 'gerencia', 'estrategico', 'tactico', 'operativo', 'analista', 'lector'}


def normalize_role(r: str) -> str:
    r = r.lower().strip()
    if r == 'gerente':
        return 'gerencia'
    if r in ('estratégico',):
        return 'estrategico'
    if r in ('táctico', 'usuario2'):
        return 'tactico'
    return r


@bp.route('/login', methods=['GET', 'POST'])
@bp.route('/login.php', methods=['GET', 'POST'])
def login():
    if session.get('active'):
        return redirect('/')

    error = ''
    if request.method == 'POST':
        u = request.form.get('usuario', '').strip()
        c = request.form.get('clave', '')
        if not u or not c:
            error = 'Usuario y contraseña requeridos.'
        else:
            try:
                conn = get_connection()
                with conn.cursor() as cur:
                    cur.execute(
                        'SELECT password_hash, is_active, role, display_name FROM app_users WHERE username = %s LIMIT 1',
                        (u,)
                    )
                    row = cur.fetchone()
                ok = False
                role = ''
                display_name = ''
                if row and int(row.get('is_active') or 0) == 1:
                    h = str(row.get('password_hash') or '')
                    if h and check_password_hash(h, c):
                        ok = True
                        with conn.cursor() as cur:
                            cur.execute('UPDATE app_users SET last_login_at = NOW() WHERE username = %s', (u,))
                        role = normalize_role(str(row.get('role') or ''))
                        if not role:
                            role = 'lector'
                        display_name = str(row.get('display_name') or '').strip()
                if ok:
                    session.clear()
                    session['active'] = True
                    session['usuario'] = u
                    session['role'] = role
                    session['display_name'] = display_name
                    return redirect('/')
                error = 'Usuario o contraseña incorrectos.'
            except Exception as e:
                error = f'No se pudo validar el acceso. Detalle: {e}'

    return render_template('login.html', error=error,
                           app_name='Ventas · cia2026',
                           app_company='GRANJA RINCONADA DEL SUR S.A.')


@bp.route('/logout')
@bp.route('/logout.php')
def logout():
    session.clear()
    return redirect('/login')
