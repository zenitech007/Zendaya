"""
server.hud_music.py
====================
Local-music identity, listing, resolution, and streaming support for the
in-HUD music player (SP-3). The HUD's <audio> element is the playback
authority; this module gives each local track a stable, opaque id, lists the
library, resolves an id back to a path (with a containment check), serves
display metadata, and lets the backend nudge the HUD's player.

Track scanning is delegated to integrations.spotify (the canonical owner of the
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
    import integrations.spotify as sp
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
    import integrations.spotify as sp
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
    import integrations.spotify as sp
    return {
        "path": str(p),
        "title": p.stem,
        "artist": p.parent.name,
        "duration_ms": sp._probe_duration_ms(p),
    }


def select(query: Optional[str]) -> Optional[Dict[str, Any]]:
    """Pick a track for a play request. Returns metadata or None if no library."""
    import integrations.spotify as sp
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

    Lazy-imports server.state_server to avoid an import cycle (the state server
    imports this module inside its route handlers).
    """
    try:
        import server.state_server as ss
        ss.set_action("music_control", {"cmd": cmd})
    except Exception:
        pass
