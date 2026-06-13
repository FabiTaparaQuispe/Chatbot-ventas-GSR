"""
Contract test — valida que las herramientas del chatbot cumplan su "contrato"
de interfaz: que devuelvan los campos esperados con los tipos correctos.

Si alguien renombra o cambia el tipo de un campo (ej. cumplimiento_pct -> cumplimiento,
o vendido_u -> vendido), este test FALLA con ValidationError ANTES de subir a producción
— el formato del chat no se rompe en silencio.

Correr:
    python -m pytest tests/contract_test.py -v

Variables de entorno (BD):
    DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME
"""
import json
import os
import sys
from pathlib import Path

import pytest

# Hacer importables los módulos de la app (services.*)
_BACKEND = Path(__file__).resolve().parents[1] / 'backend_python'
sys.path.insert(0, str(_BACKEND))

try:
    import pymysql
    from pydantic import BaseModel
except ImportError as e:  # pragma: no cover
    pytest.skip(f"Falta dependencia: {e}", allow_module_level=True)

try:
    from services.tool_executor import ToolExecutor
except Exception as e:  # pragma: no cover
    pytest.skip(f"No se pudo importar ToolExecutor: {e}", allow_module_level=True)

DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASS = os.getenv('DB_PASS', 'S3rv1d0r')
DB_NAME = os.getenv('DB_NAME', 'grsia')


# ── EL CONTRATO (esquema independiente de la app) ──────────────────────────
class FilaCumplimiento(BaseModel):
    cliente: str
    nombre: str
    item: str
    producto: str
    pedido_u: float
    vendido_u: float
    recorte: float
    cumplimiento_pct: float


class CumplimientoContract(BaseModel):
    tipo: str
    fecha_desde: str
    fecha_hasta: str
    total_pedido: float
    total_vendido: float
    total_recorte: float
    cumplimiento_total_pct: float
    total_filas: int
    filas: list[FilaCumplimiento]


def _conn():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
        database=DB_NAME, cursorclass=pymysql.cursors.DictCursor, charset='latin1',
    )


def test_contrato_cumplimiento_pedidos():
    """La herramienta cumplimiento_pedidos cumple su contrato de interfaz."""
    try:
        conn = _conn()
    except Exception as e:
        pytest.skip(f"No se pudo conectar a la BD: {e}")

    try:
        ex = ToolExecutor(conn)
        result_json = ex.execute('cumplimiento_pedidos', {
            'fecha_desde': '2026-05-01', 'fecha_hasta': '2026-05-31',
        })
        result = json.loads(result_json)
        assert not result.get('error'), f"La herramienta devolvió error: {result.get('error')}"
        # Valida el contrato: lanza ValidationError si falta o cambia un campo/tipo.
        CumplimientoContract(**result)
    finally:
        conn.close()


def test_contrato_detecta_campo_faltante():
    """Verifica que el contrato SÍ detecta un cambio (campo renombrado/faltante)."""
    from pydantic import ValidationError
    payload_roto = {
        'tipo': 'cumplimiento_pedidos',
        'fecha_desde': '2026-05-01',
        'fecha_hasta': '2026-05-31',
        'total_pedido': 100.0,
        'total_vendido': 98.0,
        'total_recorte': 2.0,
        # 'cumplimiento_total_pct' fue RENOMBRADO -> el contrato debe fallar
        'cumplimiento': 98.0,
        'total_filas': 0,
        'filas': [],
    }
    with pytest.raises(ValidationError):
        CumplimientoContract(**payload_roto)
