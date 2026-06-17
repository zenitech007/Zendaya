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
