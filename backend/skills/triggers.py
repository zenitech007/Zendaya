"""
skills.triggers — user-teachable triggers ("when X, do Y").

Skills are persistent rules stored as JSON. A daemon thread polls trigger
sources (window watcher, wall clock) and fires the skill's action — which is
just a natural-language command Zendaya executes via handle_user_command.

Public API:
    add_skill(trigger, action, name=None) -> str
    remove_skill(name_or_id) -> str
    list_skills() -> list[dict]
    parse_skill_command(user_text) -> Optional[dict]   # for the parser branch
    start() -> None                                     # spawn watcher thread
    stop() -> None

Trigger types:
    {"type": "window_focus", "match": "vscode"}      # case-insensitive substring on app name or title
    {"type": "time_at",      "hhmm": "09:00"}        # fires once per day at HH:MM local
    {"type": "wake_word"}                            # placeholder; reserved
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


_BACKEND_DIR = Path(__file__).resolve().parent
_LOGS_DIR = _BACKEND_DIR.parent / "zendaya_logs"
_LOGS_DIR.mkdir(parents=True, exist_ok=True)
_SKILLS_FILE = _LOGS_DIR / "skills.json"

_LOCK = threading.Lock()
_THREAD: Optional[threading.Thread] = None
_STOP = threading.Event()
_SKILLS: List[Dict[str, Any]] = []
# Per-skill cooldown so a "when I open X" doesn't refire every poll
_LAST_FIRED: Dict[str, float] = {}
_FOCUS_COOLDOWN_S = 60.0
# For time_at — track last day fired so it runs once per day max
_TIME_FIRED_DAY: Dict[str, str] = {}


def _z():
    import zendaya as _zmod
    return _zmod


def _now() -> float:
    return time.time()


def _short_id() -> str:
    return uuid.uuid4().hex[:6]


def _load() -> None:
    global _SKILLS
    try:
        if _SKILLS_FILE.is_file():
            data = json.loads(_SKILLS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                _SKILLS = data
                return
    except Exception as e:
        print(f"[skills] couldn't load {_SKILLS_FILE}: {e}")
    _SKILLS = []


def _save() -> None:
    try:
        _SKILLS_FILE.write_text(json.dumps(_SKILLS, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[skills] couldn't save {_SKILLS_FILE}: {e}")


_load()


# ---------------------------------------------------------------------------
# Public mutators
# ---------------------------------------------------------------------------

def add_skill(trigger: Dict[str, Any], action: str, name: Optional[str] = None) -> str:
    if not isinstance(trigger, dict) or "type" not in trigger:
        return "Skill needs a trigger {'type': 'window_focus' | 'time_at' | ..., ...}."
    if not action or not action.strip():
        return "Skill needs an action (the natural-language command to run)."
    skill = {
        "id": _short_id(),
        "name": (name or "").strip() or None,
        "trigger": trigger,
        "action": action.strip(),
        "created": _now(),
        "fire_count": 0,
        "enabled": True,
    }
    with _LOCK:
        _SKILLS.append(skill)
        _save()
    label = skill["name"] or skill["id"]
    return f"Skill saved as [{label}]. When {_describe_trigger(trigger)}, I'll: {action.strip()}"


def remove_skill(name_or_id: str) -> str:
    needle = (name_or_id or "").strip().lower()
    if not needle:
        return "Which skill should I remove?"
    with _LOCK:
        before = len(_SKILLS)
        _SKILLS[:] = [s for s in _SKILLS if (s.get("id") != needle and (s.get("name") or "").lower() != needle)]
        removed = before - len(_SKILLS)
        if removed:
            _save()
    return f"Removed {removed} skill(s)." if removed else f"No skill matched '{name_or_id}'."


def toggle_skill(name_or_id: str, enabled: bool) -> str:
    needle = (name_or_id or "").strip().lower()
    with _LOCK:
        for s in _SKILLS:
            if s.get("id") == needle or (s.get("name") or "").lower() == needle:
                s["enabled"] = bool(enabled)
                _save()
                return f"Skill [{s.get('name') or s['id']}] {'enabled' if enabled else 'disabled'}."
    return f"No skill matched '{name_or_id}'."


def list_skills() -> List[Dict[str, Any]]:
    with _LOCK:
        return [dict(s) for s in _SKILLS]


def render_list() -> str:
    items = list_skills()
    if not items:
        return "No skills yet. Teach me one: 'when I open <app>, <do something>'."
    lines = ["Skills:"]
    for s in items:
        label = s.get("name") or s["id"]
        flag = "" if s.get("enabled", True) else " (disabled)"
        lines.append(f"  [{label}]{flag} when {_describe_trigger(s['trigger'])} → {s['action']}")
    return "\n".join(lines)


def _describe_trigger(t: Dict[str, Any]) -> str:
    kind = t.get("type")
    if kind == "window_focus":
        return f"I focus a window matching '{t.get('match', '?')}'"
    if kind == "time_at":
        return f"the clock hits {t.get('hhmm', '??:??')}"
    return f"trigger '{kind}'"


# ---------------------------------------------------------------------------
# Parser — natural-language → trigger + action
# ---------------------------------------------------------------------------

_WHEN_OPEN = re.compile(
    r"\bwhen\s+(?:i\s+)?(?:open|launch|start|focus|switch\s+to)\s+(?P<app>[\w\s\.\-]+?)\s*[,:]?\s+(?P<action>.+)$",
    re.IGNORECASE,
)
_AT_TIME = re.compile(
    r"\b(?:every\s+day\s+)?at\s+(?P<hh>\d{1,2}):(?P<mm>\d{2})\s*[,:]?\s+(?P<action>.+)$",
    re.IGNORECASE,
)
_LIST_RE = re.compile(r"^(?:list\s+(?:my\s+)?skills?|show\s+skills?|what\s+skills?\s+do\s+i\s+have)\b", re.IGNORECASE)
_REMOVE_RE = re.compile(r"^(?:remove|delete|forget)\s+skill\s+(?P<name>[\w-]+)\s*$", re.IGNORECASE)
_DISABLE_RE = re.compile(r"^(?:disable|pause)\s+skill\s+(?P<name>[\w-]+)\s*$", re.IGNORECASE)
_ENABLE_RE = re.compile(r"^(?:enable|resume)\s+skill\s+(?P<name>[\w-]+)\s*$", re.IGNORECASE)


def parse_skill_command(user_text: str) -> Optional[Dict[str, Any]]:
    """Return a routing dict consumed by zendaya.py, or None if no skill command matched."""
    if not user_text:
        return None
    t = user_text.strip()

    if _LIST_RE.match(t):
        return {"op": "list"}

    m = _REMOVE_RE.match(t)
    if m:
        return {"op": "remove", "name": m.group("name")}

    m = _DISABLE_RE.match(t)
    if m:
        return {"op": "disable", "name": m.group("name")}

    m = _ENABLE_RE.match(t)
    if m:
        return {"op": "enable", "name": m.group("name")}

    m = _WHEN_OPEN.search(t)
    if m:
        app = m.group("app").strip().rstrip(",.").strip()
        action = m.group("action").strip()
        return {"op": "add", "trigger": {"type": "window_focus", "match": app}, "action": action}

    m = _AT_TIME.search(t)
    if m:
        hh = int(m.group("hh"))
        mm = int(m.group("mm"))
        if 0 <= hh < 24 and 0 <= mm < 60:
            return {
                "op": "add",
                "trigger": {"type": "time_at", "hhmm": f"{hh:02d}:{mm:02d}"},
                "action": m.group("action").strip(),
            }

    return None


def handle_skill_command(parsed: Dict[str, Any]) -> str:
    op = parsed.get("op")
    if op == "list":
        return render_list()
    if op == "remove":
        return remove_skill(parsed.get("name") or "")
    if op == "disable":
        return toggle_skill(parsed.get("name") or "", False)
    if op == "enable":
        return toggle_skill(parsed.get("name") or "", True)
    if op == "add":
        return add_skill(parsed["trigger"], parsed["action"])
    return f"Unknown skill op: {op}"


# ---------------------------------------------------------------------------
# Trigger watcher
# ---------------------------------------------------------------------------

def _fire(skill: Dict[str, Any]) -> None:
    """Dispatch a skill's action by feeding it back through the main command pipeline."""
    sid = skill["id"]
    _LAST_FIRED[sid] = _now()
    skill["fire_count"] = int(skill.get("fire_count", 0)) + 1
    _save()
    label = skill.get("name") or sid
    try:
        z = _z()
        z.send_response(f"⚡ Skill [{label}] firing: {skill['action']}")
        z.handle_user_command(skill["action"])
    except Exception as e:
        try:
            _z().send_response(f"Skill [{label}] failed: {e}")
        except Exception:
            print(f"[skills] fire failed: {e}")


def _check_window_focus(skill: Dict[str, Any]) -> bool:
    sid = skill["id"]
    if _now() - _LAST_FIRED.get(sid, 0) < _FOCUS_COOLDOWN_S:
        return False
    needle = (skill["trigger"].get("match") or "").strip().lower()
    if not needle:
        return False
    try:
        import perception.windows as _ww
        snap = _ww.get_snapshot() or {}
    except Exception:
        return False
    title = (snap.get("title") or "").lower()
    proc = (snap.get("process") or snap.get("app") or "").lower()
    # Only fire on a fresh focus event (not while the window has been focused for a while).
    fresh = bool(snap.get("fresh"))
    if not fresh:
        return False
    return needle in title or needle in proc


def _check_time_at(skill: Dict[str, Any]) -> bool:
    sid = skill["id"]
    target = (skill["trigger"].get("hhmm") or "").strip()
    if not re.match(r"^\d{2}:\d{2}$", target):
        return False
    now = datetime.now()
    today_key = now.strftime("%Y-%m-%d")
    if _TIME_FIRED_DAY.get(sid) == today_key:
        return False
    cur = now.strftime("%H:%M")
    # Allow a 1-minute matching window so we don't miss the exact second.
    if cur == target:
        _TIME_FIRED_DAY[sid] = today_key
        return True
    return False


_CHECKERS = {
    "window_focus": _check_window_focus,
    "time_at": _check_time_at,
}


def _loop() -> None:
    while not _STOP.is_set():
        try:
            with _LOCK:
                snapshot = list(_SKILLS)
            for skill in snapshot:
                if not skill.get("enabled", True):
                    continue
                checker = _CHECKERS.get(skill["trigger"].get("type"))
                if checker is None:
                    continue
                try:
                    if checker(skill):
                        _fire(skill)
                except Exception as e:
                    print(f"[skills] checker '{skill['trigger'].get('type')}' crashed: {e}")
        except Exception as e:
            print(f"[skills] loop error: {e}")
        _STOP.wait(2.0)  # 2 s tick — coarse but plenty for window focus + clock minute


def start() -> Optional[threading.Thread]:
    global _THREAD
    if _THREAD is not None and _THREAD.is_alive():
        return _THREAD
    _STOP.clear()
    _THREAD = threading.Thread(target=_loop, daemon=True, name="zendaya-skills")
    _THREAD.start()
    return _THREAD


def stop() -> None:
    _STOP.set()
