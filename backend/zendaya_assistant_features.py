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
from typing import Callable, Optional

import zendaya_data_store


# ─── Module state ──────────────────────────────────────────────────────────

_STATE_LOCK = threading.Lock()
_STATE_FILE = "aaf_state"  # data_store appends .json

# Notifier callbacks injected by zendaya.py
_speak_fn: Optional[Callable[[str], None]] = None
_toast_fn: Optional[Callable[[str, str, int], None]] = None

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
