# SP-4 · Launch & Ship — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One desktop shortcut launches Zendaya — backend hidden in the background, the Tauri HUD as a desktop window — with crash recovery, file logging, a clean quit path, and a one-time setup script.

**Architecture:** A thin PowerShell shim (behind a desktop `.lnk`) runs a small, unit-tested Python supervisor (`backend/zendaya_launcher.py`) that spawns the backend headless, waits for the state server's `/health`, opens the Tauri HUD `.exe`, and restarts the backend on crash. The backend gains a `--headless` mode (no console REPL) and a clean-quit path (`/quit` → exit code 0, which the supervisor reads as "intentional, don't restart"). The HUD gets a `/quit` command and a "connecting…" indicator.

**Tech Stack:** Python 3.14 (stdlib only for the launcher: `subprocess`, `urllib`, `logging`, `pathlib`), FastAPI/Starlette state server, pytest; React 18 + TypeScript + Zustand + Vitest; Tauri 2 (already scaffolded); Windows PowerShell.

---

## Critical Constraints (read before starting)

**Staging policy — this repo carries a large pre-existing WIP diff. Violating this loses the user's work.**

- **NEVER** `git add -A`, `git add .`, or `git add -u`. Stage only the exact files named in each task's commit step.
- **All commits disable signing:** `git -c commit.gpgsign=false commit -m "…"`.
- **After every commit, run `git status`** and confirm no protected paths were swept in.
- **Protected paths — NEVER stage/commit:** `backend/zendaya.py`, `backend/zendaya_system_access.py`, `pyproject.toml`, `.gitignore`, `zendaya_logs/assistant_history.json`, and anything under `.claude/` or `.superpowers/`.
- **Tasks 1 & 2 edit backend files that carry the user's WIP (`zendaya.py`, `zendaya_state_server.py`).** These tasks **DO NOT COMMIT** — they leave changes in the working tree for the user to review. Their pytest file (`backend/tests/test_quit.py`) is also left **uncommitted** (it can't pass without the uncommitted impl). This mirrors SP-2.
- **Tasks 3–13 create genuinely new files (the launcher, scripts, frontend) or edit clean files (README) — these COMMIT** their named files per task.
- `zendaya_logs/` is where the launcher writes `launcher.log`, `backend.log`, and `launcher.pid` at **runtime**. Those runtime artifacts are never staged.

**Test / build commands (note the `cd` — Bash cwd persists between calls):**

- Backend tests: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_launcher.py -v` (a benign `PytestConfigWarning` may print — ignore it).
- Frontend one file: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test -- <substring>`
- Frontend all: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test`
- Frontend typecheck/build: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run build`
- A benign `warning: LF will be replaced by CRLF` prints on commits — ignore it.

---

## File Structure

| File | Responsibility | Disposition |
|------|----------------|-------------|
| `backend/zendaya_state_server.py` | `POST /quit` route + `on_quit` callback wiring (Task 1) | **edit, DO NOT COMMIT** |
| `backend/zendaya.py` | `--headless` mode + `_SHUTDOWN` + `request_shutdown()` + wire `on_quit` (Task 2) | **edit, DO NOT COMMIT** |
| `backend/tests/test_quit.py` | tests for the two above | **new, DO NOT COMMIT** |
| `backend/zendaya_launcher.py` | the supervisor: health probe, PID, spawn, health-poll, launch HUD, restart, quit, CLI (Tasks 3–8) | **new, COMMIT** |
| `backend/tests/test_launcher.py` | tests for the supervisor | **new, COMMIT** |
| `launch-zendaya.ps1` | thin shim: run the supervisor hidden (Task 9) | **new, COMMIT** |
| `quit-zendaya.ps1` | shim: run the supervisor `--quit` (Task 9) | **new, COMMIT** |
| `setup-zendaya.ps1` | one-time: build HUD + drop desktop shortcuts (Task 9) | **new, COMMIT** |
| `zendaya-hud-react/src/api/backend.ts` | add `quit()` (Task 10) | **edit, COMMIT** |
| `zendaya-hud-react/src/commands/slashRegistry.ts` | add `/quit` command (Task 11) | **edit, COMMIT** |
| `zendaya-hud-react/src/components/HUD/ConnectionStatus.tsx` | "connecting…" pill (Task 12) | **new, COMMIT** |
| `zendaya-hud-react/src/App.tsx` | mount `ConnectionStatus` (Task 12) | **edit, COMMIT** |
| `zendaya-hud-react/src/index.css` | `.zen-conn-status` style (Task 12) | **edit, COMMIT** |
| `README.md` | fix stale run instructions (Task 13) | **edit, COMMIT** |
| `zendaya_backend/start_zendaya.bat` | delete (stale port-8000) (Task 13) | **delete, COMMIT** |

---

## Task 1: Backend — `POST /quit` route + `on_quit` wiring (state server)

**Files:**
- Modify: `backend/zendaya_state_server.py` (add `_ON_QUIT` global, `quit_zendaya` route near the other routes ~`:419`, `on_quit` param in `start()` ~`:640`)
- Test: `backend/tests/test_quit.py` (new)

**DO NOT COMMIT this task.** Leave all changes in the working tree.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_quit.py` with the two state-server tests (the third, for `zendaya`, is added in Task 2):

```python
"""SP-4 — clean-quit path: state-server /quit route + on_quit wiring,
and zendaya.request_shutdown(). Left UNCOMMITTED (tests uncommitted backend edits)."""
import zendaya_state_server as ss


def test_quit_route_invokes_callback(monkeypatch):
    fired = []
    monkeypatch.setattr(ss, "_ON_QUIT", lambda: fired.append(True))
    result = ss.quit_zendaya()
    assert fired == [True]
    assert result == {"ok": True, "shutting_down": True}


def test_quit_route_is_safe_without_callback(monkeypatch):
    monkeypatch.setattr(ss, "_ON_QUIT", None)
    # No callback wired yet — must not raise.
    assert ss.quit_zendaya() == {"ok": True, "shutting_down": True}


def test_start_stores_on_quit(monkeypatch):
    # Stub uvicorn so start() doesn't actually bind a port.
    monkeypatch.setattr(ss.uvicorn, "Config", lambda *a, **k: object())

    class _DummyServer:
        def __init__(self, cfg):
            pass

        def run(self):
            pass

    monkeypatch.setattr(ss.uvicorn, "Server", _DummyServer)
    cb = lambda: None
    ss.start(on_quit=cb)
    assert ss._ON_QUIT is cb
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_quit.py -v`
Expected: FAIL — `AttributeError: module 'zendaya_state_server' has no attribute 'quit_zendaya'` (and `_ON_QUIT`).

- [ ] **Step 3: Add the `_ON_QUIT` global**

In `backend/zendaya_state_server.py`, near the other injected-callback globals (where `_ON_CHAT` / `_ON_WINDOW_CONTROL` are declared), add:

```python
_ON_QUIT = None  # set from start(on_quit=...); called by POST /quit
```

- [ ] **Step 4: Add the `/quit` route**

Add next to the other routes (e.g. right after the `/health` route at `:419-421`):

```python
@app.post("/quit")
def quit_zendaya():
    """Ask the backend to shut down cleanly. Fires the injected on_quit callback."""
    if _ON_QUIT:
        _ON_QUIT()
    return {"ok": True, "shutting_down": True}
```

- [ ] **Step 5: Accept and store `on_quit` in `start()`**

Modify `start(...)` (`:640`). Add the parameter and store it:

```python
def start(
    host: str = "127.0.0.1",
    port: int = 7475,
    on_chat: Optional[Callable[[str], None]] = None,
    on_window_control: Optional[Callable[[str, str], str]] = None,
    window_get_snapshot: Optional[Callable[[], dict]] = None,
    window_pop_events: Optional[Callable[[], list]] = None,
    on_quit: Optional[Callable[[], None]] = None,
) -> threading.Thread:
    """Spawn uvicorn on a daemon thread and return the thread handle."""
    global _ON_CHAT, _ON_WINDOW_CONTROL
    global _WINDOW_GET_SNAPSHOT, _WINDOW_POP_EVENTS
    global _ON_QUIT
    _ON_CHAT = on_chat
    _ON_WINDOW_CONTROL = on_window_control
    _WINDOW_GET_SNAPSHOT = window_get_snapshot
    _WINDOW_POP_EVENTS = window_pop_events
    _ON_QUIT = on_quit

    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    t = threading.Thread(target=server.run, daemon=True, name="zendaya-state-server")
    t.start()
    return t
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_quit.py -v`
Expected: PASS — `test_quit_route_invokes_callback`, `test_quit_route_is_safe_without_callback`, `test_start_stores_on_quit` all green.

- [ ] **Step 7: DO NOT COMMIT — verify the working tree**

Run: `git -C C:/Users/IKA/Zendaya status`
Expected: `backend/zendaya_state_server.py` shows as **modified** and `backend/tests/test_quit.py` shows as **untracked**. **Create no commit.** Confirm no protected path is staged (nothing should be staged at all).

---

## Task 2: Backend — `--headless` mode + `request_shutdown()` (`zendaya.py`)

**Files:**
- Modify: `backend/zendaya.py` (module-level `_SHUTDOWN` + `request_shutdown()` before `def main():` ~`:3647`; wire `on_quit=request_shutdown` at the `_state_server.start(...)` call ~`:3893`; headless branch replacing the bare `main()` at `:3940`)
- Test: `backend/tests/test_quit.py` (append one test)

**DO NOT COMMIT this task.** Leave all changes in the working tree.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_quit.py`:

```python
def test_request_shutdown_sets_event(monkeypatch):
    import importlib
    z = importlib.import_module("zendaya")
    monkeypatch.setattr(z, "log_event", lambda *a, **k: None)
    z._SHUTDOWN.clear()
    assert z._SHUTDOWN.is_set() is False
    z.request_shutdown()
    assert z._SHUTDOWN.is_set() is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_quit.py::test_request_shutdown_sets_event -v`
Expected: FAIL — `AttributeError: module 'zendaya' has no attribute '_SHUTDOWN'`.

- [ ] **Step 3: Ensure `sys` and `threading` are imported**

Confirm `backend/zendaya.py` imports both `sys` and `threading` near the top (it spawns threads, so `threading` is present; `sys` is near-certain). If either is missing, add it to the existing import block.

- [ ] **Step 4: Add `_SHUTDOWN` + `request_shutdown()`**

Insert at module level, immediately **before** `def main():` (`:3647`):

```python
# ── Clean shutdown (headless mode) ──────────────────────
_SHUTDOWN = threading.Event()


def request_shutdown() -> None:
    """Trigger a clean, intentional exit from any quit trigger (voice / HUD /quit /
    Quit shortcut). Sets the headless wait's event so __main__ falls through and the
    process exits with code 0 — the supervisor reads exit-0 as 'do not restart'."""
    log_event("shutdown", "Shutdown requested", {})
    _SHUTDOWN.set()
```

- [ ] **Step 5: Wire `on_quit` into the state-server start**

At the `_state_server.start(...)` call (`:3893-3898`), add the `on_quit` argument:

```python
            _state_server.start(
                on_chat=_bridge_user_message,
                on_window_control=_window_control,
                window_get_snapshot=(_wwatcher.get_snapshot if _wwatcher else None),
                window_pop_events=(_wwatcher.pop_events if _wwatcher else None),
                on_quit=request_shutdown,
            )
```

- [ ] **Step 6: Add the headless branch**

Replace the final bare `main()` call at `:3940` with:

```python
    if "--headless" in sys.argv:
        print("Zendaya running headless — voice + HUD are the input methods.")
        _SHUTDOWN.wait()
        print("System shutdown complete.")
    else:
        main()
```

- [ ] **Step 7: Run the full quit test file to verify it passes**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_quit.py -v`
Expected: PASS — all four tests green.

- [ ] **Step 8: DO NOT COMMIT — verify the working tree**

Run: `git -C C:/Users/IKA/Zendaya status`
Expected: `backend/zendaya.py` and `backend/zendaya_state_server.py` show **modified**, `backend/tests/test_quit.py` shows **untracked**. **Create no commit.** Confirm nothing is staged.

---

## Task 3: Supervisor skeleton — paths, logging, health probe

**Files:**
- Create: `backend/zendaya_launcher.py`
- Test: `backend/tests/test_launcher.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_launcher.py`:

```python
"""SP-4 — zendaya_launcher supervisor tests (pure: mocked subprocess + health)."""
import zendaya_launcher as L


def test_backend_is_ours_true_on_zendaya(monkeypatch):
    monkeypatch.setattr(L, "_http_get_json", lambda url, timeout=2.0: {"ok": True, "name": "Zendaya"})
    assert L.backend_is_ours() is True


def test_backend_is_ours_false_on_wrong_name(monkeypatch):
    monkeypatch.setattr(L, "_http_get_json", lambda url, timeout=2.0: {"name": "Other"})
    assert L.backend_is_ours() is False


def test_backend_is_ours_false_when_down(monkeypatch):
    monkeypatch.setattr(L, "_http_get_json", lambda url, timeout=2.0: None)
    assert L.backend_is_ours() is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_launcher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'zendaya_launcher'`.

- [ ] **Step 3: Create the module skeleton**

Create `backend/zendaya_launcher.py`:

```python
"""zendaya_launcher.py — supervises the Zendaya backend + launches the Tauri HUD.

Run by launch-zendaya.ps1 (hidden). Spawns the backend headless, waits for the
state server's /health, opens the HUD, and restarts the backend if it crashes.
A second launch re-attaches a HUD to the already-running backend. `--quit` shuts
everything down cleanly. Console is hidden, so all diagnostics go to
zendaya_logs/launcher.log.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from logging.handlers import RotatingFileHandler
from pathlib import Path

# ── Paths ───────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
LOG_DIR = REPO_ROOT / "zendaya_logs"
PID_FILE = LOG_DIR / "launcher.pid"
LAUNCHER_LOG = LOG_DIR / "launcher.log"
BACKEND_LOG = LOG_DIR / "backend.log"
VENV_PYTHONW = REPO_ROOT / "venv" / "Scripts" / "pythonw.exe"
RELEASE_DIR = REPO_ROOT / "zendaya-hud-react" / "src-tauri" / "target" / "release"
HUD_EXE_NAME = "Zendaya HUD.exe"

HEALTH_URL = "http://127.0.0.1:7475/health"
QUIT_URL = "http://127.0.0.1:7475/quit"
HEALTH_TIMEOUT = 60.0
HEALTH_INTERVAL = 0.5

CREATE_NO_WINDOW = 0x08000000  # Windows: spawn the child with no console window

log = logging.getLogger("zendaya.launcher")


def setup_logging() -> None:
    """Attach a rotating file handler once (the console is hidden)."""
    if log.handlers:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LAUNCHER_LOG, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


def _http_get_json(url: str, timeout: float = 2.0):
    """GET a URL and parse JSON. Returns None on any error (connection, status, parse)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def backend_is_ours() -> bool:
    """True only when /health responds 200 with the Zendaya identity marker.
    Guards against latching onto an unrelated process holding port 7475."""
    data = _http_get_json(HEALTH_URL)
    return bool(data) and data.get("name") == "Zendaya"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_launcher.py -v`
Expected: PASS — 3 tests green.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/IKA/Zendaya && git -c commit.gpgsign=false commit -m "feat(launch): supervisor skeleton — paths, logging, /health probe" -- backend/zendaya_launcher.py backend/tests/test_launcher.py && git status
```
Confirm `git status` shows no protected paths staged.

---

## Task 4: Supervisor — PID file helpers

**Files:**
- Modify: `backend/zendaya_launcher.py`
- Test: `backend/tests/test_launcher.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_launcher.py`:

```python
def test_pid_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "LOG_DIR", tmp_path)
    monkeypatch.setattr(L, "PID_FILE", tmp_path / "launcher.pid")
    L.write_pid(4242)
    assert L.read_pid() == 4242


def test_read_pid_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "PID_FILE", tmp_path / "nope.pid")
    assert L.read_pid() is None


def test_remove_pid_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "LOG_DIR", tmp_path)
    monkeypatch.setattr(L, "PID_FILE", tmp_path / "launcher.pid")
    L.write_pid(99)
    L.remove_pid()
    L.remove_pid()  # second call must not raise
    assert L.read_pid() is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_launcher.py -k pid -v`
Expected: FAIL — `AttributeError: module 'zendaya_launcher' has no attribute 'write_pid'`.

- [ ] **Step 3: Add the PID helpers**

Append to `backend/zendaya_launcher.py`:

```python
# ── PID file (tracks the supervisor; used by --quit / --status) ──
def write_pid(pid: int | None = None) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid() if pid is None else pid), encoding="utf-8")


def read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def remove_pid() -> None:
    try:
        PID_FILE.unlink()
    except OSError:
        pass
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_launcher.py -k pid -v`
Expected: PASS — 3 tests green.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/IKA/Zendaya && git -c commit.gpgsign=false commit -m "feat(launch): PID-file helpers for the supervisor" -- backend/zendaya_launcher.py backend/tests/test_launcher.py && git status
```

---

## Task 5: Supervisor — spawn backend + health-poll

**Files:**
- Modify: `backend/zendaya_launcher.py`
- Test: `backend/tests/test_launcher.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_launcher.py`:

```python
class _FakePopen:
    last = None

    def __init__(self, args, cwd=None, stdout=None, stderr=None, creationflags=0):
        self.args = args
        self.cwd = cwd
        self.creationflags = creationflags
        self.pid = 1234
        _FakePopen.last = self


def test_spawn_backend_runs_headless(monkeypatch):
    monkeypatch.setattr(L, "_open_log", lambda p: None)
    monkeypatch.setattr(L.subprocess, "Popen", _FakePopen)
    proc = L.spawn_backend()
    assert proc.args[0] == str(L.VENV_PYTHONW)
    assert proc.args[-2:] == ["zendaya.py", "--headless"]
    assert proc.cwd == str(L.BACKEND_DIR)
    assert proc.creationflags == L.CREATE_NO_WINDOW


def test_wait_for_health_true_when_healthy(monkeypatch):
    monkeypatch.setattr(L, "backend_is_ours", lambda: True)
    assert L.wait_for_health(timeout=1, interval=0.01) is True


def test_wait_for_health_times_out(monkeypatch):
    monkeypatch.setattr(L, "backend_is_ours", lambda: False)
    monkeypatch.setattr(L.time, "sleep", lambda s: None)
    assert L.wait_for_health(timeout=0.05, interval=0.01) is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_launcher.py -k "spawn or health" -v`
Expected: FAIL — `AttributeError: ... has no attribute 'spawn_backend'`.

- [ ] **Step 3: Add spawn + health-poll**

Append to `backend/zendaya_launcher.py`:

```python
# ── Spawn the backend + wait for it to be healthy ──
def _open_log(path: Path):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return open(path, "a", encoding="utf-8", buffering=1)


def spawn_backend() -> subprocess.Popen:
    """Launch the backend headless (hidden), teeing its output to backend.log."""
    out = _open_log(BACKEND_LOG)
    proc = subprocess.Popen(
        [str(VENV_PYTHONW), "zendaya.py", "--headless"],
        cwd=str(BACKEND_DIR),
        stdout=out,
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
    )
    log.info("Spawned backend pid=%s", proc.pid)
    return proc


def wait_for_health(timeout: float = HEALTH_TIMEOUT, interval: float = HEALTH_INTERVAL) -> bool:
    """Poll /health until the Zendaya backend answers or the budget elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if backend_is_ours():
            return True
        time.sleep(interval)
    return False
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_launcher.py -k "spawn or health" -v`
Expected: PASS — 3 tests green.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/IKA/Zendaya && git -c commit.gpgsign=false commit -m "feat(launch): spawn backend headless + health-poll" -- backend/zendaya_launcher.py backend/tests/test_launcher.py && git status
```

---

## Task 6: Supervisor — locate + launch the Tauri HUD

**Files:**
- Modify: `backend/zendaya_launcher.py`
- Test: `backend/tests/test_launcher.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_launcher.py`:

```python
def test_find_hud_exe_prefers_product_name(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "RELEASE_DIR", tmp_path)
    monkeypatch.setattr(L, "HUD_EXE_NAME", "Zendaya HUD.exe")
    (tmp_path / "Zendaya HUD.exe").write_text("x")
    (tmp_path / "zzz.exe").write_text("x")
    assert L.find_hud_exe() == tmp_path / "Zendaya HUD.exe"


def test_find_hud_exe_glob_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "RELEASE_DIR", tmp_path)
    monkeypatch.setattr(L, "HUD_EXE_NAME", "Missing.exe")
    (tmp_path / "app.exe").write_text("x")
    assert L.find_hud_exe() == tmp_path / "app.exe"


def test_find_hud_exe_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "RELEASE_DIR", tmp_path / "does-not-exist")
    monkeypatch.setattr(L, "HUD_EXE_NAME", "Missing.exe")
    assert L.find_hud_exe() is None


def test_launch_hud_returns_false_when_missing(monkeypatch):
    monkeypatch.setattr(L, "find_hud_exe", lambda: None)
    called = []
    monkeypatch.setattr(L.subprocess, "Popen", lambda *a, **k: called.append(a))
    assert L.launch_hud() is False
    assert called == []


def test_launch_hud_starts_exe_when_present(tmp_path, monkeypatch):
    exe = tmp_path / "Zendaya HUD.exe"
    exe.write_text("x")
    monkeypatch.setattr(L, "find_hud_exe", lambda: exe)
    started = []
    monkeypatch.setattr(L.subprocess, "Popen", lambda *a, **k: started.append((a, k)))
    assert L.launch_hud() is True
    assert started and started[0][0][0] == [str(exe)]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_launcher.py -k hud -v`
Expected: FAIL — `AttributeError: ... has no attribute 'find_hud_exe'`.

- [ ] **Step 3: Add HUD discovery + launch**

Append to `backend/zendaya_launcher.py`:

```python
# ── Tauri HUD ──
def find_hud_exe() -> Path | None:
    """Locate the built Tauri HUD .exe; prefer the productName, else any top-level .exe."""
    preferred = RELEASE_DIR / HUD_EXE_NAME
    if preferred.exists():
        return preferred
    if RELEASE_DIR.is_dir():
        exes = sorted(RELEASE_DIR.glob("*.exe"))
        if exes:
            return exes[0]
    return None


def launch_hud() -> bool:
    """Open the Tauri HUD window. Returns False (and logs) if the build is missing."""
    exe = find_hud_exe()
    if exe is None:
        log.error("HUD executable not found in %s — run setup-zendaya.ps1 first.", RELEASE_DIR)
        return False
    subprocess.Popen([str(exe)], cwd=str(exe.parent))
    log.info("Launched HUD: %s", exe)
    return True
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_launcher.py -k hud -v`
Expected: PASS — 5 tests green.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/IKA/Zendaya && git -c commit.gpgsign=false commit -m "feat(launch): locate + launch the Tauri HUD exe" -- backend/zendaya_launcher.py backend/tests/test_launcher.py && git status
```

---

## Task 7: Supervisor — supervise loop + crash restart

**Files:**
- Modify: `backend/zendaya_launcher.py`
- Test: `backend/tests/test_launcher.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_launcher.py`:

```python
class _FakeProc:
    def __init__(self, codes):
        self._codes = list(codes)
        self.pid = 99

    def wait(self):
        return self._codes.pop(0)


def test_supervise_clean_exit_no_restart(monkeypatch):
    monkeypatch.setattr(L, "remove_pid", lambda: None)
    spawned = []
    monkeypatch.setattr(L, "spawn_backend", lambda: spawned.append(1))
    assert L.supervise(_FakeProc([0])) == 0
    assert spawned == []


def test_supervise_restarts_on_crash_then_clean(monkeypatch):
    monkeypatch.setattr(L, "remove_pid", lambda: None)
    monkeypatch.setattr(L.time, "sleep", lambda s: None)
    monkeypatch.setattr(L, "spawn_backend", lambda: _FakeProc([0]))  # restart exits clean
    assert L.supervise(_FakeProc([1])) == 0


def test_supervise_gives_up_after_max(monkeypatch):
    monkeypatch.setattr(L, "remove_pid", lambda: None)
    monkeypatch.setattr(L.time, "sleep", lambda s: None)
    monkeypatch.setattr(L, "spawn_backend", lambda: _FakeProc([1]))  # always crash
    assert L.supervise(_FakeProc([1])) == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_launcher.py -k supervise -v`
Expected: FAIL — `AttributeError: ... has no attribute 'supervise'`.

- [ ] **Step 3: Add the supervise loop**

Append to `backend/zendaya_launcher.py`:

```python
# ── Supervision (crash → restart with capped backoff) ──
RESTART_BACKOFF = [1, 2, 4, 8, 16]  # seconds; index clamps to last
MAX_RESTARTS = 5                     # crashes before giving up (avoids hot-loop)


def supervise(proc: subprocess.Popen) -> int:
    """Block on the backend. Exit 0 => intentional quit (stop). Crash => restart with
    capped exponential backoff. Returns the final exit code (0 = clean)."""
    restarts = 0
    while True:
        code = proc.wait()
        if code == 0:
            log.info("Backend exited cleanly (code 0) — shutting down launcher.")
            remove_pid()
            return 0
        log.warning("Backend crashed (code %s).", code)
        if restarts >= MAX_RESTARTS:
            log.error("Backend crashed %s times — giving up.", restarts)
            remove_pid()
            return code
        delay = RESTART_BACKOFF[min(restarts, len(RESTART_BACKOFF) - 1)]
        log.info("Restarting backend in %ss (attempt %s).", delay, restarts + 1)
        time.sleep(delay)
        proc = spawn_backend()
        restarts += 1
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_launcher.py -k supervise -v`
Expected: PASS — 3 tests green.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/IKA/Zendaya && git -c commit.gpgsign=false commit -m "feat(launch): supervise loop with crash restart + backoff cap" -- backend/zendaya_launcher.py backend/tests/test_launcher.py && git status
```

---

## Task 8: Supervisor — quit + CLI entrypoint

**Files:**
- Modify: `backend/zendaya_launcher.py`
- Test: `backend/tests/test_launcher.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_launcher.py`:

```python
def test_main_quit_calls_request_quit(monkeypatch):
    monkeypatch.setattr(L, "setup_logging", lambda: None)
    called = []
    monkeypatch.setattr(L, "request_quit", lambda: called.append(True))
    assert L.main(["--quit"]) == 0
    assert called == [True]


def test_main_reattaches_when_backend_up(monkeypatch):
    monkeypatch.setattr(L, "setup_logging", lambda: None)
    monkeypatch.setattr(L, "backend_is_ours", lambda: True)
    hud, spawned = [], []
    monkeypatch.setattr(L, "launch_hud", lambda: hud.append(True) or True)
    monkeypatch.setattr(L, "spawn_backend", lambda: spawned.append(True))
    assert L.main([]) == 0
    assert hud == [True]
    assert spawned == []  # did NOT start a second backend


def test_main_full_launch_path(monkeypatch):
    monkeypatch.setattr(L, "setup_logging", lambda: None)
    monkeypatch.setattr(L, "backend_is_ours", lambda: False)
    monkeypatch.setattr(L, "write_pid", lambda: None)
    sentinel = object()
    monkeypatch.setattr(L, "spawn_backend", lambda: sentinel)
    monkeypatch.setattr(L, "wait_for_health", lambda: True)
    launched = []
    monkeypatch.setattr(L, "launch_hud", lambda: launched.append(True) or True)
    monkeypatch.setattr(L, "supervise", lambda p: 0 if p is sentinel else 99)
    assert L.main([]) == 0
    assert launched == [True]


def test_main_aborts_on_health_timeout(monkeypatch):
    monkeypatch.setattr(L, "setup_logging", lambda: None)
    monkeypatch.setattr(L, "backend_is_ours", lambda: False)
    monkeypatch.setattr(L, "write_pid", lambda: None)
    monkeypatch.setattr(L, "spawn_backend", lambda: object())
    monkeypatch.setattr(L, "wait_for_health", lambda: False)
    removed, launched = [], []
    monkeypatch.setattr(L, "remove_pid", lambda: removed.append(True))
    monkeypatch.setattr(L, "launch_hud", lambda: launched.append(True))
    assert L.main([]) == 1
    assert launched == []
    assert removed == [True]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_launcher.py -k main -v`
Expected: FAIL — `AttributeError: ... has no attribute 'request_quit'` / `main`.

- [ ] **Step 3: Add quit + CLI**

Append to `backend/zendaya_launcher.py`:

```python
# ── Quit + CLI ──
def request_quit(timeout: float = 10.0) -> None:
    """Ask the running backend to shut down (POST /quit), wait briefly for it to
    exit, then drop the PID file. Used by the Quit shortcut / --quit."""
    try:
        req = urllib.request.Request(QUIT_URL, method="POST", data=b"")
        urllib.request.urlopen(req, timeout=5.0)
        log.info("Sent /quit to backend.")
    except (urllib.error.URLError, OSError) as exc:
        log.warning("Quit request failed (backend may be down): %s", exc)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not backend_is_ours():
            break
        time.sleep(0.25)
    remove_pid()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    setup_logging()

    if "--quit" in argv:
        request_quit()
        return 0

    if "--status" in argv:
        print("Zendaya backend:", "running" if backend_is_ours() else "not running")
        return 0

    # Default: launch. If a healthy Zendaya is already up, just attach a HUD.
    if backend_is_ours():
        log.info("Backend already running — attaching a new HUD.")
        launch_hud()
        return 0

    write_pid()
    proc = spawn_backend()
    if not wait_for_health():
        log.error("Backend did not become healthy within %ss — aborting.", HEALTH_TIMEOUT)
        remove_pid()
        return 1
    launch_hud()
    return supervise(proc)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the full launcher suite to verify it passes**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_launcher.py -v`
Expected: PASS — all launcher tests green (skeleton + pid + spawn/health + hud + supervise + main).

- [ ] **Step 5: Commit**

```bash
cd C:/Users/IKA/Zendaya && git -c commit.gpgsign=false commit -m "feat(launch): --quit path + CLI entrypoint (launch/quit/status, re-attach)" -- backend/zendaya_launcher.py backend/tests/test_launcher.py && git status
```

---

## Task 9: PowerShell scripts — launch / quit / setup

**Files:**
- Create: `launch-zendaya.ps1`, `quit-zendaya.ps1`, `setup-zendaya.ps1` (repo root)

These are thin shims (no unit tests). Verification = a PowerShell **parse check** (validates syntax without executing) plus the manual smoke in Task 14.

- [ ] **Step 1: Create `launch-zendaya.ps1`**

```powershell
# launch-zendaya.ps1 — start Zendaya (backend hidden + HUD) via the supervisor.
$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$pythonw  = Join-Path $repo "venv\Scripts\pythonw.exe"
$launcher = Join-Path $repo "backend\zendaya_launcher.py"
Start-Process -FilePath $pythonw -ArgumentList "`"$launcher`"" -WorkingDirectory $repo -WindowStyle Hidden
```

- [ ] **Step 2: Create `quit-zendaya.ps1`**

```powershell
# quit-zendaya.ps1 — ask the running Zendaya backend to shut down cleanly.
$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$pythonw  = Join-Path $repo "venv\Scripts\pythonw.exe"
$launcher = Join-Path $repo "backend\zendaya_launcher.py"
Start-Process -FilePath $pythonw -ArgumentList "`"$launcher`" --quit" -WorkingDirectory $repo -WindowStyle Hidden -Wait
```

- [ ] **Step 3: Create `setup-zendaya.ps1`**

```powershell
# setup-zendaya.ps1 — one-time: verify venv, build the HUD, drop desktop shortcuts.
$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
$hud  = Join-Path $repo "zendaya-hud-react"

Write-Host "[1/4] Verifying Python venv..."
$pythonw = Join-Path $repo "venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) {
    Write-Error "venv not found at $pythonw. Create it and install backend deps first."
    exit 1
}

Write-Host "[2/4] Building the HUD frontend..."
Push-Location $hud
npm ci
npm run build

Write-Host "[3/4] Building the Tauri desktop app (can take several minutes)..."
npm run build:app
Pop-Location

Write-Host "[4/4] Creating desktop shortcuts..."
$desktop = [Environment]::GetFolderPath("Desktop")
$icon = Join-Path $hud "src-tauri\icons\icon.ico"
$ws = New-Object -ComObject WScript.Shell

$launch = $ws.CreateShortcut((Join-Path $desktop "Zendaya.lnk"))
$launch.TargetPath = "powershell.exe"
$launch.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$(Join-Path $repo 'launch-zendaya.ps1')`""
$launch.WorkingDirectory = $repo
$launch.IconLocation = $icon
$launch.Save()

$quit = $ws.CreateShortcut((Join-Path $desktop "Quit Zendaya.lnk"))
$quit.TargetPath = "powershell.exe"
$quit.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$(Join-Path $repo 'quit-zendaya.ps1')`""
$quit.WorkingDirectory = $repo
$quit.IconLocation = $icon
$quit.Save()

Write-Host "Done. Shortcuts 'Zendaya' and 'Quit Zendaya' are on your desktop."
```

- [ ] **Step 4: Parse-check all three scripts (syntax only, no execution)**

Run (PowerShell tool):
```powershell
$errs = $null
foreach ($f in "launch-zendaya.ps1","quit-zendaya.ps1","setup-zendaya.ps1") {
  [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PWD $f), [ref]$null, [ref]$errs) | Out-Null
  if ($errs) { Write-Error "$f has parse errors"; $errs } else { Write-Host "$f OK" }
}
```
Expected: `launch-zendaya.ps1 OK`, `quit-zendaya.ps1 OK`, `setup-zendaya.ps1 OK` — no parse errors.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/IKA/Zendaya && git -c commit.gpgsign=false commit -m "feat(launch): PowerShell launch/quit/setup scripts" -- launch-zendaya.ps1 quit-zendaya.ps1 setup-zendaya.ps1 && git status
```

---

## Task 10: Frontend — `backend.quit()`

**Files:**
- Modify: `zendaya-hud-react/src/api/backend.ts`
- Test: `zendaya-hud-react/src/__tests__/backend-quit.test.ts` (new)

- [ ] **Step 1: Write the failing tests**

Create `zendaya-hud-react/src/__tests__/backend-quit.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { quit } from "../api/backend";

afterEach(() => vi.restoreAllMocks());

describe("quit", () => {
  it("POSTs to /quit", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    await quit();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:7475/quit");
    expect(init.method).toBe("POST");
  });

  it("swallows fetch errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    await expect(quit()).resolves.toBeUndefined();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test -- backend-quit`
Expected: FAIL — `quit` is not exported from `../api/backend`.

- [ ] **Step 3: Add `quit()`**

Append to `zendaya-hud-react/src/api/backend.ts`:

```ts
/** Ask the backend to shut down cleanly (used by the /quit command). Never throws. */
export async function quit(): Promise<void> {
  await fetch(`${backendHttpOrigin()}/quit`, { method: "POST" }).catch(() => {});
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test -- backend-quit`
Expected: PASS — 2 tests green.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/IKA/Zendaya && git -c commit.gpgsign=false commit -m "feat(hud): backend.quit() POSTs /quit" -- zendaya-hud-react/src/api/backend.ts zendaya-hud-react/src/__tests__/backend-quit.test.ts && git status
```

---

## Task 11: Frontend — `/quit` slash command

**Files:**
- Modify: `zendaya-hud-react/src/commands/slashRegistry.ts`
- Test: `zendaya-hud-react/src/__tests__/slashQuit.test.ts` (new — kept separate so the `backend` module mock doesn't touch the existing `slashRegistry.test.ts`)

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/slashQuit.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";

const { quitMock } = vi.hoisted(() => ({ quitMock: vi.fn() }));
vi.mock("../api/backend", () => ({ quit: quitMock }));

import { runSlash } from "../commands/slashRegistry";

describe("/quit slash command", () => {
  it("calls backend.quit and confirms", () => {
    const msg = runSlash("quit", []);
    expect(quitMock).toHaveBeenCalledTimes(1);
    expect(msg).toContain("shutting down");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test -- slashQuit`
Expected: FAIL — `runSlash("quit", …)` returns `unknown command: /quit` and `quitMock` is never called.

- [ ] **Step 3: Add the `/quit` command**

In `zendaya-hud-react/src/commands/slashRegistry.ts`, add the import after the existing imports:

```ts
import { quit } from "../api/backend";
```

Add a `quit` entry to `SLASH_COMMANDS` (e.g. right before the `help` entry):

```ts
  quit: {
    help: "/quit — shut Zendaya down",
    run: () => { void quit(); return "→ shutting down Zendaya…"; },
  },
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test -- slashQuit`
Expected: PASS — 1 test green.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/IKA/Zendaya && git -c commit.gpgsign=false commit -m "feat(hud): /quit slash command shuts Zendaya down" -- zendaya-hud-react/src/commands/slashRegistry.ts zendaya-hud-react/src/__tests__/slashQuit.test.ts && git status
```

---

## Task 12: Frontend — "connecting…" indicator

**Files:**
- Create: `zendaya-hud-react/src/components/HUD/ConnectionStatus.tsx`
- Modify: `zendaya-hud-react/src/App.tsx` (import + mount), `zendaya-hud-react/src/index.css` (append style)
- Test: `zendaya-hud-react/src/__tests__/ConnectionStatus.test.tsx` (new)

- [ ] **Step 1: Write the failing tests**

Create `zendaya-hud-react/src/__tests__/ConnectionStatus.test.tsx`:

```tsx
import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { useZendaya } from "../store/zendayaStore";
import ConnectionStatus from "../components/HUD/ConnectionStatus";

beforeEach(() => useZendaya.setState({ connected: true }));

describe("ConnectionStatus", () => {
  it("renders nothing when connected", () => {
    useZendaya.setState({ connected: true });
    render(<ConnectionStatus />);
    expect(screen.queryByTestId("connection-status")).toBeNull();
  });

  it("shows 'connecting…' when disconnected", () => {
    useZendaya.setState({ connected: false });
    render(<ConnectionStatus />);
    expect(screen.getByTestId("connection-status")).toBeTruthy();
    expect(screen.getByText("connecting…")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test -- ConnectionStatus`
Expected: FAIL — cannot resolve `../components/HUD/ConnectionStatus`.

- [ ] **Step 3: Create the component**

Create `zendaya-hud-react/src/components/HUD/ConnectionStatus.tsx`:

```tsx
import { useZendaya } from "../../store/zendayaStore";

/** A small corner pill shown while the HUD isn't connected to the backend, so the
 *  boot handshake and any crash-restart reconnect window read as intentional
 *  rather than broken. Hidden once connected. */
export default function ConnectionStatus() {
  const connected = useZendaya((s) => s.connected);
  if (connected) return null;
  return (
    <div className="zen-conn-status" data-testid="connection-status" role="status">
      connecting…
    </div>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test -- ConnectionStatus`
Expected: PASS — 2 tests green.

- [ ] **Step 5: Mount in `App.tsx`**

Add the import after the `CommandTerminal` import (line 12):

```tsx
import ConnectionStatus from "./components/HUD/ConnectionStatus";
```

Render it right after `<CommandTerminal />` (line 83):

```tsx
        <CommandTerminal />
        <ConnectionStatus />
```

- [ ] **Step 6: Append the style**

Append to the **end** of `zendaya-hud-react/src/index.css`:

```css
.zen-conn-status {
  position: fixed;
  top: 14px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 50;
  padding: 4px 12px;
  border-radius: 999px;
  font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
  font-size: 12px;
  letter-spacing: 0.04em;
  color: color-mix(in srgb, var(--zen-primary) 85%, #fff);
  background: color-mix(in srgb, #000 70%, transparent);
  border: 1px solid color-mix(in srgb, var(--zen-primary) 55%, transparent);
  box-shadow: 0 0 16px color-mix(in srgb, var(--zen-primary) 28%, transparent);
  backdrop-filter: blur(6px);
  animation: zen-conn-pulse 1.6s ease-in-out infinite;
}

@keyframes zen-conn-pulse {
  0%, 100% { opacity: 0.55; }
  50% { opacity: 1; }
}
```

- [ ] **Step 7: Build to typecheck the App + CSS changes**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run build`
Expected: build succeeds (no TS errors).

- [ ] **Step 8: Commit**

```bash
cd C:/Users/IKA/Zendaya && git -c commit.gpgsign=false commit -m "feat(hud): connecting… indicator driven by store.connected" -- zendaya-hud-react/src/components/HUD/ConnectionStatus.tsx zendaya-hud-react/src/__tests__/ConnectionStatus.test.tsx zendaya-hud-react/src/App.tsx zendaya-hud-react/src/index.css && git status
```

---

## Task 13: Cleanup — README run instructions + remove stale `.bat`

**Files:**
- Modify: `README.md` (`:108-112` install/run block)
- Delete: `zendaya_backend/start_zendaya.bat`

- [ ] **Step 1: Fix the stale run instructions in `README.md`**

Replace the stale block (currently lines 108-112):

```
# Test database connection
poetry run python test_db_connection.py

# Start the backend
poetry run python main.py
```

with:

```
# Dev: run the backend directly (interactive console REPL)
cd backend
python zendaya.py
```

Then, immediately **after** the closing ``` of that fenced block (after line 113), insert a production-launch note:

```markdown

> **Production launch (Windows):** run `setup-zendaya.ps1` once (builds the HUD
> and creates desktop shortcuts), then start everything with the **Zendaya**
> desktop shortcut — it runs the backend hidden in the background and opens the
> HUD. Quit with the **Quit Zendaya** shortcut or by typing `/quit` in the HUD.
```

- [ ] **Step 2: Delete the stale launcher**

```bash
cd C:/Users/IKA/Zendaya && git rm zendaya_backend/start_zendaya.bat
```

Expected: `rm 'zendaya_backend/start_zendaya.bat'`.

- [ ] **Step 3: Verify the README has no remaining `poetry run python main.py`**

Use the Grep tool: pattern `poetry run python main\.py`, path `README.md`.
Expected: no matches.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/IKA/Zendaya && git -c commit.gpgsign=false commit -m "chore(launch): fix stale README run steps; remove old start_zendaya.bat" -- README.md zendaya_backend/start_zendaya.bat && git status
```

Note: `git rm` already stages the deletion; naming the path in the commit is safe. Confirm `git status` shows no protected paths staged.

---

## Task 14: Final verification + manual smoke checklist

**Files:** none (verification only — no commit).

- [ ] **Step 1: Full backend launcher + quit suites**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_launcher.py tests/test_quit.py -v`
Expected: all green (launcher suite + the 4 quit tests). Benign `PytestConfigWarning` may print — ignore.

- [ ] **Step 2: Full frontend suite + build**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test`
Expected: all suites pass (prior 199 + the new `backend-quit`, `slashQuit`, `ConnectionStatus` tests).

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run build`
Expected: build succeeds.

- [ ] **Step 3: Confirm staging boundary held**

Run: `git -C C:/Users/IKA/Zendaya status`
Expected: `backend/zendaya.py`, `backend/zendaya_state_server.py` show **modified** but **uncommitted**; `backend/tests/test_quit.py` **untracked**; no protected path was ever committed. The committed SP-4 work is only: `zendaya_launcher.py` + `test_launcher.py`, the three `.ps1` scripts, the frontend files, README, and the `.bat` deletion.

- [ ] **Step 4: Manual smoke checklist (requires a real Windows desktop session; cannot be automated here)**

Document these for the user to run; do not block on them:

1. Run `powershell -ExecutionPolicy Bypass -File setup-zendaya.ps1` once → `dist/` builds, the Tauri `.exe` builds, and **Zendaya** + **Quit Zendaya** shortcuts appear on the desktop.
2. Double-click **Zendaya** → no console window appears; after a moment the HUD window opens already connected (the "connecting…" pill flashes then disappears). `Task Manager` shows a `pythonw.exe`.
3. Close the HUD window → `pythonw.exe` keeps running (backend stays up).
4. Double-click **Zendaya** again → a HUD window re-attaches; **no second** `pythonw` backend appears.
5. Kill the backend `pythonw.exe` from Task Manager → within the backoff delay a new backend `pythonw.exe` appears; check `zendaya_logs/launcher.log` shows "Backend crashed" + "Restarting".
6. Type `/quit` in the HUD terminal (or run the **Quit Zendaya** shortcut) → the backend exits, the supervisor exits, the HUD closes, and `zendaya_logs/launcher.pid` is gone.

- [ ] **Step 5: Report**

Summarize: tests green (counts), build clean, staging boundary intact (backend WIP left uncommitted), and the manual smoke checklist handed to the user. Then proceed to `superpowers:finishing-a-development-branch`.

---

## Self-Review (completed by plan author)

**Spec coverage:**
- Headless backend (`--headless` + idle wait) → Task 2. ✓
- Clean quit / exit-code contract (`request_shutdown`, `/quit` route, `on_quit`) → Tasks 1–2; supervisor reads exit-0 → Task 7. ✓
- Supervisor (`backend_is_ours`, PID, spawn, health-poll, find/launch HUD, supervise+backoff, request_quit, CLI, re-attach) → Tasks 3–8. ✓
- Rotating file logging + backend.log tee → Task 3 (`setup_logging`), Task 5 (`_open_log`/`stdout`). ✓
- Single-instance / re-attach (health-gated) → Task 8 `main`. ✓
- PowerShell shim + quit + one-time setup (build HUD + shortcuts) → Task 9. ✓
- `/quit` slash + `backend.quit()` → Tasks 10–11. ✓
- "connecting…" indicator on `store.connected` → Task 12. ✓
- Cleanup (README + delete `start_zendaya.bat`) → Task 13. ✓
- Testing matrix (launcher pytest, `/quit` route pytest, frontend vitest, manual smoke) → Tasks 1–12 + Task 14. ✓

**Placeholder scan:** none — every code step shows complete code; every test step shows exact commands + expected results.

**Type/name consistency:** verified across tasks — `backend_is_ours`, `spawn_backend`, `wait_for_health`, `find_hud_exe`, `launch_hud`, `supervise`, `request_quit`, `main`, `write_pid`/`read_pid`/`remove_pid`, `setup_logging`, `_http_get_json`, `_open_log`, constants (`VENV_PYTHONW`, `RELEASE_DIR`, `HUD_EXE_NAME`, `CREATE_NO_WINDOW`, `HEALTH_URL`, `QUIT_URL`, `RESTART_BACKOFF`, `MAX_RESTARTS`) are referenced identically in tests and implementations. Backend: `_ON_QUIT`, `quit_zendaya`, `start(on_quit=…)`, `_SHUTDOWN`, `request_shutdown` consistent across Tasks 1–2 and `test_quit.py`. Frontend: `quit` (api), `/quit` slash, `ConnectionStatus` + `connected` consistent.

**Staging consistency:** Tasks 1–2 explicitly DO NOT COMMIT (and `test_quit.py` stays uncommitted with them); Tasks 3–13 commit only their named files; every commit step ends with `git status`. Protected paths never staged.
