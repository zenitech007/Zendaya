"""Integration tests for the /api/v1/history* routes via TestClient."""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("ZENDAYA_MOBILE_TOKEN", "testtoken")
    from memory import transcripts
    # Isolate the DB the routes read from.
    conn = transcripts.connect(tmp_path / "conv.db")
    transcripts.record("user", "morning", source="phone",
                       ts=datetime(2026, 6, 30, 8, 0, 0), conn=conn)
    transcripts.record("Zendaya", "good morning",
                       ts=datetime(2026, 6, 30, 8, 0, 5), conn=conn)
    transcripts.record("user", "yesterday msg",
                       ts=datetime(2026, 6, 29, 8, 0, 0), conn=conn)
    conn.close()
    # Make module-level helpers use this DB by default.
    monkeypatch.setattr(transcripts, "DB_PATH", tmp_path / "conv.db")
    import server.state_server as ss
    return TestClient(ss.app)


def _auth(t="testtoken"):
    return {"Authorization": f"Bearer {t}"}


def test_days_requires_auth(client):
    assert client.get("/api/v1/history/days").status_code == 401


def test_days_lists_newest_first(client):
    res = client.get("/api/v1/history/days", headers=_auth())
    assert res.status_code == 200
    days = res.json()["days"]
    assert days[0]["day"] == "2026-06-30"
    assert days[0]["count"] == 2
    assert days[1]["day"] == "2026-06-29"


def test_history_day_returns_messages_oldest_first(client):
    res = client.get("/api/v1/history", params={"day": "2026-06-30"},
                     headers=_auth())
    assert res.status_code == 200
    body = res.json()
    assert body["day"] == "2026-06-30"
    texts = [m["text"] for m in body["messages"]]
    assert texts == ["morning", "good morning"]
    assert body["messages"][0]["source"] == "phone"


def test_history_requires_day_param(client):
    res = client.get("/api/v1/history", headers=_auth())
    assert res.status_code == 400


def test_history_requires_auth(client):
    res = client.get("/api/v1/history", params={"day": "2026-06-30"})
    assert res.status_code == 401
