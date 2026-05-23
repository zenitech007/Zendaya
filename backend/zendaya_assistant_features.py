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


# ─── Alarm parser ──────────────────────────────────────────────────────────

_ALARM_PREFIX_RE = _re.compile(
    r"^(?:set\s+(?:an?\s+)?alarm|alarm|wake me up|remind me)\b",
    _re.IGNORECASE,
)

# Hand-curated phrase → cron table. Order matters: longer patterns first.
_DAY_TO_CRON = {
    "sunday": "0", "monday": "1", "tuesday": "2", "wednesday": "3",
    "thursday": "4", "friday": "5", "saturday": "6",
}


def _try_cron(text: str) -> Optional[str]:
    """Return a cron string if text matches a known recurring phrasing, else None."""
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
    # Strip leading "for " / "at " — dateparser chokes on them.
    cleaned = _re.sub(r"^(?:for|at)\s+", "", remainder, flags=_re.IGNORECASE)
    dt = dateparser.parse(
        cleaned,
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
