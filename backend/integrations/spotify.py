"""
integrations.spotify.py
==================
Spotify Connect bridge via the Web API (spotipy).

Setup:
  1. https://developer.spotify.com/dashboard -> Create App
  2. Add redirect URI: http://127.0.0.1:8765/callback
  3. Put these in .env:
       SPOTIFY_CLIENT_ID=...
       SPOTIFY_CLIENT_SECRET=...
       SPOTIFY_REDIRECT_URI=http://127.0.0.1:8765/callback
  4. First command opens a browser once to authorize; token cached afterwards.

Premium account required for play/pause/skip (Spotify limitation, not ours).
"""

import os
import re
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv

from memory.data_store import load as ds_load, save as ds_save

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8765/callback").strip()

SCOPES = (
    "user-read-playback-state user-modify-playback-state "
    "user-read-currently-playing playlist-read-private "
    "user-library-read user-read-recently-played"
)

_TOKEN_CACHE = Path(__file__).parent.parent / "zendaya_data" / ".spotify_token_cache"
_AVAIL_CACHE = {"checked_at": 0.0, "ok": False}
_AVAIL_TTL = 60.0
_CLIENT = None


def spotify_configured() -> bool:
    return bool(SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET)


def _get_client():
    """Returns an authorized spotipy.Spotify client, or None if not usable."""
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    if not spotify_configured():
        return None
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
    except ImportError:
        return None
    try:
        auth = SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope=SCOPES,
            cache_path=str(_TOKEN_CACHE),
            open_browser=True,
        )
        _CLIENT = spotipy.Spotify(auth_manager=auth, requests_timeout=8)
        return _CLIENT
    except Exception:
        return None


def spotify_available() -> bool:
    now = time.time()
    if now - _AVAIL_CACHE["checked_at"] < _AVAIL_TTL:
        return _AVAIL_CACHE["ok"]
    ok = False
    if spotify_configured():
        c = _get_client()
        if c is not None:
            try:
                c.current_user()
                ok = True
            except Exception:
                ok = False
    _AVAIL_CACHE["checked_at"] = now
    _AVAIL_CACHE["ok"] = ok
    return ok


def spotify_unavailable_message() -> str:
    if not spotify_configured():
        return (
            "Spotify isn't connected yet. Add SPOTIFY_CLIENT_ID and "
            "SPOTIFY_CLIENT_SECRET to .env (get them from "
            "developer.spotify.com/dashboard) and restart me."
        )
    try:
        import spotipy  # noqa: F401
    except ImportError:
        return "Spotify isn't installed yet — run: pip install spotipy"
    return (
        "Spotify is configured but I can't reach it right now. "
        "Try again, or re-authorize by deleting "
        "zendaya_data\\.spotify_token_cache and asking again."
    )


def _pick_device(client, preferred: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Pick an active Spotify Connect device. Falls back to first available."""
    try:
        devs = client.devices().get("devices", [])
    except Exception:
        return None
    if not devs:
        return None
    if preferred:
        pl = preferred.lower()
        for d in devs:
            if pl in d["name"].lower():
                return d
    for d in devs:
        if d.get("is_active"):
            return d
    cached = ds_load("spotify_device", default={}).get("id")
    if cached:
        for d in devs:
            if d["id"] == cached:
                return d
    return devs[0]


def _remember_device(d: Dict[str, Any]):
    ds_save("spotify_device", {"id": d["id"], "name": d["name"]})


def spotify_list_devices() -> str:
    if not spotify_available():
        return spotify_unavailable_message()
    c = _get_client()
    try:
        devs = c.devices().get("devices", [])
    except Exception as e:
        return f"Couldn't list Spotify devices: {e}"
    if not devs:
        return "No Spotify devices found. Open Spotify on a device first."
    lines = ["Spotify devices:"]
    for d in devs:
        flags = []
        if d.get("is_active"): flags.append("active")
        if d.get("is_restricted"): flags.append("restricted")
        lines.append(f"  - {d['name']} ({d.get('type', 'device')}{', ' + ', '.join(flags) if flags else ''})")
    return "\n".join(lines)


def _launch_spotify_desktop() -> bool:
    """Best-effort: open the Spotify Windows app so it registers as a device."""
    import subprocess
    for cmd in (
        ["cmd", "/c", "start", "", "spotify:"],
        ["cmd", "/c", "start", "", "spotify"],
    ):
        try:
            subprocess.Popen(cmd, shell=False,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,
                             creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
            return True
        except Exception:
            continue
    return False


def _wait_for_device(client, hint: Optional[str], tries: int = 8, delay: float = 0.6) -> Optional[Dict[str, Any]]:
    for _ in range(tries):
        d = _pick_device(client, hint)
        if d:
            return d
        time.sleep(delay)
    return None


def spotify_play(query: Optional[str] = None, device_hint: Optional[str] = None) -> str:
    if not spotify_available():
        return spotify_unavailable_message()
    c = _get_client()
    dev = _pick_device(c, device_hint)
    if not dev:
        _launch_spotify_desktop()
        dev = _wait_for_device(c, device_hint)
    if not dev:
        # Local fallback
        local_msg = local_music_play(query)
        if local_msg:
            return local_msg
        return "No Spotify device available, and I couldn't find a local music folder either. Open Spotify first or set ZENDAYA_MUSIC_DIR in .env."
    _remember_device(dev)
    device_id = dev["id"]

    try:
        if query:
            uri = _resolve_query_to_uri(c, query)
            if not uri:
                return f"Couldn't find anything matching '{query}' on Spotify."
            kind, _ = uri.split(":", 1)[0], uri
            if uri.startswith("spotify:track:"):
                c.start_playback(device_id=device_id, uris=[uri])
            else:
                c.start_playback(device_id=device_id, context_uri=uri)
            return f"Playing '{query}' on {dev['name']}."
        c.start_playback(device_id=device_id)
        return f"Playing on {dev['name']}."
    except Exception as e:
        msg = str(e)
        if "PREMIUM_REQUIRED" in msg or "403" in msg:
            return "Spotify playback control requires a Premium account."
        return f"Couldn't start playback: {e}"


def _resolve_query_to_uri(client, query: str) -> Optional[str]:
    """Try playlist -> album -> artist -> track, in that order."""
    q = query.strip()
    try:
        for kind in ("playlist", "album", "artist", "track"):
            res = client.search(q=q, type=kind, limit=1)
            items = res.get(f"{kind}s", {}).get("items") or []
            if items:
                return items[0]["uri"]
    except Exception:
        return None
    return None


def spotify_pause() -> str:
    if not spotify_available():
        return spotify_unavailable_message()
    c = _get_client()
    try:
        c.pause_playback()
        return "Spotify paused."
    except Exception as e:
        if "No active device" in str(e):
            return "Nothing is playing on Spotify right now."
        return f"Couldn't pause: {e}"


def spotify_resume() -> str:
    return spotify_play()


def spotify_next() -> str:
    if not spotify_available():
        return spotify_unavailable_message()
    c = _get_client()
    try:
        c.next_track()
        return "Skipped to next track."
    except Exception as e:
        return f"Couldn't skip: {e}"


def spotify_previous() -> str:
    if not spotify_available():
        return spotify_unavailable_message()
    c = _get_client()
    try:
        c.previous_track()
        return "Back to previous track."
    except Exception as e:
        return f"Couldn't go back: {e}"


def spotify_volume(level: int) -> str:
    if not spotify_available():
        return spotify_unavailable_message()
    level = max(0, min(100, int(level)))
    c = _get_client()
    try:
        c.volume(level)
        return f"Spotify volume set to {level}%."
    except Exception as e:
        return f"Couldn't set Spotify volume: {e}"


def spotify_now_playing() -> str:
    if not spotify_available():
        return spotify_unavailable_message()
    c = _get_client()
    try:
        cur = c.current_playback()
    except Exception as e:
        return f"Couldn't read current playback: {e}"
    if not cur or not cur.get("item"):
        return "Nothing is playing on Spotify."
    item = cur["item"]
    name = item.get("name", "Unknown track")
    artists = ", ".join(a["name"] for a in item.get("artists", []))
    state = "Playing" if cur.get("is_playing") else "Paused"
    device = cur.get("device", {}).get("name", "unknown device")
    return f"{state}: {name} — {artists} (on {device})."


def spotify_shuffle(on: bool) -> str:
    if not spotify_available():
        return spotify_unavailable_message()
    c = _get_client()
    try:
        c.shuffle(on)
        return f"Shuffle {'on' if on else 'off'}."
    except Exception as e:
        return f"Couldn't toggle shuffle: {e}"


def spotify_repeat(mode: str) -> str:
    """mode: 'track' | 'context' | 'off'"""
    if not spotify_available():
        return spotify_unavailable_message()
    c = _get_client()
    try:
        c.repeat(mode)
        return f"Repeat mode: {mode}."
    except Exception as e:
        return f"Couldn't set repeat: {e}"


def spotify_command(user_text: str) -> Optional[str]:
    """Parse natural-language Spotify commands. Returns None if not a Spotify command."""
    t = user_text.strip()
    lt = t.lower()

    if re.fullmatch(r"\s*(?:list|show)\s+(?:my\s+)?spotify\s+devices\s*", lt):
        return spotify_list_devices()

    if re.search(r"\b(?:what(?:'s|\s+is)\s+playing|now\s+playing|current\s+(?:song|track))\b", lt):
        return spotify_now_playing()

    m = re.match(r"^(?:zendaya,\s*)?(?:set\s+)?spotify\s+volume\s+(?:to\s+)?(\d{1,3})\s*%?\s*$", lt)
    if m:
        return spotify_volume(int(m.group(1)))

    if re.fullmatch(r"\s*(?:pause|stop)\s+(?:the\s+)?(?:music|spotify|song)\s*", lt) \
            or re.fullmatch(r"\s*spotify\s+(?:pause|stop)\s*", lt):
        return _local_or_spotify("pause", spotify_pause, "Paused.")

    if re.fullmatch(r"\s*(?:resume|continue|unpause)\s+(?:the\s+)?(?:music|spotify|song)\s*", lt):
        return _local_or_spotify("play", spotify_resume, "Resumed.")

    if re.fullmatch(r"\s*(?:skip|next)\s+(?:the\s+)?(?:song|track)\s*", lt) \
            or re.fullmatch(r"\s*(?:skip|next)\s+(?:on\s+)?spotify\s*", lt) \
            or re.fullmatch(r"\s*spotify\s+(?:skip|next)\s*", lt):
        return _local_or_spotify("next", spotify_next, "Next track.")

    if re.fullmatch(r"\s*(?:previous|back|last)\s+(?:song|track)\s*", lt) \
            or re.fullmatch(r"\s*(?:go\s+back|previous)\s+(?:on\s+)?spotify\s*", lt):
        return _local_or_spotify("prev", spotify_previous, "Previous track.")

    if re.fullmatch(r"\s*shuffle\s+(?:on|on\s+spotify)\s*", lt) \
            or re.fullmatch(r"\s*turn\s+(?:on\s+)?shuffle\s*", lt):
        return spotify_shuffle(True)
    if re.fullmatch(r"\s*shuffle\s+off\s*", lt) or re.fullmatch(r"\s*turn\s+off\s+shuffle\s*", lt):
        return spotify_shuffle(False)

    if re.fullmatch(r"\s*repeat\s+(?:this\s+)?(?:song|track)\s*", lt):
        return spotify_repeat("track")
    if re.fullmatch(r"\s*repeat\s+(?:off|none)\s*", lt):
        return spotify_repeat("off")
    if re.fullmatch(r"\s*repeat\s+(?:on|all|playlist|album)\s*", lt):
        return spotify_repeat("context")

    m = re.match(
        r"^(?:zendaya,\s*)?play\s+(.+?)(?:\s+on\s+spotify)?(?:\s+on\s+(.+?))?\s*$",
        t, re.IGNORECASE,
    )
    if m:
        query = m.group(1).strip().strip("'\"")
        device_hint = (m.group(2) or "").strip() or None
        if query.lower() in ("music", "spotify", "something", "anything"):
            return spotify_play(None, device_hint)
        if "spotify" in lt or _looks_like_music_query(query):
            return spotify_play(query, device_hint)

    if re.fullmatch(r"\s*(?:play|start)\s+spotify\s*", lt):
        return spotify_play()

    return None


_MUSIC_HINT_WORDS = {
    "song", "track", "album", "playlist", "artist", "music", "tune",
    "by",  # "play X by Y"
}


def _looks_like_music_query(q: str) -> bool:
    ql = q.lower()
    if any(f" {w} " in f" {ql} " for w in _MUSIC_HINT_WORDS):
        return True
    if re.search(r"\bby\s+[A-Z]", q):
        return True
    return False


# ── Local music fallback ────────────────────────────────
_LOCAL_AUDIO_EXTS = {".mp3", ".m4a", ".flac", ".wav", ".ogg", ".aac", ".wma"}
# The HUD's <audio> element is the playback authority. _LOCAL_NOW mirrors what
# the HUD is playing: the HUD writes position/play state back via POST /music/now
# (see set_local_now). No wall-clock estimation, no auto-expiry.
_LOCAL_NOW: Dict[str, Any] = {"path": None, "track_id": None, "duration_ms": 0,
                              "position_ms": 0, "track": "", "artist": "",
                              "is_playing": False}


def _music_dirs() -> List[Path]:
    """Return candidate music directories — env var overrides Windows default."""
    out = []
    env_dir = os.getenv("ZENDAYA_MUSIC_DIR")
    if env_dir:
        p = Path(env_dir).expanduser()
        if p.is_dir():
            out.append(p)
    user_music = Path.home() / "Music"
    if user_music.is_dir():
        out.append(user_music)
    return out


def _scan_local_tracks() -> List[Path]:
    tracks: List[Path] = []
    for d in _music_dirs():
        for p in d.rglob("*"):
            if p.suffix.lower() in _LOCAL_AUDIO_EXTS:
                tracks.append(p)
    return tracks


def _pick_local_track(query: Optional[str]) -> Optional[Path]:
    tracks = _scan_local_tracks()
    if not tracks:
        return None
    if not query:
        import random
        return random.choice(tracks)
    ql = query.lower()
    for p in tracks:
        if ql in p.stem.lower():
            return p
    return tracks[0]


def local_music_play(query: Optional[str] = None) -> Optional[str]:
    """Select a local track for the HUD to play in its own <audio> element.
    Returns a status message on success, None if no local library exists.
    Does NOT spawn any external player."""
    import server.hud_music as hud_music
    sel = hud_music.select(query)
    if not sel:
        return None
    _LOCAL_NOW.update({
        "path": sel["path"],
        "track_id": sel["id"],
        "duration_ms": sel["duration_ms"],
        "position_ms": 0,
        "track": sel["title"],
        "artist": sel["artist"],
        "is_playing": True,
    })
    return f"Playing '{sel['title']}' from your local music."


def _local_active() -> bool:
    return bool(_LOCAL_NOW.get("track_id"))


def set_local_now(track_id: Optional[str], is_playing: bool, position_ms: int) -> None:
    """Single-writer sync from the HUD: it owns playback, the backend mirrors it.
    Re-derives display metadata from the id so the broadcast snapshot always
    matches the track the HUD is actually playing."""
    if not track_id:
        clear_local_now()
        return
    import server.hud_music as hud_music
    info = hud_music.track_info(track_id)
    if info:
        _LOCAL_NOW.update({
            "path": info["path"],
            "track": info["title"],
            "artist": info["artist"],
            "duration_ms": info["duration_ms"],
        })
    _LOCAL_NOW["track_id"] = track_id
    _LOCAL_NOW["is_playing"] = bool(is_playing)
    try:
        _LOCAL_NOW["position_ms"] = max(0, int(position_ms))
    except (TypeError, ValueError):
        _LOCAL_NOW["position_ms"] = 0


def clear_local_now() -> None:
    _LOCAL_NOW.update({"path": None, "track_id": None, "duration_ms": 0,
                       "position_ms": 0, "track": "", "artist": "",
                       "is_playing": False})


def _local_or_spotify(cmd: str, spotify_fn, ok_msg: str) -> str:
    """Route a transport command: Spotify when reachable, else nudge the HUD's
    local player if a local track is active."""
    if not spotify_available() and _local_active():
        import server.hud_music as hud_music
        hud_music.emit_control(cmd)
        return ok_msg
    return spotify_fn()


def _probe_duration_ms(path: Path) -> int:
    try:
        import mutagen  # optional
        f = mutagen.File(str(path))
        if f is not None and f.info is not None:
            return int(f.info.length * 1000)
    except Exception:
        pass
    return 0


def now_playing_payload() -> Optional[Dict[str, Any]]:
    """Return a dict for the HUD: track / artist / progress / duration / source."""
    # Prefer Spotify when reachable.
    if spotify_available():
        c = _get_client()
        try:
            cur = c.current_playback()
        except Exception:
            cur = None
        if cur and cur.get("item"):
            item = cur["item"]
            art = ""
            try:
                imgs = item.get("album", {}).get("images") or []
                if imgs:
                    art = imgs[0].get("url", "")
            except Exception:
                art = ""
            return {
                "track": item.get("name", "Unknown"),
                "artist": ", ".join(a["name"] for a in item.get("artists", [])),
                "album": item.get("album", {}).get("name", ""),
                "art_url": art,
                "is_playing": bool(cur.get("is_playing")),
                "progress_ms": int(cur.get("progress_ms") or 0),
                "duration_ms": int(item.get("duration_ms") or 0),
                "source": "spotify",
            }
    # Local fallback — the HUD owns playback; we mirror the snapshot it writes
    # via POST /music/now (no wall-clock estimation, no auto-expiry).
    if _LOCAL_NOW.get("track_id"):
        import server.hud_music as hud_music
        tid = _LOCAL_NOW["track_id"]
        return {
            "track": _LOCAL_NOW["track"],
            "artist": _LOCAL_NOW["artist"],
            "album": "",
            "art_url": "",
            "is_playing": bool(_LOCAL_NOW["is_playing"]),
            "progress_ms": int(_LOCAL_NOW.get("position_ms", 0)),
            "duration_ms": int(_LOCAL_NOW.get("duration_ms", 0)),
            "source": "local",
            "stream_url": hud_music.stream_url_for(tid),
            "track_id": tid,
        }
    return None
