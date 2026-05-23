# Assistant Features Wire-up (Alarms + Timers + Lists) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up alarms, timers, and named lists into `backend/zendaya.py` via a new `backend/zendaya_assistant_features.py` module so the user can say things like "set an alarm for 7am tomorrow", "10-minute timer", and "add milk to the shopping list" and have them actually work.

**Architecture:** One new module owns parsers, handlers, an APScheduler `BackgroundScheduler`, and a `try_handle(text)` dispatch hook. Persistence delegates to existing `backend/zendaya_data_store.py`. `zendaya.py` gets ~5 lines of glue (guarded import + `set_notifier` + `start` + dispatch call + `stop`). Notifier is injected so AAF stays import-clean and unit-testable.

**Tech Stack:** Python 3.11+, APScheduler (BackgroundScheduler + CronTrigger + DateTrigger), `croniter` (cron validation), `dateparser` (heuristic time parsing), `win10toast` (already imported in zendaya.py), `pytest` (test runner).

**Spec:** [docs/superpowers/specs/2026-05-23-assistant-features-wireup-design.md](../specs/2026-05-23-assistant-features-wireup-design.md)

---

## File Structure

| File / Path | Action | Responsibility |
|---|---|---|
| `C:\Users\IKA\Zendaya\pyproject.toml` | Modify | Add `croniter` + `dateparser` to `[tool.poetry.dependencies]` |
| `C:\Users\IKA\Zendaya\backend\zendaya_assistant_features.py` | Create | Parsers, handlers, scheduler lifecycle, dispatcher, notifier injection |
| `C:\Users\IKA\Zendaya\backend\tests\__init__.py` | Create | Marks `backend/tests/` as a package |
| `C:\Users\IKA\Zendaya\backend\tests\conftest.py` | Create | Pytest fixtures (tmp data_store dir, fake notifier) |
| `C:\Users\IKA\Zendaya\backend\tests\test_assistant_features.py` | Create | Unit tests for all of AAF |
| `C:\Users\IKA\Zendaya\backend\zendaya.py` | Modify (5 touch points) | Guarded import + `set_notifier` + `start` + dispatch hook + `stop` |
| `C:\Users\IKA\Zendaya\zendaya_data\alarms.json` | Created externally at runtime | Persisted alarm records (gitignored via `zendaya_data/` if applicable) |
| `C:\Users\IKA\Zendaya\zendaya_data\timers.json` | Created externally at runtime | Persisted timer records |
| `C:\Users\IKA\Zendaya\zendaya_data\lists.json` | Created externally at runtime | Persisted named lists |

---

## Conventions for this plan

- **Shell:** PowerShell 5.1 on Windows. No `&&`; use `;` or `if ($?) { ... }`.
- **Working directory:** `C:\Users\IKA\Zendaya` unless noted. Tests run from there too.
- **Test runner:** `pytest backend/tests/ -v` (pytest config in `pyproject.toml` already sets `asyncio_mode = "auto"`).
- **Commit safety:** the repo has a large pre-existing uncommitted diff the user said to leave alone. NEVER use `git add -A`, `git add .`, or `git add <dir>`. Always pass exact file paths to `git add`. Verify with `git show --stat HEAD` after each commit that only intended files landed.
- **Module-internal names:** AAF uses `_leading_underscore` for module-private helpers, no underscore for the public API (`try_handle`, `set_notifier`, `start`, `stop`).
- **Field consistency:** the record schemas (`id`, `kind`, `trigger`, `fire_at`, `label`, `created_at`, `active`) match the spec exactly. Do NOT rename them in implementation; tests assert on these keys.

---

### Task 1: Add dependencies

**Files:**
- Modify: `C:\Users\IKA\Zendaya\pyproject.toml` (insert two lines in the `[tool.poetry.dependencies]` block, alphabetical-ish — after `psycopg2-binary` is a clean spot)

- [ ] **Step 1: Verify current state**

```powershell
python -c "import importlib.util; [print(f'{m}:', importlib.util.find_spec(m) is not None) for m in ['apscheduler', 'croniter', 'dateparser', 'win10toast', 'pytest']]"
```

Expected: `apscheduler: True`, `win10toast: True`, `pytest: True`, `croniter: False`, `dateparser: False`.

- [ ] **Step 2: Edit `pyproject.toml`**

Use the `Edit` tool to insert two new lines. Anchor on a unique line:

- `old_string`:
```
psycopg2-binary = "^2.9.9"
```
- `new_string`:
```
psycopg2-binary = "^2.9.9"
croniter = "^2.0.0"
dateparser = "^1.2.0"
```

- [ ] **Step 3: Install via pip (faster than `poetry install` on Windows)**

```powershell
pip install "croniter>=2,<3" "dateparser>=1.2,<2"
```

Expected: both packages install with no errors. Exit code 0.

- [ ] **Step 4: Verify the install**

```powershell
python -c "import croniter; import dateparser; print('croniter', croniter.__version__); print('dateparser', dateparser.__version__)"
```

Expected: both versions print, no ImportError.

- [ ] **Step 5: Commit ONLY `pyproject.toml`**

```powershell
git add pyproject.toml
git -c commit.gpgsign=false commit -m "deps: add croniter and dateparser for assistant-features wire-up"
git show --stat HEAD
```

Expected: `git show --stat HEAD` shows ONLY `pyproject.toml`. **If it shows anything else, that's bad — abort and investigate** (the pre-existing modifications must not bleed in). Note: `pyproject.toml` is in the pre-existing modified list (`M pyproject.toml` at session start). Read the diff first:

```powershell
git diff --cached pyproject.toml
```

If the cached diff contains anything other than your two added lines, run `git reset HEAD pyproject.toml`, then manually amend `pyproject.toml` to revert any non-yours changes, then re-stage and re-commit. The pattern from the Graphify-setup session's gitignore split is the precedent.

---

### Task 2: Create the test scaffolding

**Files:**
- Create: `C:\Users\IKA\Zendaya\backend\tests\__init__.py` (empty)
- Create: `C:\Users\IKA\Zendaya\backend\tests\conftest.py`

- [ ] **Step 1: Create `backend/tests/__init__.py`**

Use the `Write` tool to create an empty file (one comment line is fine):

```python
# Marks backend/tests as a package so pytest collects it cleanly.
```

- [ ] **Step 2: Create `backend/tests/conftest.py`**

Use the `Write` tool with this exact content:

```python
"""Pytest fixtures for the assistant-features test suite."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the backend/ directory importable for `import zendaya_assistant_features` etc.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


@pytest.fixture()
def tmp_data_dir(tmp_path, monkeypatch):
    """Point zendaya_data_store at a fresh tmp directory for this test only."""
    import zendaya_data_store

    monkeypatch.setattr(zendaya_data_store, "DATA_DIR", tmp_path)
    return tmp_path


@pytest.fixture()
def fake_notifier():
    """Records every notify call so tests can assert on what was spoken/toasted."""
    calls = {"speak": [], "toast": []}

    def speak(text: str) -> None:
        calls["speak"].append(text)

    def toast(title: str, body: str, duration: int = 10) -> None:
        calls["toast"].append((title, body, duration))

    return speak, toast, calls
```

- [ ] **Step 3: Sanity-check pytest can collect the directory**

```powershell
pytest backend/tests/ --collect-only
```

Expected: prints `<Module conftest.py>` and exits 0. If pytest reports `ERROR`, investigate before continuing.

- [ ] **Step 4: Commit**

```powershell
git add backend/tests/__init__.py backend/tests/conftest.py
git -c commit.gpgsign=false commit -m "test: scaffold backend/tests/ with tmp data-dir and fake-notifier fixtures"
git show --stat HEAD
```

Expected: `git show --stat HEAD` shows ONLY the two new files.

---

### Task 3: AAF module skeleton + storage helpers

**Files:**
- Create: `C:\Users\IKA\Zendaya\backend\zendaya_assistant_features.py`
- Create / append: `C:\Users\IKA\Zendaya\backend\tests\test_assistant_features.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_assistant_features.py` with this exact content:

```python
"""Unit tests for zendaya_assistant_features."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest


# ─── Skeleton import smoke test ────────────────────────────────────────────


def test_module_imports_and_exposes_public_api(tmp_data_dir):
    import zendaya_assistant_features as aaf

    assert callable(aaf.set_notifier)
    assert callable(aaf.start)
    assert callable(aaf.stop)
    assert callable(aaf.try_handle)


def test_try_handle_returns_none_for_unrelated_input(tmp_data_dir):
    import zendaya_assistant_features as aaf

    assert aaf.try_handle("what time is it") is None
    assert aaf.try_handle("") is None


# ─── Storage round-trip ────────────────────────────────────────────────────


def test_state_round_trip(tmp_data_dir):
    import zendaya_assistant_features as aaf

    state = aaf._load_state()
    assert state == {"alarms": [], "timers": [], "lists": {}, "next_alarm_id": 1, "next_timer_id": 1}

    state["alarms"].append({"id": 1, "kind": "one_shot", "trigger": "2030-01-01T07:00:00",
                            "label": "alarm", "created_at": 0.0, "active": True})
    state["next_alarm_id"] = 2
    aaf._save_state(state)

    reloaded = aaf._load_state()
    assert reloaded["alarms"][0]["id"] == 1
    assert reloaded["next_alarm_id"] == 2


def test_corrupt_state_file_is_renamed_and_default_returned(tmp_data_dir):
    import zendaya_assistant_features as aaf

    (tmp_data_dir / "aaf_state.json").write_text("{not valid json", encoding="utf-8")

    state = aaf._load_state()
    assert state == {"alarms": [], "timers": [], "lists": {}, "next_alarm_id": 1, "next_timer_id": 1}

    bad_files = list(tmp_data_dir.glob("aaf_state.bad-*.json"))
    assert len(bad_files) == 1, f"expected one .bad-* file, got {bad_files}"
```

- [ ] **Step 2: Run tests — confirm they fail**

```powershell
pytest backend/tests/test_assistant_features.py -v
```

Expected: 4 errors, all `ModuleNotFoundError: No module named 'zendaya_assistant_features'`.

- [ ] **Step 3: Create the AAF module skeleton**

Use the `Write` tool to create `backend/zendaya_assistant_features.py` with this exact content:

```python
"""
zendaya_assistant_features.py
=============================
Wires alarms, timers, and named lists into the Zendaya assistant.

Public API:
  set_notifier(speak_fn, toast_fn) - inject notifier callbacks from zendaya.py
  start()                          - start the scheduler, re-arm persisted records, prune stale
  stop()                           - graceful shutdown
  try_handle(text) -> Optional[str] - parse + dispatch a user utterance; None if no match

All persistence goes through zendaya_data_store (single JSON file 'aaf_state.json').
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import zendaya_data_store


# ─── Module state ──────────────────────────────────────────────────────────

_STATE_LOCK = threading.Lock()
_STATE_FILE = "aaf_state"  # data_store appends .json

# Notifier callbacks injected by zendaya.py
_speak_fn: Optional[Callable[[str], None]] = None
_toast_fn: Optional[Callable[[str, str, int], None]] = None

_DEFAULT_STATE: dict = {
    "alarms": [],
    "timers": [],
    "lists": {},
    "next_alarm_id": 1,
    "next_timer_id": 1,
}


# ─── Storage helpers ───────────────────────────────────────────────────────

def _load_state() -> dict:
    """Load state, returning defaults on missing/corrupt file. Corrupt files renamed .bad-<ts>."""
    p = zendaya_data_store.DATA_DIR / f"{_STATE_FILE}.json"
    if not p.exists():
        return _fresh_state()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        ts = time.strftime("%Y%m%d-%H%M%S")
        bad = p.with_name(f"{_STATE_FILE}.bad-{ts}.json")
        try:
            os.replace(p, bad)
            print(f"(aaf: corrupt {p.name} renamed to {bad.name}: {e})")
        except Exception as rename_err:
            print(f"(aaf: could not rename corrupt {p.name}: {rename_err})")
        return _fresh_state()
    # Merge with defaults so missing keys don't crash callers after a schema bump.
    merged = _fresh_state()
    merged.update(data)
    return merged


def _save_state(state: dict) -> None:
    with _STATE_LOCK:
        zendaya_data_store.save(_STATE_FILE, state)


def _fresh_state() -> dict:
    return {
        "alarms": [],
        "timers": [],
        "lists": {},
        "next_alarm_id": 1,
        "next_timer_id": 1,
    }


# ─── Public API (skeleton; filled in by later tasks) ───────────────────────

def set_notifier(speak_fn: Callable[[str], None],
                 toast_fn: Optional[Callable[[str, str, int], None]]) -> None:
    global _speak_fn, _toast_fn
    _speak_fn = speak_fn
    _toast_fn = toast_fn


def start() -> None:
    """Skeleton — populated by Task 7. Touches state so corruption is caught early."""
    state = _load_state()
    _save_state(state)


def stop() -> None:
    """Skeleton — populated by Task 7."""
    pass


def try_handle(text: str) -> Optional[str]:
    """Skeleton — populated by Task 7. Returns None so the LLM path takes over."""
    return None
```

- [ ] **Step 4: Run tests — confirm they pass**

```powershell
pytest backend/tests/test_assistant_features.py -v
```

Expected: all 4 tests pass. If any fail, fix and re-run.

- [ ] **Step 5: Commit**

```powershell
git add backend/zendaya_assistant_features.py backend/tests/test_assistant_features.py
git -c commit.gpgsign=false commit -m "feat(aaf): module skeleton with persistent state and corruption recovery"
git show --stat HEAD
```

Expected: ONLY the two files listed.

---

### Task 4: Timer family

**Files:**
- Modify: `C:\Users\IKA\Zendaya\backend\zendaya_assistant_features.py`
- Modify: `C:\Users\IKA\Zendaya\backend\tests\test_assistant_features.py` (append)

- [ ] **Step 1: Write the failing tests**

Append the following to `backend/tests/test_assistant_features.py`:

```python
# ─── Timer family ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("utterance, expected_seconds", [
    ("set a timer for 10 minutes", 600),
    ("set timer for 5 min", 300),
    ("timer 90 seconds", 90),
    ("set a timer for 2 hours", 7200),
    ("timer 1 hr", 3600),
])
def test_parse_timer_command_positive(utterance, expected_seconds, tmp_data_dir):
    import zendaya_assistant_features as aaf

    action, payload = aaf.parse_timer_command(utterance)
    assert action == "create"
    assert payload["duration_seconds"] == expected_seconds


@pytest.mark.parametrize("utterance", [
    "what time is it",
    "set an alarm for 7am",
    "add milk to shopping",
    "",
])
def test_parse_timer_command_negative(utterance, tmp_data_dir):
    import zendaya_assistant_features as aaf
    assert aaf.parse_timer_command(utterance) is None


def test_create_timer_persists_record(tmp_data_dir):
    import zendaya_assistant_features as aaf

    reply = aaf._handle_timer("create", {"duration_seconds": 60, "label": "1-minute timer"})
    assert "timer" in reply.lower()

    state = aaf._load_state()
    assert len(state["timers"]) == 1
    rec = state["timers"][0]
    assert rec["id"] == 1
    assert rec["duration_seconds"] == 60
    assert rec["active"] is True


def test_list_timers_with_no_timers(tmp_data_dir):
    import zendaya_assistant_features as aaf
    reply = aaf._handle_timer("list", {})
    assert "no" in reply.lower() and "timer" in reply.lower()


def test_cancel_timer_by_index(tmp_data_dir):
    import zendaya_assistant_features as aaf

    aaf._handle_timer("create", {"duration_seconds": 60, "label": "1-min"})
    aaf._handle_timer("create", {"duration_seconds": 120, "label": "2-min"})

    reply = aaf._handle_timer("cancel", {"index": 1})
    assert "cancel" in reply.lower()

    state = aaf._load_state()
    active = [t for t in state["timers"] if t["active"]]
    assert len(active) == 1
    assert active[0]["duration_seconds"] == 120


def test_cancel_timer_out_of_range(tmp_data_dir):
    import zendaya_assistant_features as aaf
    reply = aaf._handle_timer("cancel", {"index": 5})
    assert "only" in reply.lower() or "no" in reply.lower()
```

- [ ] **Step 2: Run — confirm failures**

```powershell
pytest backend/tests/test_assistant_features.py -v -k "timer"
```

Expected: 11 errors, all `AttributeError: module ... has no attribute 'parse_timer_command'` (or `_handle_timer`).

- [ ] **Step 3: Implement**

Use the `Edit` tool to append the following to `backend/zendaya_assistant_features.py` (after the existing `try_handle` function):

```python


# ─── Timer parser ──────────────────────────────────────────────────────────

import re as _re

_TIMER_RE = _re.compile(
    r"^(?:set\s+(?:a\s+)?timer|timer)\s+(?:for|of)?\s*(\d+)\s*"
    r"(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b",
    _re.IGNORECASE,
)

_UNIT_TO_SECONDS = {
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
}


def parse_timer_command(text: str) -> Optional[tuple[str, dict]]:
    if not text:
        return None
    m = _TIMER_RE.match(text.strip())
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    seconds = n * _UNIT_TO_SECONDS[unit]
    if seconds <= 0:
        return None
    label = f"{n}-{unit.rstrip('s')} timer"
    return ("create", {"duration_seconds": seconds, "label": label})


# ─── Timer handler ─────────────────────────────────────────────────────────

def _handle_timer(action: str, payload: dict) -> str:
    state = _load_state()
    if action == "create":
        rec = {
            "id": state["next_timer_id"],
            "fire_at": datetime.now().isoformat(),  # placeholder; populated when scheduler wires it
            "duration_seconds": payload["duration_seconds"],
            "label": payload.get("label", "timer"),
            "created_at": time.time(),
            "active": True,
        }
        state["timers"].append(rec)
        state["next_timer_id"] += 1
        _save_state(state)
        # Scheduler arming happens in Task 7. For now, the record exists.
        secs = payload["duration_seconds"]
        return f"Timer set for {secs // 60} min {secs % 60} sec." if secs >= 60 else f"Timer set for {secs} sec."
    if action == "list":
        active = [t for t in state["timers"] if t["active"]]
        if not active:
            return "You have no active timers."
        lines = [f"{i + 1}. {t['label']}" for i, t in enumerate(active)]
        return "Active timers:\n" + "\n".join(lines)
    if action == "cancel":
        active = [t for t in state["timers"] if t["active"]]
        idx = payload.get("index", 0)
        if idx < 1 or idx > len(active):
            return f"You only have {len(active)} active timer(s). Try 'list my timers' to see them."
        rec = active[idx - 1]
        rec["active"] = False
        _save_state(state)
        return f"Cancelled timer {idx}: {rec['label']}."
    return f"Unknown timer action: {action}."
```

- [ ] **Step 4: Run — confirm pass**

```powershell
pytest backend/tests/test_assistant_features.py -v -k "timer"
```

Expected: all 11 timer tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/zendaya_assistant_features.py backend/tests/test_assistant_features.py
git -c commit.gpgsign=false commit -m "feat(aaf): timer parser + handler (create/list/cancel)"
git show --stat HEAD
```

Expected: only the two files.

---

### Task 5: Alarm family (one-shot + cron)

**Files:**
- Modify: `C:\Users\IKA\Zendaya\backend\zendaya_assistant_features.py`
- Modify: `C:\Users\IKA\Zendaya\backend\tests\test_assistant_features.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_assistant_features.py`:

```python
# ─── Alarm family ──────────────────────────────────────────────────────────


def test_parse_alarm_one_shot_simple(tmp_data_dir):
    import zendaya_assistant_features as aaf
    result = aaf.parse_alarm_command("set an alarm for 7am tomorrow")
    assert result is not None
    action, payload = result
    assert action == "create"
    assert payload["kind"] == "one_shot"
    # trigger is an ISO datetime string in the future
    dt = datetime.fromisoformat(payload["trigger"])
    assert dt > datetime.now()
    assert dt.hour == 7 and dt.minute == 0


@pytest.mark.parametrize("utterance, expected_cron", [
    ("alarm every weekday at 7am",        "0 7 * * 1-5"),
    ("set an alarm every sunday at 9pm",  "0 21 * * 0"),
    ("alarm every 15 minutes",            "*/15 * * * *"),
    ("alarm every monday at 8:30am",      "30 8 * * 1"),
])
def test_parse_alarm_cron_table(utterance, expected_cron, tmp_data_dir):
    import zendaya_assistant_features as aaf
    result = aaf.parse_alarm_command(utterance)
    assert result is not None, f"expected match for {utterance!r}"
    action, payload = result
    assert action == "create"
    assert payload["kind"] == "cron"
    assert payload["trigger"] == expected_cron


def test_parse_alarm_unrecognised_returns_help(tmp_data_dir):
    import zendaya_assistant_features as aaf
    result = aaf.parse_alarm_command("set an alarm on the next blue moon")
    assert result is not None
    action, payload = result
    assert action == "error"
    assert "try" in payload["message"].lower()


@pytest.mark.parametrize("utterance", [
    "set timer for 5 minutes",
    "add eggs to shopping",
    "what's the weather",
    "",
])
def test_parse_alarm_negative(utterance, tmp_data_dir):
    import zendaya_assistant_features as aaf
    assert aaf.parse_alarm_command(utterance) is None


def test_create_one_shot_alarm_persists(tmp_data_dir):
    import zendaya_assistant_features as aaf
    future = (datetime.now() + timedelta(hours=1)).isoformat()
    reply = aaf._handle_alarm("create", {"kind": "one_shot", "trigger": future, "label": "alarm in 1h"})
    assert "alarm" in reply.lower()
    state = aaf._load_state()
    assert len(state["alarms"]) == 1
    assert state["alarms"][0]["kind"] == "one_shot"


def test_create_cron_alarm_persists(tmp_data_dir):
    import zendaya_assistant_features as aaf
    reply = aaf._handle_alarm("create", {"kind": "cron", "trigger": "0 7 * * 1-5", "label": "weekday 7am"})
    assert "alarm" in reply.lower()
    state = aaf._load_state()
    assert state["alarms"][0]["kind"] == "cron"
    assert state["alarms"][0]["trigger"] == "0 7 * * 1-5"


def test_list_alarms_includes_both_kinds(tmp_data_dir):
    import zendaya_assistant_features as aaf
    future = (datetime.now() + timedelta(hours=1)).isoformat()
    aaf._handle_alarm("create", {"kind": "one_shot", "trigger": future, "label": "one-shot"})
    aaf._handle_alarm("create", {"kind": "cron", "trigger": "0 7 * * 1-5", "label": "weekday 7am"})
    reply = aaf._handle_alarm("list", {})
    assert "1." in reply and "2." in reply


def test_cancel_alarm_by_index(tmp_data_dir):
    import zendaya_assistant_features as aaf
    future = (datetime.now() + timedelta(hours=1)).isoformat()
    aaf._handle_alarm("create", {"kind": "one_shot", "trigger": future, "label": "one-shot"})
    aaf._handle_alarm("create", {"kind": "cron", "trigger": "0 7 * * 1-5", "label": "weekday"})
    aaf._handle_alarm("cancel", {"index": 1})
    state = aaf._load_state()
    active = [a for a in state["alarms"] if a["active"]]
    assert len(active) == 1 and active[0]["kind"] == "cron"
```

- [ ] **Step 2: Run — confirm failures**

```powershell
pytest backend/tests/test_assistant_features.py -v -k "alarm"
```

Expected: 14 failures, all `AttributeError` for `parse_alarm_command` / `_handle_alarm`.

- [ ] **Step 3: Implement**

Append to `backend/zendaya_assistant_features.py`:

```python


# ─── Alarm parser ──────────────────────────────────────────────────────────

_ALARM_PREFIX_RE = _re.compile(
    r"^(?:set\s+(?:an?\s+)?alarm|wake me up|remind me)\b",
    _re.IGNORECASE,
)

# Hand-curated phrase → cron table. Order matters: longer patterns first.
_DAY_TO_CRON = {
    "sunday": "0", "monday": "1", "tuesday": "2", "wednesday": "3",
    "thursday": "4", "friday": "5", "saturday": "6",
}


def _try_cron(text: str) -> Optional[str]:
    """Return a cron string if text matches a known recurring phrasing, else None."""
    import croniter as _croniter
    t = text.lower().strip()

    # "every <N> minutes" → "*/N * * * *"
    m = _re.search(r"every\s+(\d+)\s+minutes?", t)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 59:
            return f"*/{n} * * * *"

    # "every weekday at <H[:M]><am|pm>" → "M H * * 1-5"
    m = _re.search(r"every\s+weekday(?:s)?\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t)
    if m:
        h, mm, ampm = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        h = _normalise_hour(h, ampm)
        return f"{mm} {h} * * 1-5"

    # "every weekend at <H[:M]><am|pm>" → "M H * * 0,6"
    m = _re.search(r"every\s+weekend(?:s)?\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t)
    if m:
        h, mm, ampm = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        h = _normalise_hour(h, ampm)
        return f"{mm} {h} * * 0,6"

    # "every <day> at <H[:M]><am|pm>" → "M H * * D"
    m = _re.search(
        r"every\s+(sunday|monday|tuesday|wednesday|thursday|friday|saturday)\s+at\s+"
        r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
        t,
    )
    if m:
        day, h, mm, ampm = m.group(1), int(m.group(2)), int(m.group(3) or 0), m.group(4)
        h = _normalise_hour(h, ampm)
        return f"{mm} {h} * * {_DAY_TO_CRON[day]}"

    return None


def _normalise_hour(h: int, ampm: Optional[str]) -> int:
    if ampm == "pm" and h < 12:
        return h + 12
    if ampm == "am" and h == 12:
        return 0
    return h


def parse_alarm_command(text: str) -> Optional[tuple[str, dict]]:
    if not text or not _ALARM_PREFIX_RE.search(text):
        return None
    # Strip prefix, parse the remainder.
    remainder = _ALARM_PREFIX_RE.sub("", text, count=1).strip(" ,.;")

    # 1. Try cron-table for recurring phrasings.
    cron = _try_cron(remainder if remainder else text)
    if cron:
        return ("create", {"kind": "cron", "trigger": cron, "label": text.strip()})

    # 2. Try dateparser for one-shots.
    import dateparser
    dt = dateparser.parse(
        remainder,
        settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": False},
    )
    if dt and dt > datetime.now():
        return ("create", {"kind": "one_shot", "trigger": dt.isoformat(), "label": text.strip()})

    return ("error", {"message": "I couldn't parse that schedule. Try 'alarm at 7am tomorrow' or 'every weekday at 7am'."})


# ─── Alarm handler ─────────────────────────────────────────────────────────

def _handle_alarm(action: str, payload: dict) -> str:
    if action == "error":
        return payload["message"]
    state = _load_state()
    if action == "create":
        rec = {
            "id": state["next_alarm_id"],
            "kind": payload["kind"],
            "trigger": payload["trigger"],
            "label": payload.get("label", "alarm"),
            "created_at": time.time(),
            "active": True,
        }
        state["alarms"].append(rec)
        state["next_alarm_id"] += 1
        _save_state(state)
        # Scheduler arming happens in Task 7.
        if rec["kind"] == "one_shot":
            return f"Alarm set for {rec['trigger']}."
        return f"Recurring alarm set: {rec['trigger']}."
    if action == "list":
        active = [a for a in state["alarms"] if a["active"]]
        if not active:
            return "You have no active alarms."
        lines = [f"{i + 1}. [{a['kind']}] {a['trigger']} — {a['label']}" for i, a in enumerate(active)]
        return "Active alarms:\n" + "\n".join(lines)
    if action == "cancel":
        active = [a for a in state["alarms"] if a["active"]]
        idx = payload.get("index", 0)
        if idx < 1 or idx > len(active):
            return f"You only have {len(active)} active alarm(s). Try 'list my alarms' to see them."
        rec = active[idx - 1]
        rec["active"] = False
        _save_state(state)
        return f"Cancelled alarm {idx}: {rec['label']}."
    return f"Unknown alarm action: {action}."
```

- [ ] **Step 4: Run — confirm pass**

```powershell
pytest backend/tests/test_assistant_features.py -v -k "alarm"
```

Expected: all 14 alarm tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/zendaya_assistant_features.py backend/tests/test_assistant_features.py
git -c commit.gpgsign=false commit -m "feat(aaf): alarm parser (one-shot via dateparser + cron table) + handler"
git show --stat HEAD
```

Expected: only the two files.

---

### Task 6: List family

**Files:**
- Modify: `C:\Users\IKA\Zendaya\backend\zendaya_assistant_features.py`
- Modify: `C:\Users\IKA\Zendaya\backend\tests\test_assistant_features.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_assistant_features.py`:

```python
# ─── List family ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("utterance, expected_list, expected_item", [
    ("add milk to shopping list",            "shopping", "milk"),
    ("add eggs to the shopping list",        "shopping", "eggs"),
    ("put bread on my groceries list",       "groceries", "bread"),
    ("add finish the report to my todo list", "todo", "finish the report"),
])
def test_parse_list_add_explicit(utterance, expected_list, expected_item, tmp_data_dir):
    import zendaya_assistant_features as aaf
    result = aaf.parse_list_command(utterance)
    assert result is not None
    action, payload = result
    assert action == "add"
    assert payload["list_name"] == expected_list
    assert payload["item"].strip() == expected_item


@pytest.mark.parametrize("utterance, expected_list", [
    ("add milk",                "shopping"),    # grocery keyword
    ("add eggs",                "shopping"),
    ("add finish the report",   "todo"),
    ("add call mom",            "todo"),
])
def test_parse_list_add_default(utterance, expected_list, tmp_data_dir):
    import zendaya_assistant_features as aaf
    action, payload = aaf.parse_list_command(utterance)
    assert action == "add"
    assert payload["list_name"] == expected_list


@pytest.mark.parametrize("utterance, expected_list", [
    ("what's on my shopping list", "shopping"),
    ("read my todo list",          "todo"),
    ("show me my packing list",    "packing"),
])
def test_parse_list_read(utterance, expected_list, tmp_data_dir):
    import zendaya_assistant_features as aaf
    action, payload = aaf.parse_list_command(utterance)
    assert action == "read"
    assert payload["list_name"] == expected_list


def test_parse_list_remove(tmp_data_dir):
    import zendaya_assistant_features as aaf
    action, payload = aaf.parse_list_command("remove milk from shopping list")
    assert action == "remove"
    assert payload["list_name"] == "shopping"
    assert payload["item"] == "milk"


def test_parse_list_mark_done(tmp_data_dir):
    import zendaya_assistant_features as aaf
    action, payload = aaf.parse_list_command("mark milk done on shopping list")
    assert action == "mark_done"
    assert payload["list_name"] == "shopping"
    assert payload["item"] == "milk"


def test_parse_list_negative(tmp_data_dir):
    import zendaya_assistant_features as aaf
    assert aaf.parse_list_command("set alarm 7am") is None
    assert aaf.parse_list_command("what time is it") is None
    assert aaf.parse_list_command("") is None


def test_list_handler_round_trip(tmp_data_dir):
    import zendaya_assistant_features as aaf
    aaf._handle_list("add", {"list_name": "shopping", "item": "milk"})
    aaf._handle_list("add", {"list_name": "shopping", "item": "eggs"})

    reply = aaf._handle_list("read", {"list_name": "shopping"})
    assert "milk" in reply and "eggs" in reply

    aaf._handle_list("mark_done", {"list_name": "shopping", "item": "milk"})
    state = aaf._load_state()
    items = state["lists"]["shopping"]
    milk = next(i for i in items if i["text"] == "milk")
    assert milk["done"] is True

    aaf._handle_list("remove", {"list_name": "shopping", "item": "eggs"})
    state = aaf._load_state()
    texts = [i["text"] for i in state["lists"]["shopping"]]
    assert "eggs" not in texts


def test_list_remove_nonexistent_item_is_friendly(tmp_data_dir):
    import zendaya_assistant_features as aaf
    aaf._handle_list("add", {"list_name": "shopping", "item": "milk"})
    reply = aaf._handle_list("remove", {"list_name": "shopping", "item": "spaghetti"})
    assert "couldn't find" in reply.lower() or "not on" in reply.lower()


def test_list_read_empty_list_is_friendly(tmp_data_dir):
    import zendaya_assistant_features as aaf
    reply = aaf._handle_list("read", {"list_name": "nonexistent"})
    assert "empty" in reply.lower() or "no items" in reply.lower()
```

- [ ] **Step 2: Run — confirm failures**

```powershell
pytest backend/tests/test_assistant_features.py -v -k "list"
```

Expected: ~22 failures (one per `parametrize` case + the round-trip and friendly-error tests), all `AttributeError` for `parse_list_command` or `_handle_list`.

- [ ] **Step 3: Implement**

Append to `backend/zendaya_assistant_features.py`:

```python


# ─── List parser ───────────────────────────────────────────────────────────

_LIST_ADD_RE = _re.compile(
    r"^(?:add|put)\s+(.+?)(?:\s+(?:to|on|in)\s+(?:my\s+|the\s+)?(.+?))?$",
    _re.IGNORECASE,
)
_LIST_READ_RE = _re.compile(
    r"^(?:what(?:'s|\s+is)?\s+on\s+my\s+|read\s+(?:me\s+)?(?:my\s+)?|show\s+(?:me\s+)?(?:my\s+)?)(.+?)(?:\s+list)?$",
    _re.IGNORECASE,
)
_LIST_REMOVE_RE = _re.compile(
    r"^(?:remove|take|delete)\s+(.+?)\s+(?:from|off)\s+(?:my\s+|the\s+)?(.+?)(?:\s+list)?$",
    _re.IGNORECASE,
)
_LIST_MARK_RE = _re.compile(
    r"^(?:mark|check)\s+(?:off\s+)?(.+?)\s+(?:done|complete|off)(?:\s+(?:on|from)\s+(?:my\s+|the\s+)?(.+?)(?:\s+list)?)?$",
    _re.IGNORECASE,
)

_GROCERY_KEYWORDS = {
    "milk", "eggs", "bread", "butter", "cheese", "flour", "sugar", "rice",
    "pasta", "tomato", "tomatoes", "onion", "onions", "garlic", "potato",
    "potatoes", "apple", "apples", "banana", "bananas", "coffee", "tea",
    "yogurt", "chicken", "beef", "fish", "salad", "lettuce",
}


def _normalise_list_name(name: Optional[str]) -> str:
    if not name:
        return ""
    n = name.strip().lower()
    if n.endswith(" list"):
        n = n[: -len(" list")].strip()
    return n


def _default_list_for_item(item: str) -> str:
    first_word = item.strip().split()[0].lower() if item.strip() else ""
    return "shopping" if first_word in _GROCERY_KEYWORDS else "todo"


def parse_list_command(text: str) -> Optional[tuple[str, dict]]:
    if not text:
        return None
    t = text.strip()

    # Mark-done has the most-specific shape — try it first.
    m = _LIST_MARK_RE.match(t)
    if m:
        item = m.group(1).strip()
        list_name = _normalise_list_name(m.group(2)) or _default_list_for_item(item)
        return ("mark_done", {"list_name": list_name, "item": item})

    m = _LIST_REMOVE_RE.match(t)
    if m:
        return ("remove", {"list_name": _normalise_list_name(m.group(2)), "item": m.group(1).strip()})

    m = _LIST_READ_RE.match(t)
    if m:
        return ("read", {"list_name": _normalise_list_name(m.group(1))})

    m = _LIST_ADD_RE.match(t)
    if m:
        item = m.group(1).strip()
        list_name = _normalise_list_name(m.group(2)) if m.group(2) else _default_list_for_item(item)
        # Guard against the parser swallowing "add milk to shopping" with item="milk to shopping" if regex backtracks.
        if not item:
            return None
        return ("add", {"list_name": list_name, "item": item})

    return None


# ─── List handler ──────────────────────────────────────────────────────────

def _handle_list(action: str, payload: dict) -> str:
    state = _load_state()
    list_name = payload.get("list_name", "todo")
    lists = state["lists"]

    if action == "add":
        item_text = payload["item"]
        items = lists.setdefault(list_name, [])
        items.append({"text": item_text, "done": False, "added_at": time.time()})
        _save_state(state)
        return f"Added '{item_text}' to {list_name}."

    if action == "read":
        items = lists.get(list_name, [])
        if not items:
            return f"Your {list_name} list is empty."
        lines = []
        for it in items:
            mark = "✓" if it.get("done") else "•"
            lines.append(f"  {mark} {it['text']}")
        return f"Your {list_name} list:\n" + "\n".join(lines)

    if action == "remove":
        items = lists.get(list_name, [])
        target = payload["item"].lower()
        for i, it in enumerate(items):
            if it["text"].lower() == target:
                items.pop(i)
                _save_state(state)
                return f"Removed '{it['text']}' from {list_name}."
        return f"I couldn't find '{payload['item']}' on the {list_name} list."

    if action == "mark_done":
        items = lists.get(list_name, [])
        target = payload["item"].lower()
        for it in items:
            if it["text"].lower() == target:
                it["done"] = True
                _save_state(state)
                return f"Marked '{it['text']}' done on {list_name}."
        return f"I couldn't find '{payload['item']}' on the {list_name} list."

    return f"Unknown list action: {action}."
```

- [ ] **Step 4: Run — confirm pass**

```powershell
pytest backend/tests/test_assistant_features.py -v -k "list"
```

Expected: all list tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/zendaya_assistant_features.py backend/tests/test_assistant_features.py
git -c commit.gpgsign=false commit -m "feat(aaf): list parser (add/read/remove/mark-done) + default-list heuristic"
git show --stat HEAD
```

Expected: only the two files.

---

### Task 7: Scheduler lifecycle, fire callbacks, `try_handle` dispatcher

**Files:**
- Modify: `C:\Users\IKA\Zendaya\backend\zendaya_assistant_features.py`
- Modify: `C:\Users\IKA\Zendaya\backend\tests\test_assistant_features.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_assistant_features.py`:

```python
# ─── Scheduler + dispatcher ────────────────────────────────────────────────


def test_start_prunes_expired_one_shots(tmp_data_dir):
    import zendaya_assistant_features as aaf
    state = aaf._load_state()
    past = (datetime.now() - timedelta(hours=1)).isoformat()
    state["alarms"].append({
        "id": 1, "kind": "one_shot", "trigger": past,
        "label": "stale", "created_at": 0.0, "active": True,
    })
    state["next_alarm_id"] = 2
    aaf._save_state(state)

    aaf.start()
    reloaded = aaf._load_state()
    assert reloaded["alarms"][0]["active"] is False
    aaf.stop()


def test_start_keeps_active_cron_alarms(tmp_data_dir):
    import zendaya_assistant_features as aaf
    state = aaf._load_state()
    state["alarms"].append({
        "id": 1, "kind": "cron", "trigger": "0 7 * * 1-5",
        "label": "weekday 7am", "created_at": time.time(), "active": True,
    })
    state["next_alarm_id"] = 2
    aaf._save_state(state)

    aaf.start()
    reloaded = aaf._load_state()
    assert reloaded["alarms"][0]["active"] is True
    aaf.stop()


def test_fire_alarm_calls_notifier_and_deactivates_one_shot(tmp_data_dir, fake_notifier):
    import zendaya_assistant_features as aaf
    speak, toast, calls = fake_notifier
    aaf.set_notifier(speak, toast)

    state = aaf._load_state()
    rec = {
        "id": 1, "kind": "one_shot", "trigger": datetime.now().isoformat(),
        "label": "test alarm", "created_at": time.time(), "active": True,
    }
    state["alarms"].append(rec)
    aaf._save_state(state)

    aaf._fire_alarm(rec["id"])

    assert len(calls["speak"]) == 1 and "test alarm" in calls["speak"][0]
    assert len(calls["toast"]) == 1
    reloaded = aaf._load_state()
    assert reloaded["alarms"][0]["active"] is False


def test_fire_cron_alarm_keeps_active(tmp_data_dir, fake_notifier):
    import zendaya_assistant_features as aaf
    speak, toast, calls = fake_notifier
    aaf.set_notifier(speak, toast)

    state = aaf._load_state()
    state["alarms"].append({
        "id": 1, "kind": "cron", "trigger": "0 7 * * 1-5",
        "label": "cron", "created_at": time.time(), "active": True,
    })
    aaf._save_state(state)

    aaf._fire_alarm(1)

    reloaded = aaf._load_state()
    assert reloaded["alarms"][0]["active"] is True


def test_fire_timer_deactivates(tmp_data_dir, fake_notifier):
    import zendaya_assistant_features as aaf
    speak, toast, calls = fake_notifier
    aaf.set_notifier(speak, toast)

    state = aaf._load_state()
    state["timers"].append({
        "id": 1, "fire_at": datetime.now().isoformat(),
        "duration_seconds": 60, "label": "1-min timer",
        "created_at": time.time(), "active": True,
    })
    aaf._save_state(state)

    aaf._fire_timer(1)

    reloaded = aaf._load_state()
    assert reloaded["timers"][0]["active"] is False
    assert "1-min timer" in calls["speak"][0]


def test_fire_handles_missing_record_silently(tmp_data_dir, fake_notifier):
    """If a record was cancelled mid-flight, the fire callback must not crash."""
    import zendaya_assistant_features as aaf
    speak, toast, _ = fake_notifier
    aaf.set_notifier(speak, toast)
    # No record with id=999 — should be a no-op, not an exception.
    aaf._fire_alarm(999)
    aaf._fire_timer(999)


def test_pruning_drops_old_completed_list_items(tmp_data_dir):
    import zendaya_assistant_features as aaf
    old_ts = time.time() - (31 * 24 * 3600)
    state = aaf._load_state()
    state["lists"]["shopping"] = [
        {"text": "old done milk", "done": True, "added_at": old_ts},
        {"text": "fresh active eggs", "done": False, "added_at": time.time()},
    ]
    aaf._save_state(state)

    aaf.start()
    reloaded = aaf._load_state()
    texts = [i["text"] for i in reloaded["lists"]["shopping"]]
    assert "old done milk" not in texts
    assert "fresh active eggs" in texts
    aaf.stop()


def test_try_handle_routes_to_correct_family(tmp_data_dir, fake_notifier):
    import zendaya_assistant_features as aaf
    speak, toast, _ = fake_notifier
    aaf.set_notifier(speak, toast)

    assert aaf.try_handle("set timer for 5 minutes") is not None
    assert aaf.try_handle("set an alarm for 7am tomorrow") is not None
    assert aaf.try_handle("add milk to shopping") is not None
    assert aaf.try_handle("what time is it") is None
```

- [ ] **Step 2: Run — confirm failures**

```powershell
pytest backend/tests/test_assistant_features.py -v -k "fire or start_ or pruning or try_handle"
```

Expected: 8 failures, mostly `AttributeError: module ... has no attribute '_fire_alarm'` (and similar) or assertions that fail because the skeleton `try_handle` always returns None.

- [ ] **Step 3: Implement — scheduler + fire callbacks + dispatcher**

Append to `backend/zendaya_assistant_features.py`:

```python


# ─── Scheduler + fire callbacks ────────────────────────────────────────────

_scheduler = None  # type: Optional[Any]
_LIST_ITEM_TTL_SECONDS = 30 * 24 * 3600
_RECORD_TTL_SECONDS = 30 * 24 * 3600


def _get_scheduler():
    """Lazy import + init so test environments without apscheduler still load."""
    global _scheduler
    if _scheduler is None:
        from apscheduler.schedulers.background import BackgroundScheduler
        _scheduler = BackgroundScheduler()
    return _scheduler


def _prune(state: dict) -> None:
    """Drop stale records and completed list items in-place."""
    now = time.time()
    # Stale completed list items.
    for name, items in list(state["lists"].items()):
        state["lists"][name] = [
            it for it in items
            if not (it.get("done") and (now - it.get("added_at", now) > _LIST_ITEM_TTL_SECONDS))
        ]
    # Inactive alarms / timers older than the TTL.
    state["alarms"] = [
        a for a in state["alarms"]
        if a.get("active") or (now - a.get("created_at", now) <= _RECORD_TTL_SECONDS)
    ]
    state["timers"] = [
        t for t in state["timers"]
        if t.get("active") or (now - t.get("created_at", now) <= _RECORD_TTL_SECONDS)
    ]


def _expire_one_shots(state: dict) -> None:
    """Mark active one-shot alarms/timers with past trigger times as inactive."""
    now = datetime.now()
    for a in state["alarms"]:
        if not a.get("active") or a.get("kind") != "one_shot":
            continue
        try:
            if datetime.fromisoformat(a["trigger"]) < now:
                a["active"] = False
                print(f"(aaf: missed one-shot alarm '{a.get('label')}' at {a['trigger']})")
        except Exception:
            pass
    for t in state["timers"]:
        if not t.get("active"):
            continue
        try:
            if datetime.fromisoformat(t["fire_at"]) < now:
                t["active"] = False
                print(f"(aaf: missed timer '{t.get('label')}' at {t['fire_at']})")
        except Exception:
            pass


def _arm_record(rec_kind: str, rec: dict) -> None:
    """Add the appropriate APScheduler job for an active record."""
    try:
        if rec_kind == "alarm":
            if rec["kind"] == "one_shot":
                from apscheduler.triggers.date import DateTrigger
                trigger = DateTrigger(run_date=datetime.fromisoformat(rec["trigger"]))
            else:
                from apscheduler.triggers.cron import CronTrigger
                trigger = CronTrigger.from_crontab(rec["trigger"])
            _get_scheduler().add_job(
                _fire_alarm, trigger=trigger, args=[rec["id"]], id=f"alarm_{rec['id']}", replace_existing=True,
            )
        else:  # timer
            from apscheduler.triggers.date import DateTrigger
            trigger = DateTrigger(run_date=datetime.fromisoformat(rec["fire_at"]))
            _get_scheduler().add_job(
                _fire_timer, trigger=trigger, args=[rec["id"]], id=f"timer_{rec['id']}", replace_existing=True,
            )
    except Exception as e:
        print(f"(aaf: failed to arm {rec_kind} {rec.get('id')}: {e})")


def _fire_alarm(alarm_id: int) -> None:
    """APScheduler fires this on the scheduler thread. Speak + toast + persist state."""
    try:
        state = _load_state()
        rec = next((a for a in state["alarms"] if a["id"] == alarm_id), None)
        if rec is None:
            return
        label = rec.get("label", "alarm")
        _notify(f"Alarm — {label}", "Zendaya alarm", label)
        if rec.get("kind") == "one_shot":
            rec["active"] = False
            _save_state(state)
    except Exception as e:
        print(f"(aaf: _fire_alarm({alarm_id}) crashed: {e})")


def _fire_timer(timer_id: int) -> None:
    try:
        state = _load_state()
        rec = next((t for t in state["timers"] if t["id"] == timer_id), None)
        if rec is None:
            return
        label = rec.get("label", "timer")
        _notify(f"Timer — {label}", "Zendaya timer", label)
        rec["active"] = False
        _save_state(state)
    except Exception as e:
        print(f"(aaf: _fire_timer({timer_id}) crashed: {e})")


def _notify(spoken: str, toast_title: str, toast_body: str) -> None:
    try:
        if _speak_fn is not None:
            _speak_fn(spoken)
    except Exception as e:
        print(f"(aaf: speak failed: {e})")
    try:
        if _toast_fn is not None:
            _toast_fn(toast_title, toast_body, 10)
    except Exception as e:
        print(f"(aaf: toast failed: {e})")


# ─── Replace skeletons with real impls ─────────────────────────────────────

def start() -> None:
    state = _load_state()
    _expire_one_shots(state)
    _prune(state)

    # Compute one-shot timer fire times by their fire_at field; rearm timers that haven't
    # had their fire_at set yet (the timer parser stores datetime.now().isoformat() as a
    # placeholder; here we adjust to created_at + duration_seconds for any record where
    # fire_at <= created_at).
    for t in state["timers"]:
        try:
            fa = datetime.fromisoformat(t["fire_at"])
            ca = datetime.fromtimestamp(t.get("created_at", time.time()))
            if fa <= ca:
                t["fire_at"] = (ca + timedelta(seconds=int(t["duration_seconds"]))).isoformat()
        except Exception:
            pass

    _save_state(state)

    try:
        sch = _get_scheduler()
        if not sch.running:
            sch.start()
    except Exception as e:
        print(f"(aaf: scheduler start failed; alarms/timers will not fire: {e})")
        return

    for a in state["alarms"]:
        if a.get("active"):
            _arm_record("alarm", a)
    for t in state["timers"]:
        if t.get("active"):
            _arm_record("timer", t)


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None


def try_handle(text: str) -> Optional[str]:
    if not text:
        return None
    parsed = parse_timer_command(text)
    if parsed is not None:
        return _handle_timer(*parsed)
    parsed = parse_alarm_command(text)
    if parsed is not None:
        return _handle_alarm(*parsed)
    parsed = parse_list_command(text)
    if parsed is not None:
        return _handle_list(*parsed)
    return None
```

Also: import `timedelta` from `datetime` if it isn't there yet. Add to the top of the file alongside the existing `from datetime import datetime`:

```python
from datetime import datetime, timedelta
```

Use the `Edit` tool to replace `from datetime import datetime` with `from datetime import datetime, timedelta`.

Also: replace the skeleton `start`, `stop`, `try_handle` definitions from Task 3 with the real ones above. (The Edit above will leave the skeletons in place; you must delete them. Find the skeleton block matching `def start() -> None:\n    """Skeleton — populated by Task 7. Touches state so corruption is caught early."""\n    state = _load_state()\n    _save_state(state)\n\n\ndef stop() -> None:\n    """Skeleton — populated by Task 7."""\n    pass\n\n\ndef try_handle(text: str) -> Optional[str]:\n    """Skeleton — populated by Task 7. Returns None so the LLM path takes over."""\n    return None` and delete it.)

- [ ] **Step 4: Run — confirm pass**

```powershell
pytest backend/tests/test_assistant_features.py -v
```

Expected: ALL tests across all five `-k` groups pass (timer, alarm, list, fire/start/pruning/try_handle, plus the original Task 3 skeleton tests).

If `test_start_keeps_active_cron_alarms` fails because the cron job tries to run immediately and the test calls `aaf.stop()` before assertions, the BackgroundScheduler may need to be paused, not stopped, or the test moved to a separate process. Diagnose by reading the actual error.

- [ ] **Step 5: Commit**

```powershell
git add backend/zendaya_assistant_features.py backend/tests/test_assistant_features.py
git -c commit.gpgsign=false commit -m "feat(aaf): scheduler lifecycle, fire callbacks, try_handle dispatcher"
git show --stat HEAD
```

Expected: only the two files.

---

### Task 8: Wire AAF into `zendaya.py`

**Files:**
- Modify: `C:\Users\IKA\Zendaya\backend\zendaya.py` (5 touch points)

**Heads-up:** `zendaya.py` has a pre-existing `M` modification in the working tree. Your `git add backend/zendaya.py` will stage BOTH that pre-existing diff AND your wiring change. Per the user's "leave the uncommitted diff alone" rule, this commit MUST contain only your wiring changes. Read the Task 2 commit splitting precedent (or the gitignore-split incident from the Graphify-setup session). Do NOT proceed with `git add backend/zendaya.py` until you've confirmed how to isolate just your changes. The mechanism:

1. Save a copy of the current working-tree `zendaya.py` to a temp file (preserves the user's pre-existing diff).
2. Run `git checkout -- backend/zendaya.py` to revert to HEAD's version.
3. Apply ONLY your wiring edits on top of HEAD's version.
4. `git add backend/zendaya.py && git commit ...`.
5. Restore the working tree from the temp file (user's pre-existing diff returns, your wiring is now committed and the diff against HEAD shrinks accordingly).

- [ ] **Step 1: Locate the dispatch hook target**

Use the `Grep` tool: `pattern: "^def handle_user_command", path: "backend/zendaya.py", output_mode: "content", -n: true`.

Report the function's line number. Read the function (about ~50 lines starting at that line). Identify the latest point in the function where existing regex-based parsers are tried but BEFORE the LLM (`gemini_reply` or similar) is called. That is where the AAF dispatch hook goes.

If you cannot find such a clean insertion point, report BLOCKED with the function's full body — the controller needs to advise.

- [ ] **Step 2: Save current working-tree zendaya.py to a temp**

```powershell
Copy-Item backend\zendaya.py $env:TEMP\zendaya.py.worktree.bak
```

- [ ] **Step 3: Revert to HEAD**

```powershell
git checkout -- backend/zendaya.py
```

Now `backend/zendaya.py` matches the last committed version. Working tree is clean for this file.

- [ ] **Step 4: Apply the 5 wiring edits**

Edit 1 — guarded import. Find the existing pattern from the top-of-file imports section (look for `try:\n    import zendaya_coder` — match the same style). Add immediately after it using the `Edit` tool:

- old_string: (find the exact `try:\n    import zendaya_coder` block end — read the file to confirm and adapt)

For instance, if the existing block ends with:
```python
except Exception as _e:
    print(f"[zendaya] coder module unavailable: {_e}")
    zendaya_coder = None
    _CODER_READY = False
```
- new_string:
```python
except Exception as _e:
    print(f"[zendaya] coder module unavailable: {_e}")
    zendaya_coder = None
    _CODER_READY = False

try:
    import zendaya_assistant_features as aaf
    _AAF_READY = True
except Exception as _e:
    print(f"[zendaya] assistant_features unavailable: {_e}")
    aaf = None
    _AAF_READY = False
```

Edit 2 — `set_notifier` + `start` in `__main__`. In the `if __name__ == "__main__":` block at line ~3658, after `start_alerts()` (`zendaya_alerts.start_alerts()` per the file's existing layout) and before the `try: import zendaya_proactive` block, add:

```python
    if _AAF_READY:
        try:
            _voice_id = MEM.get("current_voice_id")
            def _aaf_speak(text: str) -> None:
                speak_async(text, _voice_id)
            _aaf_toast = None
            try:
                _toaster_local = ToastNotifier()
                def _aaf_toast(title: str, body: str, duration: int = 10) -> None:
                    _toaster_local.show_toast(title, body, duration=duration, threaded=True)
            except Exception:
                _aaf_toast = None
            aaf.set_notifier(_aaf_speak, _aaf_toast)
            aaf.start()
            print("⏰ Assistant features (alarms / timers / lists) active.")
        except Exception as _aaf_err:
            print(f"(Assistant features unavailable: {_aaf_err})")
```

If `ToastNotifier` isn't a name available at the call site, fall back to `from win10toast import ToastNotifier` inside the inner try block. Confirm the symbol exists by grepping zendaya.py for `ToastNotifier`.

Edit 3 — dispatch hook inside `handle_user_command`. Insert at the insertion point identified in Step 1:

```python
        # AAF — alarms / timers / lists. Returns None if no parser matched.
        if _AAF_READY:
            _aaf_reply = aaf.try_handle(user_text)
            if _aaf_reply is not None:
                send_response(_aaf_reply)
                return
```

Use `send_response` as written above only if Step 1's reading confirms `send_response(text)` is the right call to surface a reply in `handle_user_command`'s context. If `handle_user_command` instead returns a string for an outer loop to send, change `send_response(_aaf_reply); return` to `return _aaf_reply`. Adapt to match the existing pattern shown by other parsers in that function.

Edit 4 — `aaf.stop()` in shutdown. In `main()`'s `finally:` block (line ~3655), insert before the existing `print("System shutdown complete.")`:

```python
        if _AAF_READY:
            try:
                aaf.stop()
            except Exception:
                pass
```

(That's all four code edits — the spec describes them as "5 touch points" because the `set_notifier` + `start` are conceptually two calls living in the same `__main__` block.)

- [ ] **Step 5: Sanity-check the file compiles**

```powershell
python -c "import ast; ast.parse(open(r'C:\Users\IKA\Zendaya\backend\zendaya.py', encoding='utf-8').read()); print('ok')"
```

Expected: `ok`. If it raises a `SyntaxError`, fix and re-run before staging anything.

- [ ] **Step 6: Stage and commit ONLY zendaya.py**

```powershell
git add backend/zendaya.py
git diff --cached backend/zendaya.py | Select-Object -First 100
```

Read the cached diff. Confirm it contains ONLY your 5 wiring touch points (the guarded import block, the `set_notifier`/`start` block in `__main__`, the dispatch hook in `handle_user_command`, and the `aaf.stop()` in shutdown). If anything else appears, run `git reset HEAD backend/zendaya.py` and re-do Step 3-4 — something went wrong.

```powershell
git -c commit.gpgsign=false commit -m "feat(zendaya): wire assistant-features (alarms / timers / lists) into command dispatch"
git show --stat HEAD
```

Expected: ONLY `backend/zendaya.py` in the commit.

- [ ] **Step 7: Restore the user's pre-existing diff to working tree**

```powershell
Copy-Item $env:TEMP\zendaya.py.worktree.bak backend\zendaya.py -Force
git status --short backend/zendaya.py
git diff backend/zendaya.py | Select-Object -First 30
```

Expected: `backend/zendaya.py` shows as `M`, and the diff is now SMALLER than the original pre-existing diff (because some of those changes are now committed). The user's pre-existing modifications that weren't part of your wiring should still be there.

If for some reason the working tree is now in a worse state than before (e.g. the temp file overwrites your wiring), abort and report — do not push further.

- [ ] **Step 8: Run the tests one final time to make sure the wiring didn't break AAF**

```powershell
pytest backend/tests/test_assistant_features.py -v
```

Expected: all tests still pass.

---

### Task 9: Manual verification + final report

**Files:** None (read-only verification + run the assistant).

- [ ] **Step 1: Confirm all commits landed**

```powershell
git log 88fae4c..HEAD --oneline
```

Expected commits (in order, plus the four from the Graphify-setup session preceding):
- `deps: add croniter and dateparser for assistant-features wire-up`
- `test: scaffold backend/tests/ with tmp data-dir and fake-notifier fixtures`
- `feat(aaf): module skeleton with persistent state and corruption recovery`
- `feat(aaf): timer parser + handler (create/list/cancel)`
- `feat(aaf): alarm parser (one-shot via dateparser + cron table) + handler`
- `feat(aaf): list parser (add/read/remove/mark-done) + default-list heuristic`
- `feat(aaf): scheduler lifecycle, fire callbacks, try_handle dispatcher`
- `feat(zendaya): wire assistant-features (alarms / timers / lists) into command dispatch`

- [ ] **Step 2: Full test suite green**

```powershell
pytest backend/tests/test_assistant_features.py -v
```

Expected: all ~45 tests pass.

- [ ] **Step 3: Manual verification — the user runs this, not the implementer subagent**

Print the following checklist for the user, with a one-line status line at the top stating that automated work is done and only manual verification remains:

```
Manual checks (user runs):

[ ] 1. Start the assistant, say "set timer for 60 seconds", wait. Expect: spoken + toast at the 60s mark, "Timer — 1-second timer" or similar.
[ ] 2. Say "set an alarm for [now + 2 minutes]". Wait. Expect: spoken + toast fires.
[ ] 3. Say "alarm every minute". Wait two minutes — two fires. Say "list my alarms", then "cancel alarm 1". Wait another minute — no fire.
[ ] 4. Say "add milk to shopping". Say "what's on my shopping list". Expect: "milk" appears.
[ ] 5. Say "add finish report to my todo list". Say "mark finish report done". Expect: ✓ next to "finish report".
[ ] 6. Say "remove milk from shopping list". Expect: removed.
[ ] 7. Restart Zendaya. Say "list my alarms" — your cron alarm from step 3 (if not cancelled) should still be there.
[ ] 8. Manually corrupt zendaya_data/aaf_state.json (overwrite with "{not json"). Restart. Expect: boot succeeds, file renamed aaf_state.bad-<ts>.json, fresh empty state.

Run this list end-to-end and confirm each passes. If anything fails or surprises you, capture the exact utterance + observed behavior and report back.
```

- [ ] **Step 4: Status line**

Output ONE short line: `Assistant features wire-up complete: AAF module + N tests, wired into zendaya.py. Manual verification pending.` Replace `N` with the actual test count.

No commit.

---

## Out of scope (for follow-up plans)

- LLM fallback for unparseable utterances (would cost Gemini tokens; user opted out for v1).
- Named alarms/timers (UX friction during creation; can add later without data-model breakage).
- Snooze for alarms.
- Recurring lists / scheduled list reminders.
- Cross-list operations ("move milk from shopping to groceries").
- Integration with `zendaya_google_apis` (Google Calendar / Tasks).
- Touching the 4,400-line uncommitted diff — user explicit: leave it alone.
- Deleting `backend/zendaya_voice_listener.py` (stale v1 duplicate flagged by the scout — separate cleanup task).
