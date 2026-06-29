"""Bearer-token authentication for the Zendaya mobile API.

Fails closed: if ZENDAYA_MOBILE_TOKEN is unset, every request is rejected.
Token is read at call time so .env reloads / tests take effect without restart.
"""
from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


def get_mobile_token() -> str | None:
    tok = os.environ.get("ZENDAYA_MOBILE_TOKEN", "").strip()
    return tok or None


def require_token(authorization: str | None = Header(default=None)) -> None:
    """FastAPI dependency. Raises 401 unless the Authorization header is
    'Bearer <token>' and matches the configured token. Fails closed."""
    configured = get_mobile_token()
    if not configured:
        raise HTTPException(status_code=401, detail="mobile API not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    presented = authorization[len("Bearer "):].strip()
    # Constant-time compare to avoid timing leaks.
    if not hmac.compare_digest(presented, configured):
        raise HTTPException(status_code=401, detail="invalid token")
    return None
