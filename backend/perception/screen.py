"""
perception.screen — passive captioning of the active window.

Polls the focused-window title at low cost; only when the title CHANGES does
it grab a screenshot and ask Gemini to caption it. Keeps the last N captions
in a ring so gemini_reply can splice them in as ambient context.

Cost-aware design:
  - Polling at TITLE_POLL_S (5s) is free (no Gemini calls).
  - Captioning fires only on title change AND respects MIN_CAPTION_GAP_S so
    rapid app-switching can't burn API quota.
  - Each caption is one Gemini call with a downscaled JPEG (~maxdim 768px).

Public API:
    start() -> threading.Thread | None
    stop() -> None
    is_running() -> bool
    set_enabled(flag: bool) -> None      # toggle without killing the thread
    recent_captions(n=3) -> list[str]    # for gemini_reply context
    last_caption() -> Optional[dict]     # newest caption with metadata
    parse_screen_command(text) -> Optional[dict]
    handle_screen_command(parsed) -> str
"""

from __future__ import annotations

import io
import re
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional


try:
    import mss
    _MSS_READY = True
except Exception as e:
    _MSS_READY = False
    _MSS_ERR = str(e)

try:
    from PIL import Image
    _PIL_READY = True
except Exception:
    _PIL_READY = False

try:
    import win32gui
    _WIN32_READY = True
except Exception:
    _WIN32_READY = False


# --- Tunables ---
TITLE_POLL_S = 5.0
MIN_CAPTION_GAP_S = 30.0       # never caption more than ~once every 30s
MAX_CAPTIONS = 10
MAX_IMG_DIM = 768              # downscale before sending to Gemini
JPEG_QUALITY = 70
SELF_TITLE = "Zendaya Pet"


_LOCK = threading.Lock()
_THREAD: Optional[threading.Thread] = None
_STOP = threading.Event()
_ENABLED = True
_LAST_TITLE: str = ""
_LAST_CAPTION_TS: float = 0.0
_CAPTIONS: Deque[Dict[str, Any]] = deque(maxlen=MAX_CAPTIONS)


def _z():
    import zendaya as _zmod
    return _zmod


def _focused_title() -> str:
    if not _WIN32_READY:
        return ""
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return ""
        return win32gui.GetWindowText(hwnd) or ""
    except Exception:
        return ""


def _capture_jpeg() -> Optional[bytes]:
    """Grab the foreground monitor and return downscaled JPEG bytes."""
    if not (_MSS_READY and _PIL_READY):
        return None
    try:
        with mss.mss() as sct:
            # Monitor 1 = primary; 0 = full virtual screen. Use the one the focused window is on.
            mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            shot = sct.grab(mon)
            img = Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)
        img.thumbnail((MAX_IMG_DIM, MAX_IMG_DIM))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        return buf.getvalue()
    except Exception as e:
        print(f"(screen: capture failed: {e})")
        return None


def _caption_with_gemini(jpeg_bytes: bytes, title: str) -> Optional[str]:
    """One-line caption of what's on screen via Gemini."""
    try:
        z = _z()
        client = getattr(z, "_gemini_client", None)
        ready = getattr(z, "_GEMINI_READY", False)
    except Exception:
        client, ready = None, False
    if not (ready and client is not None):
        return None
    prompt = (
        "Describe what the user is currently doing in ONE short sentence (under 20 words). "
        "Focus on the activity, not the UI chrome. Don't preamble. "
        f"Window title: {title!r}."
    )
    try:
        from google.genai import types as _gtypes
    except Exception:
        _gtypes = None
    try:
        if _gtypes is not None:
            part = _gtypes.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg")
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt, part],
            )
        else:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt, {"mime_type": "image/jpeg", "data": jpeg_bytes}],
            )
        return (response.text or "").strip()
    except Exception as e:
        print(f"(screen: caption failed: {e})")
        return None


def _record_caption(title: str, caption: str) -> None:
    with _LOCK:
        _CAPTIONS.append({
            "ts": time.time(),
            "title": title,
            "caption": caption,
        })


def recent_captions(n: int = 3) -> List[str]:
    """Return the last n captions formatted for context injection."""
    with _LOCK:
        items = list(_CAPTIONS)[-n:]
    return [f"[{time.strftime('%H:%M', time.localtime(it['ts']))}] {it['caption']}" for it in items]


def last_caption() -> Optional[Dict[str, Any]]:
    with _LOCK:
        if not _CAPTIONS:
            return None
        return dict(_CAPTIONS[-1])


def render_for_context() -> str:
    """Memory-bit string consumed by gemini_reply. Empty if no data."""
    items = recent_captions(3)
    if not items:
        return ""
    return "Recent screen activity:\n- " + "\n- ".join(items)


def set_enabled(flag: bool) -> None:
    global _ENABLED
    _ENABLED = bool(flag)


def is_running() -> bool:
    return _THREAD is not None and _THREAD.is_alive()


def _loop() -> None:
    global _LAST_TITLE, _LAST_CAPTION_TS
    while not _STOP.is_set():
        try:
            if _ENABLED:
                title = _focused_title()
                if title and title != SELF_TITLE and title != _LAST_TITLE:
                    _LAST_TITLE = title
                    if (time.time() - _LAST_CAPTION_TS) >= MIN_CAPTION_GAP_S:
                        _LAST_CAPTION_TS = time.time()
                        jpeg = _capture_jpeg()
                        if jpeg:
                            cap = _caption_with_gemini(jpeg, title)
                            if cap:
                                _record_caption(title, cap)
        except Exception as e:
            print(f"(screen loop error: {e})")
        _STOP.wait(TITLE_POLL_S)


def start() -> Optional[threading.Thread]:
    global _THREAD
    if not _MSS_READY:
        print(f"(screen awareness disabled — mss missing: {_MSS_ERR})")
        return None
    if not _PIL_READY:
        print("(screen awareness disabled — Pillow missing)")
        return None
    if not _WIN32_READY:
        print("(screen awareness disabled — win32gui missing)")
        return None
    if _THREAD is not None and _THREAD.is_alive():
        return _THREAD
    _STOP.clear()
    _THREAD = threading.Thread(target=_loop, daemon=True, name="zendaya-screen")
    _THREAD.start()
    return _THREAD


def stop() -> None:
    _STOP.set()


# --- Parser hooks ---

_ON_RE = re.compile(r"^(?:turn\s+on|enable|start)\s+screen(?:\s+awareness)?\s*$", re.IGNORECASE)
_OFF_RE = re.compile(r"^(?:turn\s+off|disable|stop)\s+screen(?:\s+awareness)?\s*$", re.IGNORECASE)
_WHAT_RE = re.compile(
    r"^(?:what\s+(?:am\s+i|was\s+i|have\s+i\s+been)\s+(?:doing|working\s+on)(?:\s+just\s+now)?|"
    r"what'?s?\s+on\s+(?:my\s+)?screen)\s*\??$",
    re.IGNORECASE,
)


def parse_screen_command(user_text: str) -> Optional[Dict[str, Any]]:
    if not user_text:
        return None
    t = user_text.strip()
    if _ON_RE.match(t):
        return {"op": "enable"}
    if _OFF_RE.match(t):
        return {"op": "disable"}
    if _WHAT_RE.match(t):
        return {"op": "describe"}
    return None


def handle_screen_command(parsed: Dict[str, Any]) -> str:
    op = parsed.get("op")
    if op == "enable":
        set_enabled(True)
        if not is_running():
            start()
        return "Screen awareness on — I'll keep an eye on what you're doing."
    if op == "disable":
        set_enabled(False)
        return "Screen awareness off."
    if op == "describe":
        last = last_caption()
        if last is None:
            return "I haven't captured your screen recently — give me a moment."
        return f"Looks like: {last['caption']}"
    return f"Unknown screen op: {op}"
