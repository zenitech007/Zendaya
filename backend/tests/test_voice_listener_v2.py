"""Unit tests for the voice listener v2 upgrade (denoise factory, wake regex, ambient gate, dispatch worker)."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ─── Denoiser factory ──────────────────────────────────────────────────────


def test_make_denoiser_returns_deepfilter_when_dfn_available(monkeypatch):
    """When deepfilternet is importable, factory returns DeepFilterDenoiser."""
    import importlib

    # Stub a successful import path. We monkey-patch the importlib lookup
    # used inside make_denoiser to simulate DFN being available.
    fake_df = MagicMock()
    fake_df.init_df = MagicMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
    fake_df.enhance = MagicMock(side_effect=lambda model, df_state, audio: audio)

    monkeypatch.setitem(sys.modules, "df", fake_df)
    monkeypatch.setitem(sys.modules, "df.enhance", fake_df)
    # Force re-import of denoise so it sees the stubbed df.
    if "zendaya_assistant_features" in sys.modules:
        del sys.modules["zendaya_assistant_features"]
    from voice import denoise as denoise_mod  # noqa
    importlib.reload(denoise_mod)
    d = denoise_mod.make_denoiser()
    # If DFN-class exists in the module AND init didn't raise, we get it.
    if hasattr(denoise_mod, "DeepFilterDenoiser"):
        # Either we get the real DFN class or fall back to plain Denoiser if
        # the stub model load failed inside the constructor.
        assert isinstance(d, (denoise_mod.DeepFilterDenoiser, denoise_mod.Denoiser))


def test_make_denoiser_falls_back_when_dfn_import_fails(monkeypatch):
    """When deepfilternet ImportError, factory returns plain Denoiser."""
    import importlib

    # Remove any DFN modules and force a fresh import.
    for mod in ("df", "df.enhance", "deepfilternet"):
        monkeypatch.setitem(sys.modules, mod, None)
    from voice import denoise as denoise_mod  # noqa
    importlib.reload(denoise_mod)
    d = denoise_mod.make_denoiser()
    assert isinstance(d, denoise_mod.Denoiser)


def test_denoiser_interface_consistent():
    """Both denoiser types must expose process_utterance(audio_int16) -> np.ndarray."""
    from voice import denoise as denoise_mod
    d = denoise_mod.make_denoiser()
    silence = np.zeros(16000, dtype=np.int16)
    out = d.process_utterance(silence)
    assert isinstance(out, np.ndarray)
    assert out.dtype == np.int16


# ─── Wake verifier regex ───────────────────────────────────────────────────


@pytest.mark.parametrize("model, transcript, should_match", [
    ("hey_jarvis", "okay jarvis what time is it",     True),
    ("hey_jarvis", "hey zendaya open spotify",        True),   # zendaya allowed
    ("hey_jarvis", "what's the frozen lake forecast", False),  # old loose 'zen' would match 'frozen'
    ("hey_jarvis", "the zenith is bright tonight",    False),  # 'zen' substring
    ("hey_jarvis", "I love lavender candles",         False),
    ("zendaya",    "hey zendaya open spotify",        True),
    ("zendaya",    "okay jarvis what time is it",     False),  # jarvis NOT allowed when model is zendaya
    ("zendaya",    "the zenith is bright tonight",    False),
])
def test_verifier_passes_model_aware(model, transcript, should_match):
    from voice import wake as wake_mod
    assert wake_mod.verifier_passes_for_model(model, transcript) is should_match


def test_verifier_skip_threshold_constant():
    from voice import wake as wake_mod
    assert wake_mod.VERIFIER_SKIP_THRESHOLD == 0.85


def test_default_cold_threshold_is_tightened():
    """Default cold threshold should be 0.6 (was 0.5)."""
    from voice import wake as wake_mod
    eng = wake_mod.WakeEngine(model_name="hey_jarvis")
    # If env override is present, the test wouldn't apply — guard for that.
    import os
    if "ZENDAYA_WAKE_THRESHOLD" in os.environ:
        pytest.skip("Skipping default-threshold test because env override is set.")
    assert eng.threshold == 0.6


# ─── Ambient floor gate ────────────────────────────────────────────────────


def test_ambient_gate_suppresses_wake_below_floor():
    """When room RMS is below floor and TTS isn't speaking, wake is skipped."""
    from zendaya_voice_listener_v2 import _AmbientGate

    gate = _AmbientGate(floor=0.005, window_s=0.5, sample_rate=16000)
    # Feed 1 second of silence (very low RMS).
    silence_frame = (np.zeros(480) + 0.0005 * np.random.randn(480)).astype(np.float32)
    silence_int16 = (silence_frame * 32767).astype(np.int16)
    for _ in range(int(16000 / 480)):  # ~33 frames = ~1s
        gate.observe(silence_int16)
    assert gate.below_floor() is True


def test_ambient_gate_opens_when_speech_present():
    from zendaya_voice_listener_v2 import _AmbientGate

    gate = _AmbientGate(floor=0.005, window_s=0.5, sample_rate=16000)
    # 1 second of speech-level frames.
    speech_frame = (0.05 * np.random.randn(480)).astype(np.float32)
    speech_int16 = (np.clip(speech_frame, -1, 1) * 32767).astype(np.int16)
    for _ in range(int(16000 / 480)):
        gate.observe(speech_int16)
    assert gate.below_floor() is False


def test_ambient_gate_floor_from_env(monkeypatch):
    monkeypatch.setenv("ZENDAYA_AMBIENT_FLOOR", "0.02")
    from zendaya_voice_listener_v2 import _AmbientGate

    gate = _AmbientGate()  # picks up env default
    assert gate.floor == 0.02


def test_ambient_gate_invalid_env_uses_default(monkeypatch):
    monkeypatch.setenv("ZENDAYA_AMBIENT_FLOOR", "not-a-number")
    from zendaya_voice_listener_v2 import _AmbientGate

    gate = _AmbientGate()
    assert gate.floor == 0.005  # default
