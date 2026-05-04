from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import get_engine
from app.deps import session_user

router = APIRouter(prefix="/api", tags=["chat_threads"])


async def _json_body_async(request: Request) -> dict[str, Any]:
    raw = await request.body()
    if not raw:
        return {}
    try:
        d = json.loads(raw.decode("utf-8"))
        return d if isinstance(d, dict) else {}
    except json.JSONDecodeError:
        return {}


@router.get("/chat_threads.php")
async def chat_threads_get(request: Request) -> Any:
    user = session_user(request)
    if user is None:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión inválida"})
    username = user["username"]
    if not username:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión inválida"})

    client_id = str(request.query_params.get("thread") or "").strip()
    q = str(request.query_params.get("q") or "").strip()

    engine = get_engine()
    with engine.connect() as conn:
        if client_id:
            row = (
                conn.execute(
                    text(
                        "SELECT id, client_thread_id, title, created_at, updated_at "
                        "FROM app_chat_threads WHERE username = :u AND client_thread_id = :cid LIMIT 1"
                    ),
                    {"u": username, "cid": client_id},
                )
                .mappings()
                .first()
            )
            if not row:
                return {"ok": True, "thread": None}
            tid = int(row["id"])
            msgs = []
            for r in conn.execute(
                text(
                    "SELECT role, content, created_at FROM app_chat_messages "
                    "WHERE thread_id = :tid ORDER BY id ASC"
                ),
                {"tid": tid},
            ).mappings():
                msgs.append(
                    {
                        "role": str(r["role"] or ""),
                        "content": str(r["content"] or ""),
                        "createdAt": str(r["created_at"] or ""),
                    }
                )
            return {
                "ok": True,
                "thread": {
                    "id": str(row["client_thread_id"] or ""),
                    "title": str(row["title"] or ""),
                    "createdAt": str(row["created_at"] or ""),
                    "updatedAt": str(row["updated_at"] or ""),
                    "messages": msgs,
                },
            }

        sql = (
            "SELECT t.client_thread_id, t.title, t.updated_at, "
            "(SELECT COUNT(*) FROM app_chat_messages m WHERE m.thread_id = t.id) AS n "
            "FROM app_chat_threads t WHERE t.username = :u"
        )
        params: dict[str, Any] = {"u": username}
        if q:
            sql += (
                " AND (t.title LIKE :q OR EXISTS (SELECT 1 FROM app_chat_messages m2 "
                "WHERE m2.thread_id = t.id AND m2.content LIKE :q))"
            )
            params["q"] = f"%{q}%"
        sql += " ORDER BY t.updated_at DESC LIMIT 60"
        threads = []
        for r in conn.execute(text(sql), params).mappings():
            threads.append(
                {
                    "id": str(r["client_thread_id"] or ""),
                    "title": str(r["title"] or ""),
                    "updatedAt": str(r["updated_at"] or ""),
                    "n": int(r["n"] or 0),
                }
            )
        return {"ok": True, "threads": threads}


@router.post("/chat_threads.php")
async def chat_threads_post(request: Request) -> Any:
    user = session_user(request)
    if user is None:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión inválida"})
    username = user["username"]
    body = await _json_body_async(request)
    client_id = str(body.get("id") or "").strip()
    title = str(body.get("title") or "Nuevo chat").strip() or "Nuevo chat"
    messages = body.get("messages") if isinstance(body.get("messages"), list) else []
    if not client_id:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Falta id"})
    if len(title) > 220:
        title = title[:220]

    engine = get_engine()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT id FROM app_chat_threads WHERE username = :u AND client_thread_id = :cid LIMIT 1"
                ),
                {"u": username, "cid": client_id},
            ).first()
            if row:
                thread_id = int(row[0])
                conn.execute(
                    text("UPDATE app_chat_threads SET title = :t, updated_at = NOW() WHERE id = :id"),
                    {"t": title, "id": thread_id},
                )
                conn.execute(text("DELETE FROM app_chat_messages WHERE thread_id = :id"), {"id": thread_id})
            else:
                conn.execute(
                    text(
                        "INSERT INTO app_chat_threads (username, client_thread_id, title) VALUES (:u, :cid, :t)"
                    ),
                    {"u": username, "cid": client_id, "t": title},
                )
                lid = conn.execute(text("SELECT LAST_INSERT_ID() AS lid")).mappings().first()
                thread_id = int((lid or {}).get("lid") or 0)

            ins = text(
                "INSERT INTO app_chat_messages (thread_id, role, content) VALUES (:tid, :role, :content)"
            )
            n = 0
            for m in messages:
                if not isinstance(m, dict):
                    continue
                role = str(m.get("role") or "")
                if role not in ("user", "assistant"):
                    continue
                content = str(m.get("content") or "")
                if not content:
                    continue
                if len(content) > 524288:
                    content = content[:524288]
                conn.execute(ins, {"tid": thread_id, "role": role, "content": content})
                n += 1
                if n >= 500:
                    break
        return {"ok": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.delete("/chat_threads.php")
async def chat_threads_delete(request: Request) -> Any:
    user = session_user(request)
    if user is None:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Sesión inválida"})
    username = user["username"]
    body = await _json_body_async(request)
    purge = body.get("purge_all")
    if purge in (True, 1, "1"):
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM app_chat_threads WHERE username = :u"), {"u": username})
        return {"ok": True, "purge_all": True}

    client_id = str(body.get("id") or "").strip()
    if not client_id:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Falta id"})
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM app_chat_threads WHERE username = :u AND client_thread_id = :cid"),
            {"u": username, "cid": client_id},
        )
    return {"ok": True}
