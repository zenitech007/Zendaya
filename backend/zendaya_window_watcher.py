"""
zendaya_window_watcher.py — Watches the OS for foreground-window changes
and feeds them into the state server so the Godot avatar can perch, walk,
sleep, and react to whatever the user is doing.

Windows-only. Uses win32gui + pygetwindow (already required by the rest
of the backend). The watcher runs on a daemon thread at ~4 Hz; it never
blocks the brain process.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

try:
    import win32gui
    import win32con
    import pywintypes
    _WIN32 = True
except ImportError:
    _WIN32 = False

try:
    import pygetwindow as gw
    _PYGETWINDOW = True
except ImportError:
    _PYGETWINDOW = False


# Skip our own avatar window so Zendaya doesn't try to perch on herself.
SELF_TITLE = "Zendaya Pet"

# Don't fire "saw a new app" reactions more than once per N seconds for
# the same title — switching back and forth between two windows shouldn't
# spam quips.
RE_REACT_COOLDOWN = 30.0

# Tick period in seconds.
TICK = 0.25


# ── Shared state ────────────────────────────────────────
_LOCK = threading.Lock()
_SNAPSHOT: dict = {
    "hwnd": 0,
    "title": "",
    "rect": [0, 0, 0, 0],   # left, top, right, bottom
    "state": "none",        # normal | maximized | minimized | none
    "ts": 0.0,
}
_EVENTS: list[dict] = []     # drained by /window route
_LAST_SEEN_TITLE: dict[str, float] = {}
_logged_error_once = False


def _now() -> float:
    return time.time()


def _read_foreground() -> Optional[dict]:
    if not _WIN32:
        return None
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        title = win32gui.GetWindowText(hwnd) or ""
        if not title.strip():
            return None
        if title == SELF_TITLE:
            return None
        rect = win32gui.GetWindowRect(hwnd)
        if win32gui.IsIconic(hwnd):
            wstate = "minimized"
        elif win32gui.IsZoomed(hwnd):
            wstate = "maximized"
        else:
            wstate = "normal"
        return {
            "hwnd": int(hwnd),
            "title": title,
            "rect": [int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])],
            "state": wstate,
            "ts": _now(),
        }
    except pywintypes.error:
        return None
    except Exception:
        return None


def _push_event(kind: str, **fields) -> None:
    evt = {"kind": kind, "ts": _now()}
    evt.update(fields)
    _EVENTS.append(evt)
    # Keep the queue bounded — Godot drains it 4× a second, but a long
    # disconnect shouldn't memory-leak.
    if len(_EVENTS) > 32:
        del _EVENTS[: len(_EVENTS) - 32]


def _diff_and_emit(prev: dict, curr: dict) -> None:
    if prev.get("title") != curr.get("title"):
        last_seen = _LAST_SEEN_TITLE.get(curr["title"], 0.0)
        is_fresh = (_now() - last_seen) > RE_REACT_COOLDOWN
        _push_event("focus_changed", title=curr["title"], fresh=is_fresh)
        _LAST_SEEN_TITLE[curr["title"]] = _now()
    elif prev.get("state") != curr.get("state"):
        _push_event("window_state_changed",
                    title=curr["title"], state=curr["state"])


def _tick_loop() -> None:
    global _logged_error_once
    prev: dict = {}
    while True:
        try:
            curr = _read_foreground()
            if curr is not None:
                with _LOCK:
                    if prev:
                        _diff_and_emit(prev, curr)
                    _SNAPSHOT.update(curr)
                prev = curr
        except Exception as e:
            if not _logged_error_once:
                print(f"[window_watcher] tick error: {e}")
                _logged_error_once = True
        time.sleep(TICK)


# ── Public API ──────────────────────────────────────────
def start(state_server=None) -> threading.Thread:
    """Spawn the watcher on a daemon thread. Returns the thread handle.

    The state_server arg is accepted for symmetry with state_server.start();
    the watcher writes via the module-level functions below, which the
    state_server reads on demand from the /window route.
    """
    if not _WIN32:
        print("[window_watcher] win32gui unavailable — watcher disabled.")
        # Return a dummy thread so callers don't need to special-case None.
        t = threading.Thread(target=lambda: None, daemon=True)
        t.start()
        return t
    t = threading.Thread(target=_tick_loop, daemon=True,
                         name="zendaya-window-watcher")
    t.start()
    return t


def get_snapshot() -> dict:
    with _LOCK:
        return dict(_SNAPSHOT)


def pop_events() -> list[dict]:
    with _LOCK:
        out = list(_EVENTS)
        _EVENTS.clear()
        return out


def close_window_by_title(title: str) -> str:
    """Close any window whose title contains `title`. Returns a status string."""
    if not _PYGETWINDOW:
        return "Window control requires pygetwindow."
    try:
        matches = gw.getWindowsWithTitle(title)
    except Exception as e:
        return f"Lookup failed: {e}"
    if not matches:
        return f"No window found matching '{title}'."
    target = matches[0]
    try:
        target.close()
        return f"Closed: {target.title}"
    except Exception:
        # pygetwindow can raise on some apps; fall back to PostMessage.
        if not _WIN32:
            return f"Could not close '{target.title}'."
        try:
            hwnd = target._hWnd  # pygetwindow exposes the HWND
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            return f"Closed: {target.title}"
        except Exception as e:
            return f"Could not close '{target.title}': {e}"
