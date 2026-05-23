# Assistant Features Wire-up (Alarms + Timers + Lists) — Design

**Date:** 2026-05-23
**Status:** Approved (pending spec review)
**Author:** Claude Opus 4.7 (with zenitech007)
**Successor to:** [2026-05-23-graphify-setup-design.md](2026-05-23-graphify-setup-design.md)

## Goal

Wire up the three voice-assistant feature families that the existing `backend/zendaya_data_store.py` is designed to back but that `backend/zendaya.py` does not currently expose: **alarms**, **timers**, and **lists**. Today `data_store` is used only for routines; the rest of its intended surface is unused. After this work, the user can say things like "set an alarm for 7am tomorrow", "10-minute timer", "add milk to the shopping list", and the assistant actually does them.

## Non-goals

- Replacing or rewriting `zendaya_data_store.py` (the storage layer is already correct).
- Touching the existing routines feature.
- Adding an LLM fallback for unparseable utterances (deferred — keeps token cost at zero for v1).
- Naming alarms / timers — v1 is index-based cancellation only.
- Cross-device sync, network-served alarms, or any feature requiring a backend service.
- Touching the large pre-existing uncommitted diff the user has explicitly opted to leave alone.

## Context

`backend/zendaya.py` is a Gemini 2.5 Flash personal assistant. It already follows a regex-parser-first / dispatch pattern (`parse_voice_switch`, `parse_mode_switch`, etc.) before falling through to the LLM. The wired modules `zendaya_journal`, `zendaya_skills`, `zendaya_face_modes`, etc., all use the same pattern: small parser, small handler, no LLM call.

`backend/zendaya_data_store.py` already has atomic JSON persistence with `.bad-<timestamp>` corruption handling (visible in `zendaya_logs/`). It is currently called only from the routines code path.

APScheduler is already a project dependency (used by `zendaya_alerts.py`). `win10toast` is already imported at the top of `zendaya.py` with a graceful-degrade pattern.

User decisions captured during brainstorming:
- All three families in one spec.
- Alarms support full cron-style recurrence in addition to one-shots.
- Lists are multi-named (`shopping`, `todo`, `groceries`, user-created) — not a single global list.
- Lists v1 supports four operations: add / read / remove / mark-done.
- Cancellation is index-based only (no naming).
- Fire UX is **spoken + Windows toast**.

## Architecture

**One new module:** `backend/zendaya_assistant_features.py` (henceforth **AAF**).

| Component | Lives in |
|---|---|
| Parsers (alarm / timer / list) | AAF |
| Handlers (set / list / cancel / fire / add / read / remove / mark-done) | AAF |
| APScheduler `BackgroundScheduler` instance + lifecycle | AAF (module-scope) |
| Persistence (read/write `alarms`, `timers`, `lists`) | `zendaya_data_store` (existing, untouched) |
| Notifier injection (`speak_fn`, `toast_fn`) | AAF accepts via `set_notifier`; injected from `zendaya.py` |
| Dispatch hook (`try_handle(text)`) | AAF exposes; called from `zendaya.py`'s command-routing path |

**`zendaya.py` changes — minimal:**
- One guarded import block (matches `zendaya_coder` / `zendaya_vector_memory` pattern).
- One call: `aaf.set_notifier(speak_async, _toast_notifier)` in `__main__`.
- One call: `aaf.start()` after `set_notifier`.
- One dispatch hook: in the command-routing path, after existing regex parsers, before falling through to Gemini, call `reply = aaf.try_handle(user_text)`; if non-None, send `reply` and skip the LLM call.
- One call: `aaf.stop()` in shutdown.

**New runtime dependencies (to add to `pyproject.toml`):**
- `croniter` — cron-string validation.
- `dateparser` — heuristic time-utterance parsing ("7am tomorrow", "in 30 minutes").

(APScheduler is already a transitive dep; verify before assuming.)

## Data model (persisted via `zendaya_data_store`)

Three top-level keys.

### `alarms` — list of records

```python
{
    "id": int,                       # monotonic, used for index-based cancel
    "kind": "one_shot" | "cron",
    "trigger": str,                  # ISO8601 datetime for one_shot, cron string for cron
    "label": str,                    # short echo of original utterance
    "created_at": float,             # unix timestamp
    "active": bool,                  # False after one-shot fires or cancel
}
```

### `timers` — list of records

```python
{
    "id": int,
    "fire_at": str,                  # ISO8601 absolute datetime (timer = one-shot in disguise)
    "duration_seconds": int,         # original duration, for labels like "10-minute timer"
    "label": str,
    "created_at": float,
    "active": bool,
}
```

### `lists` — dict, keyed by normalised list name

```python
{
    "shopping": [
        {"text": "milk", "done": False, "added_at": 1234567890.0},
        {"text": "eggs", "done": True,  "added_at": 1234567900.0},
    ],
    "todo": [...],
    # user-created keys allowed
}
```

### Defaults & normalisation

- No-list-specified utterances default by keyword heuristic:
  - Grocery-ish keywords (`milk`, `eggs`, `bread`, …) → `shopping`.
  - Action-verb-ish (`finish`, `email`, `call`, …) → `todo`.
  - Otherwise → `todo` (safest default).
- List names lowercased; trailing `" list"` stripped (`"shopping list"` → `"shopping"`).
- IDs monotonic per kind (alarms and timers each have their own counter), persisted with the records, survive restart.

### Storage size guards

On every `start()`:
- Drop list items where `done=True` and `added_at` is > 30 days old.
- Drop alarm/timer records where `active=False` and either `created_at` or last-fire time is > 30 days old.
- Save the pruned state back via `data_store.save`.

## Parser strategy

Each `parse_*_command(text)` returns `(action, payload)` or `None`. **No LLM calls in any parser.**

Three-stage fallback inside each parser:

1. **Regex fast-path** for common phrasings. Examples:
   - Alarms: `^(?:set\s+(?:an?\s+)?alarm|wake me up|remind me) (?:for|at|in)?\s*(.+?)(?:\s+(?:every|on|tomorrow|today)\s+(.+))?$`
   - Timers: `^(?:set\s+(?:a\s+)?timer|timer)\s+(?:for|of)?\s*(\d+)\s*(seconds?|minutes?|hours?|min|sec|hr)s?$`
   - Lists: parallel patterns for `add` / `remove` / `read` / `mark done`.

2. **Heuristic time/date parse** via `dateparser` for the time-bearing arguments. Handles "7am", "tomorrow at 6:30", "in 30 minutes", "next Sunday 9pm". Returns a `datetime` or `None`.

3. **Cron validation** via `croniter` when the user utterance contains explicit recurrence keywords (`every`, `weekdays`, `weekends`, day names). A small hand-curated phrase→cron table covers the top ~20 patterns:
   - "every weekday at 7am" → `0 7 * * 1-5`
   - "every Sunday at 9pm" → `0 21 * * 0`
   - "every 15 minutes" → `*/15 * * * *`
   - …and so on.
   Anything not in the table returns `None` and the user gets a fallback message.

**Public API the dispatcher sees:**

```python
def try_handle(text: str) -> Optional[str]:
    """Try each parser; if one matches, run handler and return reply string.
    Returns None if no parser matched — caller falls through to Gemini."""
```

## Scheduler lifecycle & fire path

### `aaf.start()`

1. Walk `alarms` and `timers`; any `active=True` one-shot with `trigger`/`fire_at` in the past → mark `active=False` (log a one-line note). User is not notified about missed alarms in v1.
2. Prune (per "Storage size guards" above).
3. Start the `BackgroundScheduler`.
4. Re-arm every `active=True` record: `DateTrigger` for one-shots and timers, `CronTrigger` for cron alarms. Job ID = `f"alarm_{id}"` / `f"timer_{id}"`.
5. Save pruned state back via `data_store.save`.

### Fire callback (`_fire_alarm(record)` / `_fire_timer(record)`)

1. `_speak(f"Alarm — {label}")` via the injected `speak_fn`.
2. `_toast("Zendaya alarm", label, duration=10)` via the injected `toast_fn`.
3. For one-shot alarms and all timers: mark `active=False`, save. APScheduler auto-removes one-shot jobs after firing.
4. For cron alarms: stays `active=True`. APScheduler keeps the job.

### Cancellation

`cancel_alarm(idx)` / `cancel_timer(idx)`:
1. Map user-facing index (the number from the last `list_alarms` response) → stable `id`.
2. `scheduler.remove_job(...)` — swallow `JobLookupError`.
3. `active=False`, save.

### `aaf.stop()`

1. `scheduler.shutdown(wait=False)`.
2. Records remain in `data_store`; next `start()` re-arms them.

### Notifier hook

`aaf.set_notifier(speak_fn, toast_fn)` — called once from `zendaya.py:__main__`. Stored at module scope. If `toast_fn` is `None` (because `win10toast` import failed at `zendaya.py` top), the fire path skips toast silently.

### Concurrency

`BackgroundScheduler` fires in its own thread. Fire-path saves race with dispatch-path saves. `zendaya_data_store` already does atomic JSON writes, but we add a `threading.Lock` around the read-modify-write block in AAF to avoid lost updates.

## Error handling

### Parser-level (graceful — never throws to the user)

- Unparseable time/cron → return a friendly explanation (`"I couldn't parse that schedule. Try 'alarm at 7am tomorrow' or 'every weekday at 7am'."`), do NOT create the record.
- Cancel by out-of-range index → `"You only have 2 active alarms. Try 'list my alarms' to see them."`
- Add to a list with an empty item text → `"What should I add?"`

### Scheduler / dep level (graceful degrade)

- `apscheduler` import failure → AAF's `try_handle` returns `"Scheduler unavailable — alarms and timers can't be set right now. Lists still work."` for alarm/timer parsers; list family still functions.
- `croniter` / `dateparser` import failure → same per-family graceful degrade; missing dep logged once at startup.
- Fire callback exception (TTS hung, toast crashed) → logged, swallowed. Never raised into APScheduler's worker (would kill the scheduler).
- Race on cancel-while-firing → `JobLookupError` caught and ignored.

### Data-store level

- Corrupt `alarms.json` / `timers.json` / `lists.json` on boot → `zendaya_data_store`'s existing `.bad-<timestamp>` rename pattern is reused. AAF logs, renames the file, starts with an empty record set, and surfaces a one-line warning in the next assistant response.

### Import in `zendaya.py`

Matches the existing `zendaya_coder` / `zendaya_vector_memory` pattern:

```python
try:
    import zendaya_assistant_features as aaf
    _AAF_READY = True
except Exception as _e:
    print(f"[zendaya] assistant_features unavailable: {_e}")
    aaf = None
    _AAF_READY = False
```

If `_AAF_READY` is False the dispatch hook is skipped entirely. Zero impact on the rest of zendaya.

## Testing strategy

Today the repo has no visible test suite (no `tests/` dir, no `pytest` config in `pyproject.toml`). This work introduces a small one, scoped to the new module only.

**New file:** `backend/tests/test_assistant_features.py`. Uses `pytest`.

### Unit (no scheduler running)

1. **Parsers** — table-driven `(utterance, expected (action, payload))` pairs covering each family, plus negative cases ("what time is it" → `None`) and edge cases ("alarm in zero minutes" → friendly error). Spot-check the phrase→cron table.
2. **Data model round-trip** — using a fixture `data_store` pointed at `tmp_path`, write/read alarms / timers / lists, confirm IDs are monotonic and survive reload.
3. **List default-name heuristic** — "add milk" → goes to `shopping`; "add finish the report" → goes to `todo`.
4. **Stale one-shot pruning on boot** — set `fire_at` in the past, call `start()`, confirm `active=False` after.
5. **30-day pruning** — old completed list items and inactive alarms drop on boot.

### Fire-path (mocked notifier)

- Call `_fire_alarm(record)` / `_fire_timer(record)` with mocked `speak_fn` and `toast_fn`. Assert they're called with expected args and the record's `active` flag transitions correctly for one-shots vs cron.

### Smoke

- Import AAF, call `try_handle("set timer for 1 second")`, assert it returns a confirmation string and an active timer exists in `data_store`.

### Out of scope

- The real APScheduler firing on schedule (APScheduler's job, not ours).
- End-to-end `zendaya.py` integration tests.

### Manual verification checklist

Run after implementation. Lives at the bottom of the spec, not in CI.

- One-shot alarm 1 min in the future → fires, speaks, toasts.
- 10-second timer → fires.
- Cron alarm `every minute` → fires twice, then cancel → no third fire.
- Restart Zendaya mid-flight → alarm re-arms; expired one-shots don't fire.
- Add to 3 different list names → all persist; read each back.
- Manually corrupt `alarms.json` → boot succeeds, file renamed `.bad-<ts>`, user told once.

## Done criteria

- `backend/zendaya_assistant_features.py` exists with the public surface above.
- `pyproject.toml` lists `croniter` and `dateparser` as deps.
- `backend/zendaya.py` has the four touch points (import, `set_notifier`, `start`, dispatch hook, `stop`) wired with graceful-degrade.
- `backend/tests/test_assistant_features.py` exists; `pytest backend/tests/` passes.
- Manual verification checklist passes end-to-end on the user's machine.
- No regression in existing zendaya behavior (routines, journal, skills, etc. still work). Verified by running the assistant interactively after wire-up.

## Risks and unknowns

| Risk | Mitigation |
|---|---|
| APScheduler not actually installed (only assumed because `zendaya_alerts` uses it) | Plan's first task verifies `python -c "import apscheduler"` before any code change; if missing, add to `pyproject.toml` explicitly |
| `dateparser` is slow on first import (loads timezone tables) | Import lazily inside the parser; profile if startup time matters |
| `win10toast` notifications don't fire reliably across Windows 11 versions | Existing zendaya.py already has the same dep with graceful degrade; we inherit whatever reliability it has — not making it worse |
| Phrase→cron table doesn't cover the user's actual utterances | Real usage will reveal gaps. The friendly fallback message tells the user how to phrase things; expand the table as patterns surface |
| TTS hangs the fire thread | Fire callback wraps `speak_fn` in a try/except + timeout (if `speak_fn` is async, we don't await it on the scheduler thread) |
| Adding new deps without the user noticing | Plan's commit message for the `pyproject.toml` change calls out `croniter` and `dateparser` explicitly |

## Deferred / future work

- LLM fallback for unparseable utterances (would cost Gemini tokens; user explicitly opted out for v1).
- Named alarms/timers (UX friction during creation; can add later without data-model breakage by populating the existing `label` field as the cancellation key).
- Recurring lists / scheduled list reminders ("every Saturday morning, read me the shopping list").
- Snooze support for alarms.
- Cross-list operations ("move milk from shopping to groceries").
- Voice-driven list-name creation ("create a new list called packing").
- Integrating with Google Calendar / Google Tasks via the existing `zendaya_google_apis` module.

## Scope boundary with prior spec

This spec is a successor to [the Graphify setup spec](2026-05-23-graphify-setup-design.md), which made Claude Code sessions on this repo cheaper. That spec does not affect runtime behavior. This spec adds three user-visible features. The two are independent and don't share any code; `/graphify` is a tool for me, AAF is a tool for the user.
