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
