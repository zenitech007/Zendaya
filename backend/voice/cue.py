"""Short attention/backchannel clips played through sounddevice, gated so they
never overlap real TTS. Used by the follow-up 'still-listening' cue and by
backchannels during long tasks."""
from __future__ import annotations

import os
import threading

import numpy as np

SAMPLE_RATE = 16000
_LOCK = threading.Lock()


def tone_pcm(freq: float = 660.0, ms: int = 120, samplerate: int = SAMPLE_RATE,
             volume: float = 0.25) -> bytes:
    """A short sine 'blip' with a quick fade in/out, as int16 PCM bytes."""
    n = int(samplerate * ms / 1000)
    t = np.arange(n, dtype=np.float32) / samplerate
    wave = np.sin(2 * np.pi * freq * t).astype(np.float32) * volume
    fade = max(1, n // 8)
    env = np.ones(n, dtype=np.float32)
    env[:fade] = np.linspace(0.0, 1.0, fade)
    env[-fade:] = np.linspace(1.0, 0.0, fade)
    wave *= env
    return (np.clip(wave, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()


def _tts_is_active() -> bool:
    """True while real TTS is speaking (so cues don't talk over her)."""
    try:
        from voice import listener_v2
        return listener_v2._TTS_SPEAKING.is_set()
    except Exception:
        return False


def _raw_play(pcm: bytes, samplerate: int) -> None:
    try:
        import sounddevice as sd
        arr = np.frombuffer(pcm, dtype="<i2")
        sd.play(arr, samplerate=samplerate, blocking=True)
    except Exception as e:
        print(f"(cue play failed: {e})")


def play_pcm(pcm: bytes, samplerate: int = SAMPLE_RATE) -> None:
    """Play a PCM clip unless real TTS is currently active. Serialized so two
    clips never overlap."""
    if not pcm or _tts_is_active():
        return
    with _LOCK:
        if _tts_is_active():
            return
        _raw_play(pcm, samplerate)
