# SP-3 · In-HUD Music Player — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Local music plays out of the HUD's own `<audio>` element (no external app opens), triggered by Zendaya's existing voice/chat "play …" intent, with a working in-HUD transport.

**Architecture:** Frontend-authoritative. The HUD `<audio>` is the single playback authority; the Python backend **selects** a track, **serves** its bytes over HTTP, and **stores + broadcasts** a now-playing snapshot. After the initial selection the HUD is the single writer of the backend's local now-playing state via `POST /music/now`, so the broadcast snapshot never drifts from what is actually playing. Voice transport commands are *nudges* the backend fans out as a `music_control` action.

**Tech Stack:** Backend — Python 3.14, FastAPI/Starlette, pytest + `fastapi.testclient.TestClient`. Frontend — React 18 + TS, Zustand 4, Vite 5, Vitest 2 + happy-dom, @testing-library/react, framer-motion 11.

---

## Staging & commit policy (READ FIRST — non-negotiable)

This sub-project edits the backend, which intersects the user's large pre-existing untracked WIP. To respect the user's standing constraints:

- **NEVER stage/commit the protected paths:** `backend/zendaya.py`, `backend/zendaya_system_access.py`, `pyproject.toml`, `.gitignore`, `zendaya_logs/assistant_history.json`.
- **NEVER** use `git add -A`, `git add .`, or `git add -u`. Stage only files named in a commit step.
- **NEVER** touch `git config`; all commits disable signing: `git -c commit.gpgsign=false commit …`.
- **Backend tasks (1–3) DO NOT COMMIT.** Make the code change, run the tests to green, then **leave the backend changes unstaged in the working tree** for the user to review and commit. `backend/zendaya_spotify.py` is the user's untracked WIP and must never be auto-staged; for coherence the whole backend group (`zendaya_hud_music.py`, `zendaya_state_server.py`, the new backend tests) is left uncommitted alongside it.
- **Frontend tasks (4–8) COMMIT per task** by exact filename (everything lives under `zendaya-hud-react/`, cleanly tracked — same as SP-1).
- After every commit, run `git status` and confirm no protected path and nothing under `backend/`, `.superpowers/`, `.claude/`, `zendaya_logs/` was swept in.

## Commands reference

- **Backend tests:** `cd backend && python -m pytest tests/<file>.py -v` (run from `backend/`; `conftest.py` puts `backend/` on `sys.path`). Harmless `PytestConfigWarning: Unknown config option: maxfail/timeout` lines may appear — ignore them.
- **Frontend single test file:** `npm --prefix zendaya-hud-react run test -- <substring>` (e.g. `queue.test`). `test` = `vitest run` (non-interactive).
- **Frontend full suite:** `npm --prefix zendaya-hud-react run test`
- **Frontend build/type-check:** `npm --prefix zendaya-hud-react run build`

## File structure

| File | Change | Responsibility |
|---|---|---|
| `backend/zendaya_hud_music.py` | **NEW** | Track identity (`track_id`), `list_tracks`, `resolve` (containment-checked), `track_info`, `select`, `emit_control`, `stream_url_for`. Delegates scanning to `zendaya_spotify` (one scanner). |
| `backend/zendaya_spotify.py` | **EDIT** (WIP) | `_LOCAL_NOW` new shape; `local_music_play` no subprocess; `set_local_now`/`clear_local_now`/`_local_active`/`_local_or_spotify`; `now_playing_payload` local branch; transport routing in `spotify_command`. |
| `backend/zendaya_state_server.py` | **EDIT** (clean) | `NowPlayingIn` model + `/music/list`, `/music/stream/{id}`, `/music/now` routes; add `HTTPException` import. |
| `backend/zendaya.py` | **UNTOUCHED** | already routes `play`, broadcasts `now_playing`, runs the edge-triggered poll loop. |
| `backend/tests/test_hud_music.py` | **NEW** | unit tests for `zendaya_hud_music`. |
| `backend/tests/test_local_music.py` | **NEW** | unit tests for the no-subprocess local path. |
| `backend/tests/test_music_routes.py` | **NEW** | TestClient tests for `/music/*`. |
| `zendaya-hud-react/src/music/queue.ts` | **NEW** | pure `nextTrack`/`prevTrack` + `QueueTrack` type. |
| `zendaya-hud-react/src/api/music.ts` | **NEW** | `fetchTrackList`, `streamUrl`, `postNowPlaying`. |
| `zendaya-hud-react/src/store/zendayaStore.ts` | **EDIT** | `NowPlaying` += `streamUrl?`/`trackId?`; `musicCmd` + `pushMusicCmd`. |
| `zendaya-hud-react/src/hooks/useWebSocket.ts` | **EDIT** | map `stream_url`/`track_id`; `music_control` action → `pushMusicCmd`. |
| `zendaya-hud-react/src/components/HUD/MusicPlayer.tsx` | **EDIT** | `<audio>` wiring, local transport, real progress/seek, auto-advance, react to `musicCmd`. |
| `zendaya-hud-react/src/__tests__/*` | **NEW** | `queue.test.ts`, `music-api.test.ts`, `musicStore.test.ts`, `MusicPlayer.test.tsx`; additions to `useWebSocket.test.ts`. |

### Load-bearing assumption (do not break)

The reload trigger in `MusicPlayer` is **"`trackId` changed"** — nothing more. This is safe **only because** `zendaya.py`'s `_now_playing_loop` is **edge-triggered on `(track, is_playing)`** and reads the same `_LOCAL_NOW` the HUD writes via `POST /music/now`. A poll broadcast therefore only ever carries a `trackId` once `_LOCAL_NOW` already equals it, so an echo of the HUD's own local navigation matches `currentIdRef` and is ignored. `zendaya.py` is protected and unchanged; if its poll loop ever stops being edge-triggered, revisit this.

---

## Task 1: `zendaya_hud_music.py` — track identity, listing, resolution

**Files:**
- Create: `backend/zendaya_hud_music.py`
- Test: `backend/tests/test_hud_music.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_hud_music.py`:

```python
"""Unit tests for zendaya_hud_music (SP-3 local-music identity/resolution)."""
from __future__ import annotations

import pytest


@pytest.fixture()
def music_lib(tmp_path, monkeypatch):
    """A temp music dir with two fake audio files; patch the canonical scanner."""
    a = tmp_path / "Song A.mp3"
    sub = tmp_path / "sub"
    sub.mkdir(parents=True)
    b = sub / "Song B.flac"
    a.write_bytes(b"ID3fake-a")
    b.write_bytes(b"fLaCfake-b")

    import zendaya_spotify as sp
    monkeypatch.setattr(sp, "_music_dirs", lambda: [tmp_path])
    return tmp_path, a, b


def test_track_id_is_stable_and_opaque(music_lib):
    import zendaya_hud_music as hm
    _, a, _ = music_lib
    first = hm.track_id(a)
    assert first == hm.track_id(a)            # stable across calls
    assert len(first) == 16                    # 16 hex chars
    assert str(a) not in first                 # opaque: no path leaked


def test_list_tracks_shape(music_lib):
    import zendaya_hud_music as hm
    rows = hm.list_tracks()
    assert len(rows) == 2
    assert {r["title"] for r in rows} == {"Song A", "Song B"}
    for r in rows:
        assert set(r) == {"id", "title", "artist", "duration_ms", "stream_url"}
        assert r["stream_url"] == f"/music/stream/{r['id']}"


def test_resolve_valid_id_returns_path(music_lib):
    import zendaya_hud_music as hm
    _, a, _ = music_lib
    assert hm.resolve(hm.track_id(a)) == a


def test_resolve_unknown_id_returns_none(music_lib):
    import zendaya_hud_music as hm
    assert hm.resolve("deadbeefdeadbeef") is None


def test_resolve_traversal_id_returns_none(music_lib):
    import zendaya_hud_music as hm
    # An id computed for a file OUTSIDE the library never matches a scanned track.
    outside = hm.track_id("C:/Windows/system32/notepad.exe")
    assert hm.resolve(outside) is None


def test_track_info_returns_metadata(music_lib):
    import zendaya_hud_music as hm
    _, a, _ = music_lib
    info = hm.track_info(hm.track_id(a))
    assert info is not None
    assert info["title"] == "Song A"
    assert info["path"] == str(a)
    assert "duration_ms" in info


def test_select_picks_a_track(music_lib):
    import zendaya_hud_music as hm
    sel = hm.select("Song A")
    assert sel is not None
    assert sel["title"] == "Song A"
    assert sel["id"] == hm.track_id(sel["path"])


def test_select_none_when_no_library(monkeypatch):
    import zendaya_spotify as sp
    monkeypatch.setattr(sp, "_music_dirs", lambda: [])
    import zendaya_hud_music as hm
    assert hm.select(None) is None


def test_emit_control_calls_set_action(monkeypatch):
    import zendaya_state_server as ss
    seen = []
    monkeypatch.setattr(ss, "set_action", lambda name, payload=None: seen.append((name, payload)))
    import zendaya_hud_music as hm
    hm.emit_control("next")
    assert seen == [("music_control", {"cmd": "next"})]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_hud_music.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'zendaya_hud_music'`.

- [ ] **Step 3: Create the module**

Create `backend/zendaya_hud_music.py`:

```python
"""
zendaya_hud_music.py
====================
Local-music identity, listing, resolution, and streaming support for the
in-HUD music player (SP-3). The HUD's <audio> element is the playback
authority; this module gives each local track a stable, opaque id, lists the
library, resolves an id back to a path (with a containment check), serves
display metadata, and lets the backend nudge the HUD's player.

Track scanning is delegated to zendaya_spotify (the canonical owner of the
music-directory configuration) so there is exactly one scanner.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


def track_id(path: Any) -> str:
    """Stable, opaque id for a track: first 16 hex of sha1(absolute path)."""
    ap = os.path.abspath(str(path))
    return hashlib.sha1(ap.encode("utf-8")).hexdigest()[:16]


def stream_url_for(tid: str) -> str:
    """Relative URL the HUD uses as the <audio> source for a track id."""
    return f"/music/stream/{tid}"


def list_tracks() -> List[Dict[str, Any]]:
    """Enumerate the local library as HUD queue entries.

    duration_ms is left 0 here (cheap: no per-file probe); the HUD reads the
    true duration from the <audio> element once a track loads.
    """
    import zendaya_spotify as sp
    out: List[Dict[str, Any]] = []
    for p in sp._scan_local_tracks():
        tid = track_id(p)
        out.append({
            "id": tid,
            "title": p.stem,
            "artist": p.parent.name,
            "duration_ms": 0,
            "stream_url": stream_url_for(tid),
        })
    return out


def resolve(tid: str) -> Optional[Path]:
    """Map a track id back to its Path, or None.

    Only paths discovered by the canonical scanner are ever returned, so an
    attacker-supplied id (e.g. a hash of an arbitrary system path) cannot escape
    the music directories. A commonpath containment check is kept as defense.
    """
    if not tid:
        return None
    import zendaya_spotify as sp
    dirs = [os.path.abspath(str(d)) for d in sp._music_dirs()]
    for p in sp._scan_local_tracks():
        if track_id(p) == tid:
            ap = os.path.abspath(str(p))
            for d in dirs:
                try:
                    if os.path.commonpath([d, ap]) == d:
                        return p
                except ValueError:
                    continue
            return None
    return None


def track_info(tid: str) -> Optional[Dict[str, Any]]:
    """Resolve display metadata for a track id (path/title/artist/duration_ms)."""
    p = resolve(tid)
    if p is None:
        return None
    import zendaya_spotify as sp
    return {
        "path": str(p),
        "title": p.stem,
        "artist": p.parent.name,
        "duration_ms": sp._probe_duration_ms(p),
    }


def select(query: Optional[str]) -> Optional[Dict[str, Any]]:
    """Pick a track for a play request. Returns metadata or None if no library."""
    import zendaya_spotify as sp
    p = sp._pick_local_track(query)
    if p is None:
        return None
    return {
        "path": str(p),
        "id": track_id(p),
        "title": p.stem,
        "artist": p.parent.name,
        "duration_ms": sp._probe_duration_ms(p),
    }


def emit_control(cmd: str) -> None:
    """Nudge the HUD's <audio> player: cmd in play|pause|next|prev.

    Lazy-imports zendaya_state_server to avoid an import cycle (the state server
    imports this module inside its route handlers).
    """
    try:
        import zendaya_state_server as ss
        ss.set_action("music_control", {"cmd": cmd})
    except Exception:
        pass
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_hud_music.py -v`
Expected: PASS — 9 passed.

- [ ] **Step 5: Do NOT commit** (backend group is left unstaged — see Staging policy). Leave the files in the working tree.

---

## Task 2: `zendaya_spotify.py` — no-subprocess local playback + HUD sync

**Files:**
- Modify: `backend/zendaya_spotify.py`
- Test: `backend/tests/test_local_music.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_local_music.py`:

```python
"""Unit tests for the no-subprocess local-music path in zendaya_spotify (SP-3)."""
from __future__ import annotations

import pytest


@pytest.fixture()
def music_lib(tmp_path, monkeypatch):
    track = tmp_path / "Tune One.mp3"
    track.write_bytes(b"ID3fake")
    import zendaya_spotify as sp
    monkeypatch.setattr(sp, "_music_dirs", lambda: [tmp_path])
    monkeypatch.setattr(sp, "spotify_available", lambda: False)  # no Spotify in tests
    sp.clear_local_now()
    return tmp_path, track


def test_local_music_play_does_not_spawn_subprocess(music_lib, monkeypatch):
    import subprocess
    import zendaya_spotify as sp

    def _boom(*a, **k):
        raise AssertionError("local_music_play must not spawn a subprocess")
    monkeypatch.setattr(subprocess, "Popen", _boom)

    msg = sp.local_music_play("Tune One")
    assert msg == "Playing 'Tune One' from your local music."
    assert sp._LOCAL_NOW["track_id"]
    assert sp._LOCAL_NOW["is_playing"] is True
    assert sp._LOCAL_NOW["track"] == "Tune One"


def test_local_music_play_none_without_library(monkeypatch):
    import zendaya_spotify as sp
    monkeypatch.setattr(sp, "_music_dirs", lambda: [])
    assert sp.local_music_play("anything") is None


def test_now_playing_payload_local_has_stream_url_and_no_expiry(music_lib):
    import zendaya_spotify as sp
    sp.local_music_play("Tune One")
    np = sp.now_playing_payload()
    assert np is not None
    assert np["source"] == "local"
    assert np["track_id"]
    assert np["stream_url"] == f"/music/stream/{np['track_id']}"
    assert np["progress_ms"] == 0  # no wall-clock estimation


def test_set_local_now_updates_position_and_state(music_lib):
    import zendaya_spotify as sp
    sp.local_music_play("Tune One")
    tid = sp._LOCAL_NOW["track_id"]
    sp.set_local_now(tid, is_playing=False, position_ms=42000)
    np = sp.now_playing_payload()
    assert np["is_playing"] is False
    assert np["progress_ms"] == 42000


def test_clear_local_now_hides_card(music_lib):
    import zendaya_spotify as sp
    sp.local_music_play("Tune One")
    sp.clear_local_now()
    assert sp.now_playing_payload() is None


def test_spotify_command_pause_routes_to_local(music_lib, monkeypatch):
    import zendaya_spotify as sp
    import zendaya_hud_music as hm
    seen = []
    monkeypatch.setattr(hm, "emit_control", lambda cmd: seen.append(cmd))
    sp.local_music_play("Tune One")
    assert sp.spotify_command("pause music") == "Paused."
    assert seen == ["pause"]


def test_spotify_command_next_routes_to_local(music_lib, monkeypatch):
    import zendaya_spotify as sp
    import zendaya_hud_music as hm
    seen = []
    monkeypatch.setattr(hm, "emit_control", lambda cmd: seen.append(cmd))
    sp.local_music_play("Tune One")
    assert sp.spotify_command("next track") == "Next track."
    assert seen == ["next"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_local_music.py -v`
Expected: FAIL — `AttributeError: module 'zendaya_spotify' has no attribute 'clear_local_now'` (and others).

- [ ] **Step 3a: Replace the `_LOCAL_NOW` / `_LOCAL_PROC` declaration**

In `backend/zendaya_spotify.py`, find:

```python
_LOCAL_AUDIO_EXTS = {".mp3", ".m4a", ".flac", ".wav", ".ogg", ".aac", ".wma"}
_LOCAL_NOW: Dict[str, Any] = {"path": None, "started_at": 0.0, "duration_ms": 0,
                              "track": "", "artist": "", "is_playing": False}
_LOCAL_PROC = None
```

Replace with:

```python
_LOCAL_AUDIO_EXTS = {".mp3", ".m4a", ".flac", ".wav", ".ogg", ".aac", ".wma"}
# The HUD's <audio> element is the playback authority. _LOCAL_NOW mirrors what
# the HUD is playing: the HUD writes position/play state back via POST /music/now
# (see set_local_now). No wall-clock estimation, no auto-expiry.
_LOCAL_NOW: Dict[str, Any] = {"path": None, "track_id": None, "duration_ms": 0,
                              "position_ms": 0, "track": "", "artist": "",
                              "is_playing": False}
```

- [ ] **Step 3b: Replace `local_music_play` (drop the subprocess)**

Find the whole `local_music_play` function:

```python
def local_music_play(query: Optional[str] = None) -> Optional[str]:
    """Play a track from the local music folder via the system default player.
    Returns a status message on success, None if no local library exists."""
    global _LOCAL_PROC
    track = _pick_local_track(query)
    if not track:
        return None
    try:
        import subprocess
        if _LOCAL_PROC is not None:
            try:
                _LOCAL_PROC.terminate()
            except Exception:
                pass
        _LOCAL_PROC = subprocess.Popen(
            ["cmd", "/c", "start", "", "/MIN", str(track)],
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        return f"Couldn't start local playback: {e}"

    duration_ms = _probe_duration_ms(track)
    _LOCAL_NOW.update({
        "path": str(track),
        "started_at": time.time(),
        "duration_ms": duration_ms,
        "track": track.stem,
        "artist": track.parent.name,
        "is_playing": True,
    })
    return f"Playing '{track.stem}' from your local music."
```

Replace with:

```python
def local_music_play(query: Optional[str] = None) -> Optional[str]:
    """Select a local track for the HUD to play in its own <audio> element.
    Returns a status message on success, None if no local library exists.
    Does NOT spawn any external player."""
    import zendaya_hud_music as hud_music
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
    import zendaya_hud_music as hud_music
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
        import zendaya_hud_music as hud_music
        hud_music.emit_control(cmd)
        return ok_msg
    return spotify_fn()
```

> Note: `_pick_local_track`, `_scan_local_tracks`, `_music_dirs`, and `_probe_duration_ms` remain in the file — `zendaya_hud_music` reuses them. Only `_LOCAL_PROC` and the `started_at` field are removed.

- [ ] **Step 3c: Route transport commands to local in `spotify_command`**

In `spotify_command`, find these four branches:

```python
    if re.fullmatch(r"\s*(?:pause|stop)\s+(?:the\s+)?(?:music|spotify|song)\s*", lt) \
            or re.fullmatch(r"\s*spotify\s+(?:pause|stop)\s*", lt):
        return spotify_pause()

    if re.fullmatch(r"\s*(?:resume|continue|unpause)\s+(?:the\s+)?(?:music|spotify|song)\s*", lt):
        return spotify_resume()

    if re.fullmatch(r"\s*(?:skip|next)\s+(?:the\s+)?(?:song|track)\s*", lt) \
            or re.fullmatch(r"\s*(?:skip|next)\s+(?:on\s+)?spotify\s*", lt) \
            or re.fullmatch(r"\s*spotify\s+(?:skip|next)\s*", lt):
        return spotify_next()

    if re.fullmatch(r"\s*(?:previous|back|last)\s+(?:song|track)\s*", lt) \
            or re.fullmatch(r"\s*(?:go\s+back|previous)\s+(?:on\s+)?spotify\s*", lt):
        return spotify_previous()
```

Replace with (same regexes, routed through `_local_or_spotify`):

```python
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
```

- [ ] **Step 3d: Rewrite the `now_playing_payload` local branch**

Find the local-fallback block at the end of `now_playing_payload`:

```python
    # Local fallback
    if _LOCAL_NOW.get("path") and _LOCAL_NOW.get("is_playing"):
        elapsed_ms = int((time.time() - _LOCAL_NOW["started_at"]) * 1000)
        dur = _LOCAL_NOW["duration_ms"] or 0
        if dur and elapsed_ms > dur + 2000:
            _LOCAL_NOW["is_playing"] = False
            return None
        return {
            "track": _LOCAL_NOW["track"],
            "artist": _LOCAL_NOW["artist"],
            "album": "",
            "art_url": "",
            "is_playing": True,
            "progress_ms": min(elapsed_ms, dur or elapsed_ms),
            "duration_ms": dur,
            "source": "local",
        }
    return None
```

Replace with:

```python
    # Local fallback — the HUD owns playback; we mirror the snapshot it writes
    # via POST /music/now (no wall-clock estimation, no auto-expiry).
    if _LOCAL_NOW.get("track_id"):
        import zendaya_hud_music as hud_music
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_local_music.py -v`
Expected: PASS — 7 passed.

- [ ] **Step 5: Do NOT commit** (backend group stays unstaged).

---

## Task 3: `zendaya_state_server.py` — the `/music/*` routes

**Files:**
- Modify: `backend/zendaya_state_server.py`
- Test: `backend/tests/test_music_routes.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_music_routes.py`:

```python
"""Integration tests for the /music/* routes (SP-3) via FastAPI TestClient."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    track = tmp_path / "Route Song.mp3"
    track.write_bytes(b"ID3audio-bytes-xyz")
    import zendaya_spotify as sp
    monkeypatch.setattr(sp, "_music_dirs", lambda: [tmp_path])
    monkeypatch.setattr(sp, "spotify_available", lambda: False)
    sp.clear_local_now()
    import zendaya_state_server as ss
    return TestClient(ss.app), track


def test_music_list_returns_library(client):
    c, _ = client
    res = c.get("/music/list")
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["title"] == "Route Song"
    assert rows[0]["stream_url"] == f"/music/stream/{rows[0]['id']}"


def test_music_stream_serves_bytes(client):
    c, _ = client
    tid = c.get("/music/list").json()[0]["id"]
    res = c.get(f"/music/stream/{tid}")
    assert res.status_code == 200
    assert res.content == b"ID3audio-bytes-xyz"
    assert res.headers.get("accept-ranges") == "bytes"


def test_music_stream_unknown_id_404(client):
    c, _ = client
    res = c.get("/music/stream/deadbeefdeadbeef")
    assert res.status_code == 404


def test_music_now_updates_and_clears(client):
    c, track = client
    import zendaya_hud_music as hm
    import zendaya_spotify as sp
    tid = hm.track_id(track)
    res = c.post("/music/now", json={"track_id": tid, "is_playing": True, "position_ms": 5000})
    assert res.status_code == 200
    assert sp._LOCAL_NOW["track_id"] == tid
    assert sp._LOCAL_NOW["position_ms"] == 5000
    res2 = c.post("/music/now", json={"track_id": None})
    assert res2.status_code == 200
    assert sp._LOCAL_NOW["track_id"] is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_music_routes.py -v`
Expected: FAIL — all four return 404 (routes not defined yet).

- [ ] **Step 3a: Add `HTTPException` to the FastAPI import**

Find:

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
```

Replace with:

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
```

- [ ] **Step 3b: Add the `NowPlayingIn` model**

Find:

```python
class WindowControlIn(BaseModel):
    action: str
    title: str = ""
```

Insert immediately after it:

```python
class NowPlayingIn(BaseModel):
    track_id: Optional[str] = None
    is_playing: bool = True
    position_ms: int = 0
```

- [ ] **Step 3c: Add the three routes**

Find the `/telemetry` route:

```python
@app.get("/telemetry")
def telemetry():
    return get_telemetry()
```

Insert immediately after it:

```python
# ── Music (SP-3: in-HUD player) ────────────────────────
@app.get("/music/list")
def music_list():
    """List the local music library as HUD queue entries."""
    import zendaya_hud_music as hud_music
    return hud_music.list_tracks()


@app.get("/music/stream/{track_id}")
def music_stream(track_id: str):
    """Stream a local track's bytes (FileResponse provides HTTP Range → seeking)."""
    import zendaya_hud_music as hud_music
    path = hud_music.resolve(track_id)
    if path is None:
        raise HTTPException(status_code=404, detail="track not found")
    return FileResponse(str(path))


@app.post("/music/now")
def music_now(payload: NowPlayingIn):
    """Single-writer sync from the HUD: it owns playback, we mirror + rebroadcast."""
    import zendaya_spotify as sp
    if payload.track_id is None:
        sp.clear_local_now()
        set_now_playing(None)
        return {"ok": True}
    sp.set_local_now(payload.track_id, payload.is_playing, payload.position_ms)
    set_now_playing(sp.now_playing_payload())
    return {"ok": True}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_music_routes.py -v`
Expected: PASS — 4 passed.

- [ ] **Step 5: Run the whole backend music group + confirm no regression**

Run: `cd backend && python -m pytest tests/test_hud_music.py tests/test_local_music.py tests/test_music_routes.py tests/test_state_server_broadcast.py -v`
Expected: PASS — 30 passed (9 + 7 + 4 + 10).

- [ ] **Step 6: Do NOT commit.** Leave the entire backend group unstaged for the user. Run `git status` and confirm `backend/zendaya_hud_music.py`, `backend/zendaya_spotify.py`, `backend/zendaya_state_server.py`, and the three new test files appear as untracked/modified and nothing is staged.

---

## Task 4: `src/music/queue.ts` — pure queue navigation

**Files:**
- Create: `zendaya-hud-react/src/music/queue.ts`
- Test: `zendaya-hud-react/src/__tests__/queue.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `zendaya-hud-react/src/__tests__/queue.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import { nextTrack, prevTrack, type QueueTrack } from "../music/queue";

const mk = (id: string): QueueTrack => ({ id, title: id, artist: "", duration_ms: 0, stream_url: `/music/stream/${id}` });
const L = [mk("a"), mk("b"), mk("c")];

describe("nextTrack", () => {
  it("returns the following track", () => expect(nextTrack(L, "a")?.id).toBe("b"));
  it("wraps around past the last", () => expect(nextTrack(L, "c")?.id).toBe("a"));
  it("unknown current → first", () => expect(nextTrack(L, "zzz")?.id).toBe("a"));
  it("empty list → null", () => expect(nextTrack([], "a")).toBeNull());
});

describe("prevTrack", () => {
  it("returns the preceding track", () => expect(prevTrack(L, "b")?.id).toBe("a"));
  it("wraps around before the first", () => expect(prevTrack(L, "a")?.id).toBe("c"));
  it("unknown current → first", () => expect(prevTrack(L, "zzz")?.id).toBe("a"));
  it("empty list → null", () => expect(prevTrack([], "a")).toBeNull());
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- queue.test`
Expected: FAIL — cannot resolve `../music/queue`.

- [ ] **Step 3: Create the module**

Create `zendaya-hud-react/src/music/queue.ts`:

```typescript
export interface QueueTrack {
  id: string;
  title: string;
  artist: string;
  duration_ms: number;
  stream_url: string;
}

/** The track after `currentId` (wraps to first). Empty → null; unknown id → first. */
export function nextTrack(list: QueueTrack[], currentId: string | null | undefined): QueueTrack | null {
  if (list.length === 0) return null;
  const i = list.findIndex((t) => t.id === currentId);
  if (i === -1) return list[0];
  return list[(i + 1) % list.length];
}

/** The track before `currentId` (wraps to last). Empty → null; unknown id → first. */
export function prevTrack(list: QueueTrack[], currentId: string | null | undefined): QueueTrack | null {
  if (list.length === 0) return null;
  const i = list.findIndex((t) => t.id === currentId);
  if (i === -1) return list[0];
  return list[(i - 1 + list.length) % list.length];
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix zendaya-hud-react run test -- queue.test`
Expected: PASS — 8 passed.

- [ ] **Step 5: Commit**

```bash
git add zendaya-hud-react/src/music/queue.ts zendaya-hud-react/src/__tests__/queue.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): pure queue navigation for the in-HUD music player (SP-3)"
git status
```
Confirm only those two files were committed; nothing under `backend/` or protected paths.

---

## Task 5: `src/api/music.ts` — list / stream-URL / now-playing sync

**Files:**
- Create: `zendaya-hud-react/src/api/music.ts`
- Test: `zendaya-hud-react/src/__tests__/music-api.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `zendaya-hud-react/src/__tests__/music-api.test.ts`:

```typescript
import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchTrackList, streamUrl, postNowPlaying } from "../api/music";

afterEach(() => vi.restoreAllMocks());

describe("streamUrl", () => {
  it("builds an absolute URL from a track id", () => {
    expect(streamUrl("abc123")).toBe("http://127.0.0.1:7475/music/stream/abc123");
  });
  it("prefixes a relative stream_url with the origin", () => {
    expect(streamUrl("/music/stream/abc123")).toBe("http://127.0.0.1:7475/music/stream/abc123");
  });
});

describe("fetchTrackList", () => {
  it("returns the parsed list on success", async () => {
    const rows = [{ id: "a", title: "A", artist: "", duration_ms: 0, stream_url: "/music/stream/a" }];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(rows) }));
    expect(await fetchTrackList()).toEqual(rows);
  });
  it("returns [] on a non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    expect(await fetchTrackList()).toEqual([]);
  });
  it("returns [] when fetch throws", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    expect(await fetchTrackList()).toEqual([]);
  });
});

describe("postNowPlaying", () => {
  it("POSTs the body as JSON to /music/now", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    await postNowPlaying({ track_id: "a", is_playing: true, position_ms: 1000 });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:7475/music/now");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ track_id: "a", is_playing: true, position_ms: 1000 });
  });
  it("swallows fetch errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    await expect(postNowPlaying({ track_id: "a", is_playing: true, position_ms: 0 })).resolves.toBeUndefined();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- music-api.test`
Expected: FAIL — cannot resolve `../api/music`.

- [ ] **Step 3: Create the module**

Create `zendaya-hud-react/src/api/music.ts`:

```typescript
import { backendHttpOrigin } from "./backend";
import type { QueueTrack } from "../music/queue";

/** GET the local library as a queue. Returns [] on any failure. */
export async function fetchTrackList(): Promise<QueueTrack[]> {
  try {
    const res = await fetch(`${backendHttpOrigin()}/music/list`);
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? (data as QueueTrack[]) : [];
  } catch {
    return [];
  }
}

/** Absolute <audio> source URL for a track id or a relative stream_url. */
export function streamUrl(idOrUrl: string): string {
  const origin = backendHttpOrigin();
  return idOrUrl.startsWith("/") ? `${origin}${idOrUrl}` : `${origin}/music/stream/${idOrUrl}`;
}

/** Tell the backend what the HUD is playing now (best-effort; ignores failure). */
export async function postNowPlaying(body: {
  track_id: string | null;
  is_playing: boolean;
  position_ms: number;
}): Promise<void> {
  try {
    await fetch(`${backendHttpOrigin()}/music/now`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    /* ignore */
  }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix zendaya-hud-react run test -- music-api.test`
Expected: PASS — 7 passed.

- [ ] **Step 5: Commit**

```bash
git add zendaya-hud-react/src/api/music.ts zendaya-hud-react/src/__tests__/music-api.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): music API client — list, stream URL, now-playing sync (SP-3)"
git status
```

---

## Task 6: store — `NowPlaying` stream fields + `musicCmd`

**Files:**
- Modify: `zendaya-hud-react/src/store/zendayaStore.ts`
- Test: `zendaya-hud-react/src/__tests__/musicStore.test.ts`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/musicStore.test.ts`:

```typescript
import { beforeEach, describe, expect, it } from "vitest";
import { useZendaya } from "../store/zendayaStore";

beforeEach(() => useZendaya.setState({ musicCmd: null }));

describe("pushMusicCmd", () => {
  it("stores the command with a monotonic seq that re-fires on repeats", () => {
    useZendaya.getState().pushMusicCmd("next");
    const a = useZendaya.getState().musicCmd!;
    expect(a.cmd).toBe("next");
    useZendaya.getState().pushMusicCmd("next");
    const b = useZendaya.getState().musicCmd!;
    expect(b.cmd).toBe("next");
    expect(b.seq).toBeGreaterThan(a.seq);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- musicStore.test`
Expected: FAIL — `pushMusicCmd is not a function`.

- [ ] **Step 3a: Extend the `NowPlaying` interface**

Find:

```typescript
export interface NowPlaying {
  track: string;
  artist: string;
  album?: string;
  artUrl?: string;
  is_playing: boolean;
  progress_ms: number;
  duration_ms: number;
  source: "spotify" | "local";
}
```

Replace with:

```typescript
export interface NowPlaying {
  track: string;
  artist: string;
  album?: string;
  artUrl?: string;
  is_playing: boolean;
  progress_ms: number;
  duration_ms: number;
  source: "spotify" | "local";
  streamUrl?: string;
  trackId?: string;
}
```

- [ ] **Step 3b: Add `musicCmd` to the state shape**

Find:

```typescript
  notifications: Notification[];
  nowPlaying: NowPlaying | null;
  terminalLog: TerminalLine[];
```

Replace with:

```typescript
  notifications: Notification[];
  nowPlaying: NowPlaying | null;
  musicCmd: { cmd: string; seq: number } | null;
  terminalLog: TerminalLine[];
```

- [ ] **Step 3c: Declare the setter**

Find:

```typescript
  setNowPlaying: (np: NowPlaying | null) => void;
```

Replace with:

```typescript
  setNowPlaying: (np: NowPlaying | null) => void;
  pushMusicCmd: (cmd: string) => void;
```

- [ ] **Step 3d: Add the `_mseq` counter**

Find:

```typescript
let _nid = 0;
let _tid = 0;
```

Replace with:

```typescript
let _nid = 0;
let _tid = 0;
let _mseq = 0;
```

- [ ] **Step 3e: Add the initial value**

Find (the initial-state block):

```typescript
  notifications: [],
  nowPlaying: null,
  terminalLog: [],
```

Replace with:

```typescript
  notifications: [],
  nowPlaying: null,
  musicCmd: null,
  terminalLog: [],
```

- [ ] **Step 3f: Implement the setter**

Find:

```typescript
  setNowPlaying: (np) =>
    set((s) => ({
      nowPlaying: np,
      docked: np !== null ? true : s.activeModule !== "none",
    })),
```

Replace with:

```typescript
  setNowPlaying: (np) =>
    set((s) => ({
      nowPlaying: np,
      docked: np !== null ? true : s.activeModule !== "none",
    })),
  pushMusicCmd: (cmd) => set({ musicCmd: { cmd, seq: ++_mseq } }),
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix zendaya-hud-react run test -- musicStore.test`
Expected: PASS — 1 passed.

- [ ] **Step 5: Commit**

```bash
git add zendaya-hud-react/src/store/zendayaStore.ts zendaya-hud-react/src/__tests__/musicStore.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): store — now-playing stream fields + music command channel (SP-3)"
git status
```

---

## Task 7: `useWebSocket.ts` — map stream fields + `music_control` action

**Files:**
- Modify: `zendaya-hud-react/src/hooks/useWebSocket.ts`
- Test: `zendaya-hud-react/src/__tests__/useWebSocket.test.ts` (additions)

- [ ] **Step 1: Add the failing tests**

In `zendaya-hud-react/src/__tests__/useWebSocket.test.ts`, first add `musicCmd: null,` to the `beforeEach` reset. Find:

```typescript
    nowPlaying: null,
    visemes: { aa: 0, ih: 0, ee: 0, oh: 0, ou: 0 },
```

Replace with:

```typescript
    nowPlaying: null,
    musicCmd: null,
    visemes: { aa: 0, ih: 0, ee: 0, oh: 0, ou: 0 },
```

Then append these two describe blocks at the end of the file:

```typescript
describe("useWebSocket — now_playing maps stream fields", () => {
  it("maps stream_url/track_id into the store", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({
      now_playing: {
        track: "Song", artist: "Artist", is_playing: true,
        progress_ms: 0, duration_ms: 0, source: "local",
        stream_url: "/music/stream/abc", track_id: "abc",
      },
    });
    const np = useZendaya.getState().nowPlaying!;
    expect(np.streamUrl).toBe("/music/stream/abc");
    expect(np.trackId).toBe("abc");
  });
});

describe("useWebSocket — music_control action", () => {
  it("pushes a known transport command", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ action: "music_control", payload: { cmd: "next" } });
    expect(useZendaya.getState().musicCmd?.cmd).toBe("next");
  });
  it("ignores an unknown transport command", async () => {
    useZendaya.setState({ musicCmd: null });
    const { ws } = await freshHook();
    ws.fireMessage({ action: "music_control", payload: { cmd: "explode" } });
    expect(useZendaya.getState().musicCmd).toBeNull();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm --prefix zendaya-hud-react run test -- useWebSocket.test`
Expected: FAIL — `streamUrl`/`trackId` are `undefined`; `musicCmd` stays `null` for the "next" case.

- [ ] **Step 3a: Map the stream fields in the `now_playing` handler**

In `zendaya-hud-react/src/hooks/useWebSocket.ts`, find:

```typescript
            z.setNowPlaying({
              track: np.track,
              artist: np.artist ?? "",
              album: np.album,
              artUrl: np.art_url,
              is_playing: !!np.is_playing,
              progress_ms: np.progress_ms ?? 0,
              duration_ms: np.duration_ms ?? 0,
              source: np.source === "local" ? "local" : "spotify",
            });
```

Replace with:

```typescript
            z.setNowPlaying({
              track: np.track,
              artist: np.artist ?? "",
              album: np.album,
              artUrl: np.art_url,
              is_playing: !!np.is_playing,
              progress_ms: np.progress_ms ?? 0,
              duration_ms: np.duration_ms ?? 0,
              source: np.source === "local" ? "local" : "spotify",
              streamUrl: typeof np.stream_url === "string" ? np.stream_url : undefined,
              trackId: typeof np.track_id === "string" ? np.track_id : undefined,
            });
```

- [ ] **Step 3b: Add the `music_control` case to `dispatchAction`**

Find (the end of the `switch` in `dispatchAction`):

```typescript
    case "set_theme":
      setThemeById(typeof payload.name === "string" ? payload.name : "");
      break;
    default:
      // unknown action — ignore silently
      break;
```

Replace with:

```typescript
    case "set_theme":
      setThemeById(typeof payload.name === "string" ? payload.name : "");
      break;
    case "music_control": {
      const cmd = typeof payload.cmd === "string" ? payload.cmd : "";
      if (cmd === "play" || cmd === "pause" || cmd === "next" || cmd === "prev") {
        useZendaya.getState().pushMusicCmd(cmd);
      }
      break;
    }
    default:
      // unknown action — ignore silently
      break;
```

> `useZendaya` is already imported at the top of `useWebSocket.ts` — no new import needed.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm --prefix zendaya-hud-react run test -- useWebSocket.test`
Expected: PASS — all useWebSocket tests green (existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add zendaya-hud-react/src/hooks/useWebSocket.ts zendaya-hud-react/src/__tests__/useWebSocket.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): WS maps stream fields + routes music_control to the player (SP-3)"
git status
```

---

## Task 8: `MusicPlayer.tsx` — `<audio>` playback, transport, seek, auto-advance

**Files:**
- Modify: `zendaya-hud-react/src/components/HUD/MusicPlayer.tsx`
- Test: `zendaya-hud-react/src/__tests__/MusicPlayer.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/MusicPlayer.test.tsx`:

```tsx
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, cleanup, waitFor } from "@testing-library/react";
import MusicPlayer from "../components/HUD/MusicPlayer";
import { useZendaya } from "../store/zendayaStore";

const NP = (over: Partial<any> = {}) => ({
  track: "A", artist: "", is_playing: true,
  progress_ms: 0, duration_ms: 0, source: "local" as const,
  streamUrl: "/music/stream/aaa", trackId: "aaa", ...over,
});

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]) }));
  useZendaya.setState({ nowPlaying: null, musicCmd: null });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("MusicPlayer", () => {
  it("always renders the <audio> element", () => {
    const { getByTestId } = render(<MusicPlayer />);
    expect(getByTestId("hud-audio").tagName).toBe("AUDIO");
  });

  it("loads the backend-selected track into <audio>", async () => {
    const { getByTestId } = render(<MusicPlayer />);
    useZendaya.setState({ nowPlaying: NP() });
    await waitFor(() => {
      const a = getByTestId("hud-audio") as HTMLAudioElement;
      expect(a.getAttribute("src")).toBe("http://127.0.0.1:7475/music/stream/aaa");
    });
  });

  it("reloads when the backend selects a different trackId", async () => {
    const { getByTestId } = render(<MusicPlayer />);
    const a = getByTestId("hud-audio") as HTMLAudioElement;
    useZendaya.setState({ nowPlaying: NP() });
    await waitFor(() => expect(a.getAttribute("src")).toContain("/aaa"));
    useZendaya.setState({ nowPlaying: NP({ track: "B", streamUrl: "/music/stream/bbb", trackId: "bbb" }) });
    await waitFor(() => expect(a.getAttribute("src")).toContain("/bbb"));
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- MusicPlayer.test`
Expected: FAIL — no `hud-audio` test id (the current component renders no `<audio>`).

- [ ] **Step 3: Replace the component**

Replace the entire contents of `zendaya-hud-react/src/components/HUD/MusicPlayer.tsx` with:

```tsx
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useZendaya } from "../../store/zendayaStore";
import { fetchTrackList, streamUrl, postNowPlaying } from "../../api/music";
import { nextTrack, prevTrack, type QueueTrack } from "../../music/queue";

function fmt(ms: number) {
  const s = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}:${rem.toString().padStart(2, "0")}`;
}

function safePlay(a: HTMLAudioElement) {
  try {
    const p = a.play();
    if (p && typeof (p as Promise<void>).catch === "function") {
      (p as Promise<void>).catch(() => {/* autoplay blocked until a user gesture */});
    }
  } catch {
    /* happy-dom / autoplay */
  }
}

export default function MusicPlayer() {
  const np = useZendaya((s) => s.nowPlaying);
  const musicCmd = useZendaya((s) => s.musicCmd);

  const audioRef = useRef<HTMLAudioElement>(null);
  const currentIdRef = useRef<string | null>(null);
  const queueRef = useRef<QueueTrack[]>([]);

  const [playing, setPlaying] = useState(false);
  const [curMs, setCurMs] = useState(0);
  const [durMs, setDurMs] = useState(0);

  // Build the queue once (best-effort; empty if the backend is offline).
  useEffect(() => {
    let alive = true;
    fetchTrackList().then((list) => { if (alive) queueRef.current = list; });
    return () => { alive = false; };
  }, []);

  // Load a track into <audio>, optionally play it, and mirror the state back.
  function loadAndPlay(id: string, url: string, play: boolean, seekMs = 0) {
    const a = audioRef.current;
    if (!a) return;
    currentIdRef.current = id;
    a.src = streamUrl(url || id);
    try { a.load(); } catch { /* happy-dom */ }
    if (seekMs > 0) { try { a.currentTime = seekMs / 1000; } catch { /* ignore */ } }
    if (play) safePlay(a);
    postNowPlaying({ track_id: id, is_playing: play, position_ms: seekMs });
  }

  function advance(dir: 1 | -1) {
    const list = queueRef.current;
    const pick = dir === 1
      ? nextTrack(list, currentIdRef.current)
      : prevTrack(list, currentIdRef.current);
    if (!pick) return;
    loadAndPlay(pick.id, pick.stream_url, true);
  }

  // React to a NEW backend-selected track (e.g. "play some jazz"). Reload is
  // triggered ONLY by a trackId change — safe because zendaya.py's poll loop is
  // edge-triggered on (track, is_playing), so an echo of our own local
  // navigation carries the trackId we already hold and is ignored here.
  useEffect(() => {
    if (!np || !np.trackId) return;
    if (np.trackId === currentIdRef.current) return;
    loadAndPlay(np.trackId, np.streamUrl ?? np.trackId, np.is_playing);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [np?.trackId]);

  // Apply a voice/chat transport command (re-fires on every seq bump).
  useEffect(() => {
    if (!musicCmd) return;
    const a = audioRef.current;
    if (!a) return;
    switch (musicCmd.cmd) {
      case "play": safePlay(a); break;
      case "pause": try { a.pause(); } catch { /* ignore */ } break;
      case "next": advance(1); break;
      case "prev": advance(-1); break;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [musicCmd?.seq]);

  function togglePlay() {
    const a = audioRef.current;
    if (!a) return;
    if (a.paused) safePlay(a); else a.pause();
  }

  function seek(e: React.MouseEvent<HTMLDivElement>) {
    const a = audioRef.current;
    if (!a || !a.duration || !isFinite(a.duration)) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const t = pct * a.duration;
    try { a.currentTime = t; } catch { /* ignore */ }
    setCurMs(t * 1000);
    postNowPlaying({ track_id: currentIdRef.current, is_playing: !a.paused, position_ms: Math.floor(t * 1000) });
  }

  const pct = durMs > 0 ? Math.min(100, (curMs / durMs) * 100) : 0;

  return (
    <>
      <audio
        ref={audioRef}
        data-testid="hud-audio"
        onTimeUpdate={(e) => setCurMs(e.currentTarget.currentTime * 1000)}
        onLoadedMetadata={(e) => { const d = e.currentTarget.duration; setDurMs(isFinite(d) ? d * 1000 : 0); }}
        onDurationChange={(e) => { const d = e.currentTarget.duration; setDurMs(isFinite(d) ? d * 1000 : 0); }}
        onPlay={() => {
          setPlaying(true);
          const a = audioRef.current;
          postNowPlaying({ track_id: currentIdRef.current, is_playing: true, position_ms: Math.floor((a?.currentTime ?? 0) * 1000) });
        }}
        onPause={() => {
          setPlaying(false);
          const a = audioRef.current;
          postNowPlaying({ track_id: currentIdRef.current, is_playing: false, position_ms: Math.floor((a?.currentTime ?? 0) * 1000) });
        }}
        onEnded={() => advance(1)}
        onError={() => advance(1)}
      />
      <AnimatePresence>
        {np && (
          <motion.div
            key="music-player"
            initial={{ opacity: 0, y: 30, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
            className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 zen-player-card pointer-events-auto"
            style={{ width: "min(440px, 86vw)", padding: "24px 26px 22px" }}
          >
            <div className="flex items-center gap-4">
              <div
                className="rounded-xl overflow-hidden flex-shrink-0"
                style={{
                  width: 84,
                  height: 84,
                  background: np.artUrl
                    ? `url(${np.artUrl}) center/cover`
                    : "linear-gradient(135deg, var(--zen-accent), var(--zen-primary))",
                  boxShadow: "0 12px 28px rgba(0,0,0,0.45), 0 0 22px color-mix(in srgb, var(--zen-primary) 35%, transparent)",
                }}
              />
              <div className="flex-1 min-w-0">
                <div className="text-[10px] tracking-[0.32em] uppercase mb-1" style={{ color: "rgba(255,255,255,0.5)" }}>
                  {np.source === "local" ? "Local · Now Playing" : "Spotify · Now Playing"}
                </div>
                <div className="font-semibold text-base truncate" style={{ color: "#fff", letterSpacing: "0.02em" }}>
                  {np.track}
                </div>
                <div className="text-sm truncate" style={{ color: "rgba(255,255,255,0.65)" }}>
                  {np.artist}
                </div>
              </div>
            </div>

            <div className="mt-5 zen-player-progress" onClick={seek} style={{ cursor: "pointer" }}>
              <div className="zen-player-progress-fill" style={{ width: `${pct}%` }} />
            </div>
            <div className="flex justify-between mt-1.5 text-[10px] font-mono" style={{ color: "rgba(255,255,255,0.45)" }}>
              <span>{fmt(curMs)}</span>
              <span>{fmt(durMs)}</span>
            </div>

            <div className="flex items-center justify-center gap-3 mt-4">
              <button className="zen-player-btn" onClick={() => advance(-1)} aria-label="Previous">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 6h2v12H6zm3.5 6l8.5-6v12z" /></svg>
              </button>
              <button className="zen-player-btn primary" onClick={togglePlay} aria-label={playing ? "Pause" : "Play"}>
                {playing ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zm8 0h4v14h-4z" /></svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
                )}
              </button>
              <button className="zen-player-btn" onClick={() => advance(1)} aria-label="Next">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M16 6h2v12h-2zM6 6l8.5 6L6 18z" /></svg>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix zendaya-hud-react run test -- MusicPlayer.test`
Expected: PASS — 3 passed.

- [ ] **Step 5: Commit**

```bash
git add zendaya-hud-react/src/components/HUD/MusicPlayer.tsx zendaya-hud-react/src/__tests__/MusicPlayer.test.tsx
git -c commit.gpgsign=false commit -m "feat(hud): play local music in the HUD <audio> with full transport (SP-3)"
git status
```

---

## Task 9: Final verification + manual smoke

**Files:** none (verification only)

- [ ] **Step 1: Full backend music suite**

Run: `cd backend && python -m pytest tests/test_hud_music.py tests/test_local_music.py tests/test_music_routes.py tests/test_state_server_broadcast.py -v`
Expected: PASS — 30 passed.

- [ ] **Step 2: Full frontend suite**

Run: `npm --prefix zendaya-hud-react run test`
Expected: PASS — the SP-1 baseline (156) plus the SP-3 additions (queue 8, music-api 7, musicStore 1, MusicPlayer 3, useWebSocket +3) all green.

- [ ] **Step 3: Type-check + production build**

Run: `npm --prefix zendaya-hud-react run build`
Expected: exit 0 (the pre-existing dynamic-import advisory about `zendayaStore.ts` is benign and unrelated).

- [ ] **Step 4: Confirm staging hygiene**

Run: `git status`
Expected: the 5 frontend SP-3 commits are present on `main`; the backend changes (`zendaya_hud_music.py`, `zendaya_spotify.py`, `zendaya_state_server.py`, the three new backend tests) sit **unstaged/untracked** in the working tree for the user to review; the pre-existing WIP diff and protected paths are untouched and unstaged.

- [ ] **Step 5: Manual live smoke (requires a running backend + a music folder)**

This cannot be automated (happy-dom has no audio/network). With the backend running and `ZENDAYA_MUSIC_DIR` (or `~/Music`) populated, and the HUD open in a browser:

1. Say/type **"play some music"** → a track plays **out of the HUD** (the browser tab), the now-playing card appears, and **no Windows media player opens**.
2. **Play/pause** button toggles audio; the icon flips; the progress bar advances in real time.
3. **Next/Prev** load adjacent tracks (wrap-around at the ends).
4. **Click the progress bar** → audio seeks to that point.
5. Let a track **end** → it auto-advances to the next.
6. Say **"pause"** / **"next track"** → the HUD's player responds (voice nudge path).
7. Reload the page mid-playback → the card reappears from the broadcast snapshot (playback restarts on a user gesture due to browser autoplay policy — click play if needed).

- [ ] **Step 6: Report.** SP-3 is delivered: local music plays inside the HUD with full transport, voice-driven, zero `zendaya.py` changes. Note the backend diff awaits the user's own commit. Tee up SP-2 (voice-from-HUD) or SP-4 (launch & ship) for the next design cycle.

---

## Self-review

**Spec coverage:** Goals 1–5 of the spec each map to tasks — in-HUD playback (T2 `local_music_play` no-subprocess + T8 `<audio>`); transport/seek/auto-advance (T8); voice nudges (T2 `_local_or_spotify` → T7 `music_control` → T8 `musicCmd` effect); no-drift single-writer (T2 `set_local_now` re-derives from id + T3 `/music/now` + the edge-triggered-poll assumption documented); `zendaya.py` untouched (only T1–T3 backend files, `zendaya.py` not in any file list). New wire contract (`stream_url`/`track_id`, `music_control`), all three routes, and the full file map are covered. Error handling (no library → None; 404; traversal; offline → [] queue) is tested in T1–T3, T5, T8.

**Placeholder scan:** none — every code step has complete, copy-pasteable content; every command has an expected result.

**Type/name consistency:** `track_id`/`trackId`, `stream_url`/`streamUrl`, `position_ms`/`progress_ms`, `is_playing`, `musicCmd {cmd, seq}`, `pushMusicCmd`, `QueueTrack`, `nextTrack`/`prevTrack`, `fetchTrackList`/`streamUrl`/`postNowPlaying`, `set_local_now`/`clear_local_now`/`_local_active`/`_local_or_spotify`, `track_info`/`select`/`resolve`/`list_tracks`/`stream_url_for`/`emit_control` — used identically across backend, wire, and frontend. The `now_playing_payload` snapshot keeps the `track`/`is_playing` keys the protected poll loop reads (`np["track"]`, `np["is_playing"]`).
