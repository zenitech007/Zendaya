# SP-4 · Launch & Ship — Design

**Date:** 2026-06-05
**Status:** Approved (design); pending implementation plan
**Part of:** "Full AI UI" initiative (SP-4 of 4 — final)

---

## Context

The "full AI UI" initiative made the HUD a first-class surface: SP-1 added an
in-HUD command terminal, SP-3 put a music player in the HUD, and SP-2 made
Zendaya's TTS voice play **out of the HUD** instead of the backend speaker. What
is still missing is the last item of the user's original request:

> "Create a shortcut on desktop that opens the HUD once and runs the backend in
> the background … MORE things you think can make it fully ready for production."

Today, launching Zendaya is a developer ritual: open a terminal, activate the
venv, `python zendaya.py` (which blocks on a console REPL), then *separately*
start the HUD (`npm run dev` on Vite port 5180 or `npm run build:app` for
Tauri). There is no single entry point, the backend needs a visible console, and
several stale launch artifacts (an old port-8000 `start_zendaya.bat`, a README
that says `poetry run python main.py`) actively mislead.

SP-4 closes this: **one desktop shortcut launches everything** — backend hidden
in the background, HUD as a real desktop window — plus the production-readiness
polish that an always-on background process needs (crash recovery, file logs, a
clean quit path, and a one-time setup script).

This is the fourth and final decomposed sub-project:

- **SP-1 · Command bridge** *(done)* — type commands in the HUD to drive Zendaya.
- **SP-2 · Voice from the HUD** *(done)* — Zendaya's TTS audio plays in the browser.
- **SP-3 · In-HUD music player** *(done)* — local music plays out of the HUD.
- **SP-4 · Launch & ship** *(this spec)* — one desktop shortcut, backend in the
  background, production polish.

### Decisions locked in during brainstorming

1. **HUD target: Tauri desktop app.** Build on the existing
   `zendaya-hud-react/src-tauri/` scaffold (frameless "Zendaya HUD" window,
   1280×800, `frontendDist ../dist`). The HUD ships as a native `.exe`, not a
   browser tab.
2. **Backend lifecycle: launcher orchestrates.** A single launcher starts the
   Python backend (hidden, using the existing repo venv), waits until the state
   server is healthy, then opens the Tauri HUD. **No** Python-to-exe bundling.
   Targets the user's own machine.
3. **On HUD close: backend stays running (always-on).** A single-instance guard
   prevents a second backend. Re-running the shortcut re-attaches a fresh HUD to
   the already-running backend. **No system tray.**
4. **Orchestration mechanism: Approach B** — a thin PowerShell shim behind the
   desktop shortcut invokes a small, **unit-testable Python supervisor**
   (`zendaya_launcher.py`) that owns spawn-hidden, health-poll, crash-restart,
   logging, single-instance, and quit. Chosen over pure-PowerShell (Approach A —
   supervision logic is awkward and untestable in PS) and Tauri/Rust-owned
   (Approach C — conflicts with "launcher orchestrates" + "always-on backend
   survives HUD close", and is the hardest to test).
5. **Production polish: all four items** — (1) one-time setup script, (2) crash
   auto-restart + rotating file logging, (3) quit command (no tray), (4) clean up
   stale launch cruft.

### What already exists (verified)

- `zendaya.py:3704` `if __name__ == "__main__":` starts every daemon thread —
  voice listener (`:3707`), alerts (`:3710`), proactive (`:3713`), perception /
  window watcher, and the **state server** via `_state_server.start(...)`
  (`:3893`, uvicorn on `127.0.0.1:7475`, daemon thread) — and **then** calls
  `main()` at **`:3940`**. `main()` (`:3647`) is the console REPL; its only
  blocking call is `input("\nYou: ")` at `:3666`. So **every background service
  is already up before line 3940**; only that final `main()` blocks on stdin.
- `zendaya_state_server.py:419` `@app.get("/health")` → `{"ok": True, "name":
  "Zendaya"}`. A ready/identity probe already exists — the supervisor polls it.
- `zendaya_state_server.py:485` `@app.post("/chat")` and the route table
  (`/ws`, `/music/*`, `/window/control`, …) show the FastAPI `app` and its
  decorator pattern — a new `@app.post("/quit")` slots in the same way.
  `_state_server.start(on_chat=…, on_window_control=…, …)` (`:3893`) is the
  existing pattern for injecting backend callbacks into the server.
- The HUD's `useWebSocket.ts` already maintains a `connected` flag with
  **auto-reconnect** (`:41` `setConnected(true)`, `:50` `onclose` →
  `setConnected(false)` + retry). The "connecting…" affordance builds on state
  that already exists.
- SP-1 built the HUD command terminal: `src/commands/slashRegistry.ts`
  (`runSlash`) and `src/api/backend.ts` (`sendChat` → POST `/chat`). A `/quit`
  slash command + a `backend.quit()` POST follow those exact patterns.
- **Tauri is already scaffolded:** `src-tauri/tauri.conf.json`,
  `package.json` scripts `build:app` = `tauri build` and `dev:app`, deps
  `@tauri-apps/api` + `@tauri-apps/cli`. The release `.exe` lands under
  `src-tauri/target/release/`.
- The repo venv is at `C:\Users\IKA\Zendaya\venv\` (`Scripts\python.exe` /
  `Scripts\pythonw.exe`). `pyproject.toml` package `zendaya-ai-backend` v1.0.0
  has **no** `[project.scripts]` — Approach B doesn't need one (the shim invokes
  the launcher script by path).
- **Stale cruft:** `zendaya_backend/start_zendaya.bat` references the OLD
  port-8000 backend; the README says `poetry run python main.py`. Both mislead.

---

## Architecture

**A hidden Python supervisor, launched by a thin shim, orchestrates an always-on
backend and the Tauri HUD.** The supervisor is the only long-lived foreground of
the launch; it survives HUD close, so closing the window never kills Zendaya.

```
desktop .lnk "Zendaya"
        │
        ▼
launch-zendaya.ps1   (thin shim: cd repo, set PYTHONIOENCODING, run pythonw hidden)
        │
        ▼
backend/zendaya_launcher.py   ── the supervisor (testable Python) ──┐
        │                                                            │
        ├─ single-instance guard (PID file in zendaya_logs/)        │
        │     └─ already running + /health == "Zendaya"?            │
        │           → just open a HUD window, exit (re-attach)      │
        │                                                           ▼
        ├─ spawn backend:  pythonw zendaya.py --headless     zendaya_logs/launcher.log
        │     (CREATE_NO_WINDOW, repo venv, cwd=backend)       (RotatingFileHandler)
        │                                                           ▲
        ├─ health-poll  GET /health  until 200 (60 s budget) ──────┘
        │
        ├─ launch Tauri .exe  (src-tauri/target/release/…)   ← once backend healthy
        │
        └─ supervise: wait on backend process
              ├─ exit code 0  → intentional quit → clean stop, remove PID, exit
              └─ crash/non-0  → log + restart with capped exponential backoff
```

### 1. Backend: headless mode + clean quit (`zendaya.py`)

Two surgical edits to `__main__`, plus a small shutdown helper. No change to any
daemon-thread startup — they already run before `main()`.

- **`--headless` flag.** Parse it at the top of `__main__` (a plain
  `"--headless" in sys.argv` check — no argparse needed for one flag). At
  **`:3940`**, replace the unconditional `main()` with:

  ```python
  if _HEADLESS:
      print("Zendaya running headless (no console REPL). Awaiting voice / HUD input.")
      _SHUTDOWN.wait()          # module-level threading.Event — blocks without stdin
      print("System shutdown complete.")
  else:
      main()
  ```

  All input then arrives via the **voice listener** and the **HUD command
  terminal** (both already running as background services). `main()` is untouched
  for the developer's interactive `python zendaya.py` workflow.

- **`request_shutdown()` helper** (module level):

  ```python
  _SHUTDOWN = threading.Event()

  def request_shutdown() -> None:
      """Trigger a clean, intentional exit (code 0) from any quit trigger."""
      log_event("shutdown", "Shutdown requested", {})
      _SHUTDOWN.set()
  ```

  When `_SHUTDOWN` is set, the headless wait returns, `__main__` falls off the
  end, and the process exits **0**. The supervisor reads exit-0 as "intentional —
  do not restart." (A crash or kill yields non-zero / a signal → restart.) Three
  triggers call `request_shutdown()`:
  - **Voice:** "shut down" / "quit zendaya" routed through the existing command
    path.
  - **HUD `/quit`:** via the new `POST /quit` route (below).
  - **Quit shortcut:** the supervisor's `--quit` mode posts `/quit`.

- **Wire the quit callback** at `_state_server.start(...)` (`:3893`): pass
  `on_quit=request_shutdown` alongside the existing `on_chat` / `on_window_control`.

### 2. Backend: quit route (`zendaya_state_server.py`)

Mirror the existing injected-callback pattern (`on_chat`, `on_window_control`):

```python
# stored at start(...) like the other callbacks
_on_quit = None  # set from start(on_quit=...)

@app.post("/quit")
def quit_zendaya():
    if _on_quit:
        _on_quit()                       # → zendaya.request_shutdown()
    return {"ok": True, "shutting_down": True}
```

`start(...)` gains an `on_quit=None` parameter and stashes it, exactly as it
already does for `on_chat`. The route returns **before** the process exits (the
event-driven shutdown happens on the main thread), so the HUD gets a clean 200.

### 3. The supervisor — `backend/zendaya_launcher.py` (new, TDD'd)

Pure, dependency-light Python (`subprocess`, `urllib`/`requests`, `logging`,
`os`, `time`, `sys`, `pathlib`). Every branch is unit-testable by mocking
`subprocess.Popen` and the health probe. Public surface:

- **`backend_is_ours() -> bool`** — GET `http://127.0.0.1:7475/health`; true only
  when it returns 200 **and** JSON `name == "Zendaya"`. Guards against latching
  onto an unrelated process that happens to hold port 7475.
- **`already_supervising() -> bool`** — read the PID file
  (`zendaya_logs/launcher.pid`); true when that PID is alive **and**
  `backend_is_ours()`. Stale/dead PID files are ignored (and rewritten).
- **`wait_for_health(timeout=60, interval=0.5) -> bool`** — poll
  `backend_is_ours()` until true or the budget elapses.
- **`spawn_backend() -> subprocess.Popen`** — launch
  `pythonw zendaya.py --headless` with `creationflags=CREATE_NO_WINDOW`,
  `cwd=backend/`, repo-venv interpreter. Returns the handle.
- **`launch_hud() -> None`** — start the Tauri release `.exe` from
  `src-tauri/target/release/`. If the exe is missing, log a clear "run
  `setup-zendaya.ps1` first" message and abort the launch.
- **`supervise(proc) -> int`** — wait on the backend; on **exit 0** clean up and
  return; on **crash** log it and restart via `spawn_backend()` with **capped
  exponential backoff** (e.g. 1→2→4→8 s, max ~5 restarts in a rolling window;
  exceeding the cap logs "giving up" and exits non-zero so it never hot-loops).
- **`request_quit() -> None`** — POST `/quit`, wait briefly for the backend to
  exit, remove the PID file. Used by `--quit`.
- **`main(argv)`** — CLI:
  - default (`launch`): if `already_supervising()` → `launch_hud()` and exit
    (re-attach); else write PID file, `spawn_backend()`, `wait_for_health()`
    (timeout → log + exit non-zero), `launch_hud()`, `supervise(proc)`.
  - `--quit`: `request_quit()`.
  - `--status` *(small, free)*: print whether a healthy supervised backend exists.

**Logging:** module-level `RotatingFileHandler` →
`zendaya_logs/launcher.log` (e.g. 1 MB × 3 backups). Because the backend console
is hidden, this log is the operator's only window into spawns, health timeouts,
crashes, restarts, and quits. The supervisor also tees the backend's own
stdout/stderr to a sibling `zendaya_logs/backend.log` (the `Popen` stdout/stderr
redirect), so a hidden crash leaves a trace.

### 4. Scripts (PowerShell, thin, manually verified)

Live at the **repo root** so the desktop shortcuts have a stable target.

- **`launch-zendaya.ps1`** — the only thing the "Zendaya" shortcut runs. ~5
  lines: `Set-Location` to the repo, `$env:PYTHONIOENCODING="utf-8"`, then
  `Start-Process venv\Scripts\pythonw.exe -ArgumentList "backend\zendaya_launcher.py" -WindowStyle Hidden`.
  `pythonw.exe` guarantees no console flash even before the launcher sets up its
  own hidden spawn.
- **`quit-zendaya.ps1`** — what the "Quit Zendaya" shortcut runs:
  `pythonw backend\zendaya_launcher.py --quit`.
- **`setup-zendaya.ps1`** (one-time, run once per machine):
  1. Verify the venv exists and key deps import (fail fast with a clear message
     if not).
  2. `npm --prefix zendaya-hud-react ci` then `npm --prefix zendaya-hud-react run
     build` → produces `dist/`.
  3. `npm --prefix zendaya-hud-react run build:app` → produces the Tauri release
     `.exe`.
  4. Create two desktop shortcuts via `WScript.Shell` `CreateShortcut`:
     **"Zendaya"** → `launch-zendaya.ps1`, **"Quit Zendaya"** →
     `quit-zendaya.ps1` (both invoked through `powershell.exe -WindowStyle Hidden
     -File …`).
  5. Print where the shortcuts landed and a one-line "you're done" message.

### 5. HUD changes (frontend `src/`)

- **`/quit` slash command** — add to `slashRegistry.ts` a `quit` command that
  calls a new **`backend.quit()`** (POST `http://127.0.0.1:7475/quit`) added to
  `src/api/backend.ts` next to `sendChat`. Explicit and NLU-free: typing `/quit`
  in the HUD terminal shuts Zendaya down cleanly.
- **"connecting…" affordance** — a small status indicator driven by the store's
  existing `connected` flag. Visible while the WebSocket is not open, so the
  boot handshake and any crash-restart reconnect window read as **intentional**
  rather than broken. Minimal: a corner pill/text, no new connection logic
  (auto-reconnect already exists).

### 6. Cleanup (polish item 4)

- **README:** replace the stale `poetry run python main.py` run instructions
  with: run `setup-zendaya.ps1` once, then launch via the **Zendaya** desktop
  shortcut (and quit via **Quit Zendaya** or `/quit`).
- **Delete `zendaya_backend/start_zendaya.bat`** — it points at the dead
  port-8000 backend and only causes confusion.

### 7. Testing

- **Supervisor (pytest)** — the heart of the testing, all with mocked
  `subprocess`/health:
  - `backend_is_ours()`: 200 + `name=="Zendaya"` → true; wrong name / non-200 /
    connection error → false.
  - `already_supervising()`: live PID + ours → true; dead/stale PID → false (and
    PID file rewritten).
  - `wait_for_health()`: returns true once healthy; returns false at timeout.
  - `supervise()`: exit-0 → no restart + PID cleaned; crash → `spawn_backend()`
    re-called; backoff escalates and the restart cap halts the loop.
  - `request_quit()`: POSTs `/quit` and removes the PID file.
  - `main(["--status"])` / re-attach branch: `already_supervising()` true → HUD
    launched, backend **not** re-spawned.
- **State server (pytest):** `POST /quit` invokes the injected `on_quit`
  callback and returns `{"ok": True}`; `start(on_quit=…)` stashes it.
- **Frontend (vitest + happy-dom):**
  - `slashRegistry`: `/quit` routes to a mocked `backend.quit` (mirrors the SP-1
    slash tests).
  - `backend.quit()`: issues a POST to `/quit` (mock `fetch`).
  - connection indicator: renders the "connecting…" state when `connected` is
    false, hides it when true.
- **Not automatable (manual smoke checklist in the plan):** run
  `setup-zendaya.ps1`; double-click **Zendaya** → backend starts hidden, HUD
  opens connected, no console window; close the HUD → backend keeps running
  (Task Manager shows `pythonw`); re-run the shortcut → a HUD re-attaches, no
  second backend; kill the backend → supervisor restarts it (check
  `launcher.log`); `/quit` (and the **Quit Zendaya** shortcut) → backend and
  supervisor both exit, PID file gone.

---

## Staging policy

Mirrors SP-2/SP-3, adapted to the working-tree reality:

- **Committable (clean / new files):** the launcher's **new** sibling artifacts
  — `backend/zendaya_launcher.py`, its pytest file, the three root `*.ps1`
  scripts, the frontend changes (`src/api/backend.ts`,
  `src/commands/slashRegistry.ts`, the connection indicator + their tests), and
  this spec / the plan. Each task **commits only its named files** with
  `git -c commit.gpgsign=false`, and `git status` is checked after every commit.
  - **README** edit and the `start_zendaya.bat` **deletion** are committable
    (neither is a protected path).
- **DO NOT COMMIT (leave for user review):** `zendaya.py` (carries the user's
  large pre-existing WIP diff + the SP-2 edits) and `zendaya_state_server.py`
  (carries uncommitted SP-2/SP-3 edits). The `--headless` / `request_shutdown`
  edit and the `POST /quit` route are made in the working tree and left
  **unstaged** for the user to review and commit themselves — same as SP-2.
- **Never** `git add -A`, `git add .`, or `git add -u`. Stage only the exact
  files named in each task. Never touch the protected paths
  (`zendaya.py` *(edited but never auto-committed)*, `zendaya_system_access.py`,
  `pyproject.toml`, `.gitignore`, `zendaya_logs/assistant_history.json`) or
  anything under `.claude/` / `.superpowers/`. Note `zendaya_logs/` is where the
  launcher writes logs + the PID file at **runtime**; those runtime artifacts are
  never staged.

## Out of scope (YAGNI)

- **Python-to-exe bundling** (PyInstaller/Nuitka). The supervisor uses the
  existing repo venv; no single-file backend.
- **System tray / menu-bar icon.** Quit is `/quit`, voice, or the Quit shortcut.
- **Cross-platform launch.** Windows-only (PowerShell + `pythonw`); the user's
  machine is the target.
- **Auto-start on Windows login / installer (MSI).** A desktop shortcut is the
  ask; revisit only if requested.
- **Multi-machine / remote backend.** The HUD's `127.0.0.1:7475` stays
  hardcoded (with the existing `?ws=` override for dev).
- **Tauri-side backend supervision** (Approach C) and **pure-PowerShell
  supervision** (Approach A) — both rejected during brainstorming.
- **Live sink-switch on HUD reconnect mid-utterance** — out of SP-2's scope and
  unchanged here.
