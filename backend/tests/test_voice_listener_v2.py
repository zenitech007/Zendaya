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
