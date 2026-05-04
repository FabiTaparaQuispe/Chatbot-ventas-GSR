from __future__ import annotations

import html
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.sql_texto import decode_query_param

router = APIRouter(tags=["sql_texto"])


@router.get("/sql_texto.php")
def sql_texto_decode(z: int = Query(0), s: str = Query("")) -> Any:
    if z != 1:
        return PlainTextResponse("Parámetro z=1 requerido.", status_code=400)
    sql = decode_query_param(s)
    if not sql:
        return PlainTextResponse("Parámetro s inválido o corrupto.", status_code=400)
    esc = html.escape(sql, quote=True)
    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>SQL</title>
<style>body{{font-family:ui-monospace,monospace;margin:1rem;}}pre{{white-space:pre-wrap;word-break:break-word;}}</style>
</head>
<body><h1>Sentencia SQL</h1><pre>{esc}</pre></body></html>"""
    return HTMLResponse(html)
