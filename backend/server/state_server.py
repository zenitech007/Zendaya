"""
server.state_server.py — FastAPI bridge between zendaya.py and the Godot 4 frontend.

The Godot pet polls GET /ai_status a few times per second and reads the
current state ("idle" | "thinking" | "talking") plus the last reply text.
zendaya.py writes that state via set_state(); typing in the Godot chat box
POSTs to /chat which hands the message off to handle_user_command() on a
worker thread so the HTTP response stays instant.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Callable, Optional

import asyncio
import json
import base64

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn


# ── Shared state ────────────────────────────────────────
_LOCK = threading.Lock()
_STATE = {
    "state": "idle",
    "text": "",
    "ts": time.time(),
}
# Mouth amplitude for lipsync (0.0–1.0). Pushed by zendaya.py during PCM playback.
_MOUTH = {"level": 0.0, "ts": time.time()}
_MOUTH_DECAY_SECS = 0.2
# After this many seconds of no updates, stale "thinking"/"talking"
# auto-decays back to "idle" so a crashed reply doesn't pin the pet.
_DECAY_SECS = 15.0

_VALID_STATES = {"idle", "thinking", "talking"}

# State name aliases for the HUD (which uses an expanded cinematic vocabulary).
_HUD_ALIASES = {
    "idle": "idle",
    "aware": "aware",
    "thinking": "thinking",
    "talking": "speaking",
    "listening": "listening",
    "speaking": "speaking",
    "searching": "searching",
    "mapping": "mapping",
    "alert": "alert",
    "error": "error",
}

def _broadcast_state_async(payload: dict) -> None:
    """Push state to all connected WS clients on whichever loop owns them."""
    loop = _WS_LOOP
    if loop is None:
        return
    try:
        asyncio.run_coroutine_threadsafe(_ws_broadcast(payload), loop)
    except Exception:
        pass


def hud_client_count() -> int:
    """How many HUD WebSocket clients are currently connected.

    zendaya.py reads this once per utterance to decide whether the TTS voice
    plays in the browser (>=1 client) or on the local speaker (0 clients).
    """
    try:
        return len(_WS_CLIENTS)
    except Exception:
        return 0


def audio_begin(rate: int, utt_id: int) -> None:
    """Announce the start of a TTS utterance the HUD should play."""
    _broadcast_state_async({"audio": {"event": "begin", "rate": int(rate), "id": int(utt_id)}})


def push_audio_chunk(pcm_bytes: bytes, utt_id: int, seq: int) -> None:
    """Tee one PCM int16 window to the HUD as base64."""
    try:
        b64 = base64.b64encode(pcm_bytes).decode("ascii")
    except Exception:
        return
    _broadcast_state_async({"audio": {"event": "chunk", "id": int(utt_id), "seq": int(seq), "b64": b64}})


def audio_end(utt_id: int) -> None:
    """Signal that no further chunks will arrive for this utterance."""
    _broadcast_state_async({"audio": {"event": "end", "id": int(utt_id)}})


def audio_stop() -> None:
    """Barge-in: tell the HUD to flush any queued/playing audio immediately."""
    _broadcast_state_async({"audio": {"event": "stop"}})


def set_panel(name: str) -> None:
    """Tell the HUD frontend to show (or hide with 'none') a visualization panel."""
    name = (name or "none").strip().lower()
    _broadcast_state_async({"panel": name})


def set_now_playing(np: Optional[dict]) -> None:
    """Push a now-playing payload to the HUD. Pass None to clear."""
    _broadcast_state_async({"now_playing": np})


def set_action(name: str, payload: Optional[dict] = None) -> None:
    """Tell the HUD frontend to play a choreographed animation timeline.

    Blueprint actions: open_map, dock_orb, show_terminal, activate_voice,
    minimize_ui, show_notification. The frontend's WS handler routes each
    name to its GSAP timeline. `payload` is a free-form dict the timeline
    can read (e.g. {"text": "..."} for show_notification).
    """
    msg: dict = {"action": (name or "").strip().lower()}
    if payload:
        msg["payload"] = payload
    _broadcast_state_async(msg)


def set_state(name: str, text: str = "") -> None:
    """Thread-safe state writer. Called from zendaya.py."""
    # Keep original name for the WebSocket HUD
    hud_state = _HUD_ALIASES.get(name, "idle")
    
    # Filter for the legacy Godot client (only idle/thinking/talking)
    godot_state = name
    if godot_state not in _VALID_STATES:
        godot_state = "idle"

    with _LOCK:
        _STATE["state"] = godot_state
        if text:
            _STATE["text"] = text
        _STATE["ts"] = time.time()
        
    payload = {"state": hud_state}
    if text:
        payload["text"] = text
    _broadcast_state_async(payload)


def get_state() -> dict:
    """Snapshot for the HTTP route, with auto-decay applied."""
    with _LOCK:
        snap = dict(_STATE)
    if snap["state"] != "idle" and (time.time() - snap["ts"]) > _DECAY_SECS:
        snap["state"] = "idle"
    return snap


def set_amplitude(level: float) -> None:
    """Thread-safe mouth-amplitude writer. Called from zendaya.py during TTS playback."""
    try:
        lvl = float(level)
    except (TypeError, ValueError):
        return
    if lvl < 0.0:
        lvl = 0.0
    elif lvl > 1.0:
        lvl = 1.0
    with _LOCK:
        _MOUTH["level"] = lvl
        _MOUTH["ts"] = time.time()


def get_mouth() -> dict:
    """Snapshot for the HTTP route, decayed to 0 if TTS has stopped pushing."""
    with _LOCK:
        snap = dict(_MOUTH)
    if (time.time() - snap["ts"]) > _MOUTH_DECAY_SECS:
        snap["level"] = 0.0
    return snap


# ── Visemes (lipsync mouth shapes) ─────────────────────
# Stored as {"weights": {aa/ih/ee/oh/ou}, "ts": ...} so the broadcast loop
# can read a self-describing snapshot.
_VISEME_KEYS = ("aa", "ih", "ee", "oh", "ou")
_VISEMES = {"weights": {k: 0.0 for k in _VISEME_KEYS}, "ts": time.time()}
_VISEME_DECAY_SECS = 0.2


def set_visemes(weights: dict) -> None:
    """Thread-safe viseme writer. Expected keys: aa/ih/ee/oh/ou."""
    if not isinstance(weights, dict):
        return
    with _LOCK:
        w = _VISEMES.setdefault("weights", {})
        for k in _VISEME_KEYS:
            try:
                v = float(weights.get(k, 0.0))
            except (TypeError, ValueError):
                v = 0.0
            if v < 0.0:
                v = 0.0
            elif v > 1.0:
                v = 1.0
            w[k] = v
        _VISEMES["ts"] = time.time()


def get_visemes() -> dict:
    with _LOCK:
        snap = dict(_VISEMES.get("weights", {}))
        ts = _VISEMES.get("ts", 0.0)
    if (time.time() - ts) > _VISEME_DECAY_SECS:
        for k in snap:
            snap[k] = 0.0
    return snap


# ── Body language (one-shot animation cue) ─────────────
_BODY = {"action": "", "ts": 0.0}

# Decimation state for the broadcast loop.
_BROADCAST_LAST_SENT: dict = {
    "amplitude": None,          # float or None
    "visemes": None,            # dict or None
    "telemetry_failed": False,  # one-time null payload after provider exception
}
_AMPLITUDE_DELTA = 0.005
_VISEME_DELTA = 0.01
_PERCEPTION_HEARTBEAT_S = 5.0
_BODY_ACTION_ALLOWED = {"", "nod", "shake", "wave", "shrug"}


def set_body_action(action: str) -> None:
    val = (action or "").strip().lower()
    if val not in _BODY_ACTION_ALLOWED:
        print(f"(state_server: ignoring unknown body_action {val!r})")
        val = ""
    with _LOCK:
        _BODY["action"] = val
        _BODY["ts"] = time.time()


def get_body() -> dict:
    with _LOCK:
        return dict(_BODY)


# ── Telemetry hooks (HUD) ──────────────────────────────
_TELEMETRY_PROVIDER: Optional[Callable[[], dict]] = None


def set_telemetry_provider(fn: Callable[[], dict]) -> None:
    """Hand a callable that returns the current HUD payload."""
    global _TELEMETRY_PROVIDER
    _TELEMETRY_PROVIDER = fn


def get_telemetry() -> dict:
    if _TELEMETRY_PROVIDER is None:
        return {}
    try:
        return _TELEMETRY_PROVIDER() or {}
    except Exception:
        return {}


# ── Perception hooks ───────────────────────────────────
_PERCEPTION_FACE: Optional[Callable[[], dict]] = None
_PERCEPTION_LAST_GESTURE: Optional[Callable[[], dict]] = None


def set_perception_providers(
    face: Optional[Callable[[], dict]] = None,
    last_gesture: Optional[Callable[[], dict]] = None,
) -> None:
    global _PERCEPTION_FACE, _PERCEPTION_LAST_GESTURE
    if face is not None:
        _PERCEPTION_FACE = face
    if last_gesture is not None:
        _PERCEPTION_LAST_GESTURE = last_gesture


def get_perception() -> dict:
    face = _PERCEPTION_FACE() if _PERCEPTION_FACE else {"present": False, "x": 0.0, "y": 0.0, "ts": 0.0}
    last = _PERCEPTION_LAST_GESTURE() if _PERCEPTION_LAST_GESTURE else {"name": "none", "ts": 0.0}
    return {"face": face, "last_gesture": last}


# ── HTTP app ────────────────────────────────────────────
app = FastAPI(title="Zendaya State Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── WebSocket broadcast machinery ──────────────────────
_WS_CLIENTS: set = set()
_WS_LOOP: Optional[asyncio.AbstractEventLoop] = None


async def _ws_broadcast(payload: dict) -> None:
    if not _WS_CLIENTS:
        return
    msg = json.dumps(payload)
    dead = []
    for client in list(_WS_CLIENTS):
        try:
            await client.send_text(msg)
        except Exception:
            dead.append(client)
    for d in dead:
        _WS_CLIENTS.discard(d)


_ON_CHAT: Optional[Callable[[str], None]] = None
# Synchronous chat handler for the mobile API: takes a message, returns the
# assistant's reply text. Resolved at start() time from zendaya.py.
_ON_CHAT_SYNC: Optional[Callable[[str], str]] = None
# Resolved at start() time. Returns a status string. Inputs are
# (action, title) — action is one of close/maximize/minimize/focus.
_ON_WINDOW_CONTROL: Optional[Callable[[str, str], str]] = None
# Window watcher hooks; resolved at start() time. Both are optional —
# if absent, /window returns an empty snapshot and event list.
_WINDOW_GET_SNAPSHOT: Optional[Callable[[], dict]] = None
_WINDOW_POP_EVENTS: Optional[Callable[[], list]] = None
_ON_QUIT: Optional[Callable[[], None]] = None  # set from start(on_quit=...); called by POST /quit


class ChatIn(BaseModel):
    message: str


class WindowControlIn(BaseModel):
    action: str
    title: str = ""


class NowPlayingIn(BaseModel):
    track_id: Optional[str] = None
    is_playing: bool = True
    position_ms: int = 0


@app.on_event("startup")
async def _capture_loop():
    global _WS_LOOP, _broadcast_thread
    _WS_LOOP = asyncio.get_running_loop()
    # Start the 30 Hz broadcast loop that fans amplitude/visemes/telemetry/
    # perception/body_action out to connected WS clients.
    if _broadcast_thread is None or not _broadcast_thread.is_alive():
        _broadcast_stop.clear()
        _broadcast_thread = threading.Thread(
            target=_broadcast_loop, name="state-server-broadcast", daemon=True
        )
        _broadcast_thread.start()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _WS_CLIENTS.add(ws)
    # Send current snapshot so a fresh client renders the right state.
    try:
        snap = get_state()
        _snapshot = {
            "state": _HUD_ALIASES.get(snap["state"], snap["state"]),
            "text": snap.get("text", ""),
        }
        try:
            tp = globals().get("_TELEMETRY_PROVIDER")
            if tp is not None:
                _snapshot["telemetry"] = tp()
        except Exception:
            pass
        try:
            fp = globals().get("_PERCEPTION_FACE")
            gp = globals().get("_PERCEPTION_LAST_GESTURE")
            if fp is not None and gp is not None:
                _snapshot["perception"] = {"face": fp(), "last_gesture": gp()}
        except Exception:
            pass
        await ws.send_text(json.dumps(_snapshot))
    except Exception:
        pass
    try:
        while True:
            # We don't expect inbound messages, but await keeps the socket alive.
            data = await ws.receive_text()
            # Optional: accept JSON commands later. For now, ignore.
            _ = data
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _WS_CLIENTS.discard(ws)


@app.get("/health")
def health():
    return {"ok": True, "name": "Zendaya"}


@app.post("/quit")
def quit_zendaya():
    """Ask the backend to shut down cleanly. Fires the injected on_quit callback."""
    if _ON_QUIT:
        _ON_QUIT()
    return {"ok": True, "shutting_down": True}


@app.get("/ai_status")
def ai_status():
    return get_state()


@app.get("/mouth")
def mouth_level():
    return get_mouth()


@app.get("/visemes")
def visemes():
    return get_visemes()


@app.get("/body")
def body():
    return get_body()


@app.get("/perception")
def perception():
    return get_perception()


@app.get("/telemetry")
def telemetry():
    return get_telemetry()


# ── Music (SP-3: in-HUD player) ────────────────────────
@app.get("/music/list")
def music_list():
    """List the local music library as HUD queue entries."""
    import server.hud_music as hud_music
    return hud_music.list_tracks()


@app.get("/music/stream/{track_id}")
def music_stream(track_id: str):
    """Stream a local track's bytes (FileResponse provides HTTP Range → seeking)."""
    import server.hud_music as hud_music
    path = hud_music.resolve(track_id)
    if path is None:
        raise HTTPException(status_code=404, detail="track not found")
    return FileResponse(str(path))


@app.post("/music/now")
def music_now(payload: NowPlayingIn):
    """Single-writer sync from the HUD: it owns playback, we mirror + rebroadcast."""
    import integrations.spotify as sp
    if payload.track_id is None:
        sp.clear_local_now()
        set_now_playing(None)
        return {"ok": True}
    sp.set_local_now(payload.track_id, payload.is_playing, payload.position_ms)
    set_now_playing(sp.now_playing_payload())
    return {"ok": True}


@app.post("/chat")
def chat(payload: ChatIn):
    msg = (payload.message or "").strip()
    if not msg:
        return {"accepted": False, "error": "empty message"}
    if _ON_CHAT is None:
        return {"accepted": False, "error": "no handler registered"}

    def _run():
        try:
            _ON_CHAT(msg)
        except Exception as e:
            set_state("talking", f"[error: {e}]")

    threading.Thread(target=_run, daemon=True).start()
    return {"accepted": True}


@app.get("/window")
def window():
    """Snapshot of the currently focused window plus any new events."""
    snap = _WINDOW_GET_SNAPSHOT() if _WINDOW_GET_SNAPSHOT else {}
    events = _WINDOW_POP_EVENTS() if _WINDOW_POP_EVENTS else []
    return {"focused": snap, "events": events}


@app.post("/window/control")
def window_control(payload: WindowControlIn):
    """Maximize / minimize / focus / close a window by title."""
    if _ON_WINDOW_CONTROL is None:
        return {"ok": False, "message": "no handler registered"}
    action = (payload.action or "").strip().lower()
    title = (payload.title or "").strip()
    if action not in {"close", "maximize", "minimize", "focus"}:
        return {"ok": False, "message": f"unknown action: {action}"}
    try:
        msg = _ON_WINDOW_CONTROL(action, title)
        return {"ok": True, "message": msg}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# ── Broadcast loop (30 Hz with decimation) ─────────────
def _collect_tick(include_telemetry: bool = True) -> list[dict]:
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
        abs(float(weights.get(k, 0.0)) - float(last_v.get(k, 0.0))) >= _VISEME_DELTA
        for k in _VISEME_KEYS
    ):
        out.append({"visemes": {k: float(weights.get(k, 0.0)) for k in _VISEME_KEYS}})
        _BROADCAST_LAST_SENT["visemes"] = {k: float(weights.get(k, 0.0)) for k in _VISEME_KEYS}

    # telemetry (sent when due; null one time on exception). The provider is
    # only invoked when include_telemetry is set, so the caller's 2 Hz throttle
    # avoids running psutil + emotion analysis on every 30 Hz tick.
    provider = globals().get("_TELEMETRY_PROVIDER")
    if include_telemetry and provider is not None:
        try:
            tel = provider()
            out.append({"telemetry": tel})
            _BROADCAST_LAST_SENT["telemetry_failed"] = False
        except Exception as e:
            if not _BROADCAST_LAST_SENT.get("telemetry_failed", False):
                print(f"(state_server: telemetry provider raised {e!r}; sending null)")
                out.append({"telemetry": None})
                _BROADCAST_LAST_SENT["telemetry_failed"] = True

    # perception (send on every tick when providers exist)
    face_p = globals().get("_PERCEPTION_FACE")
    gesture_p = globals().get("_PERCEPTION_LAST_GESTURE")
    if face_p is not None and gesture_p is not None:
        try:
            payload = {"face": face_p(), "last_gesture": gesture_p()}
            out.append({"perception": payload})
        except Exception as e:
            print(f"(state_server: perception provider raised {e!r})")

    # body_action — on-change only; read-and-clear under the lock so a
    # concurrent set_body_action() can't be lost between read and reset.
    with _LOCK:
        body_action = _BODY.get("action", "")
        if body_action and body_action in _BODY_ACTION_ALLOWED:
            _BODY["action"] = ""  # consumed; a fresh set_body_action re-emits
        else:
            body_action = ""
    if body_action:
        out.append({"body_action": body_action})

    return out


_broadcast_stop = threading.Event()
_broadcast_thread: Optional[threading.Thread] = None
_BROADCAST_TICK_HZ = 30.0


def _broadcast_loop() -> None:
    period = 1.0 / _BROADCAST_TICK_HZ
    last_perception_hb = 0.0
    last_telemetry_send = 0.0
    while not _broadcast_stop.is_set():
        t0 = time.time()
        try:
            # Throttle telemetry to 2 Hz inside the 30 Hz loop by only asking
            # _collect_tick to invoke the (expensive) provider when due.
            want_telemetry = (t0 - last_telemetry_send) >= 0.5
            messages = _collect_tick(include_telemetry=want_telemetry)
            if want_telemetry and any("telemetry" in m for m in messages):
                last_telemetry_send = t0
            # Track perception heartbeat; _collect_tick already emits perception
            # every tick when providers exist, so only force one when absent.
            if any("perception" in m for m in messages):
                last_perception_hb = t0
            elif t0 - last_perception_hb >= _PERCEPTION_HEARTBEAT_S:
                face_p = globals().get("_PERCEPTION_FACE")
                gesture_p = globals().get("_PERCEPTION_LAST_GESTURE")
                if face_p is not None and gesture_p is not None:
                    try:
                        messages.append({"perception": {"face": face_p(), "last_gesture": gesture_p()}})
                        last_perception_hb = t0
                    except Exception:
                        pass
            for m in messages:
                _broadcast_state_async(m)  # fans out to WS clients via the captured loop
        except Exception as e:
            print(f"(state_server: broadcast tick failed: {e})")
        elapsed = time.time() - t0
        _broadcast_stop.wait(max(0.0, period - elapsed))


@app.on_event("shutdown")
async def _stop_broadcast_loop():
    _broadcast_stop.set()
    if _broadcast_thread is not None:
        _broadcast_thread.join(timeout=2.0)


def chat_sync(message: str) -> dict:
    """Run a mobile chat turn synchronously and return the reply text."""
    msg = (message or "").strip()
    if not msg:
        return {"reply": "", "error": "empty message"}
    if _ON_CHAT_SYNC is None:
        return {"reply": "", "error": "no handler registered"}
    reply = _ON_CHAT_SYNC(msg)
    return {"reply": reply, "state": get_state().get("state", "idle")}


# ── Server lifecycle ────────────────────────────────────
def start(
    host: str = "127.0.0.1",
    port: int = 7475,
    on_chat: Optional[Callable[[str], None]] = None,
    on_chat_sync: Optional[Callable[[str], str]] = None,
    on_window_control: Optional[Callable[[str, str], str]] = None,
    window_get_snapshot: Optional[Callable[[], dict]] = None,
    window_pop_events: Optional[Callable[[], list]] = None,
    on_quit: Optional[Callable[[], None]] = None,
) -> threading.Thread:
    """Spawn uvicorn on a daemon thread and return the thread handle."""
    global _ON_CHAT, _ON_CHAT_SYNC, _ON_WINDOW_CONTROL
    global _WINDOW_GET_SNAPSHOT, _WINDOW_POP_EVENTS
    global _ON_QUIT
    _ON_CHAT = on_chat
    _ON_CHAT_SYNC = on_chat_sync
    _ON_WINDOW_CONTROL = on_window_control
    _WINDOW_GET_SNAPSHOT = window_get_snapshot
    _WINDOW_POP_EVENTS = window_pop_events
    _ON_QUIT = on_quit

    bind_host = os.environ.get("ZENDAYA_BIND_HOST", host)
    config = uvicorn.Config(app, host=bind_host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    t = threading.Thread(target=server.run, daemon=True, name="zendaya-state-server")
    t.start()
    return t


if __name__ == "__main__":
    # Standalone smoke test:
    #   python server.state_server.py
    #   curl http://127.0.0.1:7475/health
    def _echo(msg: str):
        set_state("thinking")
        time.sleep(0.5)
        set_state("talking", f"echo: {msg}")

    start(on_chat=_echo)
    print("State server running on http://127.0.0.1:7475")
    while True:
        time.sleep(60)
