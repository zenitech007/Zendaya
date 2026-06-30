"""Durable SQLite store of conversation turns, keyed by local day.

Runs ALONGSIDE the brain's 30-turn working buffer (MEM["convo"]) and the
ChromaDB vector store — it never replaces them. Purpose: a complete,
chronological, per-day transcript the mobile app can browse. Stdlib only.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "zendaya_data" / "conversations.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     TEXT NOT NULL,
    day    TEXT NOT NULL,
    role   TEXT NOT NULL,
    text   TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'desktop'
);
CREATE INDEX IF NOT EXISTS idx_messages_day ON messages(day);
"""


def connect(path: "str | os.PathLike | None" = None) -> sqlite3.Connection:
    p = Path(path) if path is not None else DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def _with_conn(conn):
    """Return (conn, owned) — owned=True means caller must close it."""
    if conn is not None:
        return conn, False
    return connect(), True


def record(role: str, text: str, source: str = "desktop", *,
           ts: "datetime | None" = None,
           conn: "sqlite3.Connection | None" = None) -> int:
    if not (text or "").strip():
        return -1
    ts = ts or datetime.now()
    iso = ts.isoformat(timespec="seconds")
    day = ts.strftime("%Y-%m-%d")
    c, owned = _with_conn(conn)
    try:
        cur = c.execute(
            "INSERT INTO messages (ts, day, role, text, source) VALUES (?,?,?,?,?)",
            (iso, day, role, text, source),
        )
        c.commit()
        return int(cur.lastrowid)
    finally:
        if owned:
            c.close()


def list_days(conn: "sqlite3.Connection | None" = None) -> "list[dict]":
    c, owned = _with_conn(conn)
    try:
        rows = c.execute(
            "SELECT day, COUNT(*) AS count FROM messages "
            "GROUP BY day ORDER BY day DESC"
        ).fetchall()
        return [{"day": r["day"], "count": r["count"]} for r in rows]
    finally:
        if owned:
            c.close()


def get_day(day: str, conn: "sqlite3.Connection | None" = None) -> "list[dict]":
    c, owned = _with_conn(conn)
    try:
        rows = c.execute(
            "SELECT id, ts, role, text, source FROM messages "
            "WHERE day = ? ORDER BY id ASC",
            (day,),
        ).fetchall()
        return [
            {"id": r["id"], "ts": r["ts"], "role": r["role"],
             "text": r["text"], "source": r["source"]}
            for r in rows
        ]
    finally:
        if owned:
            c.close()
