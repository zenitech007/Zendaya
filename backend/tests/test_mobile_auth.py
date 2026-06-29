"""Unit tests for the mobile API bearer-token auth dependency."""
from __future__ import annotations

import pytest
from fastapi import HTTPException


def test_get_mobile_token_reads_env(monkeypatch):
    from server import mobile_auth
    monkeypatch.setenv("ZENDAYA_MOBILE_TOKEN", "secret123")
    assert mobile_auth.get_mobile_token() == "secret123"


def test_get_mobile_token_none_when_unset(monkeypatch):
    from server import mobile_auth
    monkeypatch.delenv("ZENDAYA_MOBILE_TOKEN", raising=False)
    assert mobile_auth.get_mobile_token() is None


def test_require_token_accepts_matching_bearer(monkeypatch):
    from server import mobile_auth
    monkeypatch.setenv("ZENDAYA_MOBILE_TOKEN", "secret123")
    # Should not raise.
    assert mobile_auth.require_token("Bearer secret123") is None


def test_require_token_rejects_wrong_token(monkeypatch):
    from server import mobile_auth
    monkeypatch.setenv("ZENDAYA_MOBILE_TOKEN", "secret123")
    with pytest.raises(HTTPException) as exc:
        mobile_auth.require_token("Bearer wrong")
    assert exc.value.status_code == 401


def test_require_token_rejects_missing_header(monkeypatch):
    from server import mobile_auth
    monkeypatch.setenv("ZENDAYA_MOBILE_TOKEN", "secret123")
    with pytest.raises(HTTPException) as exc:
        mobile_auth.require_token(None)
    assert exc.value.status_code == 401


def test_require_token_fails_closed_when_unset(monkeypatch):
    from server import mobile_auth
    monkeypatch.delenv("ZENDAYA_MOBILE_TOKEN", raising=False)
    with pytest.raises(HTTPException) as exc:
        mobile_auth.require_token("Bearer anything")
    assert exc.value.status_code == 401
