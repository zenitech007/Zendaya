# HUD Channels Wire-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire amplitude, visemes, telemetry, perception, and body-action channels end-to-end from the Python `zendaya_state_server` into the React `zendaya-hud-react` HUD — plus three bug fixes — so the orb actually reacts to real Zendaya.

**Architecture:** Backend grows a `_broadcast_loop()` daemon thread that ticks 30 Hz amplitude/visemes, 2 Hz telemetry, on-change perception/body. Frontend extends Zustand with 4 new slices, widens the WS hook's AI filter, adds two corner widgets (`TelemetryWidget`, `PerceptionIndicator`), gives the orb a viseme-driven ripple uniform on a new core `ShaderMaterial`, and runs body-action GSAP timelines on a nested inner group.

**Tech Stack:** Python 3.14 (FastAPI + websockets), React 18 + TypeScript + Vite, Three.js + R3F + GSAP, Zustand, Tailwind v3, Vitest + happy-dom + @testing-library/react (new), pytest (existing).

**Spec:** [docs/superpowers/specs/2026-05-24-hud-channels-wireup-design.md](../specs/2026-05-24-hud-channels-wireup-design.md)

---

## File Structure

| File / Path | Action | Responsibility |
|---|---|---|
| `backend/zendaya_state_server.py` | Modify | Add `_broadcast_loop()` daemon thread + decimation + extended initial snapshot |
| `backend/tests/test_state_server_broadcast.py` | Create | Pytest: tick + shape correctness + decimation + snapshot |
| `zendaya-hud-react/package.json` | Modify | Dev-deps: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `happy-dom` |
| `zendaya-hud-react/vitest.config.ts` | Create | Vitest config (happy-dom env, jest-dom setup) |
| `zendaya-hud-react/src/test-setup.ts` | Create | Imports `@testing-library/jest-dom` for matchers |
| `zendaya-hud-react/src/store/zendayaStore.ts` | Modify | Add `visemes` / `telemetry` / `perception` / `bodyActionPulse` slices + setters; export full `AiState` |
| `zendaya-hud-react/src/store/normaliseVisemes.ts` | Create | Pure helper that clamps + NaN-guards viseme weights |
| `zendaya-hud-react/src/hooks/useWebSocket.ts` | Modify | Widen AI filter; route 5 new message types; 10s heartbeat |
| `zendaya-hud-react/src/hooks/useBodyAction.ts` | Create | Subscribe to `bodyActionPulse`; run GSAP timelines on a Three group |
| `zendaya-hud-react/src/components/Orb/Orb.tsx` | Modify | Swap core mesh material to a viseme-driven `ShaderMaterial`; restructure to outer-voice/inner-body group; mount `useBodyAction` |
| `zendaya-hud-react/src/components/HUD/TelemetryWidget.tsx` | Create | Top-right widget: CPU/mem bars + mood + offline banner |
| `zendaya-hud-react/src/components/HUD/PerceptionIndicator.tsx` | Create | Top-left indicator: face dot + last-gesture chip with stale-fade |
| `zendaya-hud-react/src/components/HUD/MusicPlayer.tsx` | Modify | Bug fix: POST body key `text` → `message` |
| `zendaya-hud-react/src/components/HUD/Hud.tsx` | Modify | Mount widgets; add mood-atmosphere effect |
| `zendaya-hud-react/src/__tests__/zendayaStore.test.ts` | Create | Vitest unit tests for new store slices + helpers |
| `zendaya-hud-react/src/__tests__/useWebSocket.test.ts` | Create | Vitest: mock WS + table-driven message dispatch incl. AI filter regression cases |
| `zendaya-hud-react/src/__tests__/TelemetryWidget.test.tsx` | Create | RTL render/hide/offline cases |
| `zendaya-hud-react/src/__tests__/PerceptionIndicator.test.tsx` | Create | RTL render/hide/stale-gesture cases |
| `zendaya-hud-react/src/__tests__/useBodyAction.test.ts` | Create | Mock GSAP; keyframe smoke per action; repeat-pulse re-fire |

---

## Conventions for this plan

- **Shell:** PowerShell 5.1 on Windows. No `&&`; use `;` or `if ($?) { ... }`.
- **Working directory:** `C:\Users\IKA\Zendaya` unless noted. Frontend commands run from `C:\Users\IKA\Zendaya\zendaya-hud-react`.
- **Pytest:** `pytest backend/tests/ -v` from repo root. Existing 78 tests must continue to pass.
- **Vitest:** `npm run test` from inside `zendaya-hud-react/` once the runner is scaffolded in Task 1.
- **Commit safety:** the repo has a large pre-existing uncommitted diff (`backend/zendaya.py`, `pyproject.toml`, etc.) the user said to leave alone. Use exact file paths in `git add`; NEVER `git add -A` or `git add .`. Verify each commit with `git show --stat HEAD`.
- **Pre-existing untracked WIP:** `backend/zendaya_state_server.py` and the entire `zendaya-hud-react/` directory are untracked at session start. The `git add` of these files in their FIRST touched commit would land their entire current content. Task 0 below baselines them so subsequent task commits show clean per-task diffs.

---

### Task 0: Baseline the untracked HUD + state_server files

This task does NOT modify any code. It creates a single "snapshot" commit that brings the currently-untracked `backend/zendaya_state_server.py` and the necessary `zendaya-hud-react/` source files into git history so subsequent task commits show only deltas. **The user has accepted this trade-off at the execution-choice handoff** (or will override it before this task runs).

**Files:**
- Stage (no modification): `backend/zendaya_state_server.py`, `zendaya-hud-react/`

- [ ] **Step 1: Pre-flight — confirm what we're about to baseline**

```powershell
git ls-files backend/zendaya_state_server.py
git ls-files zendaya-hud-react/ | Measure-Object -Line | Select-Object -ExpandProperty Lines
```

Expected:
- First command: empty output (untracked).
- Second command: `0` (entire HUD untracked).

- [ ] **Step 2: Verify the HUD doesn't have a node_modules in scope**

```powershell
Test-Path zendaya-hud-react\node_modules
```

Expected: `True` — but we must NOT commit it. The HUD repo has a `.gitignore` already (verify):

```powershell
Test-Path zendaya-hud-react\.gitignore
Get-Content zendaya-hud-react\.gitignore | Select-String -Pattern "node_modules" | Select-Object -First 1
```

Expected: the .gitignore exists and ignores node_modules. If not, abort and report BLOCKED — the baseline commit risks gigabytes of build artifacts.

- [ ] **Step 3: Stage with explicit paths only**

```powershell
git add backend/zendaya_state_server.py
git add zendaya-hud-react/
git status --short | Select-String -Pattern "^A " | Measure-Object -Line | Select-Object -ExpandProperty Lines
```

Read the staged file list:

```powershell
git diff --cached --name-only | Measure-Object -Line | Select-Object -ExpandProperty Lines
git diff --cached --name-only | Select-Object -First 20
```

Confirm:
- All paths start with `backend/zendaya_state_server.py` or `zendaya-hud-react/`.
- No `node_modules/` or `dist/` content (the HUD's `.gitignore` should suppress them; if anything slips through, run `git reset HEAD zendaya-hud-react/...` to unstage).
- File count is reasonable (a few hundred at most — TypeScript source, package.json, configs, dist).

- [ ] **Step 4: Commit**

```powershell
git -c commit.gpgsign=false commit -m "chore: snapshot untracked HUD + state_server as baseline for channel wire-up"
git show --stat HEAD | Select-Object -First 5
git log -1 --format="%h %s — %an, %ad" --date=short
```

Expected: commit created. `git show --stat HEAD | Measure-Object -Line` will show many file entries (the entire HUD source tree); this is intentional. Subsequent tasks will show clean small diffs against this baseline.

- [ ] **Step 5: Verify pre-existing dirty state still intact**

```powershell
git status --short backend/zendaya.py backend/zendaya_system_access.py pyproject.toml .gitignore
```

Expected: all four still show as `M` — the user's pre-existing diff is untouched.

---

### Task 1: Vitest scaffolding in zendaya-hud-react

**Files:**
- Modify: `C:\Users\IKA\Zendaya\zendaya-hud-react\package.json` (devDeps + test script)
- Create: `C:\Users\IKA\Zendaya\zendaya-hud-react\vitest.config.ts`
- Create: `C:\Users\IKA\Zendaya\zendaya-hud-react\src\test-setup.ts`

- [ ] **Step 1: Read current package.json to confirm script and dev-dep section names**

```powershell
Get-Content zendaya-hud-react\package.json
```

Note the existing `"scripts"` and `"devDependencies"` blocks. The Edit tool calls below assume standard names — adapt if they differ.

- [ ] **Step 2: Add dev-deps via npm install (no manual edit)**

From the HUD directory:

```powershell
Push-Location zendaya-hud-react
npm install --save-dev vitest@^2 happy-dom@^15 @testing-library/react@^16 @testing-library/jest-dom@^6
Pop-Location
```

Expected: install completes; `zendaya-hud-react/package.json` and `package-lock.json` updated.

- [ ] **Step 3: Add the `test` script to package.json**

Edit `zendaya-hud-react\package.json`. Find the existing `"scripts"` object and append a `"test": "vitest run"` and `"test:watch": "vitest"` entry. Adapt to the existing object's trailing-comma style.

Example using the Edit tool — anchor on the existing `dev` script (will need to read first to confirm exact shape):

- old_string: `"dev": "vite",`
- new_string: `"dev": "vite",\n    "test": "vitest run",\n    "test:watch": "vitest",`

If the existing `dev` script differs (e.g. `"dev": "vite --port 5180"`), adapt the anchor.

- [ ] **Step 4: Create `vitest.config.ts`**

Use the `Write` tool to create `zendaya-hud-react\vitest.config.ts`:

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "happy-dom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
  },
});
```

If `@vitejs/plugin-react` is not already in devDeps (read package.json to confirm), install it:

```powershell
Push-Location zendaya-hud-react
npm install --save-dev @vitejs/plugin-react
Pop-Location
```

- [ ] **Step 5: Create `src/test-setup.ts`**

Use the `Write` tool with this exact content:

```typescript
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 6: Verify the runner starts**

```powershell
Push-Location zendaya-hud-react
npm test 2>&1 | Select-Object -Last 10
Pop-Location
```

Expected: vitest reports `No test files found, exiting with code 1` (acceptable for now — no test files yet). Or it runs with 0 tests. Either is fine. If it dies with import errors or config errors, fix before continuing.

- [ ] **Step 7: Commit**

```powershell
git add zendaya-hud-react/package.json zendaya-hud-react/package-lock.json zendaya-hud-react/vitest.config.ts zendaya-hud-react/src/test-setup.ts
git -c commit.gpgsign=false commit -m "test(hud): scaffold vitest + happy-dom + @testing-library/react"
git show --stat HEAD
```

Expected: only those 4 files in the commit. (If `package-lock.json` shows enormous diff that's fine — npm rewrote it.)

---

### Task 2: Backend broadcast loop + tests

**Files:**
- Modify: `C:\Users\IKA\Zendaya\backend\zendaya_state_server.py`
- Create: `C:\Users\IKA\Zendaya\backend\tests\test_state_server_broadcast.py`

- [ ] **Step 1: Read the current state_server.py to find insertion points**

```powershell
Select-String -Path backend\zendaya_state_server.py -Pattern "^def set_amplitude|^def set_visemes|^def set_body_action|^def set_telemetry_provider|^def set_perception_providers|^app\.|^@app\.|_broadcast_state_async|FastAPI\(|startup|shutdown" | Select-Object LineNumber,Line | Select-Object -First 30
```

Note the line numbers for:
- Module-level shared dicts (`_MOUTH`, `_VISEMES`, `_BODY`, `_TELEMETRY_PROVIDER`, `_PERCEPTION_*`)
- Existing `_broadcast_state_async()` function
- FastAPI app instance and any existing `@app.on_event("startup")` handler
- The websocket `/ws` endpoint's initial-message logic

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_state_server_broadcast.py` with this exact content:

```python
"""Unit tests for the broadcast loop and decimation logic in zendaya_state_server."""
from __future__ import annotations

import time

import pytest


@pytest.fixture(autouse=True)
def _reset_state_server():
    """Reset module-level state between tests."""
    import zendaya_state_server as ss

    ss._MOUTH = {"level": 0.0, "ts": 0.0}
    ss._VISEMES = {"weights": {"aa": 0, "ih": 0, "ee": 0, "oh": 0, "ou": 0}, "ts": 0.0}
    ss._BODY = {"action": "", "ts": 0.0}
    if hasattr(ss, "_BROADCAST_LAST_SENT"):
        ss._BROADCAST_LAST_SENT.clear()
    yield


def test_collect_tick_includes_amplitude_when_changed():
    import zendaya_state_server as ss

    ss.set_amplitude(0.42)
    tick = ss._collect_tick()
    assert any("amplitude" in m for m in tick), f"expected amplitude in {tick}"
    sent = next(m for m in tick if "amplitude" in m)
    assert sent["amplitude"] == pytest.approx(0.42, abs=0.001)


def test_collect_tick_decimates_unchanged_amplitude():
    import zendaya_state_server as ss

    ss.set_amplitude(0.5)
    _ = ss._collect_tick()  # marks 0.5 as sent
    ss.set_amplitude(0.503)  # within 0.005 delta
    tick = ss._collect_tick()
    assert not any("amplitude" in m for m in tick), f"amplitude should be decimated; got {tick}"


def test_collect_tick_includes_visemes_when_changed():
    import zendaya_state_server as ss

    ss.set_visemes({"aa": 0.5, "ih": 0, "ee": 0, "oh": 0, "ou": 0})
    tick = ss._collect_tick()
    assert any("visemes" in m for m in tick)
    sent = next(m for m in tick if "visemes" in m)
    assert sent["visemes"]["aa"] == pytest.approx(0.5)


def test_collect_tick_decimates_unchanged_visemes():
    import zendaya_state_server as ss

    ss.set_visemes({"aa": 0.5, "ih": 0, "ee": 0, "oh": 0, "ou": 0})
    _ = ss._collect_tick()
    ss.set_visemes({"aa": 0.505, "ih": 0, "ee": 0, "oh": 0, "ou": 0})  # within 0.01
    tick = ss._collect_tick()
    assert not any("visemes" in m for m in tick)


def test_collect_tick_includes_telemetry_with_provider():
    import zendaya_state_server as ss

    fake = {"cpu": 21.4, "mem": 58.2, "mic_level": 0.0, "mood": "neutral",
            "vision_active": False, "gestures_active": False,
            "hud_enabled": True, "online": True,
            "user_name": "Ikenna", "language": "english",
            "last_gesture": {"name": "none", "ts": 0.0}}
    ss.set_telemetry_provider(lambda: dict(fake))
    tick = ss._collect_tick()
    assert any("telemetry" in m for m in tick)
    sent = next(m for m in tick if "telemetry" in m)
    assert sent["telemetry"]["cpu"] == pytest.approx(21.4)
    assert sent["telemetry"]["mood"] == "neutral"


def test_collect_tick_telemetry_null_on_provider_exception():
    import zendaya_state_server as ss

    def boom():
        raise RuntimeError("intentional")
    ss.set_telemetry_provider(boom)
    tick = ss._collect_tick()
    assert any("telemetry" in m for m in tick)
    sent = next(m for m in tick if "telemetry" in m)
    assert sent["telemetry"] is None


def test_set_body_action_valid_value_broadcasts_then_resets():
    import zendaya_state_server as ss

    ss.set_body_action("nod")
    tick = ss._collect_tick()
    assert any("body_action" in m for m in tick)
    sent = next(m for m in tick if "body_action" in m)
    assert sent["body_action"] == "nod"
    # After collect, in-memory value is "" so a fresh nod is broadcast as a fresh event
    assert ss._BODY["action"] == ""


def test_set_body_action_unknown_becomes_empty():
    import zendaya_state_server as ss

    ss.set_body_action("garbage")
    assert ss._BODY["action"] == ""
    tick = ss._collect_tick()
    assert not any("body_action" in m for m in tick)


def test_collect_tick_handles_provider_value_then_recovers():
    """After a provider exception, subsequent successful ticks resume normally."""
    import zendaya_state_server as ss

    state = {"raise": True}

    def flaky():
        if state["raise"]:
            raise RuntimeError("intentional")
        return {"cpu": 10.0, "mem": 20.0, "mic_level": 0.0, "mood": "ok",
                "vision_active": False, "gestures_active": False,
                "hud_enabled": True, "online": True,
                "user_name": "", "language": "english",
                "last_gesture": {"name": "none", "ts": 0.0}}

    ss.set_telemetry_provider(flaky)
    t1 = ss._collect_tick()
    assert any("telemetry" in m and m["telemetry"] is None for m in t1)
    state["raise"] = False
    t2 = ss._collect_tick()
    sent = next(m for m in t2 if "telemetry" in m)
    assert sent["telemetry"] is not None
    assert sent["telemetry"]["cpu"] == 10.0
```

- [ ] **Step 3: Run tests — confirm they fail**

```powershell
pytest backend/tests/test_state_server_broadcast.py -v 2>&1 | Select-Object -Last 20
```

Expected: 9 errors with `AttributeError: module 'zendaya_state_server' has no attribute '_collect_tick'` and similar.

- [ ] **Step 4: Implement `_collect_tick()` + supporting decimation state**

Use the `Edit` tool on `backend/zendaya_state_server.py`. Insert these additions (adapt to the file's existing import block and module-level state — read first to confirm exact form):

Near the top of the file, in the existing module-level state section, add:

```python
# Decimation state for the broadcast loop.
_BROADCAST_LAST_SENT: dict = {
    "amplitude": None,        # float or None
    "visemes": None,          # dict or None
    "telemetry_failed": False,  # one-time null payload after provider exception
}
_AMPLITUDE_DELTA = 0.005
_VISEME_DELTA = 0.01
_PERCEPTION_HEARTBEAT_S = 5.0
_BODY_ACTION_ALLOWED = {"", "nod", "shake", "wave", "shrug"}
```

In `set_body_action`, replace its current implementation with a filtered version:

- old_string (read the file to confirm — likely matches this shape; if not, adapt):
```python
def set_body_action(action: str) -> None:
    _BODY["action"] = (action or "").lower()
    _BODY["ts"] = time.time()
```
- new_string:
```python
def set_body_action(action: str) -> None:
    val = (action or "").lower().strip()
    if val not in _BODY_ACTION_ALLOWED:
        print(f"(state_server: ignoring unknown body_action {val!r})")
        val = ""
    _BODY["action"] = val
    _BODY["ts"] = time.time()
```

Append `_collect_tick()` at the bottom of the file (above the `if __name__ == "__main__":` block if there is one):

```python
def _collect_tick() -> list[dict]:
    """Build the broadcast messages for one tick.

    Returns a list of small JSON-dict messages (one per channel with new data),
    matching the existing frontend's `if (data.X)` dispatch pattern.
    Decimation suppresses near-identical amplitude/viseme values.
    """
    out: list[dict] = []

    # amplitude (decimated)
    amp = float(_MOUTH.get("level", 0.0))
    last_amp = _BROADCAST_LAST_SENT.get("amplitude")
    if last_amp is None or abs(amp - last_amp) >= _AMPLITUDE_DELTA:
        out.append({"amplitude": amp})
        _BROADCAST_LAST_SENT["amplitude"] = amp

    # visemes (decimated)
    weights = dict(_VISEMES.get("weights", {}))
    last_v = _BROADCAST_LAST_SENT.get("visemes")
    if last_v is None or any(
        abs(weights.get(k, 0.0) - float(last_v.get(k, 0.0))) >= _VISEME_DELTA
        for k in ("aa", "ih", "ee", "oh", "ou")
    ):
        out.append({"visemes": {k: float(weights.get(k, 0.0)) for k in ("aa", "ih", "ee", "oh", "ou")}})
        _BROADCAST_LAST_SENT["visemes"] = dict(weights)

    # telemetry (always sent if provider; null one time on exception)
    provider = globals().get("_TELEMETRY_PROVIDER")
    if provider is not None:
        try:
            tel = provider()
            out.append({"telemetry": tel})
            _BROADCAST_LAST_SENT["telemetry_failed"] = False
        except Exception as e:
            if not _BROADCAST_LAST_SENT.get("telemetry_failed", False):
                print(f"(state_server: telemetry provider raised {e!r}; sending null)")
                out.append({"telemetry": None})
                _BROADCAST_LAST_SENT["telemetry_failed"] = True

    # perception (similar — send on every tick when providers exist)
    face_p = globals().get("_PERCEPTION_FACE")
    gesture_p = globals().get("_PERCEPTION_GESTURE")
    if face_p is not None and gesture_p is not None:
        try:
            payload = {"face": face_p(), "last_gesture": gesture_p()}
            out.append({"perception": payload})
        except Exception as e:
            print(f"(state_server: perception provider raised {e!r})")

    # body_action — on-change only, reset after broadcast
    body_action = _BODY.get("action", "")
    if body_action and body_action in _BODY_ACTION_ALLOWED:
        out.append({"body_action": body_action})
        _BODY["action"] = ""  # consumed; a fresh set_body_action re-emits

    return out
```

- [ ] **Step 5: Run tests — confirm pass**

```powershell
pytest backend/tests/test_state_server_broadcast.py -v 2>&1 | Select-Object -Last 20
```

Expected: 9/9 pass.

- [ ] **Step 6: Add the broadcast thread + extended snapshot**

The tests cover `_collect_tick()` deterministically. The loop itself isn't unit-tested (would be flaky); it's a thin wrapper. Add to `zendaya_state_server.py`:

```python
import threading as _threading

_broadcast_stop = _threading.Event()
_broadcast_thread: _threading.Thread | None = None
_BROADCAST_TICK_HZ = 30.0


def _broadcast_loop() -> None:
    period = 1.0 / _BROADCAST_TICK_HZ
    last_perception_hb = 0.0
    last_telemetry_send = 0.0
    while not _broadcast_stop.is_set():
        t0 = time.time()
        try:
            messages = _collect_tick()
            # Throttle telemetry to 2 Hz inside the 30 Hz loop.
            if any("telemetry" in m for m in messages):
                if t0 - last_telemetry_send < 0.5:
                    messages = [m for m in messages if "telemetry" not in m]
                else:
                    last_telemetry_send = t0
            # Perception heartbeat — always send at 0.2 Hz minimum.
            if not any("perception" in m for m in messages) and t0 - last_perception_hb >= _PERCEPTION_HEARTBEAT_S:
                # Re-run providers to get the latest snapshot.
                face_p = globals().get("_PERCEPTION_FACE")
                gesture_p = globals().get("_PERCEPTION_GESTURE")
                if face_p is not None and gesture_p is not None:
                    try:
                        messages.append({"perception": {"face": face_p(), "last_gesture": gesture_p()}})
                        last_perception_hb = t0
                    except Exception:
                        pass
            for m in messages:
                _broadcast_state_async(m)  # existing helper that fans out to WS clients
        except Exception as e:
            print(f"(state_server: broadcast tick failed: {e})")
        elapsed = time.time() - t0
        _broadcast_stop.wait(max(0.0, period - elapsed))


# Wire startup/shutdown via the existing FastAPI app.
# (If a startup/shutdown handler already exists, ADD these lines to it; do NOT replace.)
try:
    @app.on_event("startup")
    def _aaf_state_server_startup():
        global _broadcast_thread
        if _broadcast_thread is None:
            _broadcast_stop.clear()
            _broadcast_thread = _threading.Thread(target=_broadcast_loop, name="state-server-broadcast", daemon=True)
            _broadcast_thread.start()

    @app.on_event("shutdown")
    def _aaf_state_server_shutdown():
        _broadcast_stop.set()
        if _broadcast_thread is not None:
            _broadcast_thread.join(timeout=2.0)
except Exception as _e:
    print(f"(state_server: could not register startup/shutdown hooks: {_e})")
```

- [ ] **Step 7: Extend the initial-connect WS snapshot**

Find the `@app.websocket("/ws")` endpoint and locate where it sends its initial `{"state": ..., "text": ...}` message. Extend the dict to also include `telemetry`, `perception`, and `now_playing` snapshots:

Use Grep to find: `await websocket.send_json` or `await websocket.send_text` inside the ws_endpoint. Then expand the dict to also include the optional snapshot keys (skip a key when its provider/value is None).

The exact edit shape depends on the current code. Generally:

- old_string: (read first)
```python
        await websocket.send_json({"state": <state expr>, "text": <text expr>})
```
- new_string:
```python
        _snapshot = {"state": <state expr>, "text": <text expr>}
        try:
            tp = globals().get("_TELEMETRY_PROVIDER")
            if tp is not None:
                _snapshot["telemetry"] = tp()
        except Exception:
            pass
        try:
            fp = globals().get("_PERCEPTION_FACE")
            gp = globals().get("_PERCEPTION_GESTURE")
            if fp is not None and gp is not None:
                _snapshot["perception"] = {"face": fp(), "last_gesture": gp()}
        except Exception:
            pass
        if _NOW_PLAYING is not None:
            _snapshot["now_playing"] = _NOW_PLAYING
        await websocket.send_json(_snapshot)
```

Adapt to the file's actual code shape and variable names (`_NOW_PLAYING`'s exact name may differ; read the `set_now_playing` function to find the right global).

- [ ] **Step 8: Re-run tests including the existing suite**

```powershell
pytest backend/tests/ -v 2>&1 | Select-Object -Last 5
```

Expected: 78 prior + 9 new = 87 pass.

- [ ] **Step 9: Commit**

```powershell
git add backend/zendaya_state_server.py backend/tests/test_state_server_broadcast.py
git -c commit.gpgsign=false commit -m "feat(state-server): broadcast loop with decimation + extended snapshot on connect"
git show --stat HEAD
```

Expected: only the two files. The state_server.py diff should be a clean small delta against the Task 0 baseline.

---

### Task 3: Frontend store extension (new slices + setters) + tests

**Files:**
- Modify: `C:\Users\IKA\Zendaya\zendaya-hud-react\src\store\zendayaStore.ts`
- Create: `C:\Users\IKA\Zendaya\zendaya-hud-react\src\store\normaliseVisemes.ts`
- Create: `C:\Users\IKA\Zendaya\zendaya-hud-react\src\__tests__\zendayaStore.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `zendaya-hud-react/src/__tests__/zendayaStore.test.ts`:

```typescript
import { beforeEach, describe, expect, it } from "vitest";
import { useZendaya } from "../store/zendayaStore";
import { normaliseVisemes } from "../store/normaliseVisemes";

describe("zendayaStore — new slices", () => {
  beforeEach(() => {
    // Reset to defaults
    useZendaya.setState({
      visemes: { aa: 0, ih: 0, ee: 0, oh: 0, ou: 0 },
      telemetry: null,
      perception: null,
      bodyActionPulse: { action: "", ts: 0 },
    });
  });

  it("setVisemes mutates the visemes slice", () => {
    useZendaya.getState().setVisemes({ aa: 0.5, ih: 0, ee: 0, oh: 0, ou: 0 });
    expect(useZendaya.getState().visemes.aa).toBeCloseTo(0.5);
  });

  it("setTelemetry stores the payload", () => {
    const payload = {
      cpu: 23.5, mem: 60, mic_level: 0, mood: "neutral",
      vision_active: false, gestures_active: false,
      hud_enabled: true, online: true,
      user_name: "Ikenna", language: "english",
      last_gesture: { name: "none", ts: 0 },
    };
    useZendaya.getState().setTelemetry(payload);
    expect(useZendaya.getState().telemetry).toEqual(payload);
  });

  it("setPerception stores the payload", () => {
    const payload = {
      face: { present: true, ts: 1 },
      last_gesture: { name: "Thumb_Up", ts: 2 },
    };
    useZendaya.getState().setPerception(payload);
    expect(useZendaya.getState().perception).toEqual(payload);
  });

  it("firePulseBodyAction sets action and ts", () => {
    useZendaya.getState().firePulseBodyAction("nod");
    const p = useZendaya.getState().bodyActionPulse;
    expect(p.action).toBe("nod");
    expect(p.ts).toBeGreaterThan(0);
  });

  it("firePulseBodyAction increments ts on repeat", async () => {
    useZendaya.getState().firePulseBodyAction("nod");
    const t1 = useZendaya.getState().bodyActionPulse.ts;
    await new Promise((r) => setTimeout(r, 5));
    useZendaya.getState().firePulseBodyAction("nod");
    const t2 = useZendaya.getState().bodyActionPulse.ts;
    expect(t2).toBeGreaterThan(t1);
  });
});

describe("normaliseVisemes", () => {
  it("clamps to [0, 1]", () => {
    const result = normaliseVisemes({ aa: 1.5, ih: -0.2, ee: 0.5, oh: 0, ou: 0 });
    expect(result.aa).toBe(1);
    expect(result.ih).toBe(0);
    expect(result.ee).toBeCloseTo(0.5);
  });

  it("replaces NaN with 0", () => {
    const result = normaliseVisemes({ aa: NaN, ih: 0, ee: 0, oh: 0, ou: 0 });
    expect(result.aa).toBe(0);
  });

  it("fills missing keys with 0", () => {
    const result = normaliseVisemes({ aa: 0.5 } as any);
    expect(result.ih).toBe(0);
    expect(result.ee).toBe(0);
    expect(result.oh).toBe(0);
    expect(result.ou).toBe(0);
  });
});
```

- [ ] **Step 2: Run — confirm failures**

```powershell
Push-Location zendaya-hud-react
npm test 2>&1 | Select-Object -Last 15
Pop-Location
```

Expected: failures importing `setVisemes`, `normaliseVisemes`, etc. (Modules not exporting these yet.)

- [ ] **Step 3: Create `normaliseVisemes.ts`**

Use Write tool. Path: `zendaya-hud-react/src/store/normaliseVisemes.ts`:

```typescript
export type Visemes = { aa: number; ih: number; ee: number; oh: number; ou: number };

const KEYS = ["aa", "ih", "ee", "oh", "ou"] as const;

function clean(v: unknown): number {
  const n = typeof v === "number" ? v : 0;
  if (Number.isNaN(n)) return 0;
  return Math.max(0, Math.min(1, n));
}

export function normaliseVisemes(input: Partial<Visemes> | Record<string, unknown>): Visemes {
  return {
    aa: clean((input as any).aa),
    ih: clean((input as any).ih),
    ee: clean((input as any).ee),
    oh: clean((input as any).oh),
    ou: clean((input as any).ou),
  };
}
```

- [ ] **Step 4: Extend `zendayaStore.ts`**

Read the current file. Then use Edit to add the new types, state, and setters. The exact patches depend on the current file shape, but the additions are:

1. After existing type exports, add:

```typescript
export type Telemetry = {
  cpu: number; mem: number; mic_level: number;
  mood: string; vision_active: boolean; gestures_active: boolean;
  hud_enabled: boolean; online: boolean;
  user_name: string; language: string;
  last_gesture: { name: string; ts: number };
};
export type Perception = {
  face: { present: boolean; ts: number };
  last_gesture: { name: string; ts: number };
};
export type BodyAction = "" | "nod" | "shake" | "wave" | "shrug";
```

2. Re-export `Visemes` from `normaliseVisemes`:

```typescript
export type { Visemes } from "./normaliseVisemes";
```

3. In the `State` interface, add 4 new fields. Anchor on an existing slice — e.g., if the interface has `nowPlaying: NowPlaying | null`, add right after:

- old_string: `  nowPlaying: NowPlaying | null;`
- new_string:
```
  nowPlaying: NowPlaying | null;
  visemes: Visemes;
  telemetry: Telemetry | null;
  perception: Perception | null;
  bodyActionPulse: { action: BodyAction; ts: number };
```

4. Add the corresponding setters. Anchor on an existing setter — e.g., `setNowPlaying`:

- old_string: `  setNowPlaying: (np: NowPlaying | null) => void;`
- new_string:
```
  setNowPlaying: (np: NowPlaying | null) => void;
  setVisemes: (v: Visemes) => void;
  setTelemetry: (t: Telemetry | null) => void;
  setPerception: (p: Perception | null) => void;
  firePulseBodyAction: (a: BodyAction) => void;
```

5. In the Zustand `create<State>()((set) => ({ ... }))` factory, add the initial values + setter implementations. Anchor on `nowPlaying: null` in the initial values:

- old_string: `  nowPlaying: null,`
- new_string:
```
  nowPlaying: null,
  visemes: { aa: 0, ih: 0, ee: 0, oh: 0, ou: 0 },
  telemetry: null,
  perception: null,
  bodyActionPulse: { action: "" as BodyAction, ts: 0 },
```

And add the setter bodies. Anchor on the existing `setNowPlaying: (np) => set({ nowPlaying: np }),`:

- old_string: `  setNowPlaying: (np) => set({ nowPlaying: np }),`
- new_string:
```
  setNowPlaying: (np) => set({ nowPlaying: np }),
  setVisemes: (v) => set({ visemes: v }),
  setTelemetry: (t) => set({ telemetry: t }),
  setPerception: (p) => set({ perception: p }),
  firePulseBodyAction: (a) =>
    set((s) => ({
      bodyActionPulse: { action: a, ts: Math.max(s.bodyActionPulse.ts + 1, performance.now()) },
    })),
```

Adapt the exact anchor strings to match the current file's formatting (trailing commas, indentation).

- [ ] **Step 5: Run — confirm pass**

```powershell
Push-Location zendaya-hud-react
npm test 2>&1 | Select-Object -Last 15
Pop-Location
```

Expected: all store tests pass.

- [ ] **Step 6: Commit**

```powershell
git add zendaya-hud-react/src/store/zendayaStore.ts zendaya-hud-react/src/store/normaliseVisemes.ts zendaya-hud-react/src/__tests__/zendayaStore.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): extend Zustand store with visemes/telemetry/perception/body slices"
git show --stat HEAD
```

Expected: only those 3 files.

---

### Task 4: Frontend `useWebSocket` updates + tests

**Files:**
- Modify: `C:\Users\IKA\Zendaya\zendaya-hud-react\src\hooks\useWebSocket.ts`
- Create: `C:\Users\IKA\Zendaya\zendaya-hud-react\src\__tests__\useWebSocket.test.ts`

- [ ] **Step 1: Read the hook to confirm current shape**

```powershell
Get-Content zendaya-hud-react\src\hooks\useWebSocket.ts
```

Note the existing `VALID_AI` array, the message-handling `if` chain, the reconnect block. The new code mirrors those patterns.

- [ ] **Step 2: Write the failing tests**

Create `zendaya-hud-react/src/__tests__/useWebSocket.test.ts`:

```typescript
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useZendaya } from "../store/zendayaStore";
import { useWebSocket } from "../hooks/useWebSocket";

class FakeWS extends EventTarget {
  static instances: FakeWS[] = [];
  readyState = 0; // CONNECTING
  url: string;
  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = 3;
    this.dispatchEvent(new Event("close"));
  });
  constructor(url: string) {
    super();
    this.url = url;
    FakeWS.instances.push(this);
    setTimeout(() => {
      this.readyState = 1;
      this.dispatchEvent(new Event("open"));
    }, 0);
  }
  fireMessage(data: any) {
    const ev = new MessageEvent("message", { data: JSON.stringify(data) });
    this.dispatchEvent(ev);
  }
}

beforeEach(() => {
  FakeWS.instances = [];
  (globalThis as any).WebSocket = FakeWS;
  useZendaya.setState({
    ai: "idle",
    text: "",
    audioLevel: 0,
    panel: "",
    nowPlaying: null,
    visemes: { aa: 0, ih: 0, ee: 0, oh: 0, ou: 0 },
    telemetry: null,
    perception: null,
    bodyActionPulse: { action: "", ts: 0 },
  });
});

afterEach(() => {
  vi.useRealTimers();
});

async function freshHook() {
  const result = renderHook(() => useWebSocket());
  // Wait one microtask so the FakeWS open event fires.
  await Promise.resolve();
  await new Promise((r) => setTimeout(r, 5));
  const ws = FakeWS.instances[FakeWS.instances.length - 1];
  return { result, ws };
}

describe("useWebSocket — new message types", () => {
  it("amplitude updates audioLevel", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ amplitude: 0.7 });
    expect(useZendaya.getState().audioLevel).toBeCloseTo(0.7);
  });

  it("visemes payload populates the slice", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ visemes: { aa: 0.5, ih: 0, ee: 0, oh: 0, ou: 0 } });
    expect(useZendaya.getState().visemes.aa).toBeCloseTo(0.5);
  });

  it("telemetry payload populates the slice", async () => {
    const { ws } = await freshHook();
    const tel = {
      cpu: 30, mem: 50, mic_level: 0, mood: "neutral",
      vision_active: false, gestures_active: false,
      hud_enabled: true, online: true,
      user_name: "", language: "english",
      last_gesture: { name: "none", ts: 0 },
    };
    ws.fireMessage({ telemetry: tel });
    expect(useZendaya.getState().telemetry).toEqual(tel);
  });

  it("perception payload populates the slice", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ perception: { face: { present: true, ts: 1 }, last_gesture: { name: "Thumb_Up", ts: 2 } } });
    expect(useZendaya.getState().perception?.face.present).toBe(true);
  });

  it("body_action fires a pulse", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ body_action: "nod" });
    expect(useZendaya.getState().bodyActionPulse.action).toBe("nod");
    expect(useZendaya.getState().bodyActionPulse.ts).toBeGreaterThan(0);
  });
});

describe("useWebSocket — widened AI filter", () => {
  it.each(["idle", "aware", "listening", "thinking", "speaking", "searching", "mapping", "alert", "error"])(
    "accepts state '%s'",
    async (state) => {
      const { ws } = await freshHook();
      ws.fireMessage({ state });
      expect(useZendaya.getState().ai).toBe(state);
    }
  );
});

describe("useWebSocket — malformed payloads", () => {
  it("non-object telemetry is dropped", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ telemetry: 42 });
    expect(useZendaya.getState().telemetry).toBeNull();
  });

  it("non-object visemes is dropped", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ visemes: "bad" });
    expect(useZendaya.getState().visemes.aa).toBe(0);
  });
});
```

- [ ] **Step 3: Run — confirm failures**

```powershell
Push-Location zendaya-hud-react
npm test src/__tests__/useWebSocket.test.ts 2>&1 | Select-Object -Last 20
Pop-Location
```

Expected: failures because the hook doesn't yet handle the new message types and rejects most AI states.

- [ ] **Step 4: Update `useWebSocket.ts`**

Open the file and find the `VALID_AI` constant. Widen it:

- old_string:
```typescript
const VALID_AI = ["idle","listening","thinking","speaking","error"] as const;
```
- new_string:
```typescript
const VALID_AI = ["idle","aware","listening","thinking","speaking","searching","mapping","alert","error"] as const;
```

Find the inbound message handler — the block of `if (typeof data.state === "string" && VALID_AI.includes(...))` and similar. Add five new branches after the existing handled keys:

- old_string: (locate the LAST existing inbound `if` branch — typically `if ("now_playing" in data) { ... }` — and use the closing brace as the anchor.) Read the file to find the exact tail.

- new_string: insert these after the existing branches but before the `else` / end of handler:

```typescript
if (typeof data.amplitude === "number") {
  setAudioLevel(Math.max(0, Math.min(1, data.amplitude)));
}
if (data.visemes && typeof data.visemes === "object") {
  // normaliseVisemes clamps + NaN-guards each weight
  setVisemes(normaliseVisemes(data.visemes));
}
if (data.telemetry !== undefined && (data.telemetry === null || typeof data.telemetry === "object")) {
  setTelemetry(data.telemetry as any);
}
if (data.perception !== undefined && (data.perception === null || typeof data.perception === "object")) {
  setPerception(data.perception as any);
}
if (typeof data.body_action === "string" && data.body_action) {
  firePulseBodyAction(data.body_action as BodyAction);
}
```

Add the corresponding imports at the top of the file:

```typescript
import { useZendaya, type BodyAction } from "../store/zendayaStore";
import { normaliseVisemes } from "../store/normaliseVisemes";
```

(If `useZendaya` is already imported, just add `type BodyAction` to the existing import. If `setAudioLevel`/`setVisemes`/etc. are destructured from a `useZendaya.getState()` call inside the message handler, destructure the new ones too.)

Add a 10s heartbeat — find the `onopen` handler and inside it:

```typescript
const heartbeat = setInterval(() => {
  if (ws.readyState === 1) ws.send(JSON.stringify({ ping: true }));
}, 10000);
ws.addEventListener("close", () => clearInterval(heartbeat));
```

- [ ] **Step 5: Run — confirm pass**

```powershell
Push-Location zendaya-hud-react
npm test 2>&1 | Select-Object -Last 15
Pop-Location
```

Expected: all useWebSocket tests pass + store tests still pass.

- [ ] **Step 6: Commit**

```powershell
git add zendaya-hud-react/src/hooks/useWebSocket.ts zendaya-hud-react/src/__tests__/useWebSocket.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): useWebSocket handles 5 new message types + widens AI filter + heartbeat"
git show --stat HEAD
```

---

### Task 5: Orb amplitude + viseme ripple shader

**Files:**
- Modify: `C:\Users\IKA\Zendaya\zendaya-hud-react\src\components\Orb\Orb.tsx`

This task has no new tests — the orb is visual; behaviour is verified manually. Subsequent tasks reuse this restructured Orb.

- [ ] **Step 1: Read the current Orb.tsx**

The current file is small (~112 lines per the brainstorming reads). Identify:
- The `coreMat` definition (the simple `MeshBasicMaterial`)
- The `useFrame` callback that drives smoothing
- The `<group ref={group}>` JSX

- [ ] **Step 2: Replace `coreMat` with a ShaderMaterial**

Use Edit. Anchor on `const coreMat = useMemo(`:

- old_string:
```typescript
  const coreMat = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: ORB_COLOR,
        transparent: true,
        opacity: 0.95,
      }),
    []
  );
```
- new_string:
```typescript
  const coreMat = useMemo(() => {
    return new THREE.ShaderMaterial({
      uniforms: {
        uColor: { value: ORB_COLOR.clone() },
        uRippleStrength: { value: 0.0 },
        uRippleFreq: { value: 8.0 },
        uTime: { value: 0.0 },
      },
      vertexShader: `
        uniform float uTime;
        uniform float uRippleStrength;
        uniform float uRippleFreq;
        void main() {
          float ripple = sin(uTime * uRippleFreq + position.x * 6.0)
                       * sin(uTime * uRippleFreq * 1.3 + position.y * 6.0);
          vec3 displaced = position + normal * ripple * uRippleStrength * 0.06;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        void main() {
          gl_FragColor = vec4(uColor, 0.95);
        }
      `,
      transparent: true,
    });
  }, []);
```

- [ ] **Step 3: Add ripple-smoothing ref + viseme reading**

In the smoothing ref declaration, add the new field:

- old_string:
```typescript
  const smoothed = useRef({ pulse: 0, voiceScale: 1 });
```
- new_string:
```typescript
  const smoothed = useRef({ pulse: 0, voiceScale: 1, ripple: 0 });
```

In the `useFrame` body, after the existing voice-scale smoothing, add:

- old_string:
```typescript
    const t = performance.now() * 0.001;
    const breath = 1 + Math.sin(t * 1.2) * s.pulse;
```
- new_string:
```typescript
    const visemeSum = z.visemes.aa + z.visemes.ih + z.visemes.ee + z.visemes.oh + z.visemes.ou;
    const targetRipple = Math.min(1, visemeSum);
    s.ripple += (targetRipple - s.ripple) * Math.min(1, dt * 8);
    if ("uniforms" in coreMat && (coreMat as THREE.ShaderMaterial).uniforms) {
      const u = (coreMat as THREE.ShaderMaterial).uniforms;
      u.uRippleStrength.value = s.ripple;
      u.uTime.value = performance.now() * 0.001;
    }

    const t = performance.now() * 0.001;
    const breath = 1 + Math.sin(t * 1.2) * s.pulse;
```

- [ ] **Step 4: Restructure to nested groups**

Anchor on the `<group ref={group}>` opening tag and its children. Add an inner `<group ref={bodyGroup}>` so Task 6 can hook GSAP onto it without fighting voice scaling.

First add the new ref near the top of the component, alongside `group`:

- old_string:
```typescript
  const group = useRef<THREE.Group>(null!);
  const core = useRef<THREE.Mesh>(null!);
  const glow = useRef<THREE.Mesh>(null!);
```
- new_string:
```typescript
  const group = useRef<THREE.Group>(null!);
  const bodyGroup = useRef<THREE.Group>(null!);
  const core = useRef<THREE.Mesh>(null!);
  const glow = useRef<THREE.Mesh>(null!);
```

Then wrap the existing meshes in a new inner group:

- old_string:
```typescript
  return (
    <group ref={group}>
      {/* Soft outer fresnel glow */}
      <mesh ref={glow} scale={1.8}>
        <sphereGeometry args={[radius, 48, 48]} />
        <primitive object={glowMat} attach="material" />
      </mesh>
      {/* Solid orange core */}
      <mesh ref={core}>
        <sphereGeometry args={[radius * 0.55, 48, 48]} />
        <primitive object={coreMat} attach="material" />
      </mesh>
    </group>
  );
```
- new_string:
```typescript
  return (
    <group ref={group}>
      <group ref={bodyGroup}>
        {/* Soft outer fresnel glow */}
        <mesh ref={glow} scale={1.8}>
          <sphereGeometry args={[radius, 48, 48]} />
          <primitive object={glowMat} attach="material" />
        </mesh>
        {/* Solid orange core */}
        <mesh ref={core}>
          <sphereGeometry args={[radius * 0.55, 48, 48]} />
          <primitive object={coreMat} attach="material" />
        </mesh>
      </group>
    </group>
  );
```

- [ ] **Step 5: Type-check + run tests**

```powershell
Push-Location zendaya-hud-react
npx tsc --noEmit 2>&1 | Select-Object -Last 20
npm test 2>&1 | Select-Object -Last 10
Pop-Location
```

Expected: no TS errors; tests still pass (no new tests, but no regressions).

- [ ] **Step 6: Commit**

```powershell
git add zendaya-hud-react/src/components/Orb/Orb.tsx
git -c commit.gpgsign=false commit -m "feat(hud): orb core uses viseme-driven ripple shader + nested body group"
git show --stat HEAD
```

---

### Task 6: Body action GSAP hook + Orb mount

**Files:**
- Create: `C:\Users\IKA\Zendaya\zendaya-hud-react\src\hooks\useBodyAction.ts`
- Modify: `C:\Users\IKA\Zendaya\zendaya-hud-react\src\components\Orb\Orb.tsx`
- Create: `C:\Users\IKA\Zendaya\zendaya-hud-react\src\__tests__\useBodyAction.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `zendaya-hud-react/src/__tests__/useBodyAction.test.ts`:

```typescript
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import * as THREE from "three";

vi.mock("gsap", () => {
  const tweens: any[] = [];
  const gsap = {
    to: vi.fn((target: any, vars: any) => {
      tweens.push({ target, vars, kind: "to" });
      return { vars };
    }),
    fromTo: vi.fn((target: any, from: any, to: any) => {
      tweens.push({ target, from, to, kind: "fromTo" });
      return {};
    }),
    killTweensOf: vi.fn(() => {
      // no-op
    }),
  };
  // expose for assertions
  (gsap as any).__tweens = tweens;
  return { default: gsap, ...gsap };
});

import gsap from "gsap";
import { useZendaya } from "../store/zendayaStore";
import { useBodyAction } from "../hooks/useBodyAction";

beforeEach(() => {
  (gsap as any).__tweens.length = 0;
  vi.mocked(gsap.to).mockClear();
  vi.mocked(gsap.killTweensOf).mockClear();
  useZendaya.setState({ bodyActionPulse: { action: "", ts: 0 } });
});

function makeGroup() {
  return { current: new THREE.Group() };
}

describe("useBodyAction", () => {
  it("no-op when pulse.action is empty", () => {
    const ref = makeGroup();
    renderHook(() => useBodyAction(ref));
    expect(gsap.to).not.toHaveBeenCalled();
  });

  it.each(["nod", "shake", "wave", "shrug"] as const)(
    "runs at least one tween for action %s",
    (action) => {
      const ref = makeGroup();
      renderHook(() => useBodyAction(ref));
      act(() => {
        useZendaya.setState({ bodyActionPulse: { action, ts: 1 } });
      });
      expect(gsap.to).toHaveBeenCalled();
    }
  );

  it("re-fires on ts change with same action", () => {
    const ref = makeGroup();
    renderHook(() => useBodyAction(ref));
    act(() => useZendaya.setState({ bodyActionPulse: { action: "nod", ts: 1 } }));
    const firstCallCount = vi.mocked(gsap.to).mock.calls.length;
    act(() => useZendaya.setState({ bodyActionPulse: { action: "nod", ts: 2 } }));
    expect(vi.mocked(gsap.to).mock.calls.length).toBeGreaterThan(firstCallCount);
  });
});
```

- [ ] **Step 2: Run — confirm failures**

```powershell
Push-Location zendaya-hud-react
npm test src/__tests__/useBodyAction.test.ts 2>&1 | Select-Object -Last 15
Pop-Location
```

Expected: failures because `useBodyAction` doesn't exist yet.

- [ ] **Step 3: Create `useBodyAction.ts`**

Use Write tool:

```typescript
import { useEffect } from "react";
import gsap from "gsap";
import * as THREE from "three";
import { useZendaya } from "../store/zendayaStore";

function nodTimeline(g: THREE.Group) {
  gsap.to(g.position, { y: -0.15, duration: 0.15, ease: "power2.in" });
  gsap.to(g.position, { y: 0, duration: 0.30, delay: 0.15, ease: "back.out(2)" });
}

function shakeTimeline(g: THREE.Group) {
  gsap.to(g.position, { x: -0.10, duration: 0.10, ease: "sine.inOut" });
  gsap.to(g.position, { x: 0.10, duration: 0.10, delay: 0.10, ease: "sine.inOut" });
  gsap.to(g.position, { x: -0.05, duration: 0.10, delay: 0.20, ease: "sine.inOut" });
  gsap.to(g.position, { x: 0, duration: 0.30, delay: 0.30, ease: "sine.out" });
}

function waveTimeline(g: THREE.Group) {
  gsap.to(g.rotation, { z: 0.20, duration: 0.30, ease: "power2.inOut" });
  gsap.to(g.position, { x: 0.08, duration: 0.30, ease: "power2.inOut" });
  gsap.to(g.rotation, { z: 0, duration: 0.50, delay: 0.30, ease: "power2.inOut" });
  gsap.to(g.position, { x: 0, duration: 0.50, delay: 0.30, ease: "power2.inOut" });
}

function shrugTimeline(g: THREE.Group) {
  gsap.to(g.scale, { x: 1.12, y: 1.12, z: 1.12, duration: 0.15, ease: "power2.out" });
  gsap.to(g.scale, { x: 1.0, y: 1.0, z: 1.0, duration: 0.35, delay: 0.15, ease: "elastic.out(1, 0.6)" });
}

function fallbackWobble(g: THREE.Group) {
  // raf-only mini-wobble if gsap fails — visual proof of pulse.
  const start = performance.now();
  const initial = g.scale.x;
  function frame() {
    const t = (performance.now() - start) / 200;
    if (t >= 1) {
      g.scale.setScalar(initial);
      return;
    }
    g.scale.setScalar(initial * (1 + 0.08 * Math.sin(t * Math.PI)));
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

export function useBodyAction(groupRef: React.MutableRefObject<THREE.Group | null>) {
  const pulse = useZendaya((s) => s.bodyActionPulse);
  useEffect(() => {
    const g = groupRef.current;
    if (!g || !pulse.action) return;
    try {
      gsap.killTweensOf([g.position, g.rotation, g.scale]);
      switch (pulse.action) {
        case "nod":   nodTimeline(g);   break;
        case "shake": shakeTimeline(g); break;
        case "wave":  waveTimeline(g);  break;
        case "shrug": shrugTimeline(g); break;
      }
    } catch (e) {
      console.warn("[orb] body-action GSAP failed, falling back to raf wobble", e);
      fallbackWobble(g);
    }
  }, [pulse.ts, groupRef, pulse.action]);
}
```

- [ ] **Step 4: Mount in Orb.tsx**

Use Edit to import the hook and call it on `bodyGroup`:

Add import near the top of Orb.tsx:

- old_string:
```typescript
import { useZendaya, type AiState } from "../../store/zendayaStore";
```
- new_string:
```typescript
import { useZendaya, type AiState } from "../../store/zendayaStore";
import { useBodyAction } from "../../hooks/useBodyAction";
```

Mount the hook inside the component body, right after the existing `useRef` calls:

- old_string:
```typescript
  const smoothed = useRef({ pulse: 0, voiceScale: 1, ripple: 0 });
```
- new_string:
```typescript
  const smoothed = useRef({ pulse: 0, voiceScale: 1, ripple: 0 });
  useBodyAction(bodyGroup);
```

- [ ] **Step 5: Run — confirm pass**

```powershell
Push-Location zendaya-hud-react
npm test 2>&1 | Select-Object -Last 10
Pop-Location
```

Expected: all useBodyAction tests pass + prior tests still pass.

- [ ] **Step 6: Commit**

```powershell
git add zendaya-hud-react/src/hooks/useBodyAction.ts zendaya-hud-react/src/components/Orb/Orb.tsx zendaya-hud-react/src/__tests__/useBodyAction.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): body-action GSAP timelines on nested orb group (nod/shake/wave/shrug)"
git show --stat HEAD
```

---

### Task 7: TelemetryWidget component + tests

**Files:**
- Create: `C:\Users\IKA\Zendaya\zendaya-hud-react\src\components\HUD\TelemetryWidget.tsx`
- Create: `C:\Users\IKA\Zendaya\zendaya-hud-react\src\__tests__\TelemetryWidget.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `zendaya-hud-react/src/__tests__/TelemetryWidget.test.tsx`:

```typescript
import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { useZendaya } from "../store/zendayaStore";
import TelemetryWidget from "../components/HUD/TelemetryWidget";

beforeEach(() => {
  useZendaya.setState({ telemetry: null });
});

describe("TelemetryWidget", () => {
  it("renders nothing when telemetry is null", () => {
    const { container } = render(<TelemetryWidget />);
    expect(container.firstChild).toBeNull();
  });

  it("renders CPU/MEM/mood when populated", () => {
    useZendaya.setState({
      telemetry: {
        cpu: 23.5, mem: 60, mic_level: 0, mood: "neutral",
        vision_active: false, gestures_active: false,
        hud_enabled: true, online: true,
        user_name: "", language: "english",
        last_gesture: { name: "none", ts: 0 },
      },
    });
    render(<TelemetryWidget />);
    expect(screen.getByText(/CPU/)).toBeInTheDocument();
    expect(screen.getByText(/MEM/)).toBeInTheDocument();
    expect(screen.getByText(/24%/)).toBeInTheDocument();    // CPU rounded
    expect(screen.getByText(/60%/)).toBeInTheDocument();
    expect(screen.getByText(/neutral/)).toBeInTheDocument();
  });

  it("renders offline banner when online=false", () => {
    useZendaya.setState({
      telemetry: {
        cpu: 0, mem: 0, mic_level: 0, mood: "neutral",
        vision_active: false, gestures_active: false,
        hud_enabled: true, online: false,
        user_name: "", language: "english",
        last_gesture: { name: "none", ts: 0 },
      },
    });
    render(<TelemetryWidget />);
    expect(screen.getByText(/offline/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run — confirm failures**

```powershell
Push-Location zendaya-hud-react
npm test src/__tests__/TelemetryWidget.test.tsx 2>&1 | Select-Object -Last 15
Pop-Location
```

Expected: failure because the component doesn't exist.

- [ ] **Step 3: Create `TelemetryWidget.tsx`**

```typescript
import { useZendaya } from "../../store/zendayaStore";

function Row({ label, value, unit }: { label: string; value: number; unit: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-10 opacity-60">{label}</span>
      <div className="w-20 h-1 bg-orange-300/10 rounded overflow-hidden">
        <div className="h-full bg-orange-400/60" style={{ width: `${Math.min(100, value)}%` }} />
      </div>
      <span className="w-10 text-right">{value.toFixed(0)}{unit}</span>
    </div>
  );
}

export default function TelemetryWidget() {
  const t = useZendaya((s) => s.telemetry);
  if (!t) return null;

  return (
    <div className="absolute top-4 right-4 flex flex-col gap-1 text-xs
                    text-orange-300/80 font-mono select-none pointer-events-none">
      <Row label="CPU" value={t.cpu} unit="%" />
      <Row label="MEM" value={t.mem} unit="%" />
      <div className="opacity-60">mood: {t.mood}</div>
      {!t.online && <div className="text-red-400/80">offline</div>}
    </div>
  );
}
```

- [ ] **Step 4: Run — confirm pass**

```powershell
Push-Location zendaya-hud-react
npm test src/__tests__/TelemetryWidget.test.tsx 2>&1 | Select-Object -Last 10
Pop-Location
```

Expected: 3/3 pass.

- [ ] **Step 5: Commit**

```powershell
git add zendaya-hud-react/src/components/HUD/TelemetryWidget.tsx zendaya-hud-react/src/__tests__/TelemetryWidget.test.tsx
git -c commit.gpgsign=false commit -m "feat(hud): TelemetryWidget — CPU/MEM bars + mood + offline banner"
git show --stat HEAD
```

---

### Task 8: PerceptionIndicator component + tests

**Files:**
- Create: `C:\Users\IKA\Zendaya\zendaya-hud-react\src\components\HUD\PerceptionIndicator.tsx`
- Create: `C:\Users\IKA\Zendaya\zendaya-hud-react\src\__tests__\PerceptionIndicator.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `zendaya-hud-react/src/__tests__/PerceptionIndicator.test.tsx`:

```typescript
import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { useZendaya } from "../store/zendayaStore";
import PerceptionIndicator from "../components/HUD/PerceptionIndicator";

beforeEach(() => {
  useZendaya.setState({ perception: null });
});

describe("PerceptionIndicator", () => {
  it("renders nothing when perception is null", () => {
    const { container } = render(<PerceptionIndicator />);
    expect(container.firstChild).toBeNull();
  });

  it("shows 'sees you' + recent gesture", () => {
    const nowSec = Date.now() / 1000;
    useZendaya.setState({
      perception: {
        face: { present: true, ts: nowSec },
        last_gesture: { name: "Thumb_Up", ts: nowSec - 0.5 },
      },
    });
    render(<PerceptionIndicator />);
    expect(screen.getByText(/sees you/)).toBeInTheDocument();
    expect(screen.getByText(/Thumb Up/)).toBeInTheDocument();
  });

  it("hides chip when gesture is stale (>3s old)", () => {
    const nowSec = Date.now() / 1000;
    useZendaya.setState({
      perception: {
        face: { present: true, ts: nowSec },
        last_gesture: { name: "Thumb_Up", ts: nowSec - 10 },
      },
    });
    render(<PerceptionIndicator />);
    expect(screen.queryByText(/Thumb Up/)).toBeNull();
  });

  it("shows 'looking' when face not present", () => {
    useZendaya.setState({
      perception: {
        face: { present: false, ts: 0 },
        last_gesture: { name: "none", ts: 0 },
      },
    });
    render(<PerceptionIndicator />);
    expect(screen.getByText(/looking/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run — confirm failures**

```powershell
Push-Location zendaya-hud-react
npm test src/__tests__/PerceptionIndicator.test.tsx 2>&1 | Select-Object -Last 15
Pop-Location
```

Expected: failure because component doesn't exist.

- [ ] **Step 3: Create `PerceptionIndicator.tsx`**

```typescript
import { useZendaya } from "../../store/zendayaStore";

export default function PerceptionIndicator() {
  const p = useZendaya((s) => s.perception);
  if (!p) return null;

  const stale = Date.now() / 1000 - p.last_gesture.ts > 3.0;
  const gestureLabel = p.last_gesture.name && p.last_gesture.name !== "none" && !stale
    ? p.last_gesture.name.replace(/_/g, " ")
    : null;

  return (
    <div className="absolute top-4 left-4 flex items-center gap-2 text-xs
                    text-orange-300/80 font-mono select-none pointer-events-none">
      <span
        className={`w-2 h-2 rounded-full ${
          p.face.present
            ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]"
            : "bg-zinc-500/40"
        }`}
      />
      <span className="opacity-70">{p.face.present ? "sees you" : "looking"}</span>
      {gestureLabel && (
        <span className="ml-2 px-1.5 py-0.5 rounded bg-orange-400/10
                         border border-orange-400/30 animate-pulse">
          {gestureLabel}
        </span>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run — confirm pass**

```powershell
Push-Location zendaya-hud-react
npm test 2>&1 | Select-Object -Last 10
Pop-Location
```

Expected: 4/4 PerceptionIndicator tests pass + prior tests still pass.

- [ ] **Step 5: Commit**

```powershell
git add zendaya-hud-react/src/components/HUD/PerceptionIndicator.tsx zendaya-hud-react/src/__tests__/PerceptionIndicator.test.tsx
git -c commit.gpgsign=false commit -m "feat(hud): PerceptionIndicator — face dot + stale-fading gesture chip"
git show --stat HEAD
```

---

### Task 9: Hud.tsx mount + mood-atmosphere effect

**Files:**
- Modify: `C:\Users\IKA\Zendaya\zendaya-hud-react\src\components\HUD\Hud.tsx`

This task has no new tests — the widgets are tested in isolation; mounting is verified manually.

- [ ] **Step 1: Read the current Hud.tsx**

```powershell
Get-Content zendaya-hud-react\src\components\HUD\Hud.tsx
```

Note the existing imports and the existing JSX return. Decide whether the two new widgets go inside an existing wrapper or as new top-level fragments.

- [ ] **Step 2: Add imports**

Use Edit to add to the import block at the top:

```typescript
import { useEffect } from "react";
import TelemetryWidget from "./TelemetryWidget";
import PerceptionIndicator from "./PerceptionIndicator";
import { useZendaya } from "../../store/zendayaStore";
```

(If some of these are already imported, skip duplicates.)

- [ ] **Step 3: Add the mood-atmosphere effect inside the component**

Use Edit to add this near the top of the component body (e.g., right after any existing `const` declarations):

```typescript
  const mood = useZendaya((s) => s.telemetry?.mood);
  const setBgDim = useZendaya((s) => s.setBgDim);
  useEffect(() => {
    if (!mood || typeof setBgDim !== "function") return;
    const moodToBgDim: Record<string, number> = {
      neutral: 0.7,
      focused: 0.6,
      tired: 0.85,
      alert: 0.5,
    };
    setBgDim(moodToBgDim[mood] ?? 0.7);
  }, [mood, setBgDim]);
```

- [ ] **Step 4: Mount the widgets**

Anchor on the existing top-level JSX return. The exact insertion depends on the current structure. As a safe default, add the two widgets just before the closing tag of the outermost fragment / div:

If the current return is shaped like `return (<>...children...</>);`, change to:

```typescript
  return (
    <>
      {/* existing HUD contents */}
      <TelemetryWidget />
      <PerceptionIndicator />
    </>
  );
```

Or if wrapped in a div, append the two widgets at the end of the children.

- [ ] **Step 5: Type-check + run tests**

```powershell
Push-Location zendaya-hud-react
npx tsc --noEmit 2>&1 | Select-Object -Last 10
npm test 2>&1 | Select-Object -Last 10
Pop-Location
```

Expected: no TS errors; tests pass.

- [ ] **Step 6: Commit**

```powershell
git add zendaya-hud-react/src/components/HUD/Hud.tsx
git -c commit.gpgsign=false commit -m "feat(hud): mount TelemetryWidget + PerceptionIndicator; mood biases bgDim"
git show --stat HEAD
```

---

### Task 10: MusicPlayer transport key fix

**Files:**
- Modify: `C:\Users\IKA\Zendaya\zendaya-hud-react\src\components\HUD\MusicPlayer.tsx`

- [ ] **Step 1: Find the broken POST**

```powershell
Select-String -Path zendaya-hud-react\src\components\HUD\MusicPlayer.tsx -Pattern "fetch\(.*\/chat|JSON\.stringify\(\{ ?text" | Select-Object LineNumber,Line
```

Note the line(s) with `JSON.stringify({ text ... })`.

- [ ] **Step 2: Apply the fix**

Use Edit. The exact old/new depends on the file but the pattern is:

- old_string: `JSON.stringify({ text })`
- new_string: `JSON.stringify({ message: text })`

If the actual call is `JSON.stringify({ text: text })` or similar, adjust to match exactly. If there are multiple call sites, use `replace_all`.

- [ ] **Step 3: Type-check**

```powershell
Push-Location zendaya-hud-react
npx tsc --noEmit 2>&1 | Select-Object -Last 5
Pop-Location
```

Expected: no errors.

- [ ] **Step 4: Commit**

```powershell
git add zendaya-hud-react/src/components/HUD/MusicPlayer.tsx
git -c commit.gpgsign=false commit -m "fix(hud): MusicPlayer transport posts {message} (was {text}) — backend ChatIn expects message"
git show --stat HEAD
```

---

### Task 11: Final verification + manual report

**Files:** None (read-only).

- [ ] **Step 1: List the channel commits**

```powershell
git log db0ab6e..HEAD --oneline
```

(Replace `db0ab6e` with the actual baseline-commit SHA from Task 0 if different — read it from `git log -1 --format="%H" --grep "snapshot untracked HUD"`.)

Expected commits (in order, plus Task 0 baseline preceding):
- `chore: snapshot untracked HUD + state_server as baseline ...`
- `test(hud): scaffold vitest + happy-dom + @testing-library/react`
- `feat(state-server): broadcast loop with decimation + extended snapshot on connect`
- `feat(hud): extend Zustand store with visemes/telemetry/perception/body slices`
- `feat(hud): useWebSocket handles 5 new message types + widens AI filter + heartbeat`
- `feat(hud): orb core uses viseme-driven ripple shader + nested body group`
- `feat(hud): body-action GSAP timelines on nested orb group (nod/shake/wave/shrug)`
- `feat(hud): TelemetryWidget — CPU/MEM bars + mood + offline banner`
- `feat(hud): PerceptionIndicator — face dot + stale-fading gesture chip`
- `feat(hud): mount TelemetryWidget + PerceptionIndicator; mood biases bgDim`
- `fix(hud): MusicPlayer transport posts {message} ...`

- [ ] **Step 2: Run both test suites**

```powershell
pytest backend/tests/ -v 2>&1 | Select-Object -Last 3
Push-Location zendaya-hud-react
npm test 2>&1 | Select-Object -Last 5
Pop-Location
```

Expected:
- Pytest: `87 passed` (78 prior + 9 new).
- Vitest: all tests pass. Approximate count: 6 store + 13 useWebSocket + 3 TelemetryWidget + 4 PerceptionIndicator + 5 useBodyAction + 3 normaliseVisemes = ~34.

- [ ] **Step 3: Working-tree state**

```powershell
git status --short
```

Expected: only pre-existing dirty state visible (`backend/zendaya.py` etc.). NO new untracked files from execution. NO unintended modifications.

- [ ] **Step 4: Manual verification checklist (user runs)**

Print this verbatim:

```
Manual checks (user runs):

[ ] 1. Start the backend (zendaya.py). Confirm `/health` returns OK on 127.0.0.1:7475.
[ ] 2. From zendaya-hud-react/, run `npm run dev`. Open the URL printed by Vite (default http://localhost:5180).
[ ] 3. Orb is visible; logs show WS connected. Telemetry widget appears top-right within ~1s. Perception indicator appears top-left.
[ ] 4. Speak — orb visibly pulses. The core ripples during speech (not just scaling).
[ ] 5. CPU/MEM bars in TelemetryWidget update every ~500ms; mood text changes if you toggle backend mood.
[ ] 6. Webcam enabled with vision_enabled=true — Perception dot turns emerald.
[ ] 7. Make a recognised gesture — chip flashes, then fades after 3s.
[ ] 8. Trigger `set_body_action("nod")` from backend (debug endpoint or test script). Orb performs a discrete bounce.
[ ] 9. Trigger same body action twice in 500ms. Orb bounces twice (repeat-pulse working).
[ ] 10. Send `set_state("alert")` from backend. Orb takes alert pulse intensity (regression — was silently dropped).
[ ] 11. MusicPlayer transport — pause/skip a Spotify track. Backend logs receive {"message": ...}. Frontend gets accepted: true.
[ ] 12. Kill backend mid-session. Frontend WS reconnects within ~5s. Widgets clear to hidden; then repopulate on reconnect.
```

- [ ] **Step 5: Status line**

Output a single short line: `HUD channels wire-up complete: 11 commits, 87 pytest + ~34 vitest tests passing, orb amplitude+visemes+body live, telemetry+perception widgets live, MusicPlayer fixed. Manual verification pending.`

No commit.

---

## Out of scope (for follow-up plans)

- Visual polish: shader palette, glow tuning, post-processing (bloom/vignette/noise).
- New modules: command palette, conversation history, alarms-from-AAF panel.
- Body action via richer orb mesh or VRM avatar (Path B / Path C from brainstorming).
- `notifications` driven by a backend push channel (currently only via `dispatchAction("show_notification", ...)`).
- `setSpeakerAzimuth` driver for spatial audio.
- Adaptive-quality auto-tuning of broadcast cadence (drop to 15 Hz when fps < 30).
- Touching the 4,400-line uncommitted diff — user explicit: leave it alone.
