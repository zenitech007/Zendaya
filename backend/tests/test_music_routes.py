"""Integration tests for the /music/* routes (SP-3) via FastAPI TestClient."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    track = tmp_path / "Route Song.mp3"
    track.write_bytes(b"ID3audio-bytes-xyz")
    import integrations.spotify as sp
    monkeypatch.setattr(sp, "_music_dirs", lambda: [tmp_path])
    monkeypatch.setattr(sp, "spotify_available", lambda: False)
    sp.clear_local_now()
    import server.state_server as ss
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
    import server.hud_music as hm
    import integrations.spotify as sp
    tid = hm.track_id(track)
    res = c.post("/music/now", json={"track_id": tid, "is_playing": True, "position_ms": 5000})
    assert res.status_code == 200
    assert sp._LOCAL_NOW["track_id"] == tid
    assert sp._LOCAL_NOW["position_ms"] == 5000
    res2 = c.post("/music/now", json={"track_id": None})
    assert res2.status_code == 200
    assert sp._LOCAL_NOW["track_id"] is None
