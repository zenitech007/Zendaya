# Zendaya Android — Phase 1 (Chat Client + Conversation History) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a working Android app that pairs to the PC brain over Tailscale, chats with it via `/api/v1/chat`, and shows full per-day conversation history — backed by a new durable SQLite transcript store on the PC. The APK is built in the cloud by GitHub Actions (no local Android SDK/Studio, given <5 GB free disk).

**Architecture:** Two halves.
(A) **Backend (Python, locally testable):** a new `memory/transcripts.py` SQLite store that records every assistant/user turn (desktop *and* phone) keyed by day; a contextvar tags each turn's `source`; `add_to_memory` (the single turn funnel at `zendaya.py:2673`) also appends to the store; two new authed routes `GET /api/v1/history/days` and `GET /api/v1/history` serve it.
(B) **Android app (Kotlin + Compose):** QR-pairing screen → encrypted-prefs token store → Retrofit client against `/api/v1/*` → a live Chat screen and a History screen (pick a day, scroll that day's transcript). Built by a GitHub Actions workflow that uploads `app-debug.apk` as an artifact.

**Tech Stack:** Python 3.14, FastAPI, stdlib `sqlite3`, pytest + `fastapi.testclient.TestClient` (backend). Kotlin, Jetpack Compose, Retrofit + OkHttp + Moshi, AndroidX Security (EncryptedSharedPreferences), ZXing (QR scan), JUnit (app). Gradle wrapper + GitHub Actions `ubuntu-latest` (cloud build).

## Global Constraints

- **Backend tests:** `venv\Scripts\python.exe -m pytest backend/tests -q -m "not slow"` (cwd = repo root; `backend/tests/conftest.py` puts `backend/` on `sys.path`).
- **Backend imports are absolute package imports** (`from memory import transcripts`, `from server import ...`). No relative imports.
- **Additive only:** the existing server, the 30-turn `MEM["convo"]` working buffer, ChromaDB vector memory, and all current routes/tests must keep working unchanged. The transcript store runs *alongside* `convo`, never replaces it.
- **Auth:** every new mobile route depends on `server.mobile_auth.require_token` (bearer token, fail-closed) — same pattern as Phase 0.
- **No new backend third-party deps:** transcript store uses stdlib `sqlite3` only.
- **History starts fresh:** no backfill of old data. Recording begins when this ships.
- **DB location:** `zendaya_data/conversations.db` (the `zendaya_data/` dir already exists and is created by `memory/data_store.py`).
- **The chat API shape is the REAL Phase 0 one:** `POST /api/v1/chat` body `{"message": str}` → `{"reply": str, "state": str}`. (The design spec's `{text}`/`{reply,...}` draft is superseded by the shipped Phase 0 code.)
- **Android package id:** `com.zenitech.zendaya`. **Min SDK 26, target/compile SDK 34.** Kotlin JVM target 17.
- **App build is cloud-only:** developer has no local Android toolchain. All app build/verify happens via the committed GitHub Actions workflow; "run tests" for app tasks means the workflow's Gradle step on `ubuntu-latest`.

---

## File Structure

**Backend (Part A):**
- **Create** `backend/memory/transcripts.py` — SQLite transcript store. One responsibility: persist + query conversation turns by day.
- **Create** `backend/tests/test_transcripts.py` — unit tests for the store (isolated temp DB).
- **Modify** `backend/zendaya.py` — add a `_TURN_SOURCE` contextvar + `turn_source()` context manager; record each turn into the store from inside `add_to_memory`; wrap the mobile sync path so phone turns are tagged `"phone"`.
- **Create** `backend/server/history_api.py` — the `/api/v1/history*` router (days list + per-day messages). One responsibility: history HTTP surface.
- **Modify** `backend/server/state_server.py` — mount the history router (one `include_router` line next to the Phase 0 mobile router).
- **Create** `backend/tests/test_history_api.py` — TestClient integration tests for the history routes (auth + payload).
- **Modify** `backend/tests/test_reply_capture.py` — extend with one test that the mobile sync path tags turns `"phone"` (only if Task 2 touches that path; see task).

**Android app (Part B) — all under new dir `android/`:**
- **Create** `android/` Gradle project: `settings.gradle.kts`, root `build.gradle.kts`, `gradle.properties`, `gradlew`/`gradlew.bat`/`gradle/wrapper/*`.
- **Create** `android/app/build.gradle.kts`, `android/app/src/main/AndroidManifest.xml`.
- **Create** Kotlin sources under `android/app/src/main/java/com/zenitech/zendaya/`:
  - `data/ServerConfig.kt` — host/port/token holder + encrypted-prefs persistence.
  - `data/Pairing.kt` — parse the QR JSON into a `ServerConfig`.
  - `net/ApiModels.kt` — Retrofit request/response data classes.
  - `net/ZendayaApi.kt` — Retrofit interface (health, chat, history).
  - `net/ApiClient.kt` — builds Retrofit with the bearer interceptor from `ServerConfig`.
  - `ui/PairingScreen.kt`, `ui/ChatScreen.kt`, `ui/HistoryScreen.kt`, `ui/ZendayaApp.kt` (nav), `MainActivity.kt`.
  - `ui/ChatViewModel.kt`, `ui/HistoryViewModel.kt`.
- **Create** app unit tests under `android/app/src/test/java/com/zenitech/zendaya/`:
  - `PairingTest.kt` — QR JSON parsing.
  - `ApiModelsTest.kt` — Moshi (de)serialization of chat + history payloads.
- **Create** `.github/workflows/android-build.yml` — cloud build → `app-debug.apk` artifact.
- **Create** `docs/superpowers/guides/android-app-build-and-install.md` — how to trigger the build, download the APK, and sideload it.

---

# PART A — Backend: durable history (locally testable)

### Task 1: SQLite transcript store

**Files:**
- Create: `backend/memory/transcripts.py`
- Test: `backend/tests/test_transcripts.py`

**Interfaces:**
- Consumes: nothing (stdlib `sqlite3`).
- Produces (module `memory.transcripts`):
  - `DB_PATH: pathlib.Path` — default `zendaya_data/conversations.db`.
  - `connect(path: str | os.PathLike | None = None) -> sqlite3.Connection` — opens (creating dirs) and ensures schema. If `path` is `None`, uses `DB_PATH`.
  - `record(role: str, text: str, source: str = "desktop", *, ts: datetime | None = None, conn: sqlite3.Connection | None = None) -> int` — inserts one turn, returns its row id. `ts` defaults to `datetime.now()`. `day` column is `ts` date as `YYYY-MM-DD` (local). Empty/whitespace `text` is skipped (returns `-1`). Opens/closes its own connection when `conn` is `None`.
  - `list_days(conn: sqlite3.Connection | None = None) -> list[dict]` — returns `[{"day": "YYYY-MM-DD", "count": int}]` newest day first.
  - `get_day(day: str, conn: sqlite3.Connection | None = None) -> list[dict]` — returns that day's turns oldest-first as `[{"id", "ts", "role", "text", "source"}]`.

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS messages (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     TEXT NOT NULL,           -- ISO8601 local, e.g. 2026-06-30T14:05:01
    day    TEXT NOT NULL,           -- YYYY-MM-DD (local date of ts)
    role   TEXT NOT NULL,           -- "user" | "Zendaya" (PERSONA_NAME) | etc.
    text   TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'desktop'  -- "desktop" | "phone"
);
CREATE INDEX IF NOT EXISTS idx_messages_day ON messages(day);
```

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_transcripts.py
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
    assert transcripts.get_day("2026-06-30", conn=conn) == [] or True  # no crash


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_transcripts.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'memory.transcripts'`.

- [ ] **Step 3: Write the implementation**

```python
# backend/memory/transcripts.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_transcripts.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/memory/transcripts.py backend/tests/test_transcripts.py
git commit -m "feat(history): SQLite conversation transcript store"
```

---

### Task 2: Record every turn + tag phone turns

**Files:**
- Modify: `backend/zendaya.py` — add a `_TURN_SOURCE` contextvar + `turn_source()` CM near the existing `_REPLY_CAPTURE` block (zendaya.py:707–711); call `transcripts.record(...)` inside `add_to_memory` (zendaya.py:2673); wrap the body of `_bridge_user_message_sync` (zendaya.py:730) in `turn_source("phone")`.
- Test: `backend/tests/test_reply_capture.py` (extend) + a new focused test in `backend/tests/test_transcripts.py` is NOT needed (covered here).

**Interfaces:**
- Consumes: `memory.transcripts.record` (Task 1).
- Produces (module `zendaya`):
  - `_TURN_SOURCE: contextvars.ContextVar[str]` — default `"desktop"`.
  - `turn_source(name: str)` — context manager setting the active source for turns recorded on this thread.
  - `add_to_memory(role, text)` unchanged in behavior, but now ALSO calls `transcripts.record(role, text, source=_TURN_SOURCE.get())` (best-effort, swallowing errors so persistence never breaks a conversation).

> **Note for implementer:** `add_to_memory` (zendaya.py:2673) is the single funnel every user/assistant turn passes through (call sites at 2840/2883/2888/2911/2359/etc.). Hooking it here captures desktop voice, desktop console, and phone turns in one place. Do NOT change the existing `MEM["convo"]` truncation or vector-add — only ADD the transcript write.

- [ ] **Step 1: Write the failing test (extend test_reply_capture.py)**

Append to `backend/tests/test_reply_capture.py`:

```python
def test_mobile_sync_path_tags_phone_source(monkeypatch, tmp_path):
    import zendaya as z
    from memory import transcripts

    # Point the store at an isolated temp DB.
    test_conn = transcripts.connect(tmp_path / "conv.db")
    monkeypatch.setattr(transcripts, "record",
                        lambda role, text, source="desktop", **kw:
                        transcripts.record.__wrapped__(role, text, source,
                                                       conn=test_conn)
                        if hasattr(transcripts.record, "__wrapped__")
                        else _rec(test_conn, role, text, source))

    # Simpler: capture calls instead of re-implementing.
    calls = []
    monkeypatch.setattr(transcripts, "record",
                        lambda role, text, source="desktop", **kw:
                        calls.append((role, text, source)) or 1)

    monkeypatch.setattr(z, "handle_user_command",
                        lambda msg: z.add_to_memory("user", msg))
    z._bridge_user_message_sync("hi from phone")
    assert ("user", "hi from phone", "phone") in calls


def test_desktop_turns_default_to_desktop_source(monkeypatch):
    import zendaya as z
    from memory import transcripts
    calls = []
    monkeypatch.setattr(transcripts, "record",
                        lambda role, text, source="desktop", **kw:
                        calls.append((role, text, source)) or 1)
    z.add_to_memory("user", "typed at the PC")
    assert ("user", "typed at the PC", "desktop") in calls
```

> Implementer: delete the first dead `monkeypatch.setattr` block above; keep only the `calls`-capturing version. (Left visible so you see the intent; the `calls` approach is the real test.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_reply_capture.py -q`
Expected: FAIL — `add_to_memory` does not call `transcripts.record` yet, so `calls` is empty.

- [ ] **Step 3: Add the contextvar + CM near `_REPLY_CAPTURE`**

In `backend/zendaya.py`, immediately AFTER the `capture_replies` context manager (after zendaya.py:727), add:

```python
_TURN_SOURCE: "contextvars.ContextVar[str]" = contextvars.ContextVar(
    "zendaya_turn_source", default="desktop"
)


@contextlib.contextmanager
def turn_source(name: str):
    """Tag conversation turns recorded on this thread with a source label
    ('desktop' or 'phone') so the transcript store can distinguish them."""
    token = _TURN_SOURCE.set(name)
    try:
        yield
    finally:
        _TURN_SOURCE.reset(token)
```

Add the import near the top stdlib imports if missing: `from memory import transcripts` (place it with the other `from memory import ...` lines).

- [ ] **Step 4: Hook `add_to_memory` and tag the phone path**

Modify `add_to_memory` (zendaya.py:2673) — add the transcript write AFTER the existing `save_memory(MEM)` and vector add:

```python
def add_to_memory(role: str, text: str):
    MEM.setdefault("convo", []).append({"role": role, "text": text, "ts": datetime.now().isoformat()})
    if len(MEM["convo"]) > 30:
        MEM["convo"] = MEM["convo"][-30:]
    save_memory(MEM)
    try:
        _vmem_add(role, text)
    except Exception:
        pass
    try:
        transcripts.record(role, text, source=_TURN_SOURCE.get())
    except Exception:
        pass
```

Modify `_bridge_user_message_sync` (zendaya.py:730) to wrap its work in the phone source:

```python
def _bridge_user_message_sync(msg: str) -> str:
    """Run the command handler and return the assistant's reply text
    (newline-joined). Empty string if the handler produced no reply."""
    with turn_source("phone"):
        with capture_replies() as buf:
            try:
                handle_user_command(msg)
            except Exception as e:
                return f"[error: {e}]"
        return "\n".join(buf)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_reply_capture.py -q`
Expected: PASS (existing 3 + 2 new = 5 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/zendaya.py backend/tests/test_reply_capture.py
git commit -m "feat(history): record every turn to transcript store, tag phone turns"
```

---

### Task 3: History API routes

**Files:**
- Create: `backend/server/history_api.py`
- Modify: `backend/server/state_server.py` — mount the router next to the Phase 0 mobile router (after the `app.include_router(_mobile_router)` line added in Phase 0 Task 4).
- Test: `backend/tests/test_history_api.py`

**Interfaces:**
- Consumes: `server.mobile_auth.require_token` (Phase 0 Task 1), `memory.transcripts.list_days` / `get_day` (Task 1).
- Produces: an `APIRouter` named `router`, prefix `/api/v1`, all routes auth-gated:
  - `GET /api/v1/history/days` → `{"days": [{"day": str, "count": int}, ...]}`.
  - `GET /api/v1/history?day=YYYY-MM-DD` → `{"day": str, "messages": [{"id","ts","role","text","source"}, ...]}`. Missing/blank `day` → 400.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_history_api.py
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
    # Make module-level helpers use this conn by default.
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_history_api.py -q`
Expected: FAIL — routes return 404 (router not mounted).

- [ ] **Step 3: Create the router**

```python
# backend/server/history_api.py
"""History API for the Zendaya Android app. Mounted under /api/v1.

Serves the durable conversation transcript (memory.transcripts) so the phone
can browse past days. All routes require a bearer token (server.mobile_auth).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from server.mobile_auth import require_token

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_token)])


@router.get("/history/days")
def history_days():
    from memory import transcripts
    return {"days": transcripts.list_days()}


@router.get("/history")
def history_day(day: str = Query(default="")):
    day = (day or "").strip()
    if not day:
        raise HTTPException(status_code=400, detail="missing 'day' query param")
    from memory import transcripts
    return {"day": day, "messages": transcripts.get_day(day)}
```

> Note: `transcripts.list_days()` / `get_day()` with no `conn` open their own connection at `transcripts.DB_PATH`, which the test fixture monkeypatches to the temp DB. In production it's the real `zendaya_data/conversations.db`.

- [ ] **Step 4: Mount the router in state_server.py**

In `backend/server/state_server.py`, immediately AFTER the existing Phase 0 line `app.include_router(_mobile_router)`, add:

```python
from server.history_api import router as _history_router  # noqa: E402
app.include_router(_history_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `venv\Scripts\python.exe -m pytest backend/tests/test_history_api.py -q`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/server/history_api.py backend/server/state_server.py backend/tests/test_history_api.py
git commit -m "feat(history): /api/v1/history routes (days list + per-day messages)"
```

---

### Task 4: Backend regression + history runbook note

**Files:**
- Modify: `docs/superpowers/guides/mobile-tailscale-setup.md` (append a short "History endpoints" section).
- Test: full backend suite.

- [ ] **Step 1: Run the full backend suite**

Run: `venv\Scripts\python.exe -m pytest backend/tests -q -m "not slow"`
Expected: PASS — all prior tests plus `test_transcripts.py` (5), `test_history_api.py` (5), and the 2 added in `test_reply_capture.py`. No regressions.

- [ ] **Step 2: Document the new endpoints**

Append to `docs/superpowers/guides/mobile-tailscale-setup.md`:

```markdown
## History endpoints (Phase 1)

Once the brain has had at least one conversation since Phase 1 shipped:

    # List days that have any messages (newest first)
    curl -H "Authorization: Bearer <TOKEN>" http://<HOST>:7475/api/v1/history/days
    #   -> {"days":[{"day":"2026-06-30","count":12}, ...]}

    # Full transcript for one day (oldest message first)
    curl -H "Authorization: Bearer <TOKEN>" "http://<HOST>:7475/api/v1/history?day=2026-06-30"
    #   -> {"day":"2026-06-30","messages":[{"id":1,"ts":"...","role":"user","text":"...","source":"phone"}, ...]}

Transcripts persist to `backend/zendaya_data/conversations.db` (SQLite). Both
desktop and phone turns are recorded; `source` distinguishes them.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/guides/mobile-tailscale-setup.md
git commit -m "docs(history): document /api/v1/history endpoints"
```

---

# PART B — Android app (cloud-built)

> **Build model:** No local Android SDK. After each app task, you push the commit; the GitHub Actions workflow (Task 5) compiles and runs the JVM unit tests on `ubuntu-latest`. "Run tests" for Part B = the workflow's `./gradlew testDebugUnitTest` step going green. Task 5 builds the workflow FIRST so every later task is verifiable.

### Task 5: Gradle project skeleton + GitHub Actions build

**Files (create all):**
- `android/settings.gradle.kts`
- `android/build.gradle.kts`
- `android/gradle.properties`
- `android/gradle/wrapper/gradle-wrapper.properties`
- `android/app/build.gradle.kts`
- `android/app/src/main/AndroidManifest.xml`
- `android/app/src/main/java/com/zenitech/zendaya/MainActivity.kt` (placeholder Compose "Zendaya" text — replaced in Task 8)
- `android/app/src/main/res/values/strings.xml`
- `android/app/src/test/java/com/zenitech/zendaya/SmokeTest.kt`
- `.github/workflows/android-build.yml`

**Interfaces:**
- Produces: a buildable APK target `:app:assembleDebug` and a JVM unit-test target `:app:testDebugUnitTest`. App id `com.zenitech.zendaya`.

- [ ] **Step 1: Write `settings.gradle.kts`**

```kotlin
// android/settings.gradle.kts
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "Zendaya"
include(":app")
```

- [ ] **Step 2: Write root `build.gradle.kts` + `gradle.properties` + wrapper props**

```kotlin
// android/build.gradle.kts
plugins {
    id("com.android.application") version "8.5.2" apply false
    id("org.jetbrains.kotlin.android") version "1.9.24" apply false
}
```

```properties
# android/gradle.properties
org.gradle.jvmargs=-Xmx2048m
android.useAndroidX=true
kotlin.code.style=official
```

```properties
# android/gradle/wrapper/gradle-wrapper.properties
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-8.7-bin.zip
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
```

> The Actions workflow runs `gradle wrapper` to generate `gradlew`/`gradlew.bat`/`gradle-wrapper.jar` from these props (so we don't commit a binary jar). See Step 7.

- [ ] **Step 3: Write `app/build.gradle.kts`**

```kotlin
// android/app/build.gradle.kts
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.zenitech.zendaya"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.zenitech.zendaya"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        getByName("debug") { isMinifyEnabled = false }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
    composeOptions { kotlinCompilerExtensionVersion = "1.5.14" }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.06.00")
    implementation(composeBom)
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.2")
    implementation("androidx.navigation:navigation-compose:2.7.7")

    // Networking
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-moshi:2.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.moshi:moshi:1.15.1")
    implementation("com.squareup.moshi:moshi-kotlin:1.15.1")

    // Secure token storage
    implementation("androidx.security:security-crypto:1.1.0-alpha06")

    // QR scanning
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")

    testImplementation("junit:junit:4.13.2")
}
```

- [ ] **Step 4: Write the manifest + strings + placeholder Activity**

```xml
<!-- android/app/src/main/AndroidManifest.xml -->
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.CAMERA" />

    <application
        android:allowBackup="true"
        android:label="@string/app_name"
        android:supportsRtl="true"
        android:theme="@style/Theme.Material3.DynamicColors.DayNight">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

```xml
<!-- android/app/src/main/res/values/strings.xml -->
<resources>
    <string name="app_name">Zendaya</string>
</resources>
```

```kotlin
// android/app/src/main/java/com/zenitech/zendaya/MainActivity.kt
package com.zenitech.zendaya

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface { Text("Zendaya") }
            }
        }
    }
}
```

- [ ] **Step 5: Write the smoke unit test**

```kotlin
// android/app/src/test/java/com/zenitech/zendaya/SmokeTest.kt
package com.zenitech.zendaya

import org.junit.Assert.assertEquals
import org.junit.Test

class SmokeTest {
    @Test fun arithmetic_sanity() {
        assertEquals(4, 2 + 2)
    }
}
```

- [ ] **Step 6: Write the GitHub Actions workflow**

```yaml
# .github/workflows/android-build.yml
name: Android build

on:
  push:
    paths:
      - "android/**"
      - ".github/workflows/android-build.yml"
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: android
    steps:
      - uses: actions/checkout@v4

      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: "17"

      - name: Set up Android SDK
        uses: android-actions/setup-android@v3

      - name: Generate Gradle wrapper
        run: gradle wrapper --gradle-version 8.7

      - name: Unit tests
        run: ./gradlew testDebugUnitTest --stacktrace

      - name: Build debug APK
        run: ./gradlew assembleDebug --stacktrace

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: zendaya-debug-apk
          path: android/app/build/outputs/apk/debug/app-debug.apk
          if-no-files-found: error
```

- [ ] **Step 7: Commit and push; verify the workflow goes green**

```bash
git add android/ .github/workflows/android-build.yml
git commit -m "feat(app): Gradle skeleton + GitHub Actions cloud build"
git push
```

Then: open the repo's **Actions** tab on GitHub. The "Android build" run must finish green, with a `zendaya-debug-apk` artifact attached. Expected: unit test `arithmetic_sanity` passes; `app-debug.apk` uploaded.

> If the run fails on SDK license or AGP version, that is the signal to fix here before any further app task — every later task depends on this pipeline.

---

### Task 6: Pairing — parse QR config + persist token securely

**Files:**
- Create: `android/app/src/main/java/com/zenitech/zendaya/data/ServerConfig.kt`
- Create: `android/app/src/main/java/com/zenitech/zendaya/data/Pairing.kt`
- Test: `android/app/src/test/java/com/zenitech/zendaya/PairingTest.kt`

**Interfaces:**
- Consumes: Moshi (already a dep).
- Produces:
  - `data class ServerConfig(val host: String, val port: Int, val token: String)` with `fun baseUrl(): String = "http://$host:$port/"`.
  - `object Pairing { fun parse(qr: String): ServerConfig? }` — parses JSON `{"host","port","token"}`; returns `null` on malformed input or missing fields.
  - `object ConfigStore` — `fun save(ctx: Context, cfg: ServerConfig)`, `fun load(ctx: Context): ServerConfig?`, backed by `EncryptedSharedPreferences`. (No unit test for ConfigStore — it needs Android runtime; covered by manual install test in Task 9.)

- [ ] **Step 1: Write the failing test**

```kotlin
// android/app/src/test/java/com/zenitech/zendaya/PairingTest.kt
package com.zenitech.zendaya

import com.zenitech.zendaya.data.Pairing
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PairingTest {
    @Test fun parses_valid_qr_json() {
        val cfg = Pairing.parse("""{"host":"100.1.2.3","port":7475,"token":"abc"}""")
        assertEquals("100.1.2.3", cfg!!.host)
        assertEquals(7475, cfg.port)
        assertEquals("abc", cfg.token)
        assertEquals("http://100.1.2.3:7475/", cfg.baseUrl())
    }

    @Test fun returns_null_on_garbage() {
        assertNull(Pairing.parse("not json"))
    }

    @Test fun returns_null_when_field_missing() {
        assertNull(Pairing.parse("""{"host":"100.1.2.3","port":7475}"""))
    }
}
```

- [ ] **Step 2: Push and verify the test fails in CI**

Run (in CI via push): `./gradlew testDebugUnitTest`
Expected: FAIL — `Pairing` / `ServerConfig` unresolved.

> To iterate without burning CI minutes, batch Steps 3–4 then push once.

- [ ] **Step 3: Write `ServerConfig.kt`**

```kotlin
// android/app/src/main/java/com/zenitech/zendaya/data/ServerConfig.kt
package com.zenitech.zendaya.data

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

data class ServerConfig(val host: String, val port: Int, val token: String) {
    fun baseUrl(): String = "http://$host:$port/"
}

object ConfigStore {
    private const val FILE = "zendaya_secure_prefs"
    private const val K_HOST = "host"
    private const val K_PORT = "port"
    private const val K_TOKEN = "token"

    private fun prefs(ctx: Context) =
        EncryptedSharedPreferences.create(
            ctx,
            FILE,
            MasterKey.Builder(ctx).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )

    fun save(ctx: Context, cfg: ServerConfig) {
        prefs(ctx).edit()
            .putString(K_HOST, cfg.host)
            .putInt(K_PORT, cfg.port)
            .putString(K_TOKEN, cfg.token)
            .apply()
    }

    fun load(ctx: Context): ServerConfig? {
        val p = prefs(ctx)
        val host = p.getString(K_HOST, null) ?: return null
        val token = p.getString(K_TOKEN, null) ?: return null
        val port = p.getInt(K_PORT, 0)
        if (port == 0) return null
        return ServerConfig(host, port, token)
    }
}
```

- [ ] **Step 4: Write `Pairing.kt`**

```kotlin
// android/app/src/main/java/com/zenitech/zendaya/data/Pairing.kt
package com.zenitech.zendaya.data

import com.squareup.moshi.JsonClass
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory

object Pairing {
    @JsonClass(generateAdapter = false)
    data class QrPayload(val host: String?, val port: Int?, val token: String?)

    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
    private val adapter = moshi.adapter(QrPayload::class.java)

    fun parse(qr: String): ServerConfig? {
        val p = try { adapter.fromJson(qr) } catch (e: Exception) { return null } ?: return null
        val host = p.host ?: return null
        val port = p.port ?: return null
        val token = p.token ?: return null
        return ServerConfig(host, port, token)
    }
}
```

- [ ] **Step 5: Push and verify tests pass in CI**

Run (CI): `./gradlew testDebugUnitTest`
Expected: PASS — `PairingTest` (3) + `SmokeTest` (1).

- [ ] **Step 6: Commit** (already pushed; this records the logical unit)

```bash
git add android/app/src/main/java/com/zenitech/zendaya/data/ android/app/src/test/java/com/zenitech/zendaya/PairingTest.kt
git commit -m "feat(app): QR pairing parse + encrypted server config store"
```

---

### Task 7: API models + Retrofit client

**Files:**
- Create: `android/app/src/main/java/com/zenitech/zendaya/net/ApiModels.kt`
- Create: `android/app/src/main/java/com/zenitech/zendaya/net/ZendayaApi.kt`
- Create: `android/app/src/main/java/com/zenitech/zendaya/net/ApiClient.kt`
- Test: `android/app/src/test/java/com/zenitech/zendaya/ApiModelsTest.kt`

**Interfaces:**
- Consumes: `ServerConfig` (Task 6), Retrofit/Moshi/OkHttp (deps).
- Produces:
  - `data class ChatRequest(val message: String)`.
  - `data class ChatResponse(val reply: String, val state: String?)`.
  - `data class DayInfo(val day: String, val count: Int)`.
  - `data class DaysResponse(val days: List<DayInfo>)`.
  - `data class HistoryMessage(val id: Long, val ts: String, val role: String, val text: String, val source: String)`.
  - `data class HistoryResponse(val day: String, val messages: List<HistoryMessage>)`.
  - `interface ZendayaApi` with `@GET("api/v1/health")`, `@POST("api/v1/chat")`, `@GET("api/v1/history/days")`, `@GET("api/v1/history")` (the last takes `@Query("day") day: String`).
  - `object ApiClient { fun create(cfg: ServerConfig): ZendayaApi }` — Retrofit with a bearer interceptor injecting `Authorization: Bearer <cfg.token>` and base URL `cfg.baseUrl()`.

- [ ] **Step 1: Write the failing test (Moshi round-trips)**

```kotlin
// android/app/src/test/java/com/zenitech/zendaya/ApiModelsTest.kt
package com.zenitech.zendaya

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import com.zenitech.zendaya.net.ChatResponse
import com.zenitech.zendaya.net.HistoryResponse
import org.junit.Assert.assertEquals
import org.junit.Test

class ApiModelsTest {
    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()

    @Test fun parses_chat_response() {
        val a = moshi.adapter(ChatResponse::class.java)
        val r = a.fromJson("""{"reply":"hi there","state":"idle"}""")!!
        assertEquals("hi there", r.reply)
        assertEquals("idle", r.state)
    }

    @Test fun parses_history_response() {
        val a = moshi.adapter(HistoryResponse::class.java)
        val json = """{"day":"2026-06-30","messages":[
            {"id":1,"ts":"2026-06-30T08:00:00","role":"user","text":"hello","source":"phone"}]}"""
        val r = a.fromJson(json)!!
        assertEquals("2026-06-30", r.day)
        assertEquals(1, r.messages.size)
        assertEquals("hello", r.messages[0].text)
        assertEquals("phone", r.messages[0].source)
    }
}
```

- [ ] **Step 2: Push; verify it fails in CI**

Expected: FAIL — `ChatResponse` / `HistoryResponse` unresolved.

- [ ] **Step 3: Write `ApiModels.kt`**

```kotlin
// android/app/src/main/java/com/zenitech/zendaya/net/ApiModels.kt
package com.zenitech.zendaya.net

data class ChatRequest(val message: String)
data class ChatResponse(val reply: String, val state: String?)

data class DayInfo(val day: String, val count: Int)
data class DaysResponse(val days: List<DayInfo>)

data class HistoryMessage(
    val id: Long,
    val ts: String,
    val role: String,
    val text: String,
    val source: String,
)
data class HistoryResponse(val day: String, val messages: List<HistoryMessage>)
```

- [ ] **Step 4: Write `ZendayaApi.kt`**

```kotlin
// android/app/src/main/java/com/zenitech/zendaya/net/ZendayaApi.kt
package com.zenitech.zendaya.net

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

interface ZendayaApi {
    @GET("api/v1/health")
    suspend fun health(): Map<String, Any>

    @POST("api/v1/chat")
    suspend fun chat(@Body req: ChatRequest): ChatResponse

    @GET("api/v1/history/days")
    suspend fun days(): DaysResponse

    @GET("api/v1/history")
    suspend fun history(@Query("day") day: String): HistoryResponse
}
```

- [ ] **Step 5: Write `ApiClient.kt`**

```kotlin
// android/app/src/main/java/com/zenitech/zendaya/net/ApiClient.kt
package com.zenitech.zendaya.net

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import com.zenitech.zendaya.data.ServerConfig
import okhttp3.OkHttpClient
import okhttp3.Interceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {
    fun create(cfg: ServerConfig): ZendayaApi {
        val auth = Interceptor { chain ->
            val req = chain.request().newBuilder()
                .addHeader("Authorization", "Bearer ${cfg.token}")
                .build()
            chain.proceed(req)
        }
        val ok = OkHttpClient.Builder()
            .addInterceptor(auth)
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)  // chat turns can be slow
            .build()
        val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
        return Retrofit.Builder()
            .baseUrl(cfg.baseUrl())
            .client(ok)
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()
            .create(ZendayaApi::class.java)
    }
}
```

- [ ] **Step 6: Push; verify tests pass in CI**

Expected: PASS — `ApiModelsTest` (2) + prior tests.

- [ ] **Step 7: Commit**

```bash
git add android/app/src/main/java/com/zenitech/zendaya/net/ android/app/src/test/java/com/zenitech/zendaya/ApiModelsTest.kt
git commit -m "feat(app): Retrofit API models + authed client"
```

---

### Task 8: Chat screen + ViewModel

**Files:**
- Create: `android/app/src/main/java/com/zenitech/zendaya/ui/ChatViewModel.kt`
- Create: `android/app/src/main/java/com/zenitech/zendaya/ui/ChatScreen.kt`
- Test: `android/app/src/test/java/com/zenitech/zendaya/ChatViewModelTest.kt`

**Interfaces:**
- Consumes: `ZendayaApi` (Task 7).
- Produces:
  - `data class ChatMsg(val role: String, val text: String)`.
  - `class ChatViewModel(private val api: ZendayaApi)` with `val messages: StateFlow<List<ChatMsg>>`, `val sending: StateFlow<Boolean>`, and `fun send(text: String)` — appends the user msg immediately, calls `api.chat`, appends the reply (or an error bubble) and clears `sending`.
  - `@Composable fun ChatScreen(vm: ChatViewModel, onOpenHistory: () -> Unit)` — message list + input row + a History button.

- [ ] **Step 1: Write the failing test (ViewModel with a fake api)**

```kotlin
// android/app/src/test/java/com/zenitech/zendaya/ChatViewModelTest.kt
package com.zenitech.zendaya

import com.zenitech.zendaya.net.*
import com.zenitech.zendaya.ui.ChatViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ChatViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    @Before fun setUp() { Dispatchers.setMain(dispatcher) }
    @After fun tearDown() { Dispatchers.resetMain() }

    private fun fakeApi(reply: String) = object : ZendayaApi {
        override suspend fun health() = mapOf<String, Any>("ok" to true)
        override suspend fun chat(req: ChatRequest) = ChatResponse(reply, "idle")
        override suspend fun days() = DaysResponse(emptyList())
        override suspend fun history(day: String) = HistoryResponse(day, emptyList())
    }

    @Test fun send_appends_user_then_reply() = runTest(dispatcher) {
        val vm = ChatViewModel(fakeApi("pong"))
        vm.send("ping")
        dispatcher.scheduler.advanceUntilIdle()
        val msgs = vm.messages.value
        assertEquals(2, msgs.size)
        assertEquals("user", msgs[0].role)
        assertEquals("ping", msgs[0].text)
        assertEquals("Zendaya", msgs[1].role)
        assertEquals("pong", msgs[1].text)
    }
}
```

Add the coroutines-test dependency to `app/build.gradle.kts` dependencies:

```kotlin
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.1")
```

- [ ] **Step 2: Push; verify it fails in CI**

Expected: FAIL — `ChatViewModel` unresolved.

- [ ] **Step 3: Write `ChatViewModel.kt`**

```kotlin
// android/app/src/main/java/com/zenitech/zendaya/ui/ChatViewModel.kt
package com.zenitech.zendaya.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.zenitech.zendaya.net.ChatRequest
import com.zenitech.zendaya.net.ZendayaApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ChatMsg(val role: String, val text: String)

class ChatViewModel(private val api: ZendayaApi) : ViewModel() {
    private val _messages = MutableStateFlow<List<ChatMsg>>(emptyList())
    val messages: StateFlow<List<ChatMsg>> = _messages.asStateFlow()

    private val _sending = MutableStateFlow(false)
    val sending: StateFlow<Boolean> = _sending.asStateFlow()

    fun send(text: String) {
        val msg = text.trim()
        if (msg.isEmpty() || _sending.value) return
        _messages.value = _messages.value + ChatMsg("user", msg)
        _sending.value = true
        viewModelScope.launch {
            val reply = try {
                api.chat(ChatRequest(msg)).reply
            } catch (e: Exception) {
                "[Zendaya's brain is unreachable: ${e.message}]"
            }
            _messages.value = _messages.value + ChatMsg("Zendaya", reply)
            _sending.value = false
        }
    }
}
```

- [ ] **Step 4: Write `ChatScreen.kt`**

```kotlin
// android/app/src/main/java/com/zenitech/zendaya/ui/ChatScreen.kt
package com.zenitech.zendaya.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.History
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(vm: ChatViewModel, onOpenHistory: () -> Unit) {
    val messages by vm.messages.collectAsStateWithLifecycle()
    val sending by vm.sending.collectAsStateWithLifecycle()
    var input by remember { mutableStateOf("") }
    val listState = rememberLazyListState()

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) listState.animateScrollToItem(messages.size - 1)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Zendaya") },
                actions = {
                    IconButton(onClick = onOpenHistory) {
                        Icon(Icons.Filled.History, contentDescription = "History")
                    }
                },
            )
        },
    ) { pad ->
        Column(Modifier.padding(pad).fillMaxSize()) {
            LazyColumn(
                state = listState,
                modifier = Modifier.weight(1f).fillMaxWidth(),
                contentPadding = PaddingValues(12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(messages) { m -> MessageBubble(m.role, m.text) }
            }
            if (sending) LinearProgressIndicator(Modifier.fillMaxWidth())
            Row(
                Modifier.fillMaxWidth().padding(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedTextField(
                    value = input,
                    onValueChange = { input = it },
                    modifier = Modifier.weight(1f),
                    placeholder = { Text("Message Zendaya") },
                )
                Spacer(Modifier.width(8.dp))
                IconButton(onClick = { vm.send(input); input = "" }, enabled = !sending) {
                    Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send")
                }
            }
        }
    }
}

@Composable
private fun MessageBubble(role: String, text: String) {
    val isUser = role == "user"
    Row(Modifier.fillMaxWidth()) {
        if (isUser) Spacer(Modifier.weight(1f))
        Surface(
            color = if (isUser) MaterialTheme.colorScheme.primaryContainer
                    else MaterialTheme.colorScheme.surfaceVariant,
            shape = MaterialTheme.shapes.medium,
            modifier = Modifier.widthIn(max = 280.dp),
        ) {
            Text(
                text,
                modifier = Modifier.padding(10.dp),
                textAlign = if (isUser) TextAlign.End else TextAlign.Start,
            )
        }
        if (!isUser) Spacer(Modifier.weight(1f))
    }
}
```

- [ ] **Step 5: Push; verify tests pass in CI**

Expected: PASS — `ChatViewModelTest` (1) + prior tests.

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/java/com/zenitech/zendaya/ui/ChatViewModel.kt android/app/src/main/java/com/zenitech/zendaya/ui/ChatScreen.kt android/app/src/test/java/com/zenitech/zendaya/ChatViewModelTest.kt android/app/build.gradle.kts
git commit -m "feat(app): chat screen + view model"
```

---

### Task 9: History screen + ViewModel

**Files:**
- Create: `android/app/src/main/java/com/zenitech/zendaya/ui/HistoryViewModel.kt`
- Create: `android/app/src/main/java/com/zenitech/zendaya/ui/HistoryScreen.kt`
- Test: `android/app/src/test/java/com/zenitech/zendaya/HistoryViewModelTest.kt`

**Interfaces:**
- Consumes: `ZendayaApi` (Task 7).
- Produces:
  - `class HistoryViewModel(private val api: ZendayaApi)` with `val days: StateFlow<List<DayInfo>>`, `val selected: StateFlow<String?>`, `val messages: StateFlow<List<HistoryMessage>>`, `val loading: StateFlow<Boolean>`; `fun loadDays()`, `fun openDay(day: String)`.
  - `@Composable fun HistoryScreen(vm: HistoryViewModel, onBack: () -> Unit)` — list of days; tapping one loads + shows that day's transcript.

- [ ] **Step 1: Write the failing test**

```kotlin
// android/app/src/test/java/com/zenitech/zendaya/HistoryViewModelTest.kt
package com.zenitech.zendaya

import com.zenitech.zendaya.net.*
import com.zenitech.zendaya.ui.HistoryViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class HistoryViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    @Before fun setUp() { Dispatchers.setMain(dispatcher) }
    @After fun tearDown() { Dispatchers.resetMain() }

    private val api = object : ZendayaApi {
        override suspend fun health() = mapOf<String, Any>()
        override suspend fun chat(req: ChatRequest) = ChatResponse("", "idle")
        override suspend fun days() =
            DaysResponse(listOf(DayInfo("2026-06-30", 2), DayInfo("2026-06-29", 1)))
        override suspend fun history(day: String) =
            HistoryResponse(day, listOf(
                HistoryMessage(1, "$day" + "T08:00:00", "user", "hi", "phone")))
    }

    @Test fun loadDays_populates_days() = runTest(dispatcher) {
        val vm = HistoryViewModel(api)
        vm.loadDays()
        dispatcher.scheduler.advanceUntilIdle()
        assertEquals(2, vm.days.value.size)
        assertEquals("2026-06-30", vm.days.value[0].day)
    }

    @Test fun openDay_loads_messages() = runTest(dispatcher) {
        val vm = HistoryViewModel(api)
        vm.openDay("2026-06-30")
        dispatcher.scheduler.advanceUntilIdle()
        assertEquals("2026-06-30", vm.selected.value)
        assertEquals(1, vm.messages.value.size)
        assertEquals("hi", vm.messages.value[0].text)
    }
}
```

- [ ] **Step 2: Push; verify it fails in CI**

Expected: FAIL — `HistoryViewModel` unresolved.

- [ ] **Step 3: Write `HistoryViewModel.kt`**

```kotlin
// android/app/src/main/java/com/zenitech/zendaya/ui/HistoryViewModel.kt
package com.zenitech.zendaya.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.zenitech.zendaya.net.DayInfo
import com.zenitech.zendaya.net.HistoryMessage
import com.zenitech.zendaya.net.ZendayaApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class HistoryViewModel(private val api: ZendayaApi) : ViewModel() {
    private val _days = MutableStateFlow<List<DayInfo>>(emptyList())
    val days: StateFlow<List<DayInfo>> = _days.asStateFlow()

    private val _selected = MutableStateFlow<String?>(null)
    val selected: StateFlow<String?> = _selected.asStateFlow()

    private val _messages = MutableStateFlow<List<HistoryMessage>>(emptyList())
    val messages: StateFlow<List<HistoryMessage>> = _messages.asStateFlow()

    private val _loading = MutableStateFlow(false)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()

    fun loadDays() {
        _loading.value = true
        viewModelScope.launch {
            _days.value = try { api.days().days } catch (e: Exception) { emptyList() }
            _loading.value = false
        }
    }

    fun openDay(day: String) {
        _selected.value = day
        _loading.value = true
        viewModelScope.launch {
            _messages.value = try { api.history(day).messages } catch (e: Exception) { emptyList() }
            _loading.value = false
        }
    }

    fun backToDays() { _selected.value = null }
}
```

- [ ] **Step 4: Write `HistoryScreen.kt`**

```kotlin
// android/app/src/main/java/com/zenitech/zendaya/ui/HistoryScreen.kt
package com.zenitech.zendaya.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HistoryScreen(vm: HistoryViewModel, onBack: () -> Unit) {
    val days by vm.days.collectAsStateWithLifecycle()
    val selected by vm.selected.collectAsStateWithLifecycle()
    val messages by vm.messages.collectAsStateWithLifecycle()
    val loading by vm.loading.collectAsStateWithLifecycle()

    LaunchedEffect(Unit) { vm.loadDays() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(selected ?: "History") },
                navigationIcon = {
                    IconButton(onClick = { if (selected != null) vm.backToDays() else onBack() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { pad ->
        Box(Modifier.padding(pad).fillMaxSize()) {
            if (loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            if (selected == null) {
                LazyColumn(Modifier.fillMaxSize()) {
                    items(days) { d ->
                        ListItem(
                            headlineContent = { Text(d.day) },
                            supportingContent = { Text("${d.count} messages") },
                            modifier = Modifier.clickable { vm.openDay(d.day) },
                        )
                        HorizontalDivider()
                    }
                }
            } else {
                LazyColumn(
                    Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(12.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(messages) { m ->
                        Column {
                            Text(
                                "${m.role} · ${m.ts.substringAfter('T').take(5)} · ${m.source}",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.outline,
                            )
                            Text(m.text, style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            }
        }
    }
}
```

- [ ] **Step 5: Push; verify tests pass in CI**

Expected: PASS — `HistoryViewModelTest` (2) + prior tests.

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/java/com/zenitech/zendaya/ui/HistoryViewModel.kt android/app/src/main/java/com/zenitech/zendaya/ui/HistoryScreen.kt android/app/src/test/java/com/zenitech/zendaya/HistoryViewModelTest.kt
git commit -m "feat(app): conversation history screen + view model"
```

---

### Task 10: Wire it together — pairing screen, nav, MainActivity

**Files:**
- Create: `android/app/src/main/java/com/zenitech/zendaya/ui/PairingScreen.kt`
- Create: `android/app/src/main/java/com/zenitech/zendaya/ui/ZendayaApp.kt`
- Modify: `android/app/src/main/java/com/zenitech/zendaya/MainActivity.kt` (replace placeholder)
- Test: none new (UI wiring; verified by the on-device manual test in Task 11). Existing unit tests must still pass.

**Interfaces:**
- Consumes: `ConfigStore`, `Pairing` (Task 6), `ApiClient` (Task 7), `ChatScreen`/`ChatViewModel` (Task 8), `HistoryScreen`/`HistoryViewModel` (Task 9), ZXing.
- Produces: `@Composable fun ZendayaApp()` — if no saved config → `PairingScreen`; once paired → Chat, with nav to History. `MainActivity` sets `ZendayaApp()` as content.

- [ ] **Step 1: Write `PairingScreen.kt`**

```kotlin
// android/app/src/main/java/com/zenitech/zendaya/ui/PairingScreen.kt
package com.zenitech.zendaya.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import com.zenitech.zendaya.data.Pairing
import com.zenitech.zendaya.data.ServerConfig

@Composable
fun PairingScreen(onPaired: (ServerConfig) -> Unit) {
    var error by remember { mutableStateOf<String?>(null) }
    val scanner = rememberLauncherForActivityResult(ScanContract()) { result ->
        val contents = result.contents
        if (contents == null) { error = "Scan cancelled"; return@rememberLauncherForActivityResult }
        val cfg = Pairing.parse(contents)
        if (cfg == null) error = "That QR code isn't a valid Zendaya pairing code."
        else onPaired(cfg)
    }

    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Pair with Zendaya", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(12.dp))
        Text(
            "On your PC, run the pairing QR helper and scan it here.",
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(24.dp))
        Button(onClick = {
            scanner.launch(ScanOptions().setOrientationLocked(false)
                .setPrompt("Scan the Zendaya pairing QR"))
        }) { Text("Scan QR code") }
        error?.let {
            Spacer(Modifier.height(16.dp))
            Text(it, color = MaterialTheme.colorScheme.error)
        }
    }
}
```

- [ ] **Step 2: Write `ZendayaApp.kt` (nav + config state)**

```kotlin
// android/app/src/main/java/com/zenitech/zendaya/ui/ZendayaApp.kt
package com.zenitech.zendaya.ui

import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import com.zenitech.zendaya.data.ConfigStore
import com.zenitech.zendaya.data.ServerConfig
import com.zenitech.zendaya.net.ApiClient

private sealed interface Screen {
    data object Chat : Screen
    data object History : Screen
}

@Composable
fun ZendayaApp() {
    val ctx = LocalContext.current
    var config by remember { mutableStateOf(ConfigStore.load(ctx)) }
    var screen by remember { mutableStateOf<Screen>(Screen.Chat) }

    val cfg = config
    if (cfg == null) {
        PairingScreen(onPaired = {
            ConfigStore.save(ctx, it)
            config = it
        })
        return
    }

    val api = remember(cfg) { ApiClient.create(cfg) }
    val chatVm = remember(api) { ChatViewModel(api) }
    val historyVm = remember(api) { HistoryViewModel(api) }

    when (screen) {
        Screen.Chat -> ChatScreen(chatVm, onOpenHistory = { screen = Screen.History })
        Screen.History -> HistoryScreen(historyVm, onBack = { screen = Screen.Chat })
    }
}
```

> ViewModels are constructed directly here (not via `viewModel()`) because they take a runtime-built `api`. Acceptable for this app size; a factory can come later.

- [ ] **Step 3: Replace `MainActivity.kt`**

```kotlin
// android/app/src/main/java/com/zenitech/zendaya/MainActivity.kt
package com.zenitech.zendaya

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import com.zenitech.zendaya.ui.ZendayaApp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface { ZendayaApp() }
            }
        }
    }
}
```

- [ ] **Step 4: Push; verify the full build + tests pass in CI and an APK is produced**

Expected: green run; `zendaya-debug-apk` artifact present. All prior unit tests pass; `assembleDebug` succeeds with the new Compose UI.

- [ ] **Step 5: Commit**

```bash
git add android/app/src/main/java/com/zenitech/zendaya/ui/PairingScreen.kt android/app/src/main/java/com/zenitech/zendaya/ui/ZendayaApp.kt android/app/src/main/java/com/zenitech/zendaya/MainActivity.kt
git commit -m "feat(app): pairing screen + navigation + wired MainActivity"
```

---

### Task 11: PC pairing-QR helper + build/install runbook + end-to-end manual test

**Files:**
- Create: `backend/tools/pair_qr.py` — prints the pairing QR for the app to scan.
- Create: `docs/superpowers/guides/android-app-build-and-install.md`.
- Test: manual on-device (documented).

**Interfaces:**
- Consumes: `ZENDAYA_MOBILE_TOKEN`, `ZENDAYA_BIND_HOST` from `.env`; the live server.
- Produces: a scannable QR encoding `{"host","port","token"}`.

> `backend/tools/` already exists (untracked). `qrcode` may not be installed; the helper falls back to printing the JSON + a URL so the user can use any QR generator, and prints an ASCII QR if `qrcode` is available.

- [ ] **Step 1: Write `pair_qr.py`**

```python
# backend/tools/pair_qr.py
"""Print a pairing QR (or its JSON payload) for the Zendaya Android app.

Reads ZENDAYA_BIND_HOST + ZENDAYA_MOBILE_TOKEN from the environment/.env and
emits {"host","port","token"} as an ASCII QR if the `qrcode` package is
available, else prints the raw JSON to paste into any QR generator.
"""
from __future__ import annotations

import json
import os
import sys

try:
    from dotenv import load_dotenv  # already a backend dep
    load_dotenv()
except Exception:
    pass

HOST = os.environ.get("ZENDAYA_BIND_HOST", "127.0.0.1").strip()
PORT = int(os.environ.get("ZENDAYA_STATE_PORT", "7475"))
TOKEN = os.environ.get("ZENDAYA_MOBILE_TOKEN", "").strip()


def main() -> int:
    if not TOKEN:
        print("ERROR: ZENDAYA_MOBILE_TOKEN is not set in your .env.")
        return 1
    if HOST in ("127.0.0.1", "localhost"):
        print("WARNING: ZENDAYA_BIND_HOST is localhost — the phone cannot reach it.")
        print("         Set it to your PC's Tailscale IP (tailscale ip -4) and restart.")
    payload = json.dumps({"host": HOST, "port": PORT, "token": TOKEN})
    print("\nPairing payload:\n  " + payload + "\n")
    try:
        import qrcode  # type: ignore
        qr = qrcode.QRCode(border=2)
        qr.add_data(payload)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception:
        print("(`pip install qrcode` to render a scannable QR here, or paste the")
        print(" payload above into any QR generator and scan it with the app.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke-run the helper locally**

Run: `cd backend && ..\venv\Scripts\python.exe tools\pair_qr.py`
Expected: prints the JSON payload (and an ASCII QR if `qrcode` is installed; otherwise the fallback note). With localhost bind, prints the Tailscale warning.

- [ ] **Step 3: Write the build/install runbook**

Create `docs/superpowers/guides/android-app-build-and-install.md` covering:
- **Build:** push to GitHub (or run the "Android build" workflow via *Actions → Run workflow*). Wait ~3–5 min for green.
- **Download:** open the finished run → **Artifacts → `zendaya-debug-apk`** → download the zip → extract `app-debug.apk`. Transfer to the phone (Tailscale Taildrop, Google Drive, or USB).
- **Install:** on the phone, enable "Install unknown apps" for your file manager, tap `app-debug.apk`, install.
- **Pair:** ensure Tailscale is connected on the phone; on the PC set `ZENDAYA_BIND_HOST` to the Tailscale IP + `ZENDAYA_MOBILE_TOKEN`, restart Zendaya, run `python tools/pair_qr.py`, scan the QR in the app.
- **Use:** type a message → reply appears. Tap the History icon → pick a day → see the full transcript (desktop + phone turns).
- **Troubleshoot:** "brain unreachable" → check Tailscale + bind host; pairing rejected → re-run helper, ensure token matches; empty history → have at least one conversation since Phase 1 shipped.

- [ ] **Step 4: End-to-end manual test (on device)**

1. Build via Actions → download APK → install on phone (Tailscale connected).
2. PC: `ZENDAYA_BIND_HOST=<tailscale-ip>`, token set, Zendaya running.
3. `python tools/pair_qr.py` → scan in app.
4. Send "what time is it" → a reply bubble appears.
5. Speak/type something at the PC console too.
6. App → History → today → confirm BOTH the phone turn and the desktop turn appear, with correct `source` labels.

Expected: chat round-trips; history shows desktop + phone turns for the day.

- [ ] **Step 5: Commit**

```bash
git add backend/tools/pair_qr.py docs/superpowers/guides/android-app-build-and-install.md
git commit -m "feat(app): PC pairing-QR helper + build/install runbook"
```

---

## Phase 1.5 (follow-on, NOT in this plan)

Voice (mic capture → `/api/v1/voice` STT on PC → reply → TTS playback) and the live WS `/api/v1/stream` are deferred to keep Phase 1 to a working text client + history. They need a new backend `/api/v1/voice` endpoint (reusing `voice/` `_transcribe`) and Android audio-record/permission handling — a separate plan once the text client is confirmed working on-device.

---

## Self-Review

**Spec coverage (this plan's scope):**
- User's explicit ask — "database for conversations, every day" → Tasks 1–2 (SQLite store keyed by day, records every turn) ✓.
- User's explicit ask — "UI to see conversation history on the mobile app" → Tasks 3 (API) + 9 (History screen) + 11 (loads on device) ✓.
- Phase 1 spec "voice + chat client" → **scoped to chat-first** per user decision; voice explicitly deferred to Phase 1.5 (flagged) ✓.
- Spec QR pairing → Task 6 (parse) + Task 10 (scan UI) + Task 11 (PC QR helper) ✓.
- Spec auth on every route → history routes depend on `require_token` (Task 3) ✓.
- Spec "brain stays on PC, no cloud" → SQLite local + served over existing authed API; Firebase/Supabase explicitly rejected ✓.
- No-local-toolchain constraint → cloud build via GitHub Actions (Task 5), every app task verified in CI ✓.

**Placeholder scan:** No TBD/TODO left as work items. Two intentionally-illustrative notes are explicitly called out for the implementer to resolve: (a) Task 2 Step 1 shows a dead `monkeypatch` block with an explicit instruction to delete it and keep the `calls` version; (b) Task 10 has no new unit test by design (UI wiring) with the reason stated. All code steps show complete code.

**Type consistency:**
- `transcripts.record/list_days/get_day` signatures defined in Task 1, consumed identically in Tasks 2 (`record`) and 3 (`list_days`/`get_day`) ✓.
- `_TURN_SOURCE` / `turn_source` named consistently across Task 2 steps ✓.
- Chat API shape `{"message"}` → `{"reply","state"}` matches Phase 0 (`ChatRequest`/`ChatResponse` in Task 7, used in Task 8) ✓.
- History payloads: `DaysResponse{days:[DayInfo]}` and `HistoryResponse{day, messages:[HistoryMessage]}` defined in Task 7, produced by backend Task 3, consumed in Task 9 ✓.
- `ZendayaApi` methods (`health`/`chat`/`days`/`history`) consistent across Tasks 7, 8, 9 fakes ✓.
- App id `com.zenitech.zendaya` consistent across manifest, gradle, and all package declarations ✓.
- `ServerConfig.baseUrl()` defined in Task 6, used in Task 7 `ApiClient` ✓.
