import os
import re
import pymysql
import pymysql.cursors
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

_connection = None


def get_connection() -> pymysql.connections.Connection:
    global _connection
    if _connection is not None:
        try:
            _connection.ping(reconnect=True)
            return _connection
        except Exception:
            _connection = None

    dsn = os.getenv('DB_DSN', 'mysql:host=127.0.0.1;port=3306;dbname=cia2026;charset=latin1')
    user = os.getenv('DB_USER', 'root')
    password = os.getenv('DB_PASS', '')

    host = '127.0.0.1'
    port = 3306
    dbname = 'cia2026'
    charset = 'latin1'

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
        charset = m.group(1)

    _connection = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=dbname,
        charset=charset,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        init_command='SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci',
    )

    try:
        with _connection.cursor() as cur:
            cur.execute('SET SESSION max_execution_time = 120000')
    except Exception:
        pass

    return _connection


def db_label() -> str:
    dsn = os.getenv('DB_DSN', '')
    m = re.search(r'dbname=([^;]+)', dsn, re.IGNORECASE)
    return m.group(1) if m else 'cia2026'
