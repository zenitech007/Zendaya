# backend/tests/test_reply_capture.py
"""Unit tests for zendaya.py reply-capture used by the mobile sync chat path."""
from __future__ import annotations

import importlib


def _load_zendaya(monkeypatch):
    # Importing zendaya.py is heavy; only run when explicitly testing it.
    import zendaya
    return zendaya


def test_capture_collects_send_response(monkeypatch):
    z = _load_zendaya(monkeypatch)
    # Avoid TTS / printing side effects by neutering them.
    monkeypatch.setattr(z, "speak_async", lambda *a, **k: None)
    monkeypatch.setattr(z, "stream_print", lambda *a, **k: None)
    monkeypatch.setitem(z.MEM, "mode", "text")
    with z.capture_replies() as buf:
        z.send_response("hello from zendaya")
    assert buf == ["hello from zendaya"]


def test_capture_is_inactive_by_default(monkeypatch):
    z = _load_zendaya(monkeypatch)
    monkeypatch.setattr(z, "speak_async", lambda *a, **k: None)
    monkeypatch.setattr(z, "stream_print", lambda *a, **k: None)
    monkeypatch.setitem(z.MEM, "mode", "text")
    # No active buffer — must not raise.
    z.send_response("outside any capture")
    assert z._REPLY_CAPTURE.get() is None


def test_bridge_sync_returns_joined_reply(monkeypatch):
    z = _load_zendaya(monkeypatch)
    monkeypatch.setattr(z, "handle_user_command",
                        lambda msg: (z.send_response("first"), z.send_response("second")))
    out = z._bridge_user_message_sync("hi")
    assert out == "first\nsecond"
