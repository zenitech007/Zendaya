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
