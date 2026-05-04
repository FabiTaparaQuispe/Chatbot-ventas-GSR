from __future__ import annotations

import base64
import zlib
from typing import Any
from urllib.parse import quote as urlquote

MAX_QUERY_PARAM_CHARS = 7200
MAX_DECOMPRESSED_BYTES = 524288


def encode_query_param(sql: str) -> str | None:
    sql_b = sql.encode("utf-8")
    compressed = zlib.compress(sql_b, 6)
    use_zip = len(compressed) < len(sql_b) and compressed
    payload = compressed if use_zip else sql_b
    flag = "1" if use_zip else "0"
    b64 = base64.b64encode(payload).decode("ascii")
    s = flag + b64.rstrip("=").translate(str.maketrans("+/", "-_"))
    if len(s) > MAX_QUERY_PARAM_CHARS:
        return None
    return s


def format_append_lines(bloques: list[str], public_base_url: str) -> list[str]:
    if not bloques:
        return []
    base = public_base_url.rstrip("/")
    if not base:
        return []
    lines = ["---", "Sentencia SQL ejecutada (texto plano):"]
    n = 0
    for sql in bloques:
        sql = sql.strip()
        if not sql:
            continue
        n += 1
        enc = encode_query_param(sql)
        if enc is not None:
            url = f"{base}/sql_texto.php?z=1&s={urlquote(enc, safe='')}"
            lines.append(f"Consulta {n}: {url}" if n > 1 else url)
        else:
            lines.append(
                f"Consulta {n}: (demasiado larga para enlace; ejecute la misma consulta desde el depurador SQL.)"
                if n > 1
                else "(Sentencia demasiado larga para enlace; ejecute la misma consulta desde el depurador SQL.)"
            )
    return lines


def _b64url_decode(data: str) -> bytes | None:
    data = data.translate(str.maketrans("-_", "+/"))
    pad = len(data) % 4
    if pad:
        data += "=" * (4 - pad)
    try:
        return base64.b64decode(data, validate=True)
    except Exception:
        return None


def decode_query_param(s: str) -> str | None:
    s = s.strip()
    if not s:
        return None
    flag = s[0]
    body = s[1:]
    raw = _b64url_decode(body)
    if not raw:
        return None
    if flag == "1":
        try:
            dec = zlib.decompress(raw)
        except Exception:
            return None
        raw = dec
    if len(raw) > MAX_DECOMPRESSED_BYTES:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
