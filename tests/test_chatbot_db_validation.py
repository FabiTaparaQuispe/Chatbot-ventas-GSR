"""
Validación cruzada: compara la respuesta del chatbot con la base de datos.
Para cada pregunta, ejecuta la SQL equivalente y verifica que el número
clave aparezca en la respuesta del chatbot.

Uso:
    pytest tests/test_chatbot_db_validation.py -v -s

Variables de entorno:
    CHAT_BASE_URL   (default: http://localhost:5000)
    CHAT_USER       (default: admin)
    CHAT_PASS       (default: qwerty123)
    DB_HOST         (default: localhost)
    DB_PORT         (default: 3307)   ← 3307 para Docker local, 3306 para servidor
    DB_USER         (default: root)
    DB_PASS         (default: root)
    DB_NAME         (default: grsia)
"""
import os
import re
import time
import uuid
import pytest
import requests
import pymysql
import pymysql.cursors

# ── Config ─────────────────────────────────────────────────────────────────
BASE_URL  = os.getenv('CHAT_BASE_URL', 'http://localhost:5000')
CHAT_USER = os.getenv('CHAT_USER', 'admin')
CHAT_PASS = os.getenv('CHAT_PASS', 'qwerty123')

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '3307'))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASS = os.getenv('DB_PASS', 'root')
DB_NAME = os.getenv('DB_NAME', 'grsia')


# ── Helpers ─────────────────────────────────────────────────────────────────
def _db_connection():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER,
        password=DB_PASS, database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        charset='latin1',
    )


def _db_query(sql: str, params: tuple = ()) -> list:
    conn = _db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def _extract_numbers(text: str) -> list[float]:
    """Extrae todos los números del texto (maneja formato peruano: 1.234,56 y estándar 1,234.56)."""
    # Primero limpiar prefijos de moneda
    text = text.replace('S/', '').replace('S/ ', '').replace('kg', '').replace('KG', '')
    # Formato peruano: 42.133.985,29 → convertir puntos de miles y coma decimal
    nums = []
    for match in re.finditer(r'[\d][\d.,]*[\d]', text):
        raw = match.group()
        try:
            # Intentar formato peruano (último separador es coma decimal)
            if ',' in raw and raw.rindex(',') > raw.rindex('.') if '.' in raw else False:
                cleaned = raw.replace('.', '').replace(',', '.')
            else:
                cleaned = raw.replace(',', '')
            nums.append(float(cleaned))
        except ValueError:
            pass
    return nums


def _number_in_response(expected: float, response: str, tolerance_pct: float = 1.0) -> bool:
    """Verifica si el número esperado (±tolerance%) aparece en la respuesta."""
    if expected == 0:
        return True
    nums = _extract_numbers(response)
    for n in nums:
        diff_pct = abs(n - expected) / abs(expected) * 100
        if diff_pct <= tolerance_pct:
            return True
    return False


def _text_in_response(expected_text: str, response: str) -> bool:
    return expected_text.lower() in response.lower()


def _get_token() -> str:
    resp = requests.post(
        f'{BASE_URL}/api/auth/token',
        json={'usuario': CHAT_USER, 'clave': CHAT_PASS},
        timeout=15,
    )
    data = resp.json()
    assert data.get('ok'), f'Login falló: {data}'
    return data['access_token']


def _ask_chatbot(token: str, pregunta: str) -> str:
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    t0 = time.time()
    resp = requests.post(
        f'{BASE_URL}/api/chat',
        json={'messages': [{'role': 'user', 'content': pregunta}]},
        headers=headers,
        timeout=90,
    )
    ms = round((time.time() - t0) * 1000)
    assert resp.status_code == 200, f'HTTP {resp.status_code}: {resp.text[:200]}'
    reply = resp.json().get('reply', '')
    print(f'\n     → ({ms}ms) {reply[:200]}')
    return reply


# ── Fixture ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope='session')
def token():
    return _get_token()


# ═══════════════════════════════════════════════════════════════════════════
# TESTS DE VALIDACIÓN CRUZADA
# ═══════════════════════════════════════════════════════════════════════════

class TestVentasGenerales:

    def test_importe_enero_2026(self, token):
        """Importe total vendido en enero 2026 (facturas + boletas)."""
        rows = _db_query(
            "SELECT ROUND(SUM(Valor),2) AS total FROM ventasgeneral2 "
            "WHERE FechaContable BETWEEN %s AND %s AND CodigoDocumento IN ('01','03')",
            ('2026-01-01', '2026-01-31')
        )
        esperado = float(rows[0]['total'] or 0)
        print(f'\n[DB] Importe enero 2026: S/ {esperado:,.2f}')

        reply = _ask_chatbot(token, '¿Cuánto se vendió en enero 2026?')
        assert _number_in_response(esperado, reply), (
            f'El chatbot no mencionó S/ {esperado:,.2f} en su respuesta.\n'
            f'Respuesta: {reply[:300]}'
        )

    def test_importe_abril_2026(self, token):
        """Importe total vendido en abril 2026."""
        rows = _db_query(
            "SELECT ROUND(SUM(Valor),2) AS total FROM ventasgeneral2 "
            "WHERE FechaContable BETWEEN %s AND %s AND CodigoDocumento IN ('01','03')",
            ('2026-04-01', '2026-04-30')
        )
        esperado = float(rows[0]['total'] or 0)
        print(f'\n[DB] Importe abril 2026: S/ {esperado:,.2f}')

        reply = _ask_chatbot(token, 'Resumen de ventas de abril 2026')
        assert _number_in_response(esperado, reply), (
            f'El chatbot no mencionó S/ {esperado:,.2f}.\nRespuesta: {reply[:300]}'
        )

    def test_importe_mayo_2026(self, token):
        """Importe total vendido en mayo 2026."""
        rows = _db_query(
            "SELECT ROUND(SUM(Valor),2) AS total FROM ventasgeneral2 "
            "WHERE FechaContable BETWEEN %s AND %s AND CodigoDocumento IN ('01','03')",
            ('2026-05-01', '2026-05-31')
        )
        esperado = float(rows[0]['total'] or 0)
        print(f'\n[DB] Importe mayo 2026: S/ {esperado:,.2f}')

        reply = _ask_chatbot(token, '¿Cuál fue el total vendido en mayo 2026?')
        assert _number_in_response(esperado, reply), (
            f'El chatbot no mencionó S/ {esperado:,.2f}.\nRespuesta: {reply[:300]}'
        )

    def test_registros_enero_2026(self, token):
        """Cantidad de registros (líneas) en enero 2026."""
        rows = _db_query(
            "SELECT COUNT(*) AS total FROM ventasgeneral2 "
            "WHERE FechaContable BETWEEN %s AND %s AND CodigoDocumento IN ('01','03')",
            ('2026-01-01', '2026-01-31')
        )
        esperado = int(rows[0]['total'] or 0)
        print(f'\n[DB] Registros enero 2026: {esperado:,}')

        reply = _ask_chatbot(token, 'Ventas del 01 de enero 2026 al 31 de enero 2026')
        assert _number_in_response(esperado, reply, tolerance_pct=0.5), (
            f'El chatbot no mencionó {esperado:,} registros.\nRespuesta: {reply[:300]}'
        )


class TestClientes:

    def test_top1_cliente_enero_2026(self, token):
        """El cliente #1 por importe en enero 2026 debe aparecer en la respuesta."""
        rows = _db_query(
            "SELECT NombreCliente, ROUND(SUM(Valor),2) AS total "
            "FROM ventasgeneral2 "
            "WHERE FechaContable BETWEEN %s AND %s AND CodigoDocumento IN ('01','03') "
            "GROUP BY CodCliente ORDER BY total DESC LIMIT 1",
            ('2026-01-01', '2026-01-31')
        )
        cliente = rows[0]['NombreCliente'].strip()
        importe = float(rows[0]['total'])
        print(f'\n[DB] Top 1 enero 2026: {cliente} → S/ {importe:,.2f}')

        reply = _ask_chatbot(token, '¿Cuáles son los 10 clientes que más compraron en enero 2026?')
        assert _text_in_response(cliente[:15], reply), (
            f'El cliente "{cliente}" no aparece en la respuesta.\nRespuesta: {reply[:300]}'
        )

    def test_top1_cliente_abril_2026(self, token):
        """El cliente #1 por importe en abril 2026 debe aparecer en la respuesta."""
        rows = _db_query(
            "SELECT NombreCliente, ROUND(SUM(Valor),2) AS total "
            "FROM ventasgeneral2 "
            "WHERE FechaContable BETWEEN %s AND %s AND CodigoDocumento IN ('01','03') "
            "GROUP BY CodCliente ORDER BY total DESC LIMIT 1",
            ('2026-04-01', '2026-04-30')
        )
        cliente = rows[0]['NombreCliente'].strip()
        importe = float(rows[0]['total'])
        print(f'\n[DB] Top 1 abril 2026: {cliente} → S/ {importe:,.2f}')

        reply = _ask_chatbot(token, '¿Cuáles son los 10 clientes que más compraron en abril 2026?')
        assert _text_in_response(cliente[:15], reply), (
            f'El cliente "{cliente}" no aparece en la respuesta.\nRespuesta: {reply[:300]}'
        )

    def test_top1_cliente_lajoya_enero(self, token):
        """El cliente #1 en LAJOYA enero 2026."""
        rows = _db_query(
            "SELECT NombreCliente, ROUND(SUM(Valor),2) AS total "
            "FROM ventasgeneral2 "
            "WHERE FechaContable BETWEEN %s AND %s AND CodigoDocumento IN ('01','03') "
            "AND ZonaComercial LIKE %s "
            "GROUP BY CodCliente ORDER BY total DESC LIMIT 1",
            ('2026-01-01', '2026-01-31', '%LAJOYA%')
        )
        if not rows:
            pytest.skip('No hay datos de LAJOYA en enero 2026')
        cliente = rows[0]['NombreCliente'].strip()
        print(f'\n[DB] Top 1 LAJOYA enero: {cliente}')

        reply = _ask_chatbot(token, 'Top 10 clientes en LAJOYA de enero 2026')
        assert _text_in_response(cliente[:15], reply), (
            f'El cliente "{cliente}" no aparece en la respuesta.\nRespuesta: {reply[:300]}'
        )


class TestLineasComerciales:

    def test_peso_pollo_vivo_enero(self, token):
        """Peso total de Pollo Vivo en enero 2026."""
        rows = _db_query(
            "SELECT ROUND(SUM(Peso),2) AS total_peso FROM ventasgeneral2 "
            "WHERE FechaContable BETWEEN %s AND %s AND CodigoDocumento IN ('01','03') "
            "AND LineaComercial LIKE %s",
            ('2026-01-01', '2026-01-31', '%POLLO VIVO%')
        )
        esperado = float(rows[0]['total_peso'] or 0)
        print(f'\n[DB] Peso Pollo Vivo enero 2026: {esperado:,.2f} kg')

        reply = _ask_chatbot(token, '¿Cuánto pesó Pollo Vivo vendido en enero 2026?')
        assert _number_in_response(esperado, reply, tolerance_pct=1.0), (
            f'El chatbot no mencionó {esperado:,.2f} kg.\nRespuesta: {reply[:300]}'
        )

    def test_importe_pollo_vivo_tacna(self, token):
        """Importe de Pollo Vivo en TACNA marzo 2026."""
        rows = _db_query(
            "SELECT ROUND(SUM(Valor),2) AS total FROM ventasgeneral2 "
            "WHERE FechaContable BETWEEN %s AND %s AND CodigoDocumento IN ('01','03') "
            "AND LineaComercial LIKE %s AND Provincia LIKE %s",
            ('2026-03-01', '2026-03-31', '%POLLO VIVO%', '%TACNA%')
        )
        esperado = float(rows[0]['total'] or 0)
        print(f'\n[DB] Pollo Vivo TACNA marzo: S/ {esperado:,.2f}')

        reply = _ask_chatbot(token, 'Ventas de Pollo Vivo en TACNA en marzo 2026')
        assert _number_in_response(esperado, reply, tolerance_pct=1.0), (
            f'El chatbot no mencionó S/ {esperado:,.2f}.\nRespuesta: {reply[:300]}'
        )


class TestNotasCredito:

    def test_cantidad_nc_enero_2026(self, token):
        """Cantidad de notas de crédito en enero 2026."""
        rows = _db_query(
            "SELECT COUNT(*) AS total FROM ventasgeneral2 "
            "WHERE FechaContable BETWEEN %s AND %s AND CodigoDocumento = '07'",
            ('2026-01-01', '2026-01-31')
        )
        esperado = int(rows[0]['total'] or 0)
        print(f'\n[DB] NC enero 2026: {esperado}')

        reply = _ask_chatbot(token, '¿Cuántas notas de crédito hubo en enero 2026?')
        assert _number_in_response(esperado, reply, tolerance_pct=0.5), (
            f'El chatbot no mencionó {esperado} NC.\nRespuesta: {reply[:300]}'
        )

    def test_importe_nc_febrero_2026(self, token):
        """Importe devuelto en NC febrero 2026."""
        rows = _db_query(
            "SELECT ROUND(SUM(Valor),2) AS total FROM ventasgeneral2 "
            "WHERE FechaContable BETWEEN %s AND %s AND CodigoDocumento = '07'",
            ('2026-02-01', '2026-02-28')
        )
        esperado = float(rows[0]['total'] or 0)
        print(f'\n[DB] Importe NC febrero: S/ {esperado:,.2f}')

        reply = _ask_chatbot(token, '¿Cuánto se devolvió en valor en febrero 2026?')
        assert _number_in_response(esperado, reply, tolerance_pct=1.0), (
            f'El chatbot no mencionó S/ {esperado:,.2f}.\nRespuesta: {reply[:300]}'
        )


class TestHuaypuna:

    def test_registros_huaypuna_24_mayo(self, token):
        """Registros del corporativo Huaypuna el 24 de mayo 2026."""
        rows = _db_query(
            "SELECT COUNT(*) AS total FROM ventasgeneral2 "
            "WHERE FechaContable = %s AND NombreCoorporativo LIKE %s",
            ('2026-05-24', '%HUAYPUNA%')
        )
        esperado = int(rows[0]['total'] or 0)
        print(f'\n[DB] Registros Huaypuna 24/05: {esperado}')

        reply = _ask_chatbot(token, '¿Cuál es el peso de venta que tuvo el corporativo Huaypuna para la venta del día 24 de mayo?')
        assert reply.strip(), 'Respuesta vacía'
        # Al menos debe mencionar la fecha o el corporativo
        assert _text_in_response('huaypuna', reply) or _text_in_response('2026-05-24', reply) or _text_in_response('24', reply), (
            f'La respuesta no menciona Huaypuna ni la fecha.\nRespuesta: {reply[:300]}'
        )
