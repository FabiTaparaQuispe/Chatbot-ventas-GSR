"""
Pruebas automáticas del chatbot — 58 preguntas reales por categoría.
Uso:
    pip install pytest requests
    pytest tests/test_chatbot_auto.py -v                          # local
    pytest tests/test_chatbot_auto.py -v --tb=short               # resumen corto
    pytest tests/test_chatbot_auto.py -v -k "clientes"            # solo una categoría

Variables de entorno opcionales:
    CHAT_BASE_URL  (default: http://localhost:5000)
    CHAT_USER      (default: admin)
    CHAT_PASS      (default: qwerty123)
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL  = os.getenv('CHAT_BASE_URL', 'http://localhost:5000')
CHAT_USER = os.getenv('CHAT_USER', 'admin')
CHAT_PASS = os.getenv('CHAT_PASS', 'qwerty123')

# Prefijo para identificar estos threads en el historial
THREAD_PREFIX = 'pytest_auto'

# ── 58 preguntas organizadas por categoría ─────────────────────────────────
PREGUNTAS = [

    # ── 1. Fechas / rangos ──────────────────────────────────────────────────
    ('fechas', '¿Cuánto se vendió en enero 2026?'),
    ('fechas', 'Ventas del mes de abril (sin año)'),
    ('fechas', 'Ventas del 15 de marzo (día único, sin año)'),
    ('fechas', 'Ventas del 01 de enero 2026 al 31 de enero 2026'),
    ('fechas', 'Ventas de febrero 2026 (año bisiesto)'),

    # ── 2. Líneas comerciales ───────────────────────────────────────────────
    ('lineas', 'Ventas de Pollo Vivo en enero 2026'),
    ('lineas', 'Ventas de Pollo Vivo en TACNA en marzo 2026'),
    ('lineas', 'Ventas de Embutidos en febrero 2026'),
    ('lineas', '¿Cuánto pesó Pollo Vivo vendido en abril 2026?'),
    ('lineas', 'Resumen de ventas por línea comercial de enero 2026'),

    # ── 3. Clientes ─────────────────────────────────────────────────────────
    ('clientes', 'Top 10 clientes en LAJOYA de enero 2026'),
    ('clientes', 'Top 5 clientes en TACNA de febrero 2026'),
    ('clientes', 'Top 10 clientes con más venta en la provincia de Arequipa en marzo 2026'),
    ('clientes', '¿Cuáles son los 10 clientes que más compraron en abril 2026?'),
    ('clientes', 'Los 5 mejores clientes por peso en enero 2026'),

    # ── 4. Zona / Provincia ─────────────────────────────────────────────────
    ('zona', '¿Cuánto se vendió en la zona AQP en enero 2026?'),
    ('zona', 'Ventas en la provincia de Tacna en febrero 2026'),
    ('zona', 'Resumen de ventas por provincia en marzo 2026'),
    ('zona', '¿Qué provincias compraron Pollo Vivo en abril 2026?'),
    ('zona', 'Ventas en Moquegua en enero 2026'),

    # ── 5. Precios ──────────────────────────────────────────────────────────
    ('precios', '¿Cuáles son los precios de venta más altos del 01 de enero 2026 para Pollo Vivo?'),
    ('precios', 'Precio promedio por kg de Pollo Vivo en enero 2026'),
    ('precios', '¿Qué cliente pagó más caro por kg en LAJOYA en febrero 2026?'),
    ('precios', 'Precio por kg de Embutidos por provincia en marzo 2026'),

    # ── 6. Notas de crédito ─────────────────────────────────────────────────
    ('notas_credito', '¿Cuántas notas de crédito hubo en enero 2026?'),
    ('notas_credito', '¿Cuánto se devolvió en valor en febrero 2026?'),
    ('notas_credito', 'Clientes con nota de crédito en marzo 2026'),
    ('notas_credito', '¿Cuál es la venta neta de enero 2026? (facturas menos NC)'),

    # ── 7. Cliente específico ───────────────────────────────────────────────
    ('cliente_especifico', 'Ventas del cliente PACHO PACHO PEDRO PABLO en enero 2026'),
    ('cliente_especifico', '¿Cuánto compró SALAZAR MACHICAO IVONEE PATRICIA en el primer trimestre 2026?'),
    ('cliente_especifico', 'Facturas del cliente SULLCA QUISPE MARTHA de febrero 2026'),

    # ── 8. Documentos ───────────────────────────────────────────────────────
    ('documentos', 'Busca la factura número 3750004023'),
    ('documentos', '¿Qué contiene la boleta 3750004023?'),

    # ── 9. Análisis temporal ────────────────────────────────────────────────
    ('temporal', 'Resumen de enero, febrero y marzo 2026 por mes'),
    ('temporal', '¿Cuánto se vendió por semana en enero 2026?'),
    ('temporal', '¿Qué día de enero 2026 se vendió más?'),
    ('temporal', 'Comparar ventas de Pollo Vivo en enero 2026 vs febrero 2026'),

    # ── 10. Abril / Mayo 2026 ───────────────────────────────────────────────
    ('abril_mayo', '¿Cuál fue el total vendido en valor y peso en lo que va de mayo 2026?'),
    ('abril_mayo', 'Top 10 clientes del mes de mayo 2026 por valor'),
    ('abril_mayo', '¿Qué línea comercial vendió más en abril 2026?'),
    ('abril_mayo', '¿Cuánto representan las notas de crédito sobre el total vendido en abril 2026?'),
    ('abril_mayo', 'Resumen de ventas por provincia en abril 2026'),
    ('abril_mayo', '¿Cuál es el precio promedio por kg de Pollo Vivo en mayo 2026?'),
    ('abril_mayo', '¿Qué zonas de precio tuvieron más venta en abril 2026?'),
    ('abril_mayo', 'Los 5 clientes con mayor volumen en kg en abril 2026'),

    # ── 11. Historial del chatbot ───────────────────────────────────────────
    ('historial', '¿Quién es el usuario que más preguntas ha hecho este mes?'),
    ('historial', '¿Cuántas preguntas se hicieron en total en abril 2026?'),
    ('historial', '¿Cuántas preguntas se hicieron por día en la semana del 5 al 11 de mayo 2026?'),
    ('historial', '¿Cuáles fueron las últimas 10 preguntas del administrador?'),
    ('historial', 'Muéstrame las preguntas del usuario fabiola.tapara en abril 2026'),
    ('historial', '¿Quiénes son los 5 usuarios que más usaron el chatbot en mayo 2026?'),
    ('historial', 'Busca conversaciones donde se preguntó sobre notas de crédito'),
    ('historial', '¿Cuántas conversaciones se iniciaron en abril 2026?'),
    ('historial', '¿Cuál fue el día con más actividad en el chatbot en mayo 2026?'),

    # ── 12. Corporativo Huaypuna ────────────────────────────────────────────
    ('huaypuna', '¿Cuáles son los números de documentos de la venta de Huaypuna Mamani para el día 24 de mayo?'),
    ('huaypuna', '¿Cuáles son los códigos de ítem para la venta de Huaypuna Mamani del 24 de mayo?'),
    ('huaypuna', '¿Cuál es el peso de venta que tuvo el corporativo Huaypuna para la venta del día 24 de mayo?'),
    ('huaypuna', '¿Qué clientes pertenecen al corporativo Huaypuna Mamani Rony Angel?'),
]

TOTAL = len(PREGUNTAS)


# ── Fixture: token JWT (una sola vez por sesión) ───────────────────────────
@pytest.fixture(scope='session')
def token():
    resp = requests.post(
        f'{BASE_URL}/api/auth/token',
        json={'usuario': CHAT_USER, 'clave': CHAT_PASS},
        timeout=15,
    )
    assert resp.status_code == 200, f'Login falló HTTP {resp.status_code}: {resp.text[:200]}'
    data = resp.json()
    assert data.get('ok'), f'Login rechazado: {data}'
    print(f'\n✓ JWT obtenido para {CHAT_USER} | {TOTAL} preguntas a ejecutar')
    return data['access_token']


def _save_to_historial(token: str, thread_id: str, pregunta: str, reply: str, categoria: str):
    """Guarda la pregunta y respuesta en app_chat_threads para que aparezca en el historial."""
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    titulo = f'[{categoria}] {pregunta[:60]}'
    payload = {
        'id': thread_id,
        'title': titulo,
        'messages': [
            {'role': 'user',      'content': pregunta},
            {'role': 'assistant', 'content': reply},
        ],
    }
    try:
        requests.post(
            f'{BASE_URL}/api/chat_threads',
            json=payload,
            headers=headers,
            timeout=15,
        )
    except Exception:
        pass  # no bloquear el test si falla el guardado


def _send_question(token: str, pregunta: str, categoria: str = '') -> dict:
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    # Thread único por pregunta para que aparezca individualmente en el historial
    thread_id = f'{THREAD_PREFIX}_{uuid.uuid4().hex[:12]}'
    payload = {'messages': [{'role': 'user', 'content': pregunta}]}
    t0 = time.time()
    try:
        resp = requests.post(
            f'{BASE_URL}/api/chat',
            json=payload,
            headers=headers,
            timeout=90,
        )
        ms = round((time.time() - t0) * 1000)
        if resp.status_code == 200:
            data = resp.json()
            reply = data.get('reply', '')
            if reply:
                _save_to_historial(token, thread_id, pregunta, reply, categoria)
            return {'reply': reply, 'status': 200, 'ms': ms}
        return {'reply': '', 'status': resp.status_code, 'ms': ms, 'error': resp.text[:300]}
    except requests.exceptions.Timeout:
        return {'reply': '', 'status': -1, 'ms': 90000, 'error': 'Timeout (>90s)'}
    except Exception as e:
        return {'reply': '', 'status': -2, 'ms': 0, 'error': str(e)}


# ── Tests parametrizados ───────────────────────────────────────────────────
@pytest.mark.parametrize(
    'idx,categoria,pregunta',
    [(i, cat, q) for i, (cat, q) in enumerate(PREGUNTAS, 1)],
    ids=[f'{i:02d}-{cat}-{q[:40]}' for i, (cat, q) in enumerate(PREGUNTAS, 1)],
)
def test_pregunta(token, idx, categoria, pregunta):
    resultado = _send_question(token, pregunta, categoria)
    status = resultado['status']
    reply  = resultado.get('reply', '')
    ms     = resultado['ms']

    print(f'\n[{idx:02d}/{TOTAL}] [{categoria}] {pregunta[:70]}')
    if reply:
        print(f'     → ({ms}ms) {reply[:150]}')
    else:
        print(f'     → ERROR HTTP {status} ({ms}ms): {resultado.get("error", "")}')

    assert status == 200, (
        f'[{categoria}] Pregunta #{idx} devolvió HTTP {status}: {resultado.get("error", "")}\n'
        f'Pregunta: {pregunta}'
    )
    assert reply.strip(), (
        f'[{categoria}] Pregunta #{idx} devolvió respuesta vacía\n'
        f'Pregunta: {pregunta}'
    )
    assert len(reply) >= 5, (
        f'[{categoria}] Pregunta #{idx} respuesta muy corta ({len(reply)} chars): {reply!r}'
    )
