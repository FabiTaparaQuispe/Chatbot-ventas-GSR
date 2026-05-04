from __future__ import annotations

import re
from urllib.parse import quote_plus

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from app.settings import get_settings


def _parse_pdo_mysql_dsn(dsn: str) -> tuple[str, int, str, str]:
    """mysql:host=...;port=...;dbname=...;charset=..."""
    if not dsn.lower().startswith("mysql:"):
        raise ValueError("DB_DSN debe comenzar con mysql:")
    body = dsn.split(":", 1)[1]
    parts: dict[str, str] = {}
    for seg in body.split(";"):
        seg = seg.strip()
        if not seg or "=" not in seg:
            continue
        k, v = seg.split("=", 1)
        parts[k.strip().lower()] = v.strip()
    host = parts.get("host", "127.0.0.1")
    port = int(parts.get("port", "3306"))
    dbname = parts.get("dbname", "cia2026")
    charset = parts.get("charset", "utf8mb4")
    return host, port, dbname, charset


def _build_sqlalchemy_url() -> str:
    s = get_settings()
    host, port, db, charset = _parse_pdo_mysql_dsn(s.db_dsn)
    user = quote_plus(s.db_user)
    pw = quote_plus(s.db_pass)
    return f"mysql+pymysql://{user}:{pw}@{host}:{port}/{db}?charset={charset}"


def db_label_from_dsn() -> str:
    m = re.search(r"dbname=([^;]+)", get_settings().db_dsn, flags=re.I)
    return m.group(1).strip() if m else "cia2026"


_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        eng = create_engine(
            _build_sqlalchemy_url(),
            pool_pre_ping=True,
            pool_recycle=300,
        )

        @event.listens_for(eng, "connect")
        def _on_connect(dbapi_conn, _record) -> None:  # type: ignore[no-untyped-def]
            cur = dbapi_conn.cursor()
            try:
                cur.execute("SET SESSION max_execution_time = 120000")
            except Exception:
                pass
            finally:
                cur.close()

        _engine = eng

    return _engine
