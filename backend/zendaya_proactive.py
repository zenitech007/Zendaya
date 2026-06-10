"""
zendaya_proactive — ambient check-in scheduler.

Runs on a background daemon thread and lets Zendaya speak first when:
  1. Time-of-day reaches a notable slot (morning, lunch, evening, night) —
     once per slot per day.
  2. The emotion engine flips into 'alert' or 'stressed' from a calmer
     mood — system pressure is climbing.
  3. The user has been silent for a long time (idle nudge).
  4. Git working copy under ~/Zendaya picks up uncommitted changes that
     have been sitting for >30min (commit-nudge — once per day).
  5. A calendar event from zendaya_google_apis is starting within 10min.
  6. Files in ~/Zendaya were edited but the user has been idle for a while
     (quiet-progress check-in — fires once per idle window).

A global cooldown keeps triggers from stacking.

Public API:
    note_user_activity()        # call from handle_user_command
    start(send_response, analyze_emotion, mem)
    stop()
"""

from __future__ import annotations

import datetime
import os
import random
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional
from datetime import datetime as _dt

# --- State -------------------------------------------------------------
_THREAD: Optional[threading.Thread] = None
_STOP = threading.Event()
_LAST_USER_TS: float = time.time()
_LAST_PROACTIVE_TS: float = 0.0
_FIRED_TODAY: set[str] = set()
_LAST_MOOD: str = "neutral"
_LAST_GIT_CHECK: float = 0.0
_LAST_CAL_CHECK: float = 0.0
_CAL_NOTIFIED: set[str] = set()        # event ids we've already nudged about

# --- Tunables ----------------------------------------------------------
IDLE_MIN_S = 30 * 60           # 30 min of silence before idle nudge
QUIET_PROGRESS_MIN_S = 20 * 60 # 20 min idle but files moving → check-in
COOLDOWN_S = 15 * 60           # min gap between proactive turns
POLL_S = 30                    # check loop cadence
GIT_CHECK_EVERY_S = 10 * 60    # cap on git status work
CAL_CHECK_EVERY_S = 5 * 60     # cap on Google Calendar polling
CAL_LOOKAHEAD_S = 10 * 60      # warn this far before an event
ZENDAYA_ROOT = Path.home() / "Zendaya"


def note_user_activity() -> None:
    """Reset the idle clock — call whenever the user types or speaks."""
    global _LAST_USER_TS
    _LAST_USER_TS = time.time()


def _today_tag(slot: str) -> str:
    return f"{slot}-{datetime.date.today().isoformat()}"


def _time_of_day_slot() -> Optional[str]:
    h = datetime.datetime.now().hour
    if 7 <= h < 10:
        return "morning"
    if 12 <= h < 14:
        return "lunch"
    if 17 <= h < 19:
        return "evening"
    if 22 <= h < 24:
        return "night"
    return None


def _idle_message(mood: str) -> str:
    pool = {
        "soothing": [
            "Still up? I'm here when you need me.",
            "Quiet evening — want me to wind down with you?",
        ],
        "playful": [
            "You ghosting me? I have jokes.",
            "I've been polishing my circuits. What now?",
        ],
        "focused": [
            "Locked in for a while — water break?",
            "Anything to add to the queue?",
        ],
        "calm": [
            "It's been quiet. Anything brewing?",
            "I'm here whenever you need me.",
        ],
    }.get(
        mood,
        [
            "I'm still here whenever you need me.",
            "Anything I can pick up while you're heads-down?",
        ],
    )
    return random.choice(pool)


def _time_of_day_message(slot: str, user_name: Optional[str]) -> str:
    name = f", {user_name}" if user_name else ""
    return {
        "morning": f"Morning{name}. What's the priority today?",
        "lunch": "Lunch window — want me to pause anything for you?",
        "evening": "Heads up — evening is settling in. Anything to wrap?",
        "night": "Late shift, I see. Want me to dim things down?",
    }[slot]


def _mood_message(mood: str) -> tuple[str, str]:
    """Return (message, pending_action_key) for the mood alert."""
    if mood == "stressed":
        return (
            "System's running hot — CPU and memory pressure are climbing. "
            "Want me to flag the heaviest processes?",
            "flag_heavy_processes",
        )
    return (
        "Heads up — multiple subsystems are flagging. Want me to check what's failing?",
        "check_subsystems",
    )


def _git_dirty_summary() -> Optional[tuple[int, int]]:
    """Return (changed_files, oldest_modify_age_s) for ZENDAYA_ROOT, or None."""
    if not (ZENDAYA_ROOT / ".git").is_dir():
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(ZENDAYA_ROOT), "status", "--porcelain"],
            capture_output=True, text=True, timeout=8,
        )
        if out.returncode != 0:
            return None
        lines = [ln for ln in out.stdout.splitlines() if ln.strip()]
        if not lines:
            return None
        # Oldest mtime among the listed files — proxy for "how long has this been pending".
        oldest = 0.0
        now = time.time()
        for ln in lines:
            path = ln[3:].strip().split(" -> ")[-1]
            full = ZENDAYA_ROOT / path
            try:
                m = full.stat().st_mtime
                age = now - m
                if age > oldest:
                    oldest = age
            except OSError:
                continue
        return len(lines), int(oldest)
    except Exception:
        return None


def _upcoming_calendar_event() -> Optional[dict]:
    """Return the next upcoming event within CAL_LOOKAHEAD_S, or None."""
    try:
        import zendaya_google_apis as _g
    except Exception:
        return None
    fn = getattr(_g, "next_calendar_event", None) or getattr(_g, "get_upcoming_events", None)
    if fn is None:
        return None
    try:
        events = fn() if fn.__name__ != "next_calendar_event" else [fn()]
    except Exception:
        return None
    if not events:
        return None
    now = datetime.datetime.now().astimezone()
    for ev in events:
        if not isinstance(ev, dict):
            continue
        start_iso = ev.get("start") or ev.get("start_time") or (ev.get("start", {}) if isinstance(ev.get("start"), dict) else None)
        if isinstance(start_iso, dict):
            start_iso = start_iso.get("dateTime") or start_iso.get("date")
        if not start_iso:
            continue
        try:
            start_dt = datetime.datetime.fromisoformat(str(start_iso).replace("Z", "+00:00"))
            if start_dt.tzinfo is None:
                start_dt = start_dt.astimezone()
        except Exception:
            continue
        delta_s = (start_dt - now).total_seconds()
        if 0 < delta_s <= CAL_LOOKAHEAD_S:
            ev = dict(ev)
            ev["_seconds_until"] = int(delta_s)
            return ev
    return None


def _files_recently_modified(since_s: float) -> int:
    """Count text files in ZENDAYA_ROOT modified in the last `since_s` seconds. Fast: stops at 5."""
    if not ZENDAYA_ROOT.is_dir():
        return 0
    cutoff = time.time() - since_s
    skip_dirs = {"__pycache__", "node_modules", ".git", ".venv", "venv", "dist", "build"}
    text_exts = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".md", ".css", ".html"}
    count = 0
    try:
        for dirpath, dirnames, filenames in os.walk(ZENDAYA_ROOT):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
            for name in filenames:
                if os.path.splitext(name)[1].lower() not in text_exts:
                    continue
                try:
                    if os.path.getmtime(os.path.join(dirpath, name)) > cutoff:
                        count += 1
                        if count >= 5:
                            return count
                except OSError:
                    continue
    except Exception:
        pass
    return count


def _git_message(changed: int, oldest_min: int) -> str:
    return (
        f"You've got {changed} uncommitted change{'s' if changed != 1 else ''} in Zendaya — "
        f"oldest is {oldest_min} min old. Want me to commit them?"
    )


def _calendar_message(ev: dict) -> str:
    title = ev.get("summary") or ev.get("title") or "an event"
    mins = max(1, ev["_seconds_until"] // 60)
    return f"Heads up — '{title}' starts in {mins} min."


def _quiet_progress_message() -> str:
    return random.choice([
        "I see edits flowing but it's been quiet on your side. Want me to summarize what's changed?",
        "Files are moving but you haven't said a word. Stuck on anything?",
        "Lots of edits, no chatter. Want me to run a quick syntax check on the recent stuff?",
    ])


def _set_pending(
    mem: dict,
    message: str,
    action: str,
    send_response: Callable[[str], None],
) -> None:
    """Store a proactive follow-up action and record the message in convo memory."""
    mem["pending_proactive"] = {"action": action, "message": message}
    # Also inject into conversation history so Gemini has context if the
    # user's reply falls through to the LLM.
    mem.setdefault("convo", []).append(
        {"role": "Zendaya", "text": message, "ts": _dt.now().isoformat()}
    )
    send_response(message)


def _loop(
    send_response: Callable[[str], None],
    analyze_emotion: Callable[[], str],
    mem: dict,
) -> None:
    global _LAST_PROACTIVE_TS, _LAST_USER_TS, _LAST_MOOD, _LAST_GIT_CHECK, _LAST_CAL_CHECK

    while not _STOP.wait(POLL_S):
        if not mem.get("proactive_enabled", True):
            continue

        now = time.time()
        if (now - _LAST_PROACTIVE_TS) < COOLDOWN_S:
            continue

        # 1) Time of day — once per slot per day.
        slot = _time_of_day_slot()
        if slot:
            tag = _today_tag(slot)
            if tag not in _FIRED_TODAY:
                _FIRED_TODAY.add(tag)
                _LAST_PROACTIVE_TS = now
                try:
                    send_response(_time_of_day_message(slot, mem.get("user_name")))
                except Exception as e:
                    print(f"(proactive: time-of-day send failed: {e})")
                continue

        # Resolve current mood (used by 2 and 3).
        try:
            mood = analyze_emotion()
        except Exception:
            mood = _LAST_MOOD

        # 2) Mood/system shift — only when transitioning into an alert state.
        if mood in ("alert", "stressed") and _LAST_MOOD not in ("alert", "stressed"):
            _LAST_PROACTIVE_TS = now
            _LAST_MOOD = mood
            try:
                msg, action = _mood_message(mood)
                _set_pending(mem, msg, action, send_response)
            except Exception as e:
                print(f"(proactive: mood send failed: {e})")
            continue
        _LAST_MOOD = mood

        # 3) Idle nudge.
        if (now - _LAST_USER_TS) > IDLE_MIN_S:
            _LAST_PROACTIVE_TS = now
            _LAST_USER_TS = now  # reset so we don't double-fire next tick
            try:
                send_response(_idle_message(mood))
            except Exception as e:
                print(f"(proactive: idle send failed: {e})")
            continue

        # 4) Calendar — upcoming event in the next CAL_LOOKAHEAD_S.
        if (now - _LAST_CAL_CHECK) > CAL_CHECK_EVERY_S:
            _LAST_CAL_CHECK = now
            ev = _upcoming_calendar_event()
            if ev is not None:
                ev_id = str(ev.get("id") or ev.get("summary") or ev.get("_seconds_until"))
                if ev_id not in _CAL_NOTIFIED:
                    _CAL_NOTIFIED.add(ev_id)
                    _LAST_PROACTIVE_TS = now
                    try:
                        send_response(_calendar_message(ev))
                    except Exception as e:
                        print(f"(proactive: calendar send failed: {e})")
                    continue

        # 5) Git — uncommitted changes sitting >30 min, once per day.
        if (now - _LAST_GIT_CHECK) > GIT_CHECK_EVERY_S:
            _LAST_GIT_CHECK = now
            git_tag = f"git-{datetime.date.today().isoformat()}"
            if git_tag not in _FIRED_TODAY:
                summary = _git_dirty_summary()
                if summary is not None:
                    changed, oldest_s = summary
                    if oldest_s > 30 * 60:
                        _FIRED_TODAY.add(git_tag)
                        _LAST_PROACTIVE_TS = now
                        try:
                            msg = _git_message(changed, oldest_s // 60)
                            _set_pending(mem, msg, "git_commit", send_response)
                        except Exception as e:
                            print(f"(proactive: git send failed: {e})")
                        continue

        # 6) Quiet progress — files moving while user is silent.
        idle_for = now - _LAST_USER_TS
        if idle_for > QUIET_PROGRESS_MIN_S and idle_for < IDLE_MIN_S:
            qtag = f"quiet-{int(_LAST_USER_TS)}"
            if qtag not in _FIRED_TODAY:
                if _files_recently_modified(QUIET_PROGRESS_MIN_S) >= 2:
                    _FIRED_TODAY.add(qtag)
                    _LAST_PROACTIVE_TS = now
                    try:
                        msg = _quiet_progress_message()
                        _set_pending(mem, msg, "summarize_changes", send_response)
                    except Exception as e:
                        print(f"(proactive: quiet-progress send failed: {e})")


def start(
    send_response: Callable[[str], None],
    analyze_emotion: Callable[[], str],
    mem: dict,
) -> Optional[threading.Thread]:
    """Spawn the daemon thread. No-op if already running."""
    global _THREAD
    if _THREAD is not None and _THREAD.is_alive():
        return _THREAD
    _STOP.clear()
    _THREAD = threading.Thread(
        target=_loop,
        args=(send_response, analyze_emotion, mem),
        daemon=True,
        name="zendaya-proactive",
    )
    _THREAD.start()
    return _THREAD


def stop() -> None:
    _STOP.set()
