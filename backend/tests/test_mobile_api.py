"""Integration tests for the /api/v1/* mobile routes via TestClient."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_chat_sync_uses_injected_handler(monkeypatch):
    import server.state_server as ss
    monkeypatch.setattr(ss, "_ON_CHAT_SYNC", lambda msg: f"echo: {msg}")
    out = ss.chat_sync("hello")
    assert out["reply"] == "echo: hello"
    assert "state" in out


def test_chat_sync_no_handler(monkeypatch):
    import server.state_server as ss
    monkeypatch.setattr(ss, "_ON_CHAT_SYNC", None)
    out = ss.chat_sync("hello")
    assert out["reply"] == ""
    assert out["error"] == "no handler registered"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("ZENDAYA_MOBILE_TOKEN", "testtoken")
    import server.state_server as ss
    monkeypatch.setattr(ss, "_ON_CHAT_SYNC", lambda msg: f"reply to {msg}")
    return TestClient(ss.app)


def test_health_requires_auth(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 401


def test_health_with_token(client):
    res = client.get("/api/v1/health", headers={"Authorization": "Bearer testtoken"})
    assert res.status_code == 200
    assert res.json()["name"] == "Zendaya"


def test_chat_requires_auth(client):
    res = client.post("/api/v1/chat", json={"message": "hi"})
    assert res.status_code == 401


def test_chat_returns_reply(client):
    res = client.post("/api/v1/chat", json={"message": "hi"},
                      headers={"Authorization": "Bearer testtoken"})
    assert res.status_code == 200
    body = res.json()
    assert body["reply"] == "reply to hi"
    assert "state" in body


def test_chat_rejects_wrong_token(client):
    res = client.post("/api/v1/chat", json={"message": "hi"},
                      headers={"Authorization": "Bearer nope"})
    assert res.status_code == 401
