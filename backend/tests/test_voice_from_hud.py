"""SP-2 — voice-from-HUD: state-server frames + _stream_pcm_playback routing."""
import base64
import sys
import types

import zendaya_state_server as ss


def _capture(monkeypatch):
    """Capture every payload passed to _broadcast_state_async."""
    sent = []
    monkeypatch.setattr(ss, "_broadcast_state_async", lambda p: sent.append(p))
    return sent


def test_hud_client_count_reflects_ws_clients(monkeypatch):
    monkeypatch.setattr(ss, "_WS_CLIENTS", set())
    assert ss.hud_client_count() == 0
    fake_clients = {object(), object()}
    monkeypatch.setattr(ss, "_WS_CLIENTS", fake_clients)
    assert ss.hud_client_count() == 2


def test_audio_begin_frame(monkeypatch):
    sent = _capture(monkeypatch)
    ss.audio_begin(22050, 7)
    assert sent == [{"audio": {"event": "begin", "rate": 22050, "id": 7}}]


def test_push_audio_chunk_base64_encodes(monkeypatch):
    sent = _capture(monkeypatch)
    pcm = b"\x01\x02\x03\x04"
    ss.push_audio_chunk(pcm, 7, 3)
    assert len(sent) == 1
    frame = sent[0]["audio"]
    assert frame["event"] == "chunk"
    assert frame["id"] == 7
    assert frame["seq"] == 3
    assert base64.b64decode(frame["b64"]) == pcm


def test_audio_end_frame(monkeypatch):
    sent = _capture(monkeypatch)
    ss.audio_end(7)
    assert sent == [{"audio": {"event": "end", "id": 7}}]


def test_audio_stop_frame(monkeypatch):
    sent = _capture(monkeypatch)
    ss.audio_stop()
    assert sent == [{"audio": {"event": "stop"}}]


class _FakeResponse:
    def __init__(self, chunks):
        self._chunks = chunks

    def iter_content(self, chunk_size=4096):
        for c in self._chunks:
            yield c


class _FakeStateServer:
    def __init__(self, client_count):
        self._n = client_count
        self.begin_calls = []
        self.chunk_calls = []
        self.end_calls = []
        self.amp_calls = []
        self.viseme_calls = []

    def hud_client_count(self):
        return self._n

    def audio_begin(self, rate, utt_id):
        self.begin_calls.append((rate, utt_id))

    def push_audio_chunk(self, pcm, utt_id, seq):
        self.chunk_calls.append((pcm, utt_id, seq))

    def audio_end(self, utt_id):
        self.end_calls.append(utt_id)

    def audio_stop(self):
        pass

    def set_amplitude(self, level):
        self.amp_calls.append(level)

    def set_visemes(self, weights):
        self.viseme_calls.append(weights)


class _FakeStream:
    instances = []

    def __init__(self, *a, **k):
        _FakeStream.instances.append(self)
        self.writes = []

    def start(self):
        pass

    def write(self, samples):
        self.writes.append(samples)

    def stop(self):
        pass

    def close(self):
        pass


def _load_zendaya():
    import importlib
    return importlib.import_module("zendaya")


def test_routes_to_hud_when_client_connected(monkeypatch):
    z = _load_zendaya()
    fake_ss = _FakeStateServer(client_count=1)
    _FakeStream.instances = []
    monkeypatch.setattr(z, "_state_server", fake_ss)
    monkeypatch.setattr(z.sd, "OutputStream", _FakeStream)
    # 8 bytes => 4 int16 samples per chunk
    resp = _FakeResponse([b"\x00\x10\x00\x20\x00\x30\x00\x40", b"\x01\x10\x01\x20\x01\x30\x01\x40"])
    z._stream_pcm_playback(resp)
    # HUD path: begin once, a chunk per window, end once — and NO local stream.
    assert len(fake_ss.begin_calls) == 1
    assert len(fake_ss.chunk_calls) == 2
    assert len(fake_ss.end_calls) == 1
    assert _FakeStream.instances == []
    # Lip-sync still fed.
    assert len(fake_ss.amp_calls) >= 1


def test_routes_to_local_speaker_when_no_client(monkeypatch):
    z = _load_zendaya()
    fake_ss = _FakeStateServer(client_count=0)
    _FakeStream.instances = []
    monkeypatch.setattr(z, "_state_server", fake_ss)
    monkeypatch.setattr(z.sd, "OutputStream", _FakeStream)
    resp = _FakeResponse([b"\x00\x10\x00\x20\x00\x30\x00\x40"])
    z._stream_pcm_playback(resp)
    # Local path: a real stream was opened and written to; HUD frames NOT sent.
    assert len(_FakeStream.instances) == 1
    assert len(_FakeStream.instances[0].writes) >= 1
    assert fake_ss.begin_calls == []
    assert fake_ss.chunk_calls == []
    # Lip-sync still fed.
    assert len(fake_ss.amp_calls) >= 1
