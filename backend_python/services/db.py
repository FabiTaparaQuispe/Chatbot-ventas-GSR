import os
import re
from contextvars import ContextVar
from typing import Any

import pymysql
import pymysql.cursors
from dotenv import load_dotenv

# Conexión por request para contextos sin Flask (FastAPI, scripts, workers)
_ctx_conn: ContextVar = ContextVar('_db_conn', default=None)

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'), override=False)

_G_CONN_KEY = '_pymysql_conn'


def _parse_dsn() -> dict[str, Any]:
    dsn = os.getenv('DB_DSN', 'mysql:host=127.0.0.1;port=3306;dbname=cia2026;charset=utf8mb4')
    user = os.getenv('DB_USER', 'root')
    password = os.getenv('DB_PASS', '')

    host = '127.0.0.1'
    port = 3306
    dbname = 'cia2026'
    charset = 'utf8mb4'

    m = re.search(r'host=([^;]+)', dsn)
    if m:
        host = m.group(1)
    m = re.search(r'port=(\d+)', dsn)
    if m:
        port = int(m.group(1))
    m = re.search(r'dbname=([^;]+)', dsn, re.IGNORECASE)
    if m:
        dbname = m.group(1)
    m = re.search(r'charset=([^;]+)', dsn, re.IGNORECASE)
    if m:
        charset = m.group(1).strip()

    # PyMySQL usa `charset` para decodificar bytes del servidor. Si el DSN sigue en
    # latin1 (legado XAMPP/PHP) pero los textos en tablas son UTF-8, aparece mojibake
    # (ej. CAMPIÃ'A en lugar de CAMPIÑA). Forzamos utf8mb4 en el cliente alineado con SET NAMES.
    if charset.lower() in ('latin1', 'latin2', 'iso8859-1', 'iso-8859-1', 'cp1252'):
        charset = 'utf8mb4'

    return {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'database': dbname,
        'charset': charset,
    }


def _create_connection() -> pymysql.connections.Connection:
    cfg = _parse_dsn()
    conn = pymysql.connect(
        host=cfg['host'],
        port=cfg['port'],
        user=cfg['user'],
        password=cfg['password'],
        database=cfg['database'],
        charset=cfg['charset'],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        use_unicode=True,
        init_command='SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci',
    )
    try:
        with conn.cursor() as cur:
            cur.execute('SET SESSION max_execution_time = 120000')
    except Exception:
        pass
    return conn


def get_connection() -> pymysql.connections.Connection:
    """
    Una conexión por petición HTTP (Flask `g`). No reutilizar un único socket global:
    con peticiones concurrentes PyMySQL falla (p. ej. WinError 10038, packet sequence wrong).
    """
    try:
        from flask import g, has_request_context

        if has_request_context():
            conn = getattr(g, _G_CONN_KEY, None)
            if conn is not None:
                try:
                    conn.ping(reconnect=True)
                    return conn
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    setattr(g, _G_CONN_KEY, None)
            conn = _create_connection()
            setattr(g, _G_CONN_KEY, conn)
            return conn
    except ImportError:
        pass

    # FastAPI / scripts: conexión por contexto de ejecución (ContextVar)
    conn = _ctx_conn.get()
    if conn is not None:
        try:
            conn.ping(reconnect=True)
            return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            _ctx_conn.set(None)
    conn = _create_connection()
    _ctx_conn.set(conn)
    return conn


def close_request_connection() -> None:
    """Cerrar la conexión de esta petición."""
    try:
        from flask import g, has_request_context

        if has_request_context():
            conn = getattr(g, _G_CONN_KEY, None)
            if conn is None:
                return
            try:
                conn.close()
            except Exception:
                pass
            try:
                delattr(g, _G_CONN_KEY)
            except Exception:
                setattr(g, _G_CONN_KEY, None)
            return
    except ImportError:
        pass

    # FastAPI / scripts
    conn = _ctx_conn.get()
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        _ctx_conn.set(None)


def db_label() -> str:
    dsn = os.getenv('DB_DSN', '')
    m = re.search(r'dbname=([^;]+)', dsn, re.IGNORECASE)
    return m.group(1) if m else 'cia2026'
