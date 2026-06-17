"""Pack A conversation-flow tests: cue gating, barge detector, backchannel, follow-up."""
from __future__ import annotations

import numpy as np
import pytest

from voice import cue


def test_tone_pcm_is_int16_and_right_length():
    pcm = cue.tone_pcm(freq=660, ms=120, samplerate=16000)
    arr = np.frombuffer(pcm, dtype="<i2")
    assert arr.dtype == np.int16
    assert abs(len(arr) - int(16000 * 0.120)) <= 2


def test_play_skips_when_tts_active(monkeypatch):
    played = []
    monkeypatch.setattr(cue, "_raw_play", lambda pcm, sr: played.append(len(pcm)))
    monkeypatch.setattr(cue, "_tts_is_active", lambda: True)
    cue.play_pcm(b"\x00\x00" * 100, samplerate=16000)
    assert played == []  # gated out while real TTS speaks


def test_play_runs_when_idle(monkeypatch):
    played = []
    monkeypatch.setattr(cue, "_raw_play", lambda pcm, sr: played.append(len(pcm)))
    monkeypatch.setattr(cue, "_tts_is_active", lambda: False)
    cue.play_pcm(b"\x00\x00" * 100, samplerate=16000)
    assert played == [200]


def test_followup_seconds_env(monkeypatch):
    monkeypatch.setenv("ZENDAYA_FOLLOWUP_S", "7.5")
    import importlib
    from voice import listener_v2
    importlib.reload(listener_v2)
    assert listener_v2._followup_seconds() == 7.5
    monkeypatch.delenv("ZENDAYA_FOLLOWUP_S", raising=False)
    importlib.reload(listener_v2)
    assert listener_v2._followup_seconds() == 10.0


def test_backchannel_plays_a_clip(monkeypatch):
    from voice import listener_v2
    calls = []
    monkeypatch.setattr(listener_v2, "_play_backchannel_clip", lambda: calls.append(1))
    monkeypatch.setenv("ZENDAYA_BACKCHANNEL", "on")
    listener_v2._maybe_backchannel()
    assert calls == [1]


def test_backchannel_off_is_noop(monkeypatch):
    from voice import listener_v2
    calls = []
    monkeypatch.setattr(listener_v2, "_play_backchannel_clip", lambda: calls.append(1))
    monkeypatch.setenv("ZENDAYA_BACKCHANNEL", "off")
    listener_v2._maybe_backchannel()
    assert calls == []


class _StubVAD:
    def __init__(self, speech=True):
        self._speech = speech
    def is_speech(self, frame):
        return self._speech


def _frame(rms, n=512):
    # build an int16 frame with the target normalized RMS
    val = int(rms * 32768)
    return np.full(n, val, dtype=np.int16)


def test_barge_fires_on_sustained_overtalk(monkeypatch):
    from voice import listener_v2
    monkeypatch.delenv("ZENDAYA_BARGE_MARGIN", raising=False)
    det = listener_v2._BargeDetector(_StubVAD(speech=True), trigger_frames=3)
    # establish a low echo/ambient baseline with non-speech-energy frames
    det._baseline = 0.02
    fired = [det.observe(_frame(0.20)) for _ in range(3)]   # loud over-talk
    assert fired[-1] is True


def test_barge_ignores_echo_level_energy(monkeypatch):
    from voice import listener_v2
    det = listener_v2._BargeDetector(_StubVAD(speech=True), trigger_frames=3)
    det._baseline = 0.20            # speakers: baseline already at her echo level
    fired = [det.observe(_frame(0.20)) for _ in range(6)]   # only echo-level energy
    assert not any(fired)


def test_barge_needs_sustained_frames():
    from voice import listener_v2
    det = listener_v2._BargeDetector(_StubVAD(speech=True), trigger_frames=4)
    det._baseline = 0.02
    assert det.observe(_frame(0.30)) is False  # 1 frame
    assert det.observe(_frame(0.30)) is False  # 2
    assert det.observe(_frame(0.02)) is False  # dip resets counter
    assert det.observe(_frame(0.30)) is False  # 1 again


def test_barge_mode_env(monkeypatch):
    from voice import listener_v2
    for val, expected in [("wake", "wake"), ("off", "off"), ("ACOUSTIC", "acoustic"),
                          ("bogus", "acoustic")]:
        monkeypatch.setenv("ZENDAYA_BARGE_MODE", val)
        assert listener_v2._barge_mode() == expected
    monkeypatch.delenv("ZENDAYA_BARGE_MODE", raising=False)
    assert listener_v2._barge_mode() == "acoustic"


def test_backchannel_synth_is_cached(monkeypatch):
    from voice import listener_v2
    monkeypatch.setattr(listener_v2, "_BACKCHANNEL_TEXTS", ("xx",))
    listener_v2._backchannel_idx = 0
    listener_v2._backchannel_cache.clear()
    calls = []
    import voice.offline_tts as ot
    monkeypatch.setattr(ot, "synth_to_pcm", lambda text, target_sr=16000: calls.append(text) or b"\x00\x00")
    from voice import cue
    monkeypatch.setattr(cue, "play_pcm", lambda pcm, samplerate=16000: None)
    listener_v2._play_backchannel_clip()
    listener_v2._play_backchannel_clip()
    assert len(calls) == 1   # synthesized once, then served from cache
