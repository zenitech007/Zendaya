# Zendaya Android — Phase 0 (Backend Mobile API) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an authenticated, network-reachable mobile API to Zendaya's existing FastAPI server so an Android app can chat with the brain over a Tailscale mesh.

**Architecture:** A new `backend/server/mobile_api.py` router is mounted on the existing FastAPI `app` under `/api/v1/`. Every route depends on a bearer-token check. A new synchronous chat path captures the brain's reply (today's `/chat` is fire-and-forget) and returns it in the HTTP response. The uvicorn bind host becomes configurable so the server can listen on the Tailscale interface in addition to localhost.

**Tech Stack:** Python 3.14, FastAPI, uvicorn, pydantic, pytest + `fastapi.testclient.TestClient`.

## Global Constraints

- Run tests with: `venv\Scripts\python.exe -m pytest backend/tests -q -m "not slow"` (cwd = repo root; `backend/tests/conftest.py` puts `backend/` on `sys.path`).
- Modules use absolute package imports (`from server import ...`, `import server.state_server`). No relative imports.
- The existing server (`server/state_server.py`) and its routes/tests must keep working unchanged — additive only.
- Auth token is read from the environment variable `ZENDAYA_MOBILE_TOKEN`. If unset, mobile API auth must FAIL CLOSED (reject every request) — never allow unauthenticated access.
- Bind host is read from env `ZENDAYA_BIND_HOST`, default `"127.0.0.1"` (preserves current localhost-only behavior unless explicitly overridden).
- Destructive PC actions keep their existing confirmation gates; the mobile API must not introduce a bypass.
- Do not add new third-party dependencies — everything here uses libraries already imported by `state_server.py`.

---

## File Structure

- **Create** `backend/server/mobile_auth.py` — token loading + FastAPI dependency. One responsibility: authenticate a request.
- **Create** `backend/server/mobile_api.py` — the `/api/v1/*` router (health, chat). One responsibility: mobile HTTP surface.
- **Modify** `backend/server/state_server.py` — mount the router, add a `_ON_CHAT_SYNC` injection point + `chat_sync()` helper, make `start()` accept/forward the new handler, read `ZENDAYA_BIND_HOST`.
- **Modify** `backend/zendaya.py` — implement reply capture around `send_response`, define `_bridge_user_message_sync(msg) -> str`, pass it to `_state_server.start(on_chat_sync=...)`.
- **Create** `backend/tests/test_mobile_auth.py` — unit tests for the auth dependency.
- **Create** `backend/tests/test_mobile_api.py` — TestClient integration tests for the routes.
- **Create** `backend/tests/test_reply_capture.py` — unit tests for the zendaya.py reply-capture buffer.

---

### Task 1: Bearer-token auth dependency

**Files:**
- Create: `backend/server/mobile_auth.py`
- Test: `backend/tests/test_mobile_auth.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `get_mobile_token() -> str | None` — returns the configured token from `os.environ["ZENDAYA_MOBILE_TOKEN"]`, or `None` if unset/empty. Read at call time (not import time) so tests and `.env` reloads take effect.
  - `require_token(authorization: str | None) -> None` — raises `fastapi.HTTPException(status_code=401)` if the token is unset (fail closed) or the header does not match `Bearer <token>`. Returns `None` on success. This is the FastAPI dependency callable (uses `Header(default=None)`).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_mobile_auth.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_mobile_auth.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.mobile_auth'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/server/mobile_auth.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_mobile_auth.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/server/mobile_auth.py backend/tests/test_mobile_auth.py
git commit -m "feat(mobile): bearer-token auth dependency (fail-closed)"
```

---

### Task 2: Reply-capture buffer in zendaya.py

**Files:**
- Modify: `backend/zendaya.py` (the `send_response` function at ~line 706; add helpers just above it)
- Test: `backend/tests/test_reply_capture.py`

**Interfaces:**
- Consumes: nothing.
- Produces (all in module `zendaya`):
  - `_REPLY_CAPTURE: contextvars.ContextVar[list[str] | None]` — holds the active capture buffer for the current context, or `None`.
  - `capture_replies()` — a context manager yielding a `list[str]`; while active, every `send_response(text)` call appends `text` to that list.
  - `_bridge_user_message_sync(msg: str) -> str` — runs `handle_user_command(msg)` inside `capture_replies()` and returns the captured replies joined by `"\n"` (empty string if none).

> **Note for implementer:** `send_response` (zendaya.py:706) is the single funnel for all assistant replies. You are adding a capture hook at its top. Do NOT change its existing behavior (printing / TTS / state-server push) — only additionally append to the active buffer when one is set.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_reply_capture.py -q`
Expected: FAIL with `AttributeError: module 'zendaya' has no attribute 'capture_replies'`.

- [ ] **Step 3: Add `contextvars` import and the capture helpers**

Near the top of `backend/zendaya.py`, with the other stdlib imports, ensure `import contextvars` is present (add it if missing).

Immediately ABOVE `def send_response(text: str):` (zendaya.py:706) insert:

```python
import contextlib

_REPLY_CAPTURE: "contextvars.ContextVar[list[str] | None]" = contextvars.ContextVar(
    "zendaya_reply_capture", default=None
)


@contextlib.contextmanager
def capture_replies():
    """While active, every send_response(text) also appends text to the
    yielded list. Used by the mobile sync chat path to return the reply."""
    buf: list[str] = []
    token = _REPLY_CAPTURE.set(buf)
    try:
        yield buf
    finally:
        _REPLY_CAPTURE.reset(token)


def _bridge_user_message_sync(msg: str) -> str:
    """Run the command handler and return the assistant's reply text
    (newline-joined). Empty string if the handler produced no reply."""
    with capture_replies() as buf:
        try:
            handle_user_command(msg)
        except Exception as e:
            return f"[error: {e}]"
    return "\n".join(buf)
```

- [ ] **Step 4: Add the capture hook inside `send_response`**

Modify `send_response` (zendaya.py:706). Add these two lines as the FIRST statements inside the function body, before the existing `if MEM["mode"] ...`:

```python
def send_response(text: str):
    _buf = _REPLY_CAPTURE.get()
    if _buf is not None:
        _buf.append(text)
    if MEM["mode"] in ("both", "text"):
        stream_print(text)
    # ... rest unchanged ...
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_reply_capture.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/zendaya.py backend/tests/test_reply_capture.py
git commit -m "feat(mobile): capture send_response output for sync chat replies"
```

---

### Task 3: state_server sync-chat injection point + bind host

**Files:**
- Modify: `backend/server/state_server.py` (injection global near line 321; `chat_sync` helper; `start()` signature line 631; uvicorn host line 650)
- Test: `backend/tests/test_mobile_api.py` (the `chat_sync` portion; full route test is Task 4)

**Interfaces:**
- Consumes: `zendaya._bridge_user_message_sync` (injected at runtime via `start(on_chat_sync=...)`).
- Produces (in module `server.state_server`):
  - `_ON_CHAT_SYNC: Optional[Callable[[str], str]]` — module global, default `None`.
  - `chat_sync(message: str) -> dict` — if `_ON_CHAT_SYNC` is `None`, returns `{"reply": "", "error": "no handler registered"}`; otherwise returns `{"reply": _ON_CHAT_SYNC(message), "state": get_state().get("state", "idle")}`.
  - `start(...)` gains keyword `on_chat_sync: Optional[Callable[[str], str]] = None`, stored into `_ON_CHAT_SYNC`.
  - uvicorn binds to `os.environ.get("ZENDAYA_BIND_HOST", host)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_mobile_api.py  (create now; extended in Task 4)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_mobile_api.py -q`
Expected: FAIL with `AttributeError: module 'server.state_server' has no attribute 'chat_sync'`.

- [ ] **Step 3: Add `import os`, the global, and `chat_sync`**

In `backend/server/state_server.py`, ensure `import os` is present near the top imports (add if missing).

Just below the existing `_ON_CHAT` global (state_server.py:321), add:

```python
# Synchronous chat handler for the mobile API: takes a message, returns the
# assistant's reply text. Resolved at start() time from zendaya.py.
_ON_CHAT_SYNC: Optional[Callable[[str], str]] = None
```

Add this helper near the other plain functions (e.g. just above `def start(`):

```python
def chat_sync(message: str) -> dict:
    """Run a mobile chat turn synchronously and return the reply text."""
    msg = (message or "").strip()
    if not msg:
        return {"reply": "", "error": "empty message"}
    if _ON_CHAT_SYNC is None:
        return {"reply": "", "error": "no handler registered"}
    reply = _ON_CHAT_SYNC(msg)
    return {"reply": reply, "state": get_state().get("state", "idle")}
```

- [ ] **Step 4: Extend `start()` to accept and store the handler, and bind configurable host**

Modify `start()` (state_server.py:631). Add the parameter and global, store it, and change the uvicorn host:

```python
def start(
    host: str = "127.0.0.1",
    port: int = 7475,
    on_chat: Optional[Callable[[str], None]] = None,
    on_chat_sync: Optional[Callable[[str], str]] = None,
    on_window_control: Optional[Callable[[str, str], str]] = None,
    window_get_snapshot: Optional[Callable[[], dict]] = None,
    window_pop_events: Optional[Callable[[], list]] = None,
    on_quit: Optional[Callable[[], None]] = None,
) -> threading.Thread:
    """Spawn uvicorn on a daemon thread and return the thread handle."""
    global _ON_CHAT, _ON_CHAT_SYNC, _ON_WINDOW_CONTROL
    global _WINDOW_GET_SNAPSHOT, _WINDOW_POP_EVENTS
    global _ON_QUIT
    _ON_CHAT = on_chat
    _ON_CHAT_SYNC = on_chat_sync
    _ON_WINDOW_CONTROL = on_window_control
    _WINDOW_GET_SNAPSHOT = window_get_snapshot
    _WINDOW_POP_EVENTS = window_pop_events
    _ON_QUIT = on_quit

    bind_host = os.environ.get("ZENDAYA_BIND_HOST", host)
    config = uvicorn.Config(app, host=bind_host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    t = threading.Thread(target=server.run, daemon=True, name="zendaya-state-server")
    t.start()
    return t
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_mobile_api.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/server/state_server.py backend/tests/test_mobile_api.py
git commit -m "feat(mobile): sync-chat injection point + configurable bind host"
```

---

### Task 4: Mobile API router (/api/v1/health, /chat)

**Files:**
- Create: `backend/server/mobile_api.py`
- Modify: `backend/server/state_server.py` (mount the router once, after `app` is defined and after `chat_sync` exists — e.g. just below the `CORSMiddleware` block, add an import + `app.include_router`)
- Test: `backend/tests/test_mobile_api.py` (extend)

**Interfaces:**
- Consumes: `server.mobile_auth.require_token` (Task 1), `server.state_server.chat_sync` (Task 3).
- Produces: an `APIRouter` named `router` with prefix `/api/v1`, exposing:
  - `GET /api/v1/health` → `{"ok": True, "name": "Zendaya"}` (auth required).
  - `POST /api/v1/chat` body `{"message": str}` → `{"reply": str, "state": str}` (auth required).

- [ ] **Step 1: Write the failing tests (extend test_mobile_api.py)**

Append to `backend/tests/test_mobile_api.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_mobile_api.py -q`
Expected: FAIL — `/api/v1/health` returns 404 (router not mounted yet).

- [ ] **Step 3: Create the router**

```python
# backend/server/mobile_api.py
"""Mobile API router for the Zendaya Android app. Mounted under /api/v1.

All routes require a valid bearer token (see server.mobile_auth). The chat
route runs a synchronous turn through the brain and returns the reply text.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from server.mobile_auth import require_token

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_token)])


class MobileChatIn(BaseModel):
    message: str


@router.get("/health")
def mobile_health():
    return {"ok": True, "name": "Zendaya"}


@router.post("/chat")
def mobile_chat(payload: MobileChatIn):
    # Imported here (not at module load) to avoid an import cycle with
    # state_server, which mounts this router.
    from server.state_server import chat_sync
    return chat_sync(payload.message)
```

- [ ] **Step 4: Mount the router in state_server.py**

In `backend/server/state_server.py`, immediately after the `app.add_middleware(CORSMiddleware, ...)` block (ends at state_server.py:300), add:

```python
# Mobile API (Android app). Mounted here so all of app's machinery applies.
from server.mobile_api import router as _mobile_router  # noqa: E402
app.include_router(_mobile_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_mobile_api.py -q`
Expected: PASS (7 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/server/mobile_api.py backend/server/state_server.py backend/tests/test_mobile_api.py
git commit -m "feat(mobile): /api/v1 router with authed health + sync chat"
```

---

### Task 5: Wire the sync handler into the live server + token bootstrap

**Files:**
- Modify: `backend/zendaya.py` (the `_state_server.start(...)` call at line 4079; add `on_chat_sync=_bridge_user_message_sync`)
- Modify: `backend/zendaya.py` (near startup banner — print whether the mobile API is configured)
- Test: manual smoke test (documented below) — no new unit test; covered by Tasks 1–4.

**Interfaces:**
- Consumes: `_bridge_user_message_sync` (Task 2), `start(on_chat_sync=...)` (Task 3).
- Produces: a running server that answers authenticated `/api/v1/chat`.

- [ ] **Step 1: Pass the sync handler to start()**

Modify the call at `backend/zendaya.py:4079`:

```python
            _state_server.start(
                on_chat=_bridge_user_message,
                on_chat_sync=_bridge_user_message_sync,
                on_window_control=_window_control,
                window_get_snapshot=(_wwatcher.get_snapshot if _wwatcher else None),
                window_pop_events=(_wwatcher.pop_events if _wwatcher else None),
                on_quit=request_shutdown,
            )
```

- [ ] **Step 2: Add a startup hint about mobile API config**

Immediately after the existing `print("🪟 State server: http://127.0.0.1:7475")` line (zendaya.py:4086), add:

```python
            import os as _os
            if _os.environ.get("ZENDAYA_MOBILE_TOKEN", "").strip():
                _bh = _os.environ.get("ZENDAYA_BIND_HOST", "127.0.0.1")
                print(f"📱 Mobile API ready at /api/v1 (bind {_bh}; token set).")
            else:
                print("📱 Mobile API disabled (set ZENDAYA_MOBILE_TOKEN in .env to enable).")
```

- [ ] **Step 3: Document the env vars in .env.example (if present) or CLAUDE.md**

Check for `backend/.env.example` or repo `.env.example`. If it exists, append:

```
# Mobile API (Android app). Generate a long random token, e.g.
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
ZENDAYA_MOBILE_TOKEN=
# Set to your PC's Tailscale IP (e.g. 100.x.y.z) to accept phone connections.
# Leave as 127.0.0.1 for localhost-only.
ZENDAYA_BIND_HOST=127.0.0.1
```

If no `.env.example` exists, add the same two-knob note to the "Conversation-flow knobs" area of `CLAUDE.md`.

- [ ] **Step 4: Manual smoke test**

```bash
# 1. Generate a token and put it in backend/.env:
venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
# 2. Start the assistant:
cd backend && ..\venv\Scripts\python.exe zendaya.py
# 3. From another shell (replace TOKEN):
curl -H "Authorization: Bearer TOKEN" http://127.0.0.1:7475/api/v1/health
#    Expected: {"ok":true,"name":"Zendaya"}
curl -X POST -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" ^
     -d "{\"message\":\"what time is it\"}" http://127.0.0.1:7475/api/v1/chat
#    Expected: {"reply":"...","state":"..."}
curl http://127.0.0.1:7475/api/v1/health
#    Expected: 401 (no token)
```

Expected: health returns ok with token, 401 without; chat returns a real reply.

- [ ] **Step 5: Commit**

```bash
git add backend/zendaya.py
git commit -m "feat(mobile): wire sync chat handler into live server + startup hint"
```

---

### Task 6: Full suite regression + Tailscale runbook

**Files:**
- Create: `docs/superpowers/guides/mobile-tailscale-setup.md`
- Test: full backend suite.

- [ ] **Step 1: Run the full backend suite**

Run: `venv\Scripts\python.exe -m pytest backend/tests -q -m "not slow"`
Expected: PASS — all prior tests plus the new `test_mobile_auth.py` (6), `test_mobile_api.py` (7), `test_reply_capture.py` (3). No regressions.

- [ ] **Step 2: Write the Tailscale runbook**

Create `docs/superpowers/guides/mobile-tailscale-setup.md` with: install Tailscale on PC + Android (same account), find the PC's `100.x` IP (`tailscale ip -4`), set `ZENDAYA_BIND_HOST` to that IP and `ZENDAYA_MOBILE_TOKEN` to the generated token in `backend/.env`, restart Zendaya, verify from the phone browser at `http://100.x.y.z:7475/api/v1/health` with the token. Include the QR-pairing note (the Android app in Phase 1 will scan a QR encoding `{host, port, token}`).

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/guides/mobile-tailscale-setup.md
git commit -m "docs(mobile): Tailscale setup runbook for the Android app"
```

---

## Phase 1 (Android app) — follow-on, NOT in this plan

Phase 1 builds the Kotlin + Compose client and requires **Android Studio installed on the PC** and a **physical Android device or emulator**. It is intentionally a separate plan because it cannot be unit-tested with the Python toolchain and needs interactive device testing. Once Phase 0 is merged and Android Studio is confirmed available, write `docs/superpowers/plans/<date>-zendaya-android-phase1-client.md` covering: project scaffold, QR-pairing screen, retrofit/OkHttp API client against `/api/v1/*`, chat UI (Compose), push-to-talk recording → `/api/v1/voice` (note: `/api/v1/voice` is itself a Phase 1 backend addition), and TTS playback of replies.

---

## Self-Review

- **Spec coverage (Phase 0 scope):** Auth (Task 1) ✓, network bind for Tailscale (Task 3) ✓, `/api/v1` router with health + chat (Task 4) ✓, sync reply path replacing fire-and-forget chat (Tasks 2–4) ✓, wiring into live brain (Task 5) ✓, security fail-closed (Task 1, Global Constraints) ✓, regression + runbook (Task 6) ✓. Phases 1–4 of the spec are explicitly out of this plan and flagged as follow-on.
- **Placeholder scan:** No TBD/TODO; every code step shows complete code; commands have expected output.
- **Type consistency:** `require_token` (Task 1) used as `Depends(require_token)` in Task 4 ✓. `chat_sync(message) -> dict` defined in Task 3, consumed in Task 4 ✓. `_bridge_user_message_sync(msg) -> str` defined in Task 2, injected in Task 3's `start()` signature, called in Task 5 ✓. `_ON_CHAT_SYNC` name consistent across Tasks 3–5 ✓. `MobileChatIn.message` matches `chat_sync(message=...)` ✓.
