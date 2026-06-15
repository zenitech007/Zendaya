"""Unit tests for the no-subprocess local-music path in integrations.spotify (SP-3)."""
from __future__ import annotations

import pytest


@pytest.fixture()
def music_lib(tmp_path, monkeypatch):
    track = tmp_path / "Tune One.mp3"
    track.write_bytes(b"ID3fake")
    import integrations.spotify as sp
    monkeypatch.setattr(sp, "_music_dirs", lambda: [tmp_path])
    monkeypatch.setattr(sp, "spotify_available", lambda: False)  # no Spotify in tests
    sp.clear_local_now()
    return tmp_path, track


def test_local_music_play_does_not_spawn_subprocess(music_lib, monkeypatch):
    import subprocess
    import integrations.spotify as sp

    def _boom(*a, **k):
        raise AssertionError("local_music_play must not spawn a subprocess")
    monkeypatch.setattr(subprocess, "Popen", _boom)

    msg = sp.local_music_play("Tune One")
    assert msg == "Playing 'Tune One' from your local music."
    assert sp._LOCAL_NOW["track_id"]
    assert sp._LOCAL_NOW["is_playing"] is True
    assert sp._LOCAL_NOW["track"] == "Tune One"


def test_local_music_play_none_without_library(monkeypatch):
    import integrations.spotify as sp
    monkeypatch.setattr(sp, "_music_dirs", lambda: [])
    assert sp.local_music_play("anything") is None


def test_now_playing_payload_local_has_stream_url_and_no_expiry(music_lib):
    import integrations.spotify as sp
    sp.local_music_play("Tune One")
    np = sp.now_playing_payload()
    assert np is not None
    assert np["source"] == "local"
    assert np["track_id"]
    assert np["stream_url"] == f"/music/stream/{np['track_id']}"
    assert np["progress_ms"] == 0  # no wall-clock estimation


def test_set_local_now_updates_position_and_state(music_lib):
    import integrations.spotify as sp
    sp.local_music_play("Tune One")
    tid = sp._LOCAL_NOW["track_id"]
    sp.set_local_now(tid, is_playing=False, position_ms=42000)
    np = sp.now_playing_payload()
    assert np["is_playing"] is False
    assert np["progress_ms"] == 42000


def test_clear_local_now_hides_card(music_lib):
    import integrations.spotify as sp
    sp.local_music_play("Tune One")
    sp.clear_local_now()
    assert sp.now_playing_payload() is None


def test_spotify_command_pause_routes_to_local(music_lib, monkeypatch):
    import integrations.spotify as sp
    import server.hud_music as hm
    seen = []
    monkeypatch.setattr(hm, "emit_control", lambda cmd: seen.append(cmd))
    sp.local_music_play("Tune One")
    assert sp.spotify_command("pause music") == "Paused."
    assert seen == ["pause"]


def test_spotify_command_next_routes_to_local(music_lib, monkeypatch):
    import integrations.spotify as sp
    import server.hud_music as hm
    seen = []
    monkeypatch.setattr(hm, "emit_control", lambda cmd: seen.append(cmd))
    sp.local_music_play("Tune One")
    assert sp.spotify_command("next track") == "Next track."
    assert seen == ["next"]
