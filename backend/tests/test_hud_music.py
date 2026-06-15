"""Unit tests for server.hud_music (SP-3 local-music identity/resolution)."""
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

    import integrations.spotify as sp
    monkeypatch.setattr(sp, "_music_dirs", lambda: [tmp_path])
    return tmp_path, a, b


def test_track_id_is_stable_and_opaque(music_lib):
    import server.hud_music as hm
    _, a, _ = music_lib
    first = hm.track_id(a)
    assert first == hm.track_id(a)            # stable across calls
    assert len(first) == 16                    # 16 hex chars
    assert str(a) not in first                 # opaque: no path leaked


def test_list_tracks_shape(music_lib):
    import server.hud_music as hm
    rows = hm.list_tracks()
    assert len(rows) == 2
    assert {r["title"] for r in rows} == {"Song A", "Song B"}
    for r in rows:
        assert set(r) == {"id", "title", "artist", "duration_ms", "stream_url"}
        assert r["stream_url"] == f"/music/stream/{r['id']}"


def test_resolve_valid_id_returns_path(music_lib):
    import server.hud_music as hm
    _, a, _ = music_lib
    assert hm.resolve(hm.track_id(a)) == a


def test_resolve_unknown_id_returns_none(music_lib):
    import server.hud_music as hm
    assert hm.resolve("deadbeefdeadbeef") is None


def test_resolve_traversal_id_returns_none(music_lib):
    import server.hud_music as hm
    # An id computed for a file OUTSIDE the library never matches a scanned track.
    outside = hm.track_id("C:/Windows/system32/notepad.exe")
    assert hm.resolve(outside) is None


def test_track_info_returns_metadata(music_lib):
    import server.hud_music as hm
    _, a, _ = music_lib
    info = hm.track_info(hm.track_id(a))
    assert info is not None
    assert info["title"] == "Song A"
    assert info["path"] == str(a)
    assert "duration_ms" in info


def test_select_picks_a_track(music_lib):
    import server.hud_music as hm
    sel = hm.select("Song A")
    assert sel is not None
    assert sel["title"] == "Song A"
    assert sel["id"] == hm.track_id(sel["path"])


def test_select_none_when_no_library(monkeypatch):
    import integrations.spotify as sp
    monkeypatch.setattr(sp, "_music_dirs", lambda: [])
    import server.hud_music as hm
    assert hm.select(None) is None


def test_emit_control_calls_set_action(monkeypatch):
    import server.state_server as ss
    seen = []
    monkeypatch.setattr(ss, "set_action", lambda name, payload=None: seen.append((name, payload)))
    import server.hud_music as hm
    hm.emit_control("next")
    assert seen == [("music_control", {"cmd": "next"})]
