"""Unit tests for the durable SQLite conversation transcript store."""
from __future__ import annotations

from datetime import datetime

import pytest


@pytest.fixture()
def db(tmp_path):
    from memory import transcripts
    path = tmp_path / "conversations.db"
    conn = transcripts.connect(path)
    yield transcripts, conn
    conn.close()


def test_record_returns_rowid_and_get_day(db):
    transcripts, conn = db
    ts = datetime(2026, 6, 30, 9, 0, 0)
    rid = transcripts.record("user", "hello", source="phone", ts=ts, conn=conn)
    assert rid > 0
    rows = transcripts.get_day("2026-06-30", conn=conn)
    assert len(rows) == 1
    assert rows[0]["role"] == "user"
    assert rows[0]["text"] == "hello"
    assert rows[0]["source"] == "phone"
    assert rows[0]["ts"].startswith("2026-06-30T09:00")


def test_record_skips_empty_text(db):
    transcripts, conn = db
    assert transcripts.record("user", "   ", conn=conn) == -1
    assert transcripts.get_day("2026-06-30", conn=conn) == []


def test_get_day_is_oldest_first(db):
    transcripts, conn = db
    transcripts.record("user", "first", ts=datetime(2026, 6, 30, 8, 0, 0), conn=conn)
    transcripts.record("Zendaya", "second", ts=datetime(2026, 6, 30, 8, 1, 0), conn=conn)
    rows = transcripts.get_day("2026-06-30", conn=conn)
    assert [r["text"] for r in rows] == ["first", "second"]


def test_list_days_newest_first_with_counts(db):
    transcripts, conn = db
    transcripts.record("user", "a", ts=datetime(2026, 6, 29, 8, 0, 0), conn=conn)
    transcripts.record("user", "b", ts=datetime(2026, 6, 30, 8, 0, 0), conn=conn)
    transcripts.record("user", "c", ts=datetime(2026, 6, 30, 9, 0, 0), conn=conn)
    days = transcripts.list_days(conn=conn)
    assert days[0] == {"day": "2026-06-30", "count": 2}
    assert days[1] == {"day": "2026-06-29", "count": 1}


def test_default_source_is_desktop(db):
    transcripts, conn = db
    transcripts.record("user", "hi", ts=datetime(2026, 6, 30, 8, 0, 0), conn=conn)
    rows = transcripts.get_day("2026-06-30", conn=conn)
    assert rows[0]["source"] == "desktop"
